# Schema Failures

## What This Looks Like

Schema failures occur when the *shape* of the data does not match what the pipeline expects. Unlike network or quota failures, schema failures are deterministic — retrying the same data through the same step will fail identically. They typically surface during the `validation` step (when our explicit schema checks reject the data) but can also appear during `transformation` (when a rename or filter references a column that no longer exists) or `load` (when the destination table's expected schema diverges from the transformed dataframe).

Typical error types include `ValidationStepError`, `TransformationStepError`, and `LoadStepError`. Error messages reference missing columns, unexpected columns, null values in non-null columns, type mismatches, or row counts below configured minimums. Strings like `Missing required columns`, `contains null values`, `Unknown filter column`, `Type mismatch`, or `expected at least N rows` are reliable schema-failure signals.

The distinguishing characteristic of schema failures is that they signal a *change* — either in the source data (the upstream provider added, removed, or renamed a column) or in the pipeline configuration (someone updated the validation config but the source data hasn't caught up yet).

## Common Root Causes

- Source data provider added, removed, or renamed columns without notice
- Source data provider changed column data types (string to integer, etc.)
- Source data is empty or smaller than expected (zero rows, or below the configured `min_rows`)
- Pipeline `validation` config was updated to be stricter than the current source data supports
- Pipeline `transformation` config references columns that no longer exist in the source
- Null values appearing in columns that were historically non-null (data quality regression upstream)

## Recommended Recovery Actions

`schema_evolution` is the targeted action for additive schema changes — new columns appearing in the source that the pipeline doesn't know about, or columns becoming nullable. This action attempts a safe schema evolution (adding nullable columns, expanding type compatibility) and re-runs the step. It is NOT appropriate for destructive changes (columns disappearing, types narrowing) — those need human review.

`escalate` is the default action for most schema failures. Schema drift is rarely truly automatic-recoverable — it usually means the contract between the source and the pipeline has changed, and a human needs to decide whether the change is intentional, whether the pipeline config should be updated, or whether the upstream provider should be notified. The cost of incorrectly auto-recovering a schema failure is high (silently dropping data, loading misshapen rows) so the bias is toward escalation.

`replay_from_raw` is occasionally appropriate when the schema failure occurred at `transformation` or `load` but the validation step had already passed — the raw ingested data is known-good, and the failure was downstream. Replaying from the raw snapshot with adjusted transformation logic may recover without re-fetching.

Retry actions (`retry`, `retry_with_backoff`) are almost never appropriate for schema failures. The same data through the same step will fail again. Recommending a retry on a schema failure is usually a sign the classification was wrong.

## When To Escalate

- Any schema failure that is not clearly additive — column removals, type narrowing, structural changes
- First-time occurrence of a schema failure on a previously stable pipeline — possible upstream change worth investigating
- Schema failure occurring during `load` — destination schema mismatches can cause partial loads or silent data corruption
- Validation rule changes that haven't been communicated to source data owners
- Repeated schema failures across multiple unrelated pipelines for the same tenant — suggests a coordinated upstream change

## Examples

**Example 1: Source added a new column**
A pipeline failed at the `validation` step with `error_type=ValidationStepError` and `error_message="Validation failed: Missing required columns: ['email_verified']"`. Investigation shows the source CSV does have an `email_verified` column, but the validation config lists `email` as the expected name. The source provider renamed `email` to `email_verified`. Recommendation: `escalate`. This is a column rename, not an additive change — automated schema evolution cannot safely guess that `email_verified` is the replacement for `email`. A human needs to update the validation config.

**Example 2: Null values in a non-null column**
A pipeline failed at the `validation` step with `error_type=ValidationStepError` and `error_message="Validation failed: Column 'user_id' contains null values"`. The pipeline has run successfully for months with this rule. Recommendation: `escalate`. This is a data quality regression at the source, not a schema change the pipeline can adapt to. Auto-recovering by relaxing the null check would silently load bad data.

**Example 3: Transformation references missing column**
A pipeline failed at the `transformation` step with `error_type=TransformationStepError` and `error_message="Unknown filter column: 'legacy_status'"`. The validation step passed, indicating the source data is intact. The transformation config filters on a column that no longer exists. Recommendation: `escalate`. The transformation config is out of date relative to the schema the pipeline now ingests; a human needs to update or remove the obsolete filter.

**Example 4: Row count below minimum (genuinely empty source)**
A pipeline failed at the `validation` step with `error_type=ValidationStepError` and `error_message="CSV has 0 rows, expected at least 1"`. The source returned an empty file. Recommendation: `escalate`. An empty source could be a legitimate signal (no events to report today) or a broken source. The system cannot tell the difference without human judgment.
