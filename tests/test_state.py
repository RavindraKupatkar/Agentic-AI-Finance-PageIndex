"""
Tests for Agent State Schemas — PageIndex Finance RAG

Tests state factory functions and Pydantic sub-component models:
- create_initial_query_state defaults and population
- create_initial_ingestion_state defaults
- PlanStep creation and defaults
- CriticEvaluation creation and validation
- PageSource creation
"""

import pytest
from src.agents.schemas.state import (
    PageIndexQueryState,
    PageIndexIngestionState,
    PlanStep,
    ExecutionPlan,
    CriticEvaluation,
    GeneratedResponse,
    PageSource,
    create_initial_query_state,
    create_initial_ingestion_state,
)


# ──────────────────────────────────────────────────────────────
# Query state factory
# ──────────────────────────────────────────────────────────────


def test_create_initial_query_state():
    """Test creating initial PageIndex query state."""
    state = create_initial_query_state(
        question="What is the revenue?",
        thread_id="test-123",
    )

    assert state["question"] == "What is the revenue?"
    assert state["thread_id"] == "test-123"
    assert state["query_type"] == "standard"
    assert state["retry_count"] == 0
    assert state["messages"] == []
    assert state["tree_structures"] == {}
    assert state["relevant_pages"] == {}
    assert state["needs_retry"] is False
    assert state["answer"] is None
    assert state["error"] is None


def test_create_initial_query_state_with_scoped_docs():
    """Test initial state with scoped_doc_ids."""
    state = create_initial_query_state(
        question="Summarize this document",
        thread_id="t-456",
        scoped_doc_ids=["doc-a", "doc-b"],
    )
    assert state["scoped_doc_ids"] == ["doc-a", "doc-b"]


# ──────────────────────────────────────────────────────────────
# Ingestion state factory
# ──────────────────────────────────────────────────────────────


def test_create_initial_ingestion_state():
    """Test creating initial PageIndex ingestion state."""
    state = create_initial_ingestion_state(
        pdf_path="/data/pdfs/report.pdf",
        filename="report.pdf",
    )
    assert state["pdf_path"] == "/data/pdfs/report.pdf"
    assert state["filename"] == "report.pdf"
    assert state["is_valid"] is False
    assert state["total_pages"] == 0
    assert state["stored"] is False


def test_create_initial_ingestion_state_filename_from_path():
    """Test that filename is extracted from path when not provided."""
    state = create_initial_ingestion_state(
        pdf_path="/some/path/my_doc.pdf",
    )
    assert state["filename"] == "my_doc.pdf"


# ──────────────────────────────────────────────────────────────
# Pydantic sub-component models
# ──────────────────────────────────────────────────────────────


def test_plan_step():
    """Test PlanStep model."""
    step = PlanStep(
        step_id=1,
        action="retrieve",
        query="Find revenue data",
    )

    assert step.step_id == 1
    assert step.action == "retrieve"
    assert step.completed is False
    assert step.result is None


def test_plan_step_to_dict():
    """Test PlanStep serialization."""
    step = PlanStep(
        step_id=2,
        action="analyze",
        query="Compare Q3 vs Q4",
        rationale="Need quarter comparison",
        completed=True,
        result="Q4 up 12%",
    )
    d = step.to_dict()
    assert d["step_id"] == 2
    assert d["completed"] is True
    assert d["result"] == "Q4 up 12%"


def test_critic_evaluation():
    """Test CriticEvaluation model."""
    evaluation = CriticEvaluation(
        relevance_score=0.8,
        groundedness_score=0.75,
        completeness_score=0.9,
        needs_retry=False,
        feedback="Good retrieval",
    )

    assert evaluation.relevance_score == 0.8
    assert evaluation.needs_retry is False
    assert evaluation.suggested_query is None


def test_execution_plan_get_current_step():
    """Test ExecutionPlan.get_current_step."""
    plan = ExecutionPlan(
        original_query="What is the debt?",
        steps=[
            PlanStep(step_id=1, action="retrieve", query="Find debt data"),
            PlanStep(step_id=2, action="analyze", query="Analyze debt breakdown"),
        ],
        estimated_complexity=0.6,
    )
    assert plan.get_current_step(0).step_id == 1
    assert plan.get_current_step(1).step_id == 2
    assert plan.get_current_step(5) is None


def test_page_source():
    """Test PageSource model."""
    source = PageSource(
        doc_id="doc-abc",
        filename="report.pdf",
        page_number=42,
        section_title="Balance Sheet",
    )
    assert source.doc_id == "doc-abc"
    assert source.page_number == 42
