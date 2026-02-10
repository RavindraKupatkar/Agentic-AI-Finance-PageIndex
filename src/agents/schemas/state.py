"""
LangGraph State Schemas - Core state definitions for agent graph

Uses TypedDict for LangGraph compatibility with Pydantic models for sub-components.
"""

from typing import TypedDict, Annotated, Sequence, Optional, Literal, List
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT STATE (TypedDict for LangGraph)
# ═══════════════════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    """
    Main state that flows through the LangGraph agent graph.
    
    This state is passed between nodes and accumulates information
    as the query is processed through the pipeline.
    """
    # ─────────────────────────────────────────────
    # Input
    # ─────────────────────────────────────────────
    question: str                                    # Original user question
    thread_id: str                                   # Conversation thread ID
    user_id: Optional[str]                          # User identifier
    
    # ─────────────────────────────────────────────
    # Messages (LangGraph reducer for appending)
    # ─────────────────────────────────────────────
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # ─────────────────────────────────────────────
    # Routing
    # ─────────────────────────────────────────────
    query_type: Literal["simple", "standard", "complex", "multi_hop"]
    complexity_score: float                          # 0-1 complexity score
    
    # ─────────────────────────────────────────────
    # Retrieval State
    # ─────────────────────────────────────────────
    query_embedding: Optional[List[float]]          # Question embedding vector
    retrieved_docs: List[dict]                      # Raw retrieved documents
    reranked_docs: List[dict]                       # After reranking
    
    # ─────────────────────────────────────────────
    # Planning State (for complex queries)
    # ─────────────────────────────────────────────
    plan: Optional[List[dict]]                      # Execution plan steps
    current_step: int                               # Current step index
    sub_results: List[dict]                         # Results from sub-queries
    
    # ─────────────────────────────────────────────
    # Evaluation State
    # ─────────────────────────────────────────────
    relevance_score: float                          # Retrieved docs relevance
    groundedness_score: float                       # Answer grounded in context
    needs_retry: bool                               # Should retry retrieval
    retry_count: int                                # Number of retries so far
    max_retries: int                                # Maximum allowed retries
    
    # ─────────────────────────────────────────────
    # Output State
    # ─────────────────────────────────────────────
    answer: Optional[str]                           # Generated answer
    sources: List[str]                              # Source citations
    confidence: float                               # Overall confidence score
    
    # ─────────────────────────────────────────────
    # Error Handling
    # ─────────────────────────────────────────────
    error: Optional[str]                            # Error message if any
    
    # ─────────────────────────────────────────────
    # Guardrails
    # ─────────────────────────────────────────────
    input_valid: bool                               # Input passed validation
    output_valid: bool                              # Output passed validation
    guardrail_warnings: List[str]                   # Any guardrail warnings


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS FOR SUB-COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

class RetrievedDocument(BaseModel):
    """Document retrieved from vector store"""
    id: str
    content: str = Field(..., description="Document text content")
    source: str = Field(..., description="Source filename")
    page: int = Field(default=0, description="Page number in source")
    chunk_index: int = Field(default=0, description="Chunk index")
    score: float = Field(..., ge=0, le=1, description="Similarity score")
    metadata: dict = Field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return self.model_dump()


class PlanStep(BaseModel):
    """Single step in query execution plan"""
    step_id: int = Field(..., description="Step number")
    action: Literal["retrieve", "analyze", "calculate", "synthesize", "verify"]
    query: str = Field(..., description="Sub-query for this step")
    rationale: str = Field(default="", description="Why this step is needed")
    completed: bool = Field(default=False)
    result: Optional[str] = Field(default=None)
    
    def to_dict(self) -> dict:
        return self.model_dump()


class ExecutionPlan(BaseModel):
    """Full execution plan for complex queries"""
    original_query: str
    steps: List[PlanStep]
    estimated_complexity: float = Field(ge=0, le=1)
    
    def get_current_step(self, index: int) -> Optional[PlanStep]:
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None


class CriticEvaluation(BaseModel):
    """Critic agent evaluation result"""
    relevance_score: float = Field(ge=0, le=1, description="Are docs relevant to query?")
    groundedness_score: float = Field(ge=0, le=1, description="Is answer grounded in docs?")
    completeness_score: float = Field(ge=0, le=1, description="Does answer fully address query?")
    needs_retry: bool = Field(default=False, description="Should retry retrieval?")
    feedback: str = Field(default="", description="Feedback for improvement")
    suggested_query: Optional[str] = Field(default=None, description="Refined query if retry needed")


class GeneratedResponse(BaseModel):
    """Final generated response"""
    answer: str
    sources: List[str]
    confidence: float = Field(ge=0, le=1)
    reasoning_trace: Optional[str] = Field(default=None)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_initial_state(
    question: str,
    thread_id: str = "default",
    user_id: Optional[str] = None
) -> AgentState:
    """Create initial state for a new query"""
    return AgentState(
        question=question,
        thread_id=thread_id,
        user_id=user_id,
        messages=[],
        query_type="standard",
        complexity_score=0.5,
        query_embedding=None,
        retrieved_docs=[],
        reranked_docs=[],
        plan=None,
        current_step=0,
        sub_results=[],
        relevance_score=0.0,
        groundedness_score=0.0,
        needs_retry=False,
        retry_count=0,
        max_retries=3,
        answer=None,
        sources=[],
        confidence=0.0,
        error=None,
        input_valid=True,
        output_valid=True,
        guardrail_warnings=[]
    )
