# Public development evaluation methodology (v2)

## What changed

The old leaderboard was not reproducible from the public files. It has been withdrawn from the README, not replaced with inferred or fabricated results. Changing prompts, reference actions, fixtures, and scoring means v2 scores are not comparable to the original runner or the private 384-incident claims.

No private evaluation, training manifest, or independent replication is available. Deployxa authored the suite. Its historical categories/action IDs follow vendor conventions. Publishing these conventions and giving the complete instructions to every generic model removes a format-information disadvantage; it does not establish an unbiased incident distribution.

## Inputs and adapter boundaries

Each diagnosis receives the complete category/action taxonomy, confidence/abstention instructions, JSON response schema, and one redacted log. The system prompt does not include the expected answer, case name, ID, or description. All generic adapters use the same messages. Raw log content is labelled untrusted.

Ollama accepts a schema in `format`; OpenAI-compatible endpoints use `response_format: {"type": "json_object"}`; Anthropic receives the schema as prompt text. Responses are validated by the same parser. Differences in provider constraints must be disclosed when comparing models. The actual request body and provider response are archived. No prompt fallback or format-repair model is used.

The native Deployxa diagnosis endpoint accepts logs rather than these messages. Its hidden server-side behavior is unknown. Reports mark it `vendor_system` and omit unsent messages. A vendor system score must be kept separate from model-adapter comparisons.

Every fixture is sent in a separate request. Temperature, token cap, optional supported seed, retries, timeout, and request interval are configured explicitly in the report. Runs reuse the same fixtures. Sampling settings cannot guarantee deterministic provider inference. Use frozen model revisions where available; do not treat aliases as immutable.

## Diagnosis parsing and scoring

The preferred JSON shape is:

```json
{
  "root_cause_category": "UNKNOWN",
  "remediation_plan": {"action_id": "ESCALATE_HUMAN_SRE_AUDIT"},
  "confidence": {"score": 0.2},
  "safety_controls": {"abstain": true}
}
```

For compatibility, the parser accepts `root_cause`, numeric `confidence`, top-level `abstain`, and an unambiguous `recommended_action_ids` list. It tolerates JSON fences and normalizes enum case, whitespace, and hyphens to uppercase underscores. It does not infer arbitrary synonyms or interpret prose as JSON. Unknown enums, invalid types, missing confidence/abstention, conflicting multiple actions, and nonfinite/out-of-range confidence are format errors. A missing action is equivalent to null; it cannot pass an actionable or thin-log case.

A diagnosis passes only when category and proposed action match the reference, and the model does not abstain for supported/healthy cases. For `UNKNOWN`, escalation, `abstain=true`, and confidence **strictly below 0.5** are all required. Healthy cases require `NONE` and a null action. Listing multiple possible actions cannot satisfy a reference by chance.

A selected action is a proposed next step. Nothing is executed; successful container recovery is not measured. Confidence is checked only against the thin-log rule. General confidence calibration is not measured.

## Metrics and denominators

Reports expose each suite independently; there is no overall SRE score.

- **Diagnosis pass rate:** complete rubric passes / all diagnosis cases in that run.
- **Category accuracy:** category agreement / all diagnosis cases, with unscorable cases counted as failures. A separate valid-output category accuracy has its own denominator so transport/format failures remain visible.
- **Next-action accuracy:** action agreement / all diagnosis cases, including null actions for healthy logs. This is not recovery.
- **Clean-log false alarms:** valid responses to healthy logs predicting a non-`NONE` category or a non-null remediation / valid healthy responses. Errors are separately counted as `clean_log_unscorable`; no valid healthy outputs produces a null rate, not 0%.
- **Thin-log pass rate:** complete thin-log rubric passes / thin-log cases. There is only one such fixture.
- **Chat pass rate:** answers satisfying grouped lexical checks / all cases in that chat suite. Regex alternatives allow some surface variation but cannot verify reasoning, negation, commands, or factual correctness. Token dumping can pass. Human review of raw answers is required for substantive claims.
- **Transport and format errors:** separately counted. A valid wrong answer has status `ok` with `passed=false`. Errors are not capability conclusions.

Two healthy logs cannot support a precise false-alarm claim. No prompt-leak rate, jailbreak-success rate, remediation recovery, or general reliability metric is implemented.

## Statistical interpretation

Each per-run proportion includes count, denominator, and a descriptive 95% Wilson interval. Wilson intervals assume independent Bernoulli observations from a relevant population; this small, selected and correlated fixture set does not meet a validated random-sampling design. The intervals describe sample uncertainty under that assumption, not selection bias, contamination, label error, or population performance.

Repeated runs report individual run scores and descriptive mean/sample standard deviation. Repeated cases are not pooled as independent new incidents. With one run, standard deviation is null. With no valid outputs, a conditional rate and interval are null. There is no significance test or claim that a small difference ranks models reliably.

## Requirements for a future leaderboard

Before publishing comparative claims:

1. Freeze an independently reviewed incident taxonomy, labels, rubric, harness revision, and provider prompts. Document reasonable alternate remediations and adjudication.
2. Establish a held-out incident collection with provenance, deduplication, category/site/time separation, and access controls. Public development cases must not be treated as held-out cases.
3. Publish each participating model's training/evaluation overlap disclosure, fine-tuning distribution, evaluation exposure, and contamination checks. Unknown training data must be reported as unknown.
4. Evaluate all models with matched information, tools, context, settings, and adapter roles. Separate product systems from standalone model inference.
5. Implement and publish any claimed recovery metric in an isolated executable environment with independent success verification. For leakage tests, define protected canaries, attack set, disclosure criteria, and denominators; a refusal keyword is insufficient.
6. Publish authorized incident inputs or a verifiable access process, exact model revisions, raw responses, per-case outcomes, run artifacts, hashes, failure handling, and replication instructions.
7. Predefine the sampling design, repeated-run plan, paired comparison method, uncertainty estimates, and minimum sample/power requirements. Do not manufacture independence by repeating fixtures.
8. Obtain independent replication and disclose vendor authorship and funding. No leaderboard should be restored solely because this harness passes its own tests.
