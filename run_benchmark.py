#!/usr/bin/env python3
"""
Cloud SRE Bench: Official Evaluation Runner
Benchmark runner for evaluating LLMs on 26 real-world deployment failure logs
and 14 grounded platform chat queries.

Usage:
  python3 run_benchmark.py --target api
  python3 run_benchmark.py --target ollama --model deployxa/deployxa-lm
  python3 run_benchmark.py --target local --url http://localhost:8080
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# ANSI colors
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
AMBER = "\033[33m"
SLATE = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

DATA_DIR = Path(__file__).parent / "data"

def make_http_request(url, payload=None, timeout=30):
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json", "User-Agent": "Cloud-SRE-Bench/1.0"}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))

def query_target(target, base_url, model, logs=None, prompt=None, case_id="test"):
    if target in ("api", "local"):
        if logs is not None:
            url = f"{base_url}/diagnose"
            payload = {"logs": logs, "episode_id": f"bench-{case_id}-{time.time()}"}
            return make_http_request(url, payload)
        else:
            url = f"{base_url}/v1/chat/completions"
            payload = {
                "model": model or "deployxa-lm-1.0",
                "messages": [{"role": "user", "content": prompt}]
            }
            res = make_http_request(url, payload)
            return res["choices"][0]["message"]["content"]
    elif target == "ollama":
        url = f"{base_url}/api/chat"
        content = logs if logs is not None else prompt
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
            "format": "json" if logs is not None else ""
        }
        res = make_http_request(url, payload)
        raw_text = res["message"]["content"]
        if logs is not None:
            try:
                return json.loads(raw_text)
            except Exception:
                return {"root_cause_category": "PARSE_ERROR", "raw": raw_text}
        return raw_text

def run_diagnose_benchmark(target, base_url, model):
    cases_file = DATA_DIR / "cases_26_diagnose.json"
    with open(cases_file, "r") as f:
        cases = json.load(f)

    print(f"\n{BOLD}======================================================================{RESET}")
    print(f"{BOLD} RUNNING CLOUD SRE BENCH: 26 REAL-WORLD FAILURE LOG CASES{RESET}")
    print(f" Target: {CYAN}{target}{RESET} | URL: {SLATE}{base_url}{RESET} | Model: {AMBER}{model}{RESET}")
    print(f"{BOLD}======================================================================{RESET}\n")

    passed = 0
    total = len(cases)
    latencies = []

    for i, c in enumerate(cases, 1):
        name = c["name"]
        expected_cat = c["category"]
        expected_act = c.get("expected_action")
        log = c["log"]

        t0 = time.time()
        try:
            res = query_target(target, base_url, model, logs=log, case_id=c.get("id", str(i)))
            latency = round(time.time() - t0, 2)
            latencies.append(latency)

            cat = res.get("root_cause_category") or res.get("root_cause", "UNKNOWN")
            plan = res.get("remediation_plan")
            action = plan.get("action_id") if plan else (res.get("recommended_action_ids", [None])[0])
            status = res.get("deployment_status", "UNKNOWN")
            conf = res.get("confidence", {}).get("score", res.get("confidence", 0.0))

            cat_ok = (cat == expected_cat)
            action_ok = (expected_act is None) or (action == expected_act) or (expected_act in res.get("recommended_action_ids", []))
            
            # Special check for thin logs (Case 26)
            if expected_cat == "UNKNOWN":
                abstain_ok = res.get("safety_controls", {}).get("abstain", False) or res.get("abstain", False) or conf <= 0.50
                case_passed = cat_ok and abstain_ok
            else:
                case_passed = cat_ok and action_ok

            if case_passed:
                passed += 1
                badge = f"{GREEN}PASS{RESET}"
            else:
                badge = f"{RED}FAIL{RESET}"

            print(f"[{i:02d}/{total}] {badge} {name:<42} ({latency}s) Category: {cat}")
            if not case_passed:
                print(f"       Expected: {expected_cat} | Got: {cat}")
                if expected_act:
                    print(f"       Expected Action: {expected_act} | Got: {action}")

        except Exception as e:
            print(f"[{i:02d}/{total}] {RED}ERROR{RESET} {name:<42} (Exception: {e})")

    avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    accuracy = round((passed / total) * 100, 1)

    print(f"\n{BOLD}Diagnose Summary:{RESET} {passed}/{total} Passed ({accuracy}%) | Avg Latency: {avg_lat}s")
    return passed, total

def run_chat_benchmark(target, base_url, model):
    prompts_file = DATA_DIR / "prompts_14_chat.json"
    with open(prompts_file, "r") as f:
        prompts = json.load(f)

    print(f"\n{BOLD}======================================================================{RESET}")
    print(f"{BOLD} RUNNING CLOUD SRE BENCH: 14 GROUNDED PLATFORM CHAT PROMPTS{RESET}")
    print(f"{BOLD}======================================================================{RESET}\n")

    passed = 0
    total = len(prompts)

    for i, p in enumerate(prompts, 1):
        name = p["name"]
        prompt = p["prompt"]
        must_include = p.get("must_include", [])
        must_not_include = p.get("must_not_include", [])

        try:
            res = query_target(target, base_url, model, prompt=prompt)
            res_str = str(res)

            include_ok = all(term.lower() in res_str.lower() for term in must_include)
            exclude_ok = all(term.lower() not in res_str.lower() for term in must_not_include)
            case_passed = include_ok and exclude_ok

            if case_passed:
                passed += 1
                badge = f"{GREEN}PASS{RESET}"
            else:
                badge = f"{RED}FAIL{RESET}"

            print(f"[{i:02d}/{total}] {badge} {name:<38}")
            if not case_passed:
                if not include_ok:
                    missing = [t for t in must_include if t.lower() not in res_str.lower()]
                    print(f"       Missing required facts: {missing}")
                if not exclude_ok:
                    present = [t for t in must_not_include if t.lower() in res_str.lower()]
                    print(f"       Present forbidden terms: {present}")

        except Exception as e:
            print(f"[{i:02d}/{total}] {RED}ERROR{RESET} {name:<38} (Exception: {e})")

    accuracy = round((passed / total) * 100, 1)
    print(f"\n{BOLD}Chat Grounding Summary:{RESET} {passed}/{total} Passed ({accuracy}%)\n")
    return passed, total

def main():
    parser = argparse.ArgumentParser(description="Cloud SRE Bench Evaluation Harness")
    parser.add_argument("--target", choices=["api", "ollama", "local"], default="api",
                        help="Target engine: 'api' (chat.deployxa.com), 'ollama', or 'local'")
    parser.add_argument("--url", default=None, help="Base URL for target")
    parser.add_argument("--model", default=None, help="Model name")
    args = parser.parse_args()

    if args.target == "api":
        base_url = args.url or "https://chat.deployxa.com"
        model = args.model or "deployxa-lm-1.0"
    elif args.target == "ollama":
        base_url = args.url or "http://localhost:11434"
        model = args.model or "deployxa/deployxa-lm"
    elif args.target == "local":
        base_url = args.url or "http://localhost:8080"
        model = args.model or "deployxa-lm-1.0"

    p1, t1 = run_diagnose_benchmark(args.target, base_url, model)
    p2, t2 = run_chat_benchmark(args.target, base_url, model)

    tot_p = p1 + p2
    tot_t = t1 + t2
    tot_acc = round((tot_p / tot_t) * 100, 1)

    print(f"{BOLD}======================================================================{RESET}")
    print(f"{BOLD} FINAL CLOUD SRE BENCH SCORECARD: {tot_p}/{tot_t} ({tot_acc}%){RESET}")
    print(f"{BOLD}======================================================================{RESET}\n")

if __name__ == "__main__":
    main()
