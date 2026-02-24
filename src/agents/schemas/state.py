"""
LangGraph State Schemas — PageIndex Finance RAG

Defines the TypedDict states for the LangGraph agent graphs:
    - PageIndexQueryState:     Data flowing through the query pipeline
    - PageIndexIngestionState: Data flowing through the ingestion pipeline

Uses TypedDict for LangGraph compatibility. Pydantic models are used
for validated sub-components (CriticEvaluation, GeneratedResponse, etc.).

Design decisions:
    - InjectedState pattern: heavy services (TreeStore, GroqClient,
      TelemetryService) are injected via RunnableConfig, NOT stored
      in state. This keeps state lightweight and serializable.
    - States only contain data, never service references.
"""

from typing import TypedDict, Annotated, Optional, Literal, List
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY STATE — Data flowing through the PageIndex query graph
# ═══════════════════════════════════════════════════════════════════════════════


class PageIndexQueryState(TypedDict):
    """
    State for the PageIndex query pipeline.

    This replaces the old vector-based AgentState. All vector-specific
    fields (embeddings, reranked_docs) are removed and replaced with
    PageIndex-specific fields (tree_structures, relevant_pages, etc.).

    Services (TreeStore, GroqClient, TelemetryService) are NOT stored
    here — they are injected via RunnableConfig using InjectedState.
    """

    # ─── Input ─────────────────────────────────────────
    question: str                                       # Original user question
    thread_id: str                                      # Conversation thread ID
    user_id: Optional[str]                              # User identifier

    # ─── Telemetry ─────────────────────────────────────
    query_id: Optional[str]                             # Telemetry query UUID

    # ─── Messages ──────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ─── Routing ───────────────────────────────────────
    query_type: Literal["simple", "standard", "complex", "multi_hop"]
    complexity_score: float                             # 0.0 - 1.0

    # ─── Planning (complex queries) ────────────────────
    plan: Optional[list[dict]]                          # Execution plan steps
    current_step: int                                   # Current step index
    sub_results: list[dict]                             # Results from sub-queries

    # ─── Document Selection ────────────────────────────
    available_docs: list[dict]                          # All indexed doc metadata
    selected_doc_ids: list[str]                         # Docs chosen for search

    # ─── Tree Search (replaces vector retrieval) ───────
    tree_structures: dict                               # {doc_id: DocumentTree dict}
    relevant_pages: dict                                # {doc_id: [page_numbers]}
    reasoning_trace: list[dict]                         # Step-by-step LLM reasoning
    search_confidence: float                            # Tree search confidence 0-1

    # ─── Page Retrieval (replaces chunk retrieval) ─────
    page_contents: list[dict]                           # [{doc_id, page_num, text}]
    context: str                                        # Merged context for generator

    # ─── Evaluation ────────────────────────────────────
    relevance_score: float                              # Retrieved content relevance
    groundedness_score: float                           # Answer grounded in context
    needs_retry: bool                                   # Should retry tree search
    retry_count: int                                    # Number of retries so far
    max_retries: int                                    # Maximum allowed retries
    refined_query: Optional[str]                        # Critic's suggested refinement

    # ─── Output ────────────────────────────────────────
    answer: Optional[str]                               # Generated answer
    sources: list[dict]                                 # [{doc_id, page_num, title}]
    confidence: float                                   # Overall confidence score

    # ─── Guardrails ────────────────────────────────────
    input_valid: bool                                   # Input passed validation
    output_valid: bool                                  # Output passed validation
    guardrail_warnings: list[str]                       # Any warnings

    # ─── Error Handling ────────────────────────────────
    error: Optional[str]                                # Error message if any


# ═══════════════════════════════════════════════════════════════════════════════
# INGESTION STATE — Data flowing through the PageIndex ingestion graph
# ═══════════════════════════════════════════════════════════════════════════════


class PageIndexIngestionState(TypedDict):
    """
    State for the PageIndex document ingestion pipeline.

    Replaces the old chunking → embedding → vector store flow
    with tree generation and storage.
    """

    # ─── Input ─────────────────────────────────────────
    pdf_path: str                                       # Absolute path to PDF
    filename: str                                       # Original filename

    # ─── Telemetry ─────────────────────────────────────
    query_id: Optional[str]                             # Telemetry tracking ID

    # ─── Validation ────────────────────────────────────
    is_valid: bool                                      # File passed validation
    validation_error: Optional[str]                     # Error if invalid

    # ─── PDF Metadata ──────────────────────────────────
    total_pages: int                                    # Total page count
    title: str                                          # Document title
    existing_toc: Optional[list[dict]]                  # PDF's built-in TOC
    page_texts: list[str]                               # Text per page

    # ─── Tree Generation ───────────────────────────────
    doc_id: str                                         # Generated document ID
    tree_structure: Optional[dict]                      # Generated tree JSON
    tree_depth: int                                     # Max depth of tree
    node_count: int                                     # Total nodes in tree

    # ─── Storage ───────────────────────────────────────
    tree_path: str                                      # Path to saved JSON
    stored: bool                                        # Successfully stored

    # ─── Error Handling ────────────────────────────────
    error: Optional[str]                                # Error message if any


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS FOR SUB-COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════


class CriticEvaluation(BaseModel):
    """Critic agent evaluation of retrieved page content."""
    relevance_score: float = Field(ge=0, le=1, description="Are pages relevant to query?")
    groundedness_score: float = Field(ge=0, le=1, description="Is answer grounded in pages?")
    completeness_score: float = Field(ge=0, le=1, description="Does content fully address query?")
    needs_retry: bool = Field(default=False, description="Should retry tree search?")
    feedback: str = Field(default="", description="Feedback for improvement")
    suggested_query: Optional[str] = Field(
        default=None, description="Refined query if retry needed"
    )


class PlanStep(BaseModel):
    """Single step in query execution plan."""
    step_id: int = Field(..., description="Step number")
    action: Literal["retrieve", "analyze", "calculate", "synthesize", "verify"]
    query: str = Field(..., description="Sub-query for this step")
    rationale: str = Field(default="", description="Why this step is needed")
    completed: bool = Field(default=False)
    result: Optional[str] = Field(default=None)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return self.model_dump()


class ExecutionPlan(BaseModel):
    """Full execution plan for complex queries."""
    original_query: str
    steps: List[PlanStep]
    estimated_complexity: float = Field(ge=0, le=1)

    def get_current_step(self, index: int) -> Optional[PlanStep]:
        """Get the step at the given index.

        Args:
            index: Step index.

        Returns:
            PlanStep if valid index, None otherwise.
        """
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None


class GeneratedResponse(BaseModel):
    """Final generated response from the generator node."""
    answer: str
    sources: List[dict] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reasoning_trace: Optional[str] = Field(default=None)


class PageSource(BaseModel):
    """A source citation with page-level traceability."""
    doc_id: str = Field(..., description="Document identifier")
    filename: str = Field(default="", description="Original PDF filename")
    page_number: int = Field(..., description="1-indexed page number")
    section_title: str = Field(default="", description="Section title from tree node")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def create_initial_query_state(
    question: str,
    thread_id: str = "default",
    user_id: Optional[str] = None,
    query_id: Optional[str] = None,
) -> PageIndexQueryState:
    """
    Create initial state for a new PageIndex query.

    Args:
        question: The user's question.
        thread_id: Conversation thread ID for memory.
        user_id: Optional user identifier.
        query_id: Telemetry query UUID (assigned by TelemetryService).

    Returns:
        Initialized PageIndexQueryState with safe defaults.
    """
    return PageIndexQueryState(
        question=question,
        thread_id=thread_id,
        user_id=user_id,
        query_id=query_id,
        messages=[],
        query_type="standard",
        complexity_score=0.5,
        plan=None,
        current_step=0,
        sub_results=[],
        available_docs=[],
        selected_doc_ids=[],
        tree_structures={},
        relevant_pages={},
        reasoning_trace=[],
        search_confidence=0.0,
        page_contents=[],
        context="",
        relevance_score=0.0,
        groundedness_score=0.0,
        needs_retry=False,
        retry_count=0,
        max_retries=2,
        refined_query=None,
        answer=None,
        sources=[],
        confidence=0.0,
        input_valid=True,
        output_valid=True,
        guardrail_warnings=[],
        error=None,
    )


def create_initial_ingestion_state(
    pdf_path: str,
    filename: Optional[str] = None,
    query_id: Optional[str] = None,
) -> PageIndexIngestionState:
    """
    Create initial state for document ingestion.

    Args:
        pdf_path: Absolute path to the PDF file.
        filename: Original filename (extracted from path if None).
        query_id: Telemetry tracking ID.

    Returns:
        Initialized PageIndexIngestionState with safe defaults.
    """
    if filename is None:
        filename = pdf_path.replace("\\", "/").split("/")[-1]

    return PageIndexIngestionState(
        pdf_path=pdf_path,
        filename=filename,
        query_id=query_id,
        is_valid=False,
        validation_error=None,
        total_pages=0,
        title="",
        existing_toc=None,
        page_texts=[],
        doc_id="",
        tree_structure=None,
        tree_depth=0,
        node_count=0,
        tree_path="",
        stored=False,
        error=None,
    )
