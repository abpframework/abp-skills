# Skill effectiveness by model

Does loading a skill's `SKILL.md` change the code a model writes toward ABP idiom?
Per-skill × per-model result of the single-shot A/B experiment. Method, numbers, and
caveats: [model-comparison.md](model-comparison.md). Regenerate with
`eng/experiment/gen_effectiveness_matrix.py` after any run updates.

## Legend

| | meaning |
| --- | --- |
| ✅ | **Helped** — with the skill the model wrote more ABP-idiomatic code (idiom markers up, or generic .NET shortcuts removed). |
| ⚪ | **No lift (ceiling)** — the model already writes the ABP idiom unprompted; the skill is flat (guardrail, no harm). |
| 🔸 | **No lift** — baseline wasn't idiomatic yet the skill didn't move the markers either (weak/soft probe or genuinely little help). |
| ⚠️ | **Slight regression** — the skill pushed the model toward **generic .NET shortcuts** (anti-pattern markers rose): a genuine regression. A bare idiom-marker dip where the code stays fully ABP-idiomatic (no shortcut increase) is *not* counted here — that is marker-count noise, shown as ⚪/🔸. |
| ⬜ | **No data yet** — that (skill, model) run hasn't produced a scored result. |
| — | **N/A** — not measurable this way (CLI / architecture-decision / concept skills). |

Measured on `64` of `80` skills across 4 models (`16` are N/A). Single-shot generation, 3 runs/arm, markers scored on the generated code (build skipped for this sweep). Verdict thresholds are in the generator.

## Tally (across measured skill × model cells)

- ✅ helped: **128**
- ⚪ no lift / ceiling: **90**
- 🔸 no lift despite headroom: **34**
- ⚠️ slight regression: **4**
- ⬜ no data yet: **0**

## Per-model summary

| model | ✅ helped | ⚪ ceiling | 🔸 no lift | ⚠️ regressed |
| --- | --- | --- | --- | --- |
| `gpt-5.6-sol` | 4 (6%) | 42 | 17 | 1 |
| `opus-4.8` | 13 (20%) | 40 | 9 | 2 |
| `glm-4.7` | 55 (86%) | 3 | 6 | 0 |
| `glm-4.7-flash` | 56 (88%) | 5 | 2 | 1 |

## Findings

These are the results of **one preliminary internal run** (single-shot generation, 3 runs/arm, lexical-marker scoring, the 4 models below) — a directional signal, not a generalizable benchmark.

- **Open models shifted on most measured skills in this run.** `glm-4.7-flash` and `glm-4.7` wrote more ABP-idiomatic code with the skill on ~**86–88%** of measured skills — the skill raised ABP-specific markers and removed generic .NET shortcuts. Each regressed on **at most one** skill (a single-run anti-marker uptick at n=3).
- **Frontier models were mostly at ceiling here.** `gpt-5.6-sol` and `opus-4.8` already wrote the idiom unprompted on most skills, so the skill was mostly flat (no lift, no harm) in this run.
- **Few regressions.** ⚠️ counts *only* cases where the skill actually raised generic-shortcut markers (the model started reaching for `File.Write` / `SemaphoreSlim`-style code): a handful across the 256 cells, mostly on frontier models (with one on `glm-4.7-flash`), all at n=3. A bare idiom-marker dip where the code stays fully ABP-idiomatic (anti-markers flat) is run-to-run marker-count noise — it shows as ⚪/🔸.
- **Reading:** on this measured set, the skills helped most where the model didn't already know the ABP idiom (the open models tested here); for the frontier models they acted as a guardrail. Treat percentages as specific to this run, not a general claim.

## Full matrix (all skills, by plugin)

### abp-api

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `configure-cors` | — | — | — | — |
| `configure-swagger-openapi` | 🔸 | ⚪ | ✅ | ✅ |
| `consume-remote-services` | 🔸 | ⚠️ | ✅ | ✅ |
| `expose-http-apis` | 🔸 | 🔸 | 🔸 | ✅ |
| `use-abp-standard-endpoints` | ⚪ | ⚪ | ✅ | ✅ |
| `version-http-apis` | 🔸 | 🔸 | ✅ | ✅ |

### abp-authentication

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `configure-dynamic-claims` | ⚪ | ⚪ | ✅ | ✅ |
| `configure-openiddict-authentication` | — | — | — | — |
| `configure-openiddict-validation` | — | — | — | — |

### abp-authorization

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `authorize-resources` | 🔸 | ✅ | ✅ | ✅ |
| `permissions-and-authorization` | 🔸 | 🔸 | ✅ | ✅ |

### abp-cli

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `abp-cli-commands` | — | — | — | — |
| `choose-solution-architecture` | — | — | — | — |

### abp-data-access

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `apply-data-filters` | ⚪ | ⚪ | ✅ | ✅ |
| `configure-connection-strings` | — | — | — | — |
| `ef-core-integration` | ⚪ | ⚪ | ✅ | ✅ |
| `handle-optimistic-concurrency` | ⚪ | ⚪ | ✅ | ✅ |
| `manage-units-of-work` | ⚪ | ⚪ | ✅ | ✅ |
| `mongodb-integration` | ⚪ | ⚪ | ✅ | ✅ |
| `query-with-dapper` | ⚪ | ⚪ | ✅ | ✅ |
| `seed-application-data` | ⚪ | ⚪ | ⚪ | ⚪ |
| `use-abp-repositories` | ⚪ | ⚪ | ✅ | ✅ |

### abp-files

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `manage-virtual-files` | ⚪ | ✅ | ✅ | ✅ |
| `store-blobs` | ⚪ | ⚪ | ✅ | ✅ |

### abp-infrastructure

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `check-simple-state` | — | — | — | — |
| `configure-audit-logging` | 🔸 | ✅ | ✅ | ✅ |
| `configure-logging` | — | — | — | — |
| `encrypt-strings` | 🔸 | ⚪ | ✅ | ✅ |
| `generate-guids` | 🔸 | 🔸 | ✅ | ✅ |
| `handle-dates-and-time` | 🔸 | ✅ | ✅ | ✅ |
| `integrate-ai` | — | — | — | — |
| `integrate-autofac` | — | — | — | — |
| `manage-settings-and-features` | ⚪ | ⚪ | ⚪ | ✅ |
| `manipulate-images` | ⚪ | ⚪ | ✅ | ✅ |
| `propagate-correlation-id` | ⚪ | ⚪ | ✅ | ✅ |
| `read-configuration` | — | — | — | — |
| `serialize-json` | ⚪ | ⚪ | ⚪ | ⚪ |
| `toggle-global-features` | — | — | — | — |
| `use-cancellation-tokens` | ⚪ | ⚪ | 🔸 | ⚠️ |
| `use-interceptors-and-dynamic-proxy` | ⚪ | ⚪ | ✅ | ✅ |

### abp-microservices

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `design-module-and-service-communication` | ⚪ | ⚪ | ✅ | ✅ |
| `integrate-dapr-services` | 🔸 | ⚠️ | 🔸 | ✅ |

### abp-module-development

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `application-services` | ⚪ | ✅ | ✅ | ⚪ |
| `build-crud-application-services` | ⚪ | ⚪ | ✅ | ✅ |
| `create-plugin-modules` | ⚪ | ⚪ | ✅ | ✅ |
| `customize-application-modules` | ⚪ | ⚪ | ✅ | ✅ |
| `define-application-modules` | ⚪ | ✅ | ✅ | ⚪ |
| `extend-objects-with-extra-properties` | ⚠️ | 🔸 | ✅ | ✅ |
| `handle-validation-and-errors` | ✅ | 🔸 | ✅ | ✅ |
| `layered-architecture` | — | — | — | — |
| `localize-applications` | ⚪ | ⚪ | ✅ | ✅ |
| `map-objects-and-dtos` | ⚪ | ⚪ | ✅ | ✅ |
| `model-domain-aggregates` | ⚪ | ⚪ | ✅ | ✅ |
| `register-and-replace-services` | ⚪ | ⚪ | ✅ | ✅ |
| `separate-domain-and-application-logic` | — | — | — | — |

### abp-multitenancy

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `configure-multi-tenancy` | ⚪ | ⚪ | ✅ | ⚪ |

### abp-realtime

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `add-signalr-realtime` | ⚪ | ⚪ | ✅ | ✅ |

### abp-runtime

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `background-jobs-and-events` | ⚪ | ⚪ | ✅ | ✅ |
| `cache-entities` | ⚪ | ⚪ | ✅ | ✅ |
| `configure-app-urls` | ⚪ | ⚪ | ✅ | ✅ |
| `configure-production-hosting` | — | — | — | — |
| `distributed-caching-and-locking` | ⚪ | ⚪ | ✅ | ✅ |
| `render-text-templates` | ⚪ | ⚪ | ✅ | ✅ |
| `secure-web-requests` | ✅ | ✅ | ✅ | ✅ |
| `send-emails` | ⚪ | ⚪ | ✅ | ✅ |
| `send-sms` | 🔸 | ⚪ | ✅ | ✅ |
| `use-hybrid-caching` | 🔸 | ✅ | ✅ | ✅ |

### abp-testing

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `test-abp-applications` | 🔸 | ⚪ | ✅ | 🔸 |
| `test-angular-ui` | ⚪ | ✅ | ✅ | ✅ |
| `test-mvc-razor-ui` | ⚪ | ✅ | ✅ | ✅ |

### abp-ui

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `angular-ui` | 🔸 | ✅ | ✅ | ✅ |
| `blazor-ui` | ✅ | 🔸 | ✅ | ✅ |
| `build-angular-lists-and-forms` | ⚪ | ⚪ | ✅ | ✅ |
| `build-mvc-widgets` | ✅ | ✅ | 🔸 | ✅ |
| `extend-angular-module-ui` | ⚪ | ⚪ | ✅ | ✅ |
| `extend-application-shell` | ⚪ | ⚪ | ✅ | ✅ |
| `menus-and-localization` | ⚪ | ✅ | ✅ | ✅ |
| `mvc-razor-ui` | 🔸 | 🔸 | 🔸 | 🔸 |
| `use-mvc-javascript-apis` | 🔸 | 🔸 | 🔸 | ✅ |

### abp-upgrade

| skill | gpt-5.6-sol | opus-4.8 | glm-4.7 | glm-4.7-flash |
| --- | --- | --- | --- | --- |
| `version-upgrade` | — | — | — | — |

> Raw aggregates: `results_gpt.json` (ChatGPT via codex), `results_opus.json` (Opus via claude), `results_glm47.json` (glm-4.7), `results_glm.json` (glm-4.7-flash) — all single-shot `run_experiment_chat.py`. Per-run artifacts under `runs_*/` (gitignored).
