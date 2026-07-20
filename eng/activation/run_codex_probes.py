#!/usr/bin/env python3
"""Drive the activation probes against a locally installed Codex CLI + plugins.

Automates the *Codex* column of the activation matrix (README.md). Codex `exec`
has no turn cap and runs the whole task, so we stream its `--json` events and stop
as soon as the router commits to a skill — the first `command_execution` that reads
`.../skills/<skill>/SKILL.md` (Codex loads a skill by cat-ing its SKILL.md), with the
agent's `abp-<plugin>:<skill>` mention as a fallback. A watchdog kills the process at
`--timeout` so a probe that never routes can't hang the run.

It also records Codex's "skills context budget" truncation notice, which fires when
enough plugins are installed that Codex shortens skill descriptions to fit its budget
(observed with all 15 plugins / 79 skills) — a real full-menu characteristic.

Prereqs: plugins installed into Codex (`codex plugin add ...`, see README) and the
`codex` CLI on PATH.

Usage:
  python3 eng/activation/run_codex_probes.py                     # all probes
  python3 eng/activation/run_codex_probes.py --only 8 --jobs 2
  python3 eng/activation/run_codex_probes.py --out /tmp/codex-probes.json

Output: JSON report (default eng/activation/codex-probes.json) + printed summary.
"""
import argparse
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent.parent
PROBES = ROOT / "eng" / "activation" / "probes.yaml"

SKILL_READ = re.compile(r"/skills/([a-z0-9-]+)/SKILL\.md")
MENTION = re.compile(r"abp-[a-z]+:([a-z0-9-]+)")


def run_probe(probe, timeout):
    """Run one probe through Codex; stop at the first skill it loads. Returns the annotated probe."""
    result = dict(probe)
    proc = subprocess.Popen(
        ["codex", "exec", "--json", "--skip-git-repo-check", "-s", "read-only",
         "-c", "model_reasoning_effort=low", probe["prompt"]],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, stdin=subprocess.DEVNULL,
    )
    watchdog = threading.Timer(timeout, proc.kill)
    watchdog.start()
    activated = None
    truncated = False
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if "skills context budget" in json.dumps(event):
                truncated = True
            item = event.get("item", {})
            if item.get("type") == "command_execution":
                match = SKILL_READ.search(item.get("command", ""))
                if match:
                    activated = match.group(1)
                    break
            if item.get("type") == "agent_message":
                match = MENTION.search(item.get("text", ""))
                if match:
                    activated = match.group(1)
                    break
    finally:
        watchdog.cancel()
        proc.kill()

    result["activated"] = activated
    result["truncated_menu"] = truncated
    expected = probe["expected_skill"]
    if probe["expect"] == "activate":
        result["pass"] = activated == expected
    else:
        result["pass"] = activated != expected
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, help="run only the first N probes")
    parser.add_argument("--jobs", type=int, default=2, help="concurrent probes")
    parser.add_argument("--timeout", type=int, default=90, help="per-probe seconds before kill")
    parser.add_argument("--out", default=str(ROOT / "eng" / "activation" / "codex-probes.json"))
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
        "menu_truncated": any(r.get("truncated_menu") for r in results),
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
    print(f"menu truncated (context budget): {summary['menu_truncated']}")
    print(f"misfires: {len(summary['misfires'])}")
    for m in summary["misfires"]:
        print(f"  [{m['expect']}] expected {m['expected']} -> activated {m['activated']}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
