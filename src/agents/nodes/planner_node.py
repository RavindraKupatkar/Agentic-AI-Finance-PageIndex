"""
Planner Node - Query Decomposition for Complex Queries

Breaks down complex queries into executable sub-tasks.
"""

from typing import List
import json

from ..schemas.state import AgentState, PlanStep
from ...llm.groq_client import GroqClient
from ...observability.tracing import tracer


PLANNER_PROMPT = """You are a query planner for a finance RAG system.

Given a complex query, break it down into simple, executable steps.

Query: {question}

Create a plan with 2-5 steps. Each step should be one of:
- RETRIEVE: Search for specific information
- ANALYZE: Analyze retrieved information
- CALCULATE: Perform a calculation
- SYNTHESIZE: Combine information from previous steps
- VERIFY: Verify a claim or statement

Output as JSON array:
[
  {{"step_id": 1, "action": "RETRIEVE", "query": "...", "rationale": "..."}},
  ...
]

Only output the JSON array, nothing else."""


def create_plan(state: AgentState) -> dict:
    """
    Node: Create execution plan for complex queries.
    
    Input: question
    Output: plan, current_step
    """
    with tracer.start_as_current_span("planner_node") as span:
        question = state["question"]
        
        llm = GroqClient()
        response = llm.generate(
            PLANNER_PROMPT.format(question=question),
            model="llama-3.3-70b-versatile",  # Use powerful model for planning
            max_tokens=500
        )
        
        plan = _parse_plan(response)
        span.set_attribute("plan_steps", len(plan))
        
        return {
            "plan": [step.model_dump() for step in plan],
            "current_step": 0,
            "sub_results": []
        }


def _parse_plan(response: str) -> List[PlanStep]:
    """Parse JSON plan from LLM response"""
    try:
        # Try to extract JSON from response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        steps_data = json.loads(response)
        
        return [
            PlanStep(
                step_id=step.get("step_id", i + 1),
                action=step.get("action", "retrieve").lower(),
                query=step.get("query", ""),
                rationale=step.get("rationale", "")
            )
            for i, step in enumerate(steps_data)
        ]
    except (json.JSONDecodeError, KeyError):
        # Fallback: single retrieve step
        return [
            PlanStep(
                step_id=1,
                action="retrieve",
                query=response[:200],
                rationale="Fallback single-step plan"
            )
        ]
