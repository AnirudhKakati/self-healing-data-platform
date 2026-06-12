# Partial Load Failures

## What This Looks Like

Partial load failures occur when the pipeline successfully completed earlier steps (`ingestion`, `validation`, possibly `transformation`) but failed during or after the `load` step in a way that may have left the destination warehouse in an inconsistent state. The defining concern is not just that the load failed, but that *some data may have been written before the failure*, meaning the destination table is now in an unknown intermediate state.

Typical error types include `LoadStepError` with messages referencing dropped connections mid-write, transaction failures during commit, partial inserts, or warehouse errors that occurred after some rows were already streamed. Errors that explicitly mention `aborted`, `mid-transaction`, `connection lost during write`, `partial commit`, or `transaction rolled back` are strong signals. Warehouse-side errors that happened after the load began (rather than at planning time) generally fall here.

The distinguishing characteristic of partial load failures versus other load failures is the *timing*: failures that happened before any data was written are usually classified as `network` (couldn't connect) or `quota` (rejected upfront). Partial load failures are specifically about failures *during* the write, where the destination state is now uncertain.

## Common Root Causes

- Warehouse connection dropped mid-write due to network instability between the worker and the warehouse
- Warehouse hit a resource limit (memory, slot exhaustion) partway through a large write and aborted
- Transaction was killed by a warehouse admin operation, deployment, or maintenance window
- The destination table's write semantics are not transactional (e.g., row-by-row insert without an outer transaction) and the failure occurred after some rows committed
- Worker process was terminated mid-load (kubelet eviction, OOM kill) leaving the warehouse-side transaction in limbo
- Schema or constraint violation occurred on a specific row partway through the load — earlier rows succeeded, the violating row aborted the rest

## Recommended Recovery Actions

`replay_from_raw` is the canonical action for partial load failures. The raw ingested data is preserved on disk (per our ingestion step), and re-running just the load step from that snapshot avoids re-fetching from the source and avoids re-running expensive transformations. Crucially, our load step uses `if_exists='replace'` semantics — the replay will overwrite any partial state in the destination table, restoring consistency.

`retry_with_backoff` is acceptable when the failure pattern strongly suggests transient warehouse instability (intermittent connection drops, transient resource pressure) and the destination table is known to be replaceable rather than append-only. With our current `if_exists='replace'` load semantics, retry is reasonably safe — but `replay_from_raw` is more explicit about intent and avoids re-running upstream steps.

`escalate` is appropriate when the partial load failure references warehouse-side schema violations, constraint failures, or persistent resource issues. These are not transient and a human needs to look. Also escalate when the same pipeline has had multiple partial load failures in a short window — a pattern of partial loads suggests deeper warehouse or worker instability.

Avoid `retry` (without backoff) for partial load failures. If the cause was warehouse resource pressure, an immediate retry will likely fail the same way.

## When To Escalate

- Partial load failure references a constraint violation, schema violation, or referential integrity error — these are deterministic and will recur on retry
- Multiple partial loads on the same pipeline within a short window — suggests warehouse-side instability beyond a single transient issue
- The destination table is append-only or transactional consistency cannot be guaranteed via replace — replay may not safely restore state
- The error message indicates the warehouse-side transaction state is unknown — manual inspection of the destination table is warranted before automated recovery
- Worker process was killed (not a warehouse-side failure) — escalate to investigate worker stability

## Examples

**Example 1: Connection dropped mid-write**
A pipeline failed at the `load` step with `error_type=LoadStepError` and `error_message="Failed to write table to data warehouse: connection closed unexpectedly during INSERT"`. The transformation step succeeded and produced a 50,000-row CSV. Recommendation: `replay_from_raw`. The transformed file is on disk, the destination table is replaceable, and replaying just the load step will restore consistency without re-fetching or re-transforming.

**Example 2: Transient warehouse resource pressure**
A pipeline failed at the `load` step with `error_type=LoadStepError` and `error_message="Failed to write table to data warehouse: query exceeded memory limit, transaction aborted"`. The warehouse has been under heavy load from other tenants. Recommendation: `retry_with_backoff`. Resource pressure is likely transient and a backed-off retry should land when load has eased. If it recurs, the table size may be exceeding warehouse capacity and a human should consider chunked loads.

**Example 3: Constraint violation mid-load**
A pipeline failed at the `load` step with `error_type=LoadStepError` and `error_message="Failed to write table to data warehouse: unique constraint violated on row 12847"`. Recommendation: `escalate`. This is not transient — a specific row violates a destination constraint, and retrying will fail identically. A human needs to investigate the data and either adjust the transformation to deduplicate, relax the constraint, or correct the source.

**Example 4: Worker terminated mid-load**
A pipeline's most recent run shows `status=failed` with `error_type=LoadStepError` and `error_message="Worker process terminated"`. The destination table state is unknown. Recommendation: `escalate`. Before any automated retry, a human should verify the destination table state to ensure a replay won't leave duplicates or other inconsistencies. After verification, `replay_from_raw` may be appropriate, but the verification step is not safely automatable.
