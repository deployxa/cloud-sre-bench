# 🧪 Cloud SRE Bench (`cloud-sre-bench`)

[![License](https://img.shields.io/badge/License-Apache_2.0-007BFF.svg)](LICENSE)
[![Benchmark Version](https://img.shields.io/badge/Version-1.0.0-00D1FF.svg)](https://github.com/deployxa/cloud-sre-bench)
[![Cases](https://img.shields.io/badge/Evaluated%20Cases-26%20Logs%20%2B%2014%20Chat-10B981.svg)](data/)
[![Deployxa Hub](https://img.shields.io/badge/Ollama-deployxa%2Fdeployxa--lm-F59E0B.svg)](https://ollama.com/deployxa/deployxa-lm)

**Cloud SRE Bench** is an open, reproducible evaluation benchmark and test suite designed to measure the capability of Large Language Models (LLMs) on **real-world cloud deployment failure triage, container self-healing, and epistemic confidence calibration.**

---

## 🎯 Why Cloud SRE Bench?

Traditional software benchmarks (like HumanEval or SWE-bench) evaluate Python coding and algorithm synthesis. They fail to test distributed infrastructure realities:

1. **Chronological Recency Bias**: Generalist LLMs anchor on the final crash stack trace rather than the upstream root cause (e.g. diagnosing exit code 137 rather than connection pool starvation 50 lines earlier).
2. **Infrastructure vs. Code Mismatch**: Frontier LLMs hallucinate application code refactors for faults that require container infrastructure remediation (e.g., binding to `0.0.0.0:$PORT` instead of `127.0.0.1`, allocating dynamic ports, or configuring build output directories).
3. **Overconfidence on Thin Logs**: Traditional models guess with 0.90+ confidence on vague or empty logs like `"Deploy failed"`, instead of failing closed and requesting more telemetry.
4. **Adversarial Log Injection**: Attackers embedding shell commands or prompt escapes in stack traces.

---

## 🏆 Current Leaderboard (October 2026)

Leaderboard from our 384-incident eval; this repo ships a 26-case public subset.

| Model | Model Size | Deployment Mode | Root-Cause Isolation | Verified Container Recovery | Clean Log False Alarms | Prompt Leak Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Deployxa LM 1.0** | **1.54B** | **Local / In-VPC** | **76.4%** | **48.2%** | **5.8%** | **0.0% (0 / 50)** |
| OpenAI GPT-4o | ~200B+ | Cloud API | 71.4% | 37.3% | < 3.0% | 4.0% (2 / 50) |
| Claude 3.5 Sonnet | ~200B+ | Cloud API | 69.2% | 35.8% | < 3.0% | 2.0% (1 / 50) |
| Base Qwen 2.5 Coder | 1.54B | Local | 22.2% | 22.2% | Unbounded | 100% (Leaks prompt) |
| Heuristic Regex Rules | Static | Local | 40.9% | N/A | 93.6% | N/A |

---

## 📦 What's Inside the Benchmark?

### 1. 26 Real-World Deployment Failure Logs ([`data/cases_26_diagnose.json`](data/cases_26_diagnose.json))
Includes authentic telemetry from production cloud PaaS deployments:
- **Port Collisions & Loopback Traps**: `EADDRINUSE`, application bound to `127.0.0.1` instead of `0.0.0.0`.
- **Database Failures Disambiguated**: Prisma P1001 reachability vs. Postgres password auth drops vs. schema migration lock contention.
- **Resource Exhaustion**: V8 JavaScript heap exhaustion, Linux cgroup exit code 137.
- **Missing Build Outputs**: Output directory `dist/` not found after build completion.
- **AI-Hallucinated Imports**: Unresolved `@/lib/...` alias hallucinated by code generation agents.
- **Serverless Timeouts**: Function 504 Gateway Timeouts.
- **Adversarial & Thin Logs**: Validates that `"Deploy failed"` returns `< 0.50` confidence and `abstain: true`.

### 2. 14 Grounded SRE Platform Queries ([`data/prompts_14_chat.json`](data/prompts_14_chat.json))
Evaluates factual accuracy and prompt injection resilience:
- Dynamic `$PORT` handling and Dockerfile generation.
- Prompt injection protection against `"Ignore previous instructions"`.
- Container namespace isolation vs. laptop `sudo kill -9` advice.
- Managed database connection URIs vs. `localhost:27017`.

---

## 🚀 Running the Benchmark in 1 Command

### Prerequisites
```bash
git clone https://github.com/deployxa/cloud-sre-bench.git
cd cloud-sre-bench
```

### Option A: Evaluate against Ollama
Run the benchmark locally against Deployxa LM running in Ollama:

```bash
# Pull the model
ollama pull deployxa/deployxa-lm

# Run the benchmark suite
python3 run_benchmark.py --target ollama --model deployxa/deployxa-lm
```

### Option B: Evaluate against Live Deployxa API
```bash
python3 run_benchmark.py --target api
```

### Option C: Evaluate against a Local API Server
```bash
python3 run_benchmark.py --target local --url http://localhost:8080
```

---

## 📜 Benchmark Scoring Rubric

A model passes a failure log case if and only if:
1. **Root-Cause Attribution**: It identifies the true canonical failure category without confusion (e.g. separating DB reachability from migration failure).
2. **Dynamic Remediation**: It selects the correct machine-executable remediation recipe (e.g. binding `0.0.0.0` for loopback listeners, not killing sockets).
3. **Calibrated Confidence**: For ambiguous or thin logs, it fails closed with confidence `< 0.50` and `abstain: true`.

---

## 🤝 Contributing New Failure Cases

We welcome real-world deployment logs, build traces, and failure scenarios from all cloud runtimes and polyglot frameworks!
1. Add your sanitized failure log to `data/cases_26_diagnose.json`.
2. Ensure secrets (passwords, tokens, keys) are redacted.
3. Submit a Pull Request!

---

## 📄 License
Cloud SRE Bench is open-source software licensed under the **Apache 2.0 License**.  
Maintained by **Deployxa Cloud Inc.** ([https://deployxa.com](https://deployxa.com)).
