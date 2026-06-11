from pydantic import BaseModel, Field
from typing import Literal

#these are the structured outputs we expect the LLM to produce
#they are SEPARATE from the API-facing schemas in control_plane/app/schemas/agent_recommendations.py because the LLM output is an INTERNAL contract between Claude/Gemini and our code,
#while the API schema is the EXTERNAL contract between our API and tenants.
#even though the fields overlap right now, keeping them separate means we can evolve the LLM output (add reasoning fields, confidence scores, citations) 
# without affecting the public API shape, and vice versa.

#these Literals MUST match the design doc's failure categories and recovery actions exactly. Otherwise the agent will produce values that don't map to anything downstream
FailureClassification=Literal["network", "quota", "schema", "partial_load", "unknown"]
RecommendedAction=Literal["retry", "retry_with_backoff", "schema_evolution", "replay_from_raw", "escalate", "pause_schedule"]

class DiagnosticAgentOutput(BaseModel):
    """The structured response we ask Gemini to produce when diagnosing a failed pipeline run.

    We use Pydantic + LangChain's with_structured_output() to FORCE the LLM to return JSON
    that matches this shape. The LLM cannot return free-form text — it must populate these fields.
    This is critical because:
    1. Downstream code writes these values straight into typed DB columns
    2. The eval harness later needs deterministic field access for accuracy metrics
    3. It eliminates a whole class of parsing bugs we'd otherwise have to handle
    """

    failure_classification: FailureClassification=Field(description="The category of failure based on the error type, error message, and step attempts.")
    recommended_action: RecommendedAction=Field(description="The specific recovery action to take. Must be one of the allowed values.")
    explanation: str=Field(description="A clear explanation of what went wrong and why this recommendation was chosen. "
                    "Reference specific evidence from the run_context (step that failed, error type, retry attempts). "
                    "This will be shown to a human operator, so be concise but specific.",min_length=20,  #force the model to actually explain itself, not just say "network issue"
                    max_length=2000  #cap it so we don't blow up the DB column or run up token costs
    )