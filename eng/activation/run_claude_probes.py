#!/usr/bin/env python3
"""Drive the activation probes against a locally installed Claude Code + plugins.

This automates the *Claude Code* column of the activation matrix (README.md). It
runs each probe from probes.yaml through `claude -p ... --output-format stream-json`
and reads which skill the router actually selected — the first `Skill` tool_use in
the event stream, whose input is `{"skill": "<plugin>:<skill>"}`.

It does NOT drive Codex / Cursor / VS Code (different tools, different observation).
Codex has its own observation path; Cursor / VS Code stay manual (GUI).

Prereqs: the plugins installed into Claude Code (see README "Install"), and the
`claude` CLI on PATH. `--max-turns 2` bounds each probe to the routing decision plus
one follow-up, so the model never has to complete the task — we only read the route.

Usage:
  python3 eng/activation/run_claude_probes.py                     # all probes
  python3 eng/activation/run_claude_probes.py --only 8 --jobs 2   # first 8, 2 at a time
  python3 eng/activation/run_claude_probes.py --out /tmp/claude-probes.json

Output: a JSON report (default eng/activation/claude-probes.json) plus a printed
summary. Feed the summary into results.md per the README template.
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent.parent
PROBES = ROOT / "eng" / "activation" / "probes.yaml"


def activated_skill(stream_text):
    """Return (plugin, skill) of the first Skill tool_use in a stream-json dump, or None."""
    for line in stream_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                ref = str((block.get("input") or {}).get("skill", ""))
                if not ref:
                    continue
                plugin, _, skill = ref.partition(":")
                return (plugin, skill or plugin)
    return None


def run_probe(probe, timeout):
    """Run one probe through headless Claude Code; return the probe annotated with the result."""
    prompt = probe["prompt"]
    result = dict(probe)
    try:
        completed = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "stream-json",
             "--verbose", "--max-turns", "2"],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        result["activated"] = None
        result["error"] = "timeout"
        result["pass"] = False
        return result

    hit = activated_skill(completed.stdout)
    activated = hit[1] if hit else None
    result["activated"] = activated
    result["activated_plugin"] = hit[0] if hit else None
    expected = probe["expected_skill"]
    if probe["expect"] == "activate":
        result["pass"] = activated == expected
    else:  # not-activate: expected_skill must NOT be the one selected
        result["pass"] = activated != expected
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, help="run only the first N probes")
    parser.add_argument("--jobs", type=int, default=3, help="concurrent probes (mind API rate limits)")
    parser.add_argument("--timeout", type=int, default=180, help="per-probe seconds")
    parser.add_argument("--out", default=str(ROOT / "eng" / "activation" / "claude-probes.json"))
    parser.add_argument("--probes", default=str(PROBES), help="probe YAML (default the generated set)")
    args = parser.parse_args()

    probes = (yaml.safe_load(Path(args.probes).read_text(encoding="utf-8")) or {}).get("probes", [])
    if args.only:
        probes = probes[: args.only]

    results = [None] * len(probes)
    done = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_probe, p, args.timeout): i for i, p in enumerate(probes)}
        for fut in as_completed(futures):
            i = futures[fut]
            results[i] = fut.result()
            done += 1
            r = results[i]
            mark = "PASS" if r["pass"] else "FAIL"
            act = r["activated"] or "(none)"
            print(f"[{done}/{len(probes)}] {mark} {r['expect']:12} expected={r['expected_skill']:32} activated={act}",
                  file=sys.stderr, flush=True)

    pos = [r for r in results if r["expect"] == "activate"]
    neg = [r for r in results if r["expect"] == "not-activate"]
    summary = {
        "total": len(results),
        "positive_pass": sum(r["pass"] for r in pos),
        "positive_total": len(pos),
        "negative_pass": sum(r["pass"] for r in neg),
        "negative_total": len(neg),
        "misfires": [
            {"prompt": r["prompt"][:90], "expected": r["expected_skill"],
             "activated": r["activated"], "expect": r["expect"]}
            for r in results if not r["pass"]
        ],
    }
    Path(args.out).write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\n=== summary ===")
    print(f"positive (should activate):     {summary['positive_pass']}/{summary['positive_total']}")
    print(f"negative (should NOT activate): {summary['negative_pass']}/{summary['negative_total']}")
    print(f"misfires: {len(summary['misfires'])}")
    for m in summary["misfires"]:
        print(f"  [{m['expect']}] expected {m['expected']} -> activated {m['activated']}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
