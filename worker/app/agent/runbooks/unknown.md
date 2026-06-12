# Unknown Failures

## What This Looks Like

Unknown failures are the residual category — they are what gets assigned when the failure signal does not clearly fit `network`, `quota`, `schema`, or `partial_load`. The defining characteristic is *not* that something exotic happened, but that the available evidence (error type, error message, step context, attempt pattern) does not unambiguously point to one of the four primary categories.

Typical situations include generic `Exception` types with no descriptive subclass, error messages that are empty or uninformative, errors originating from code paths the agent does not have visibility into, or failure patterns that span multiple categories (a network error that turned into a partial load, for example). Failures classified as `unknown` with low confidence (below 0.5) are also legitimately routed here — the classification node opted out rather than guess.

This category is also where degraded agent outputs end up. When the log analysis or classification nodes fail and return their sentinel values, the failure is effectively unknown by construction.

## Common Root Causes

- Genuinely novel failures the system has not encountered before
- Errors with insufficient diagnostic information (empty message, generic `Exception`)
- Errors that span multiple categories — partial state from one root cause and surface symptoms from another
- Failures in step handlers not yet covered by the existing exception hierarchy
- Agent layer itself degraded during this run (log analysis or classification sentinel triggered)
- Underlying infrastructure issue (database connection lost, worker memory pressure, container restart) that surfaced as a generic exception

## Recommended Recovery Actions

`escalate` is the default action for unknown failures. The whole point of this category is "the system cannot safely recommend an automated recovery" — by definition, autonomous action carries unacceptable risk. A human operator is the right next step.

`retry_with_backoff` is acceptable only in a narrow case: the failure has no diagnostic information, the pipeline has been stable historically, and the cost of one cautious retry is low. This is a *guess*, and the explanation should explicitly acknowledge that retrying without understanding the failure is a hedge, not a diagnosis. Repeated unknown failures on the same pipeline should always escalate.

`pause_schedule` is appropriate when unknown failures recur on a scheduled pipeline — even without knowing the root cause, continuing to run a pipeline that keeps failing is wasteful and pollutes the failure history. Pausing buys time for human investigation.

Specific actions (`schema_evolution`, `replay_from_raw`) should not be recommended for unknown failures. These actions are targeted interventions; recommending them without a matching diagnosis is worse than escalation.

## When To Escalate

- Almost always. `unknown` is the category whose default is escalation.
- Especially escalate when the agent itself produced degraded outputs (notable_signals contains `log_analysis_failed`, classification confidence is 0.0)
- Escalate when the error message is empty or generic — the system has no signal to act on
- Escalate when unknown failures recur — pattern detection is a human job when the system itself cannot pattern-match
- Escalate when the unknown failure occurred at the `load` step — destination state may be uncertain and automated recovery could compound the issue

## Examples

**Example 1: Generic exception with no message**
A pipeline failed at the `transformation` step with `error_type=Exception` and `error_message=""`. The attempt pattern shows a single attempt with no retries. Recommendation: `escalate`. There is no diagnostic signal to act on; the system cannot distinguish between a transient issue and a deterministic bug. A human needs to look at the worker logs.

**Example 2: Agent degraded during analysis**
A pipeline failed at the `ingestion` step with `error_type=ConnectTimeout`. The log analysis node produced a sentinel output (`notable_signals=['log_analysis_failed']`), and the classification node consequently produced `unknown` with `confidence=0.0`. Recommendation: `escalate`. Even though the surface error looks network-like, the agent layer itself did not function fully on this run, and the explanation should be honest about that. A human should review.

**Example 3: Novel failure pattern**
A pipeline failed at the `load` step with `error_type=RuntimeError` and `error_message="dictionary changed size during iteration"`. This is not a category the system has seen — it looks like an internal Python error during the load handler. Recommendation: `escalate`. This is likely a worker-side bug rather than a pipeline or data issue; escalating gives engineering visibility into a possible code defect.

**Example 4: Cautious retry on a stable pipeline**
A pipeline that has run successfully every day for two months failed once with `error_type=Exception` and `error_message="unexpected internal state"`. No prior unknown failures on this pipeline. Recommendation: `retry_with_backoff`. The historical stability suggests this is likely transient — possibly an environmental hiccup that won't recur. The explanation should acknowledge this is a hedge, and if the next run also fails the recommendation should shift to escalate.
