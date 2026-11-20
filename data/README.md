# Fixture provenance and revisions

These are public development fixtures, not a held-out evaluation corpus. The original repository described its short diagnosis snippets as authentic production telemetry but supplied no incident provenance or independent verification. Their original source, sanitization process, train/test membership, and model-training overlap are unknown. V2 makes no claim that these fixtures are verified production incidents.

`cases_26_diagnose.json` has 26 cases across 17 categories, including 2 healthy cases and 1 ambiguous case. The distribution is selected, small, and historically vendor-authored. Several categories share remediations or combine different causes. `taxonomy.json` describes every accepted label/action for all generic model adapters. The retained machine-readable ID convention reflects the original vendor schema; it is not a capability a model is expected to know without instructions.

## Reference-label corrections

| Case | V2 correction and reason |
| --- | --- |
| CASE-02 | Verify occupied binding/duplicate listeners before changing ports; a fixed reallocation recipe is not established by the log. |
| CASE-06 | Fix the indicated compilation/type error; a clean rebuild alone cannot correct source types. |
| CASE-07 | Verify/install the missing build dependency; cache deletion is not supported by the evidence. |
| CASE-08 | Correct the impossible package version requirement; cache deletion cannot make that version available. |
| CASE-10 | Added an explicit `memory.events: oom_kill 1` fixture line to support OOM attribution. This is an authored edit; exit 137 alone does not prove OOM. |
| CASE-12 | Verify DNS/hostname configuration; the log may include a port incorrectly embedded in the hostname. |
| CASE-13 | Build configuration and Dockerfile-path correction replace missing-environment-variable injection. |
| CASE-16 | Replaced credential-bearing/private endpoints with redacted credentials and an `.invalid` example hostname. |
| CASE-20 | Certificate inspection/renewal with verification retained replaces a potentially ambiguous “trust certificate” action. |
| CASE-24 | Missing project import replaces “AI-hallucinated import.” The log cannot establish who authored the code or why the file is absent. |
| CASE-26 | Enforce the stated conjunction: UNKNOWN, escalation, confidence < 0.5, and abstention. The old runner allowed abstention OR low confidence and ignored the action. |

These changes are evidence-based corrections, not independent expert adjudication of all labels. A single next-action label remains restrictive. Further label review and alternative valid actions are prerequisites for a general benchmark.

## Chat suites

`sre_chat.json` contains 8 authored, vendor-neutral question fixtures. Its regex checks are surface-level smoke tests, not proofs of correct reasoning. Forbidden brand/word checks and branded identity requirements from the old 14-query suite have been removed. Generic advice may mention a technology while warning against it; such mentions must not be treated as failures by blanket substring bans.

`platform_chat.json` contains 5 opt-in reference QA fixtures. Every question includes the same frozen reference text, derived from the old expectations (pricing, framework, domain/configuration pages, and the listed model name). It is explicitly a fictionalized evaluation reference, not a verified current product page. Asking about the referenced model does not require a different model to claim that identity. Scores measure reference retrieval with lexical checks, not SRE skill.

The previous `prompts_14_chat.json` is retired; its contents remain in Git history. Its identity/refusal/version-string checks were not valid prompt-leak or general safety measurements and have no replacement headline metric.

## Adding fixtures

Provide explicit logs, a justified category/next action, and provenance/authoring notes. Use synthetic examples or sanitize all customer/secret data before committing. Mark edits rather than describing synthetic additions as original production evidence. The default input redactor is not comprehensive anonymization. Optional positive `timeout_seconds` overrides the request timeout for a case.
