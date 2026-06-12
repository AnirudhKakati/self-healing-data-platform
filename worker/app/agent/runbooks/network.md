# Network Failures

## What This Looks Like

Network failures occur when a pipeline step cannot complete an HTTP or external service interaction due to connectivity issues. They appear most often during the `ingestion` step, where the pipeline fetches data from an external `source_url`, but can also surface during `load` if the destination warehouse is unreachable.

Typical error types include `ConnectTimeout`, `ReadTimeout`, `ConnectionError`, `RemoteDisconnected`, `httpx.ConnectError`, and `httpx.TimeoutException`. Error messages often reference DNS resolution failures, connection refused, TLS handshake failures, or timed-out reads. HTTP 5xx responses from the source server also fall in this category when they indicate a transient upstream issue.

The distinguishing characteristic of network failures is that they are typically transient — a retry seconds or minutes later often succeeds without any configuration change.

## Common Root Causes

- Source server is temporarily down or restarting
- DNS resolution intermittently failing
- Network congestion causing timeouts under default timeout values
- TLS certificate validation failures on the source server side
- Source server is rate-limiting our requests at the network layer (often distinct from a true quota error)
- The configured `source_url` is permanently dead (404, gone), which looks like a network failure but is NOT transient and should not be retried indefinitely

## Recommended Recovery Actions

`retry_with_backoff` is the default action for genuine transient network failures. Exponential backoff with jitter gives the upstream service time to recover and avoids retry storms.

`retry` (without backoff) is acceptable only if the original step already had a retry strategy configured and the failure occurred on the first attempt — the next attempt may simply succeed.

`pause_schedule` is the right call when network failures are sustained — for example, three consecutive runs failing with the same `ConnectTimeout` against the same `source_url` strongly suggests the source endpoint is dead or moved, not transiently unavailable. Continuing to retry burns resources and floods the failure history.

`escalate` is appropriate when the failure pattern is ambiguous — for example, a 404 response on a URL that was working yesterday could be a deployment issue at the source, a configuration error, or genuine endpoint removal. A human should look.

## When To Escalate

- The `source_url` returns 404 or 410 — endpoint may be permanently gone, retrying will not help
- The same network error has occurred on three or more consecutive runs against the same target — pattern suggests the failure is not transient
- The failure occurred during `load` rather than `ingestion` — destination warehouse unreachability is a more serious infrastructure concern than upstream flakiness
- Error message references TLS or certificate issues that have not appeared before — possible security or configuration drift

## Examples

**Example 1: Transient ingestion timeout**
A pipeline failed at the `ingestion` step with `error_type=ConnectTimeout` and `error_message="HTTPSConnectionPool(host='api.example.com', port=443): Read timed out"`. The step had no retry configured (first and only attempt failed). Recommendation: `retry_with_backoff`. This is a textbook transient network failure; the source is likely under temporary load and a backed-off retry will probably succeed.

**Example 2: Sustained 404 on known-good URL**
A pipeline failed at the `ingestion` step with `error_type=IngestionStepError` and `error_message="Failed to fetch from https://example.com/data.csv: 404 Not Found"`. Three prior runs of this pipeline failed identically. Recommendation: `pause_schedule`. The `source_url` is not transiently unavailable — it is gone. Continuing to schedule runs is wasteful and pollutes the failure history. A human needs to update the pipeline configuration.

**Example 3: First-attempt connection error with retries configured**
A pipeline failed at the `ingestion` step with `error_type=ConnectionError` on attempt 1 of 3. The `attempt_pattern` from log analysis shows the step had not yet exhausted its retry budget when the run was marked failed (uncommon — usually retries are exhausted within the step). Recommendation: `retry`. The retry mechanism itself should handle this; no backoff override needed.
