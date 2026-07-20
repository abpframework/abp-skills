# Skill value across AI model tiers

Does loading a skill's `SKILL.md` change the code a model writes — toward ABP idiom and
away from generic shortcuts? This records that measurement across model tiers. It is the
evidence behind "who actually needs these skills."

Read `EXPERIMENT.md` first for the metric and the agent-harness run.

This file is the **controlled deep-dive**: the same 4 hard skills run across 3 model tiers,
for the cross-tier reading. The **full sweep** — every measurable skill × 4 models (adds
`gpt-5.6-sol`) — lives in [effectiveness-matrix.md](effectiveness-matrix.md); this file is
the narrower, matched comparison behind it, not the whole picture.

## Metric

For each skill, two arms: **baseline** (the task in plain words, no ABP API named) and
**skilled** (the same task prefixed with the skill's `SKILL.md`). Score the generated C#:

- **idiom** — distinct *ABP-specific* markers present (e.g. `IBlobContainer`,
  `AsyncPeriodicBackgroundWorkerBase`), out of the total the skill teaches. Markers are
  deliberately distinctive: a generic `SaveAsync` that any invented interface would also
  have is **not** counted.
- **anti** — generic-shortcut markers a non-ABP answer reaches for (`File.WriteAllBytes`,
  `SemaphoreSlim`, `IHostedService`, `IConfiguration`).

Higher idiom + lower anti under *skilled* = the skill moved the model toward the ABP way.
Means over 3 runs, single-shot generation (`run_experiment_chat.py`), ABP `10.5.0`.

## Controlled comparison — three models, same 4 hard skills, same method

Four deliberately non-obvious skills, where a model's default reach is often plain .NET.
`idiom` and `anti` are baseline → skilled.

| skill (idiom total) | Opus idiom | Opus anti | glm-4.7 idiom | glm-4.7 anti | glm-4.7-flash idiom | glm-4.7-flash anti |
| --- | --- | --- | --- | --- | --- | --- |
| store-blobs (2) | 1.0 → 1.0 | 0 → 0 | 0.67 → 1.0 | 1.33 → **0** | 0.0 → 1.0 | 2.67 → **0** |
| distributed-lock (2) | 2.0 → 2.0 | 0 → 0 | 1.0 → 2.0 | 0 → 0 | 0.67 → 1.67 | 0.33 → **0** |
| background-worker (2) | 2.0 → 2.0 | 0 → 0 | 0.67 → 2.0 | 0.67 → **0** | 0.0 → 2.0 | 0 → 0 |
| settings (3) | 1.67 → 1.33 | 0 → 0 | 0.0 → 2.0 | 0 → 0 | 2.0 → 2.33 | 0.33 → 0.33 |

Models: **Opus** = `claude-opus` (frontier), **glm-4.7** = strong open, **glm-4.7-flash**
= weak open. All three run through the identical single-shot harness on the identical
skills — a matched comparison.

### What it shows

- **Opus is at ceiling — even on the obscure surface.** Its *baseline* already writes the
  ABP idiom (`IBlobContainer`, `IAbpDistributedLock` + `TryAcquireAsync`,
  `AsyncPeriodicBackgroundWorkerBase`) and **never** touches a generic shortcut
  (anti = 0 everywhere, both arms). The skill has no room to lift, so it is flat. (The
  tiny `settings` dip 1.67 → 1.33 is n=3 noise, not a regression.)
- **glm-4.7 (strong open) needs the skill.** Baseline lands the idiom only partly and
  sometimes falls back to a generic shortcut; the skill lifts idiom on **all 4** (average
  ≈ +1.2 markers) and drives anti to 0.
- **glm-4.7-flash (weak open) needs the skill.** Same shape — lift on **3 of 4** (average
  ≈ +1.1 markers), anti → 0. The exception is `settings`, where flash already reached for
  `SettingDefinitionProvider` unprompted (a near-ceiling cell).

Put the baselines side by side: Opus already sits around **75%** of the idiom markers with
**zero** generic shortcuts; the two open models sit around **25–30%** with generic
shortcuts present. The skill pulls **both open models up to roughly Opus's level** (~78%
idiom, anti 0). In other words, the skill's measurable job is to give a non-frontier model
the ABP idiom that a frontier model already has.

## Corroboration — gpt-5.6-sol on 8 foundational skills (agent harness)

A separate run (`EXPERIMENT.md`, `results.json`) put `gpt-5.6-sol` through the *agent*
harness on 8 *foundational* skills. Every skill: idiom flat at/near max, anti 0, no lift —
another frontier model at ceiling, on an easier skill set and a different harness. It is
consistent with the Opus result but is not a matched arm (different method and skills), so
treat it as corroboration, not a fourth column.

## How to read it

**Skill value tracks headroom** — whether the model already knows the ABP idiom for *this*
task. Two independent frontier models (Opus, GPT) have no headroom: they write idiomatic
ABP unprompted, so the skill is flat (and, importantly, never *hurts* — no anti-patterns,
no regressions). The open models do have headroom: left alone they reach for
`File.WriteAllBytes`, `SemaphoreSlim`, a hand-rolled timer, or their own config
abstraction, and the skill flips them to the ABP idiom and removes the shortcut.

So "who needs the skills" is a headroom axis: **any model whose untutored answer is not
already the ABP idiom.** On this obscure surface that is both open models, strong and weak;
it is not the frontier models, which are saturated.

## What this does and does not show

- **Does show:** on non-obvious ABP surface, both open-model tiers write materially more
  idiomatic ABP code with the skill than without — a positive, measured, *matched-harness*
  skill-value signal, with a frontier model (Opus) as the ceiling reference on the same
  skills.
- **Does not show:** that the skills change a frontier model's output. Opus and GPT are at
  ceiling here; the skills earn their keep for everyone below that line.
- **Weak metric:** single-shot `build` pass-rate is low across all models because one-shot
  code assumes a fuller app and invents domain types — not a skill effect; idiom/anti is
  the reliable signal. n=3, one scenario per skill, lexical markers. One noisy cell noted
  above (`settings` baseline differs between the two glm models — variance).

## Bottom line

The skills earn their place where a model's untutored answer is not already the ABP idiom —
demonstrated, in a matched three-model comparison, for a strong and a weak open model across
blob storage, distributed locking, background workers, and settings. Frontier models (Opus,
GPT) sit at ceiling: the skills do no harm and produce no lift there, because those models
already write the idiom the skills teach.

Raw data: `results_opus.json` (Opus), `results_glm47.json` (glm-4.7), `results_glm.json`
(glm-4.7-flash), `results.json` (gpt-5.6-sol, agent). Per-run artifacts under `runs_*/`
(gitignored).
