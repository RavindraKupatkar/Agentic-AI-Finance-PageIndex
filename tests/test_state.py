"""
Test Agent State and Schemas
"""

import pytest
from src.agents.schemas.state import (
    AgentState,
    RetrievedDocument,
    PlanStep,
    ExecutionPlan,
    CriticEvaluation,
    create_initial_state
)


def test_create_initial_state():
    """Test creating initial agent state"""
    state = create_initial_state(
        question="What is the revenue?",
        thread_id="test-123"
    )
    
    assert state["question"] == "What is the revenue?"
    assert state["thread_id"] == "test-123"
    assert state["query_type"] == "standard"
    assert state["retry_count"] == 0
    assert state["messages"] == []


def test_retrieved_document():
    """Test RetrievedDocument model"""
    doc = RetrievedDocument(
        id="doc-1",
        content="Test content",
        source="test.pdf",
        page=1,
        score=0.85
    )
    
    assert doc.content == "Test content"
    assert doc.score == 0.85
    assert doc.to_dict()["source"] == "test.pdf"


def test_plan_step():
    """Test PlanStep model"""
    step = PlanStep(
        step_id=1,
        action="retrieve",
        query="Find revenue data"
    )
    
    assert step.step_id == 1
    assert step.action == "retrieve"
    assert step.completed is False


def test_critic_evaluation():
    """Test CriticEvaluation model"""
    eval = CriticEvaluation(
        relevance_score=0.8,
        groundedness_score=0.75,
        completeness_score=0.9,
        needs_retry=False,
        feedback="Good retrieval"
    )
    
    assert eval.relevance_score == 0.8
    assert eval.needs_retry is False
