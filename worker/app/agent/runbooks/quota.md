# Quota Failures

## What This Looks Like

Quota failures occur when a pipeline step is rejected because a usage limit has been hit — either at the source API, the destination warehouse, or an intermediate service. They most often surface during the `ingestion` step (source API rate limits) or the `load` step (warehouse quota or concurrent-query limits), and are distinguished from network failures by the *deliberate* rejection from the remote service: the request reached its destination and was refused.

Typical signals include HTTP 429 (`Too Many Requests`) responses, HTTP 403 with quota-related error bodies, error messages containing strings like `quota exceeded`, `rate limit`, `concurrent queries`, `daily limit`, `monthly usage`, or vendor-specific quota error codes. The error often includes a `Retry-After` header or a hint about when the quota resets.

Unlike network failures, quota failures are not random — they correlate with usage patterns. A pipeline that just ran ten times in five minutes hitting a 429 is a quota failure, not a network failure, even if the surface error type looks similar.

## Common Root Causes

- Source API rate limit (per-second, per-minute, or daily request cap) exceeded
- Destination warehouse concurrent-query limit reached (multiple pipelines loading simultaneously)
- Warehouse daily or monthly bytes-processed quota hit
- API key tier limits reached on the source service
- Burst of pipeline runs triggered by a schedule misconfiguration causing self-inflicted rate limiting
- Genuine capacity upgrade needed on the source or destination — the pipeline has outgrown the current tier

## Recommended Recovery Actions

`retry_with_backoff` is the default action. Quota failures usually resolve themselves with time — the rate limit window slides, the daily quota resets at midnight, the concurrent query slot frees up. Exponential backoff with jitter is essential here because immediate retry will hit the same limit, and synchronized retries across multiple failed runs will make it worse.

`pause_schedule` is appropriate when the quota failure is sustained across multiple runs and backoff alone is not helping — for example, a daily quota is exhausted and the next reset is hours away. Pausing the schedule until the quota window resets is cheaper than continuing to fail.

`escalate` is the right call when the quota failure suggests structural capacity issues, not transient bursts. If the same pipeline regularly hits quota on its normal schedule, the tier needs to be upgraded — a recommendation alone won't fix that.

Avoid `retry` (without backoff) for quota failures — immediate retry against a rate-limited endpoint almost always fails again and may extend the rate-limit window.

## When To Escalate

- Quota failures recur on every scheduled run of the same pipeline — the pipeline has outgrown its current tier
- The failure references a daily or monthly quota rather than a per-second rate limit — backoff won't fix that within the run
- The same tenant has multiple pipelines hitting quota concurrently — possible self-inflicted rate limiting from schedule overlap
- Error message references billing or payment issues rather than usage — operational matter for a human

## Examples

**Example 1: Source API rate limit hit during ingestion**
A pipeline failed at the `ingestion` step with `error_type=IngestionStepError` and `error_message="Failed to fetch from https://api.vendor.com/data: 429 Too Many Requests"`. The pipeline runs every minute and the source allows 30 requests per minute across all clients. Recommendation: `retry_with_backoff`. The rate-limit window is short; a backed-off retry should land in a new window. If the failures persist across multiple runs, escalate to consider a slower schedule or a higher tier.

**Example 2: Warehouse daily quota exhausted**
A pipeline failed at the `load` step with `error_type=LoadStepError` and `error_message="Failed to write table to data warehouse: 403 Quota Exceeded — daily bytes processed limit reached"`. The failure occurred at 4pm and the quota resets at midnight. Recommendation: `pause_schedule`. Retrying for the next eight hours will burn resources without succeeding. Pausing the schedule until the quota resets is the right call.

**Example 3: Recurring quota failures on a stable pipeline**
A pipeline has failed at the `load` step on its last five scheduled runs, each time with `429 concurrent queries exceeded`. The pipeline schedule has not changed. Recommendation: `escalate`. This is no longer a transient quota issue — the warehouse cannot handle the steady-state load. A human needs to either spread the schedule, batch the loads, or upgrade the warehouse tier.
