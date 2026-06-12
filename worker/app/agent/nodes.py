from langchain_google_genai import ChatGoogleGenerativeAI
from shared.config import GOOGLE_API_KEY, GEMINI_MODEL
from worker.app.agent.state import (DiagnosticState,log_analysis_sentinel,classification_sentinel,recovery_plan_sentinel,)
from worker.app.agent.schemas import (LogAnalysisOutput,ClassificationOutput,RecoveryPlanOutput,)
from worker.app.agent.prompts import (log_analysis_prompt,classification_prompt,recovery_planning_prompt,render_retrieved_context,)

#one shared LLM client at module load, same reasoning as the legacy diagnostic_agent.py:
#the client is stateless and thread-safe, so reusing the same instance avoids re-authentication overhead on every invocation. temperature=0 keeps outputs deterministic for a given input,
#which matters for the eval harness later. All three nodes use the SAME model per our earlier decision (gemini-2.5-flash). If we ever want to specialize like heavier model for classification, 
# faster model for log analysis, this is the one spot to change.

_llm=ChatGoogleGenerativeAI(model=GEMINI_MODEL,google_api_key=GOOGLE_API_KEY,temperature=0)

#each node gets its own structured chain, built once at module load.
#with_structured_output() per node means each LLM call is constrained to produce JSON matching
#its specific output schema — the model literally cannot return the wrong shape. This is
#the reliability win that makes multi-node graphs viable: each call has a tight constraint
#instead of one big call trying to populate everything.

_log_analysis_chain=log_analysis_prompt|_llm.with_structured_output(LogAnalysisOutput)
_classification_chain=classification_prompt|_llm.with_structured_output(ClassificationOutput)
_recovery_planning_chain=recovery_planning_prompt|_llm.with_structured_output(RecoveryPlanOutput)


# ============================================================================
# Node functions.
#
# LangGraph contract for each node:
#   - Signature: async def x_node(state: DiagnosticState) -> dict
#   - The returned dict is MERGED into state by LangGraph. Each node returns
#     a dict containing only the single field it's responsible for populating.
#   - Exceptions inside a node WILL propagate and crash the graph. We don't
#     want that — graceful degradation means catching here and returning the
#     sentinel. Downstream nodes get a well-typed input either way.
#
# The print statements are intentional. They give us visibility during local
# dev — being able to see at a glance which node succeeded vs which fell back
# to a sentinel is what makes multi-node debugging tractable. They can become
# proper structured logs later.
# ============================================================================


async def log_analysis_node(state: DiagnosticState) -> dict:
    """First node in the graph. Describes what happened — does not classify or recommend.

    Reads: error_type, error_message, run_context_json, pipeline_id, run_id (from state inputs)
    Writes: log_analysis (a LogAnalysisOutput or its sentinel)
    """
    run_id=state["run_id"]

    try:
        result: LogAnalysisOutput=await _log_analysis_chain.ainvoke({
            "pipeline_id": state["pipeline_id"],
            "run_id": run_id,
            "error_type": state["error_type"],
            "error_message": state["error_message"],
            "run_context_json": state["run_context_json"],
        })
        print(f"Agent[log_analysis]: completed for run_id={run_id} — failed_step={result.failed_step}")
        return {"log_analysis": result}
    
    except Exception as e:
        #we catch broad Exception because LLM calls fail in many shapes — network errors,
        #rate limits, content filter blocks, malformed structured outputs, API key issues.
        #none of those should crash the graph. The sentinel keeps the run_context flowing
        #to downstream nodes so they can still produce something useful (likely an escalate).
        print(f"Agent[log_analysis]: failed for run_id={run_id}, using sentinel: {e}")
        return {"log_analysis": log_analysis_sentinel(state["error_type"], state["error_message"])}


async def classification_node(state: DiagnosticState) -> dict:
    """Second node. Assigns a category + confidence based on log analysis and raw error metadata.

    Reads: error_type, error_message, log_analysis (from previous node)
    Writes: classification (a ClassificationOutput or its sentinel)
    """
    run_id=state["run_id"]
    log_analysis=state["log_analysis"]

    #if log_analysis is somehow None here, something is structurally wrong with the graph wiring,
    #not just an LLM hiccup. We still degrade gracefully rather than crash — return the sentinel
    #directly without even calling the LLM, since there's nothing to feed it.
    if log_analysis is None:
        print(f"Agent[classification]: log_analysis is None for run_id={run_id}, using sentinel")
        return {"classification": classification_sentinel()}

    try:
        result: ClassificationOutput=await _classification_chain.ainvoke({
            "error_type": state["error_type"],
            "error_message": state["error_message"],
            "failed_step": log_analysis.failed_step,
            "attempt_pattern": log_analysis.attempt_pattern,
            "error_interpretation": log_analysis.error_interpretation,
            #notable_signals is a list — Python's str() rendering of a list is readable enough
            #for the prompt ('[\"log_analysis_failed\"]'), and the LLM handles it fine.
            "notable_signals": log_analysis.notable_signals,
        })
        print(f"Agent[classification]: completed for run_id={run_id} — {result.failure_classification} (confidence={result.confidence:.2f})")
        return {"classification": result}

    except Exception as e:
        print(f"Agent[classification]: failed for run_id={run_id}, using sentinel: {e}")
        return {"classification": classification_sentinel()}


async def recovery_planning_node(state: DiagnosticState) -> dict:
    """Third node. Recommends a recovery action based on everything upstream.

    Reads: error_type, error_message, log_analysis, classification (from prior nodes)
    Writes: recovery_plan (a RecoveryPlanOutput or its sentinel)
    """
    run_id=state["run_id"]
    log_analysis=state["log_analysis"]
    classification=state["classification"]

    #same defensive None check as classification_node — if either upstream output is missing,
    #the graph wiring is broken, so we sentinel-out without burning an LLM call.
    if log_analysis is None or classification is None:
        print(f"Agent[recovery_planning]: upstream output missing for run_id={run_id}, using sentinel")
        return {"recovery_plan": recovery_plan_sentinel()}

    try:
        retrieved_context_block=render_retrieved_context(state["retrieved_context"])
        result: RecoveryPlanOutput=await _recovery_planning_chain.ainvoke({
            "error_type": state["error_type"],
            "error_message": state["error_message"],
            "failed_step": log_analysis.failed_step,
            "attempt_pattern": log_analysis.attempt_pattern,
            "error_interpretation": log_analysis.error_interpretation,
            "notable_signals": log_analysis.notable_signals,
            "failure_classification": classification.failure_classification,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning,
            "retrieved_context_block": retrieved_context_block,
        })
        print(f"Agent[recovery_planning]: completed for run_id={run_id} — recommended_action={result.recommended_action}")
        return {"recovery_plan": result}

    except Exception as e:
        print(f"Agent[recovery_planning]: failed for run_id={run_id}, using sentinel: {e}")
        return {"recovery_plan": recovery_plan_sentinel()}