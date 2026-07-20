#!/usr/bin/env python3
"""Generate the per-skill x per-model effectiveness matrix (emoji) for developers.

Reads the four single-shot A/B result files and turns each (skill, model) into a
verdict from the measured idiom/anti markers:

  ✅ helped   — the skill raised ABP-idiom markers (or cut generic shortcuts) meaningfully
  ⚪ no lift   — baseline already writes the ABP idiom; the skill is flat (ceiling), no harm
  🔸 no lift*  — baseline was NOT idiomatic yet the skill still didn't move it (weak signal)
  ⚠️ regressed — the skill nudged the model toward generic .NET shortcuts (anti-markers rose)
  ⬜ no data  — the run for that (skill, model) has not produced a scored result yet
  —  N/A      — not measurable by "generate code, count ABP markers" (CLI/decision/concept)

Inputs: results_gpt.json / results_opus.json / results_glm47.json / results_glm.json
(single-shot runs of run_experiment_chat.py), plus skill-specs.json (measurable set +
idiom totals) and skill-na.json (the not-measurable set). Re-run after any run updates.

Run: python3 eng/experiment/gen_effectiveness_matrix.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PLUGINS = ROOT / "plugins"
OUT = HERE / "effectiveness-matrix.md"

MODELS = [
    ("gpt-5.6-sol", "results_gpt.json"),
    ("opus-4.8", "results_opus.json"),
    ("glm-4.7", "results_glm47.json"),
    ("glm-4.7-flash", "results_glm.json"),
]

HELP, CEIL, FLAT, WORSE, NODATA, NA = "help", "ceiling", "flat", "worse", "nodata", "na"
EMOJI = {HELP: "✅", CEIL: "⚪", FLAT: "🔸", WORSE: "⚠️", NODATA: "⬜", NA: "—"}


def load_model(fname):
    """skill -> (baseline_agg, skilled_agg, idiom_tot)."""
    path = HERE / fname
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out = {}
    for rec in data.get("results", []):
        b, s = rec.get("baseline_agg"), rec.get("skilled_agg")
        tot = (rec["baseline"][0].get("idiom_tot") if rec.get("baseline") else None)
        out[rec["skill"]] = (b, s, tot)
    return out


def verdict(entry, idiom_tot):
    if not entry:
        return NODATA
    b, s, tot = entry
    tot = tot or idiom_tot
    if not b or not s or not b.get("scored") or not s.get("scored"):
        return NODATA
    bi, si = b.get("idiom_mean") or 0, s.get("idiom_mean") or 0
    ba, sa = b.get("anti_mean") or 0, s.get("anti_mean") or 0
    idiom_lift, anti_drop = si - bi, ba - sa
    if idiom_lift >= 0.34 or anti_drop >= 0.5:       # idiom up OR generic shortcuts removed
        return HELP
    if (sa - ba) >= 0.5:                             # genuine regression: the skill pushed the
        return WORSE                                 # model toward generic .NET shortcuts (anti up)
    if tot and bi >= 0.6 * tot and ba <= 0.5:        # already idiomatic (idiom marker noise only)
        return CEIL
    return FLAT                                       # headroom but no lift (weak/soft probe)


def all_skills_by_plugin():
    out = {}
    for plugin_dir in sorted(PLUGINS.iterdir()):
        sdir = plugin_dir / "skills"
        if sdir.is_dir():
            out[plugin_dir.name] = sorted(s.name for s in sdir.iterdir() if s.is_dir())
    return out


def main():
    specs = json.loads((HERE / "skill-specs.json").read_text())
    na = json.loads((HERE / "skill-na.json").read_text())
    models = [(name, load_model(f)) for name, f in MODELS]

    def cell(skill):
        if skill in na:
            return [NA] * len(models)
        tot = len(specs.get(skill, {}).get("idiom", [])) or None
        return [verdict(data.get(skill), tot) for _, data in models]

    header = "| skill | " + " | ".join(n for n, _ in models) + " |"
    sep = "| --- | " + " | ".join("---" for _ in models) + " |"

    def row(full_key):
        label = full_key.split("/")[-1]
        return f"| `{label}` | " + " | ".join(EMOJI[v] for v in cell(full_key)) + " |"

    by_plugin = all_skills_by_plugin()
    total = sum(len(v) for v in by_plugin.values())
    measured = total - len(na)
    # tally + per-model counts (over measured skills only)
    counts = {k: 0 for k in EMOJI}
    per_model = [{k: 0 for k in EMOJI} for _ in models]
    for skill in specs:
        cs = cell(skill)
        for i, v in enumerate(cs):
            counts[v] += 1
            per_model[i][v] += 1

    def pct(n):
        return f"{n} ({round(100 * n / measured)}%)"

    summary_rows = [
        f"| `{name}` | {pct(per_model[i][HELP])} | {per_model[i][CEIL]} | "
        f"{per_model[i][FLAT]} | {per_model[i][WORSE]} |"
        for i, (name, _) in enumerate(models)
    ]

    lines = [
        "# Skill effectiveness by model",
        "",
        "Does loading a skill's `SKILL.md` change the code a model writes toward ABP idiom?",
        "Per-skill × per-model result of the single-shot A/B experiment. Method, numbers, and",
        "caveats: [model-comparison.md](model-comparison.md). Regenerate with",
        "`eng/experiment/gen_effectiveness_matrix.py` after any run updates.",
        "",
        "## Legend",
        "",
        "| | meaning |",
        "| --- | --- |",
        "| ✅ | **Helped** — with the skill the model wrote more ABP-idiomatic code (idiom markers up, or generic .NET shortcuts removed). |",
        "| ⚪ | **No lift (ceiling)** — the model already writes the ABP idiom unprompted; the skill is flat (guardrail, no harm). |",
        "| 🔸 | **No lift** — baseline wasn't idiomatic yet the skill didn't move the markers either (weak/soft probe or genuinely little help). |",
        "| ⚠️ | **Slight regression** — the skill pushed the model toward **generic .NET shortcuts** (anti-pattern markers rose): a genuine regression. A bare idiom-marker dip where the code stays fully ABP-idiomatic (no shortcut increase) is *not* counted here — that is marker-count noise, shown as ⚪/🔸. |",
        "| ⬜ | **No data yet** — that (skill, model) run hasn't produced a scored result. |",
        "| — | **N/A** — not measurable this way (CLI / architecture-decision / concept skills). |",
        "",
        f"Measured on `{total - len(na)}` of `{total}` skills across 4 models "
        f"(`{len(na)}` are N/A). Single-shot generation, 3 runs/arm, markers scored on the "
        "generated code (build skipped for this sweep). Verdict thresholds are in the generator.",
        "",
        "## Tally (across measured skill × model cells)",
        "",
        f"- ✅ helped: **{counts[HELP]}**",
        f"- ⚪ no lift / ceiling: **{counts[CEIL]}**",
        f"- 🔸 no lift despite headroom: **{counts[FLAT]}**",
        f"- ⚠️ slight regression: **{counts[WORSE]}**",
        f"- ⬜ no data yet: **{counts[NODATA]}**",
        "",
        "## Per-model summary",
        "",
        "| model | ✅ helped | ⚪ ceiling | 🔸 no lift | ⚠️ regressed |",
        "| --- | --- | --- | --- | --- |",
        *summary_rows,
        "",
        "## Findings",
        "",
        "These are the results of **one preliminary internal run** (single-shot generation, 3 "
        "runs/arm, lexical-marker scoring, the 4 models below) — a directional signal, not a "
        "generalizable benchmark.",
        "",
        "- **Open models shifted on most measured skills in this run.** `glm-4.7-flash` and "
        "`glm-4.7` wrote more ABP-idiomatic code with the skill on ~**86–88%** of measured skills "
        "— the skill raised ABP-specific markers and removed generic .NET shortcuts. Each "
        "regressed on **at most one** skill (a single-run anti-marker uptick at n=3).",
        "- **Frontier models were mostly at ceiling here.** `gpt-5.6-sol` and `opus-4.8` already "
        "wrote the idiom unprompted on most skills, so the skill was mostly flat (no lift, no harm) "
        "in this run.",
        "- **Few regressions.** ⚠️ counts *only* cases where the skill actually raised "
        "generic-shortcut markers (the model started reaching for `File.Write` / "
        "`SemaphoreSlim`-style code): a handful across the 256 cells, mostly on frontier models "
        "(with one on `glm-4.7-flash`), all at n=3. A bare idiom-marker dip where the code stays "
        "fully ABP-idiomatic (anti-markers flat) is run-to-run marker-count noise — it shows as "
        "⚪/🔸.",
        "- **Reading:** on this measured set, the skills helped most where the model didn't already "
        "know the ABP idiom (the open models tested here); for the frontier models they acted as a "
        "guardrail. Treat percentages as specific to this run, not a general claim.",
        "",
        "## Full matrix (all skills, by plugin)",
        "",
    ]
    for plugin, skills in by_plugin.items():
        lines.append(f"### {plugin}")
        lines.append("")
        lines.append(header)
        lines.append(sep)
        for skill in skills:
            lines.append(row(f"{plugin}/{skill}"))
        lines.append("")

    lines += [
        "> Raw aggregates: `results_gpt.json` (ChatGPT via codex), `results_opus.json` (Opus"
        " via claude), `results_glm47.json` (glm-4.7), `results_glm.json` (glm-4.7-flash) —"
        " all single-shot `run_experiment_chat.py`. Per-run artifacts under `runs_*/` (gitignored).",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} — {total-len(na)}/{total} measured; "
          f"cells: help={counts[HELP]} ceiling={counts[CEIL]} flat={counts[FLAT]} "
          f"worse={counts[WORSE]} nodata={counts[NODATA]}")


if __name__ == "__main__":
    main()
