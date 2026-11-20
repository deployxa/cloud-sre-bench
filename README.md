# Cloud SRE Bench

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A small, public development suite for deployment-log diagnosis and SRE answer smoke tests. Maintained by Deployxa. It is **not a validated leaderboard or evidence that one model outperforms another on general SRE work**.

## Results and scope

The previous README published a vendor-reported comparison attributed to a private 384-incident evaluation. This repository contains neither those incidents nor the execution environment, metric implementations, raw outputs, or per-case results needed to reproduce it. That table has been removed. **There are currently no substantiated comparative results published here.** Previously quoted model parameter counts were also unsupported and have been removed.

The runner does not execute remediation, verify container recovery, or measure prompt leakage. Its public results must not be presented as those metrics.

| Suite | Fixtures | What its score means |
| --- | ---: | --- |
| `diagnose` | 26 | Category and proposed next-action agreement with public reference labels; includes 2 healthy logs and 1 thin log |
| `sre-chat` | 8 | Lexical checks of general SRE answers; requires human review for correctness |
| `platform-chat` | 5 | Optional reference-grounded platform QA; identical reference text is supplied to every model |

The default runs `diagnose` and `sre-chat`, reporting them separately. Platform QA is opt-in and is not an SRE competence score. There is no combined score across suites.

These are public fixtures, not a secret test set. Their original production provenance is unverified. No held-out split, training-data exclusion, external replication, or contamination audit is available. Vendor authorship and the historical taxonomy create a possible distribution advantage; actual train-on-test contamination cannot be established from this repository. See [methodology](docs/METHODOLOGY.md) and [data provenance and label revisions](data/README.md).

## Run locally

Python 3.10+; no third-party Python packages required. Install and start Ollama separately, then choose an explicit model:

```bash
ollama pull deployxa/deployxa-lm
python3 run_benchmark.py --target ollama --model deployxa/deployxa-lm \
  --runs 3 --temperature 0 --seed 42 \
  --output results/ollama.json --csv results/ollama.csv
```

Every invocation requires `--target`. There is no implicit vendor network destination. Ollama defaults to `http://localhost:11434`.

Inspect redacted inputs and shared instructions without making network calls:

```bash
python3 run_benchmark.py --target ollama --model deployxa/deployxa-lm \
  --dry-run --output results/input-review.json
```

## Other model endpoints

Generic adapters receive the same complete taxonomy, response schema, system instructions, and case inputs. The public taxonomy is in [data/taxonomy.json](data/taxonomy.json); it contains no case-specific answers. Format errors and transport errors are reported separately from valid but incorrect answers.

API keys are read from environment variables and are never included in report configuration or request headers in artifacts. Supply keys through your usual environment/secret manager.

```bash
# OPENAI_API_KEY must be set. Use an exact model snapshot where available.
python3 run_benchmark.py --target openai --model gpt-4o-2024-08-06 \
  --suite diagnose --output results/gpt4o.json

# ANTHROPIC_API_KEY must be set. Availability of historical models varies.
python3 run_benchmark.py --target anthropic --model YOUR_EXACT_MODEL_ID \
  --suite diagnose --output results/claude.json

# An OpenAI-compatible local server. URL is the root, without /v1.
python3 run_benchmark.py --target openai --url http://localhost:8080 \
  --api-key-env LOCAL_MODEL_API_KEY --model YOUR_MODEL_ID \
  --output results/local.json
```

`openai` sends JSON-object mode for diagnosis; Ollama sends the JSON schema in `format`; Anthropic receives the schema in the common system prompt. Provider-specific output constraints differ and are recorded in request bodies. The harness does not silently retry with a different prompt or response mode. Endpoint/model support and live API behavior have not been established by the offline tests.

The legacy Deployxa `/diagnose` service is explicitly a **vendor system evaluation**, not a model-only comparison. It may include server-side prompts, routing, or recipes that this repo cannot inspect. It requires an explicit destination:

```bash
python3 run_benchmark.py --target deployxa-api --url https://chat.deployxa.com \
  --suite diagnose --output results/deployxa-system.json
```

`--target api` and `--target local` remain aliases for that vendor system adapter, also requiring `--url`. Use the generic OpenAI adapter for an OpenAI-compatible server. Revised action labels may be unsupported by legacy vendor services; no hidden mapping is applied.

Optional platform reference QA:

```bash
python3 run_benchmark.py --target ollama --model YOUR_MODEL_ID \
  --suite platform-chat --output results/reference-qa.json
```

## Artifacts, request controls, and CI

JSON reports contain redacted input messages, actual request bodies without authentication headers, provider responses, normalized predictions, reference labels, per-case scores, errors, timings, model/settings, source/data hashes, and per-run summaries. Successful HTTP responses are preserved, including malformed model answers; HTTP error bodies are omitted to avoid archiving server secrets. The vendor diagnosis API does not accept shared messages; its actual payload is recorded instead. JSON is checkpointed after each completed case. CSV provides a score export; JSON is the authoritative artifact. Existing output files are not overwritten.

Use `--runs`, `--temperature`, and supported `--seed` controls for repeated requests. Runs are reported separately with descriptive mean and standard deviation; repeated cases are not pooled as extra independent incidents. Per-run proportions include descriptive 95% Wilson intervals with their denominators. This is not a significance test or a remedy for biased fixtures.

Use `--timeout` (seconds per attempt), `--retries`, `--retry-backoff`, `--min-interval`, and `--max-tokens` to control requests. A fixture can override the timeout with a positive `timeout_seconds`. Only transient network errors and HTTP 408/429/500/502/503/504 are retried; format or scoring failures are not. A seed does not guarantee reproducibility across provider/model versions.

Exit status is `0` for all cases passing or a successful dry run, `1` for failed/unscorable cases, `2` for CLI configuration errors, and `130` for interruption.

```bash
python3 -m unittest discover -s tests -v
```

## Log handling

Inputs are redacted before transmission by a best-effort masker for URL credentials, common token/password forms, emails, some internal hostnames, and private IPv4 addresses. Loopback and wildcard addresses remain visible because they are diagnostic evidence. Remote HTTP endpoints are rejected; redirects are not followed.

**This is not comprehensive anonymization.** IPv6, arbitrary identifiers, proprietary names, novel secret formats, and other sensitive content may remain. Review a dry-run report and sanitize fixtures before sending them to any remote endpoint. Reports include model outputs and may contain sensitive content echoed or generated by the provider. Keep artifacts private unless reviewed. The harness evaluates fixture files; it does not collect production logs automatically.

## Contributions and license

Add sanitized fixtures with explicit evidence and defensible reference labels. Describe provenance and any synthetic edits; do not assert AI authorship or successful remediation without evidence. Contributor-owned fixtures must not enter a future held-out split after being used in training. See the [publication requirements](docs/METHODOLOGY.md#requirements-for-a-future-leaderboard).

Licensed under the full [Apache License 2.0](LICENSE). Copyright attribution is preserved in [NOTICE](NOTICE). Replacing the previous abbreviated license notice does not establish third-party provenance or rights to any incident data.
