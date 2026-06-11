import json
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.exc import SQLAlchemyError
from shared.db import async_session
from shared.config import GOOGLE_API_KEY, GEMINI_MODEL
from shared.utils import now_naive
from control_plane.app.models.agent_recommendations import AgentRecommendation
from worker.app.agent.schemas import DiagnosticAgentOutput
from worker.app.agent.prompts import diagnostic_prompt

#we build the LLM client ONCE at module load time, not per-invocation
#langchain-google-genai clients are stateless and thread-safe, so reusing the same instance avoids re-authentication overhead on every failed run.
#temperature=0 makes the output deterministic for a given input — critical for reproducibility in the eval harness later.

_llm=ChatGoogleGenerativeAI(model=GEMINI_MODEL,google_api_key=GOOGLE_API_KEY,temperature=0)

#with_structured_output() wires the Pydantic schema into the LLM call.
#under the hood it uses Gemini's native structured output / function calling
#so the model is CONSTRAINED at decode time to produce valid JSON matching our schema.
#this is much more reliable than asking the model to "please return JSON" in the prompt and parsing it ourselves.

_structured_llm=_llm.with_structured_output(DiagnosticAgentOutput)

#the chain combines the prompt template and the structured LLM into one callable.
#we build it once at module load. Each invocation just does: chain.ainvoke({...variables...})

_diagnostic_chain=diagnostic_prompt | _structured_llm

async def run_diagnostic_agent(run_context:dict)-> int|None:
    """Diagnose a failed pipeline run and persist a recommendation row.

    Called by the executor in the finally block, AFTER the run has been marked as failed and observability has been recorded, BEFORE the webhook is dispatched.
    The returned recommendation_id (or None) is used by the webhook payload's recommendations_url.

    We open a FRESH database session here (not the executor's) for clean isolation:
    - the executor's session has been through commits, rollbacks, and many writes by this point
    - the agent is its own logical unit and shouldn't inherit that state
    - failures inside the agent stay contained — they cannot poison the executor's session
    This mirrors the pattern used by shared/webhook_dispatcher.py.

    Returns the new AgentRecommendation.id on success, or None on any failure (the agent is best-effort — if Gemini is down or returns garbage, the rest of the pipeline run flow must still complete).
    """
    
    #we only invoke the agent when the run actually failed.
    #being defensive here means the executor can call us unconditionally in finally without needing to check run_status itself, keeping the executor cleaner.
    if run_context.get("run_status")!="failed":
        return None

    run_id=run_context.get("run_id")
    pipeline_id=run_context.get("pipeline_id")
    tenant_id=run_context.get("tenant_id")
    error_type=run_context.get("error_type","Unknown")
    error_message=run_context.get("error_message","No error message available")

    #serialize run_context to JSON for the prompt. 
    # default=str handles datetime objects and other non-JSON-native types gracefully
    # without it, json.dumps would throw on the first datetime it encounters. indent=2 makes the model's parsing more reliable than a single-line dump.
    try:
        run_context_json=json.dumps(run_context, indent=2, default=str)
    except Exception as e:
        print(f"Agent: failed to serialize run_context: {e}")
        return None

    #call the LLM. This is the network/inference latency hot spot — typically 1-5s for flash.
    #we catch broad Exception here because LLM calls can fail in many ways:
    #network errors, rate limits, API key issues, malformed responses, content filter blocks, etc.
    #none of those should ever crash the executor's finally block.
    try:
        diagnosis: DiagnosticAgentOutput=await _diagnostic_chain.ainvoke({"pipeline_id":pipeline_id,"run_id":run_id,"error_type": error_type,
                                                                          "error_message": error_message,"run_context_json": run_context_json})
    except Exception as e:
        print(f"Agent: LLM call failed for run_id={run_id}: {e}")
        return None

    #persist the recommendation in a fresh session.
    #separate try/except from the LLM call so we can distinguish failure modes in logs —
    #"the model gave us a bad answer" is a very different problem from "we couldn't write to the DB"
    async with async_session() as session:
        try:
            recommendation=AgentRecommendation(tenant_id=tenant_id,pipeline_id=pipeline_id,run_id=run_id, failure_classification=diagnosis.failure_classification, 
                                               recommended_action=diagnosis.recommended_action,explanation=diagnosis.explanation,
                                                #status defaults to "pending" on the model — the tenant decides what to do with the recommendation (apply it, dismiss it). 
                                                #We never auto-set status to anything else from the agent.
                                            )
            session.add(recommendation)
            await session.commit()
            await session.refresh(recommendation)
            print(f"Agent: wrote recommendation_id={recommendation.id} for run_id={run_id}")
            return recommendation.id
        except SQLAlchemyError as e:
            await session.rollback()
            print(f"Agent: failed to persist recommendation for run_id={run_id}: {e}")
            return None