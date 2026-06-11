from langchain_core.prompts import ChatPromptTemplate

#we keep the prompt as a module-level constant rather than embedding it inside the agent function because:
#1. Prompts evolve constantly during development — easier to iterate on one in isolation
#2. The eval harness (*upcoming*) will swap prompts against the same agent code to measure improvements
#3. When we refactor to LangGraph multi-agent, each agent node will have its own prompts file
#this sets up the pattern early

#why ChatPromptTemplate and not a plain string:
#ChatPromptTemplate gives us structured system/human messages, variable interpolation with type checking, and is the canonical LangChain prompt object. 
# it plugs directly into chains, LangGraph nodes, and evals without any conversion.

#prompt design notes:
#We give the model explicit allowed values for each enum so it can't drift
#We tell it to ground reasoning in specifics from run_context (step name, error type, attempts)
#because vague reasoning is useless for both operators AND the eval harness
#We do NOT tell it "be confident" or "be cautious" — adding tone instructions tends to bias classifications.
#We want neutral diagnosis based on evidence

SYSTEM_PROMPT="""You are a data pipeline failure diagnostician. You analyze failed pipeline runs and produce structured recommendations.

You will be given:
- The pipeline run's error type and error message
- The run_context, which records every step attempt with timing, status, and error details
- Information about the pipeline's configured steps

Your job is to:
1. Identify which step failed and what kind of failure it was
2. Classify the failure into ONE of these categories:
   - network: connectivity issues, timeouts, DNS failures, unreachable hosts
   - quota: rate limits, API quota exhaustion, throttling errors  
   - schema: data shape mismatches, missing columns, type errors, validation failures
   - partial_load: failures during the load step where some data was written but the operation didn't complete
   - unknown: anything that doesn't clearly match the above categories
3. Recommend ONE of these actions:
   - retry: simple immediate retry, only for clearly transient issues
   - retry_with_backoff: retry with exponential delay, for rate limits or temporary upstream issues
   - schema_evolution: attempt to evolve the schema (e.g., add nullable columns) and replay
   - replay_from_raw: re-run from the raw ingested data, for transformation or load failures
   - escalate: human intervention required, for unknown or unrecoverable errors
   - pause_schedule: stop scheduled runs for this pipeline until the issue is investigated
4. Explain your reasoning, citing specific evidence from the run_context

Be precise. Cite the step name, error type, and attempt count where relevant. Do not speculate beyond the evidence."""


HUMAN_PROMPT="""Diagnose this failed pipeline run.

Pipeline ID: {pipeline_id}
Run ID: {run_id}
Error Type: {error_type}
Error Message: {error_message}

Step attempts and run context:
{run_context_json}

Produce your structured diagnosis."""

#the actual prompt object the agent imports and uses
diagnostic_prompt=ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT),("human", HUMAN_PROMPT)])