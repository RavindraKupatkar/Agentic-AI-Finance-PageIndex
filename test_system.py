import asyncio
import os
import time
import json
from pathlib import Path
from src.core.config import settings

# Output report file
REPORT_FILE = "comprehensive_test_report.md"
report = []

def log(category: str, detail: str, success: bool = True):
    status_emoji = "✅ PASS" if success else "❌ FAIL"
    status_text = "PASS" if success else "FAIL"
    report.append(f"| {category} | {status_emoji} | {detail} |")
    print(f"[{status_text}] {category}: {detail}")

async def test_databases():
    print("\n--- Testing Databases ---")
    try:
        from src.observability.telemetry import get_telemetry_service
        from src.observability.conversations import get_conversation_service
        
        telemetry = await get_telemetry_service()
        conversations = await get_conversation_service()
        
        counts = await telemetry.get_table_counts()
        log("Database", f"Telemetry tables initialized. Counts: {counts}", True)
        
        # Test conversation adding
        conv_id = await conversations.create_conversation("Test DB Init")
        msg_id = await conversations.add_message(conv_id, "user", "Hello DB", confidence=0.99)
        if msg_id != -1:
            log("Database", f"Conversation CRUD successful (Conv ID: {conv_id}, Msg ID: {msg_id})", True)
        else:
            log("Database", "Conversation message insertion failed", False)
            
        await conversations.delete_conversation(conv_id)
        
    except Exception as e:
        log("Database", f"Initialization Error: {e}", False)

async def test_schemas_and_state():
    print("\n--- Testing Agent State and Injected State ---")
    try:
        from src.agents.schemas.state import create_initial_query_state
        from src.agents.schemas.injected import get_deps, create_deps
        
        deps_obj = await create_deps("test_query_schemas")
        
        # Test Query State Initialization
        state = create_initial_query_state("What is the revenue?", "test_thread", "user_123")
        if state["question"] == "What is the revenue?" and state["thread_id"] == "test_thread":
            log("Schemas", "Query State initialized correctly", True)
        else:
            log("Schemas", "Query State initialization failed", False)
            
        # Test Deps Injection
        config = {"configurable": {"thread_id": "test_thread", "deps": deps_obj}}
        deps = get_deps(config)
        if deps.telemetry and deps.llm:
            log("Schemas", "InjectedState/Deps resolved plugins successfully", True)
        else:
            log("Schemas", "InjectedState failed to load plugins", False)
            
    except Exception as e:
        log("Schemas", f"State Error: {e}", False)

async def test_nodes():
    print("\n--- Testing LangGraph Nodes (Unit tests) ---")
    try:
        from src.agents.schemas.state import create_initial_query_state
        from src.agents.nodes.router_node import classify_query
        from src.agents.nodes.guardrail_node import validate_input
        from src.agents.schemas.injected import create_deps
        from dotenv import load_dotenv
        
        load_dotenv() # Ensure env vars are loaded for LLM
        deps_obj = await create_deps("test_query_nodes")
        config = {"configurable": {"thread_id": "test_nodes", "deps": deps_obj}}
        
        # Test Guardrail on empty input
        state_empty = create_initial_query_state("", "test_nodes")
        res_empty = await validate_input(state_empty, config)
        if not res_empty["is_valid"]:
            log("Nodes:Guardrail", "Empty query correctly flagged as invalid", True)
        else:
            log("Nodes:Guardrail", "Failed to flag empty query", False)

        # Test Guardrail on valid input
        state_valid = create_initial_query_state("Explain the Q3 financial results.", "test_nodes")
        res_valid = await validate_input(state_valid, config)
        if res_valid["is_valid"]:
            log("Nodes:Guardrail", "Valid query passed guardrail", True)
        else:
            log("Nodes:Guardrail", "Failed on valid query", False)
            
        # Test Router
        state_route = create_initial_query_state("Summarize the document", "test_nodes")
        res_route = await classify_query(state_route, config)
        if "query_type" in res_route:
            log("Nodes:Router", f"Classified query type as: {res_route['query_type']}", True)
        else:
            log("Nodes:Router", "Router failed to classify query", False)
            
    except Exception as e:
        log("Nodes", f"Node execution error: {e}", False)

async def main():
    report.append("# Auto-Generated Test Report\n")
    report.append("| Category | Status | Details |")
    report.append("|---|---|---|")
    
    await test_databases()
    await test_schemas_and_state()
    await test_nodes()
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print(f"\nReport written to {REPORT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
