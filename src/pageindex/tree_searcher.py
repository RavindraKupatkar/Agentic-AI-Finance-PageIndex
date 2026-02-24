"""
Tree Searcher — LLM Reasoning-based Tree Search

The core innovation of PageIndex: uses LLM reasoning to navigate the
hierarchical tree index and find the most relevant document sections.

Replaces vector similarity search from traditional RAG:
    Vector Search + BM25 + Reranker → LLM Tree Search (Reasoning)

Search process:
    1. Read root node summaries
    2. LLM reasons: "Which child node likely contains the answer?"
    3. Drill into selected nodes, read their children
    4. Repeat until reaching leaf nodes (exact pages)
    5. Return relevant page ranges + reasoning trace

Design decisions:
    - Async throughout (agenerate for LLM calls)
    - Accepts GroqClient and TelemetryService via dependency injection
    - Breadth-first evaluation: at each level, LLM evaluates all siblings
    - Configurable search breadth limits how many branches to explore
    - Full reasoning trace for explainability and debugging
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .tree_generator import DocumentTree, TreeNode
from ..core.config import settings
from ..observability.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from ..llm.groq_client import GroqClient
    from ..observability.telemetry import TelemetryService


# ──────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────


@dataclass
class SearchStep:
    """
    A single step in the tree search reasoning trace.

    Records the LLM's decision at each tree level for
    explainability and audit trails.

    Attributes:
        level: Depth level in the tree.
        node_id: ID of the node being evaluated.
        node_title: Title of the node.
        reasoning: LLM's reasoning for selecting/skipping this node.
        selected: Whether this node was selected for deeper search.
        page_range: Page range of this node (start_page-end_page).
    """

    level: int
    node_id: str
    node_title: str
    reasoning: str
    selected: bool
    page_range: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary for state storage."""
        return {
            "level": self.level,
            "node_id": self.node_id,
            "node_title": self.node_title,
            "reasoning": self.reasoning,
            "selected": self.selected,
            "page_range": self.page_range,
        }


@dataclass
class SearchResult:
    """
    Result from a tree search operation.

    Attributes:
        relevant_pages: List of page numbers identified as relevant.
        relevant_nodes: TreeNode objects that matched the query.
        reasoning_trace: Step-by-step trace of LLM reasoning.
        confidence: Confidence score from the search (0.0-1.0).
        total_tokens_used: Total tokens consumed during search.
    """

    relevant_pages: list[int] = field(default_factory=list)
    relevant_nodes: list[TreeNode] = field(default_factory=list)
    reasoning_trace: list[SearchStep] = field(default_factory=list)
    confidence: float = 0.0
    total_tokens_used: int = 0

    def to_dict(self) -> dict:
        """Serialize to dictionary for state storage."""
        return {
            "relevant_pages": self.relevant_pages,
            "relevant_nodes": [n.to_dict() for n in self.relevant_nodes],
            "reasoning_trace": [s.to_dict() for s in self.reasoning_trace],
            "confidence": self.confidence,
            "total_tokens_used": self.total_tokens_used,
        }


# ──────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────

_EVALUATE_NODES_PROMPT = """You are a document navigation expert. Given a user's question, evaluate which document sections are most likely to contain the answer.

Question: {question}

{context_section}

Available sections at this level:
{node_list}

Evaluate EACH section and decide if it likely contains information relevant to the question.

Output a JSON array with one object per section, in the SAME ORDER as listed above:
[
    {{
        "node_id": "section_id",
        "selected": true,
        "reasoning": "Brief explanation of why this section is or isn't relevant",
        "confidence": 0.0
    }}
]

Rules:
1. Select at most {max_selections} sections (prioritize the most relevant)
2. A section is relevant if its summary suggests it contains information needed to answer the question
3. If unsure, include the section (better to retrieve too broadly than miss relevant content)
4. confidence is 0.0-1.0 indicating how sure you are this section is relevant
5. Output ONLY valid JSON, no markdown fences"""


# ──────────────────────────────────────────────────────────────
# Core Searcher
# ──────────────────────────────────────────────────────────────


class TreeSearcher:
    """
    LLM-based reasoning tree search for document retrieval.

    Navigates the PageIndex tree top-down using LLM reasoning,
    simulating how a human expert would find information in a
    complex document.

    Example:
        Query: "What was the total debt in 2024?"
        Reasoning:
            → "This is a debt question"
            → "Check Financial Statements section"
            → "Check Balance Sheet (p.23-30)"
            → "Also check Notes to Financial Statements"
        Result: Pages 23-30, 66-72

    Args:
        llm: GroqClient for LLM calls. Injected via InjectedState.
        telemetry: TelemetryService for logging. Injected via InjectedState.
        query_id: Telemetry query ID for tracking this operation.
    """

    def __init__(
        self,
        llm: GroqClient,
        telemetry: Optional[TelemetryService] = None,
        query_id: Optional[str] = None,
    ) -> None:
        """
        Initialize TreeSearcher with injected dependencies.

        Args:
            llm: GroqClient for LLM generation.
            telemetry: TelemetryService for observability.
            query_id: Current operation's telemetry tracking ID.
        """
        self._llm = llm
        self._telemetry = telemetry
        self._query_id = query_id
        self._model: str = settings.tree_search_model
        self._max_breadth: int = settings.tree_search_breadth
        self._max_depth: int = settings.max_tree_depth

        logger.info(
            "tree_searcher.initialized",
            model=self._model,
            max_breadth=self._max_breadth,
            max_depth=self._max_depth,
        )

    async def search(
        self,
        query: str,
        tree: DocumentTree,
        max_depth: Optional[int] = None,
    ) -> SearchResult:
        """
        Search the document tree for sections relevant to the query.

        Performs a top-down breadth-limited search through the tree:
        1. At each level, LLM evaluates all sibling nodes
        2. Selected nodes are drilled into (their children evaluated)
        3. Process repeats until leaf nodes or max_depth
        4. Leaf nodes' page ranges become the search results

        Args:
            query: User's question or search query.
            tree: The DocumentTree to search through.
            max_depth: Maximum tree depth to traverse (None = use config).

        Returns:
            SearchResult with relevant pages, nodes, and reasoning trace.

        Raises:
            ValueError: If the tree has no root nodes.
        """
        start_time = time.time()
        effective_depth = max_depth or self._max_depth

        if not tree.root_nodes:
            raise ValueError(
                f"Document tree '{tree.doc_id}' has no root nodes. "
                f"Cannot perform tree search."
            )

        logger.info(
            "tree_searcher.search.start",
            query=query[:100],
            doc_id=tree.doc_id,
            root_nodes=len(tree.root_nodes),
            max_depth=effective_depth,
        )

        reasoning_trace: list[SearchStep] = []
        relevant_nodes: list[TreeNode] = []

        # Start search from root nodes
        current_nodes = tree.root_nodes
        context_path: list[str] = []  # Track the path taken for context

        for depth in range(effective_depth):
            if not current_nodes:
                break

            logger.debug(
                "tree_searcher.evaluating_level",
                depth=depth,
                candidates=len(current_nodes),
            )

            # LLM evaluates which nodes are relevant at this level
            evaluations = await self._evaluate_nodes(
                query=query,
                nodes=current_nodes,
                context=" → ".join(context_path) if context_path else "",
            )

            # Collect selected nodes and record reasoning
            selected_for_drill: list[TreeNode] = []

            for node, reasoning, is_selected, confidence in evaluations:
                step = SearchStep(
                    level=depth,
                    node_id=node.node_id,
                    node_title=node.title,
                    reasoning=reasoning,
                    selected=is_selected,
                    page_range=f"p.{node.start_page}-{node.end_page}",
                )
                reasoning_trace.append(step)

                if is_selected:
                    if node.children:
                        # Has children → drill deeper
                        selected_for_drill.append(node)
                        context_path.append(node.title)
                    else:
                        # Leaf node → these are our results
                        relevant_nodes.append(node)

            # If no nodes were selected, stop searching
            if not selected_for_drill and not relevant_nodes:
                logger.info(
                    "tree_searcher.no_relevant_nodes",
                    depth=depth,
                )
                break

            # Gather all children of selected nodes for next iteration
            next_level_nodes: list[TreeNode] = []
            for selected_node in selected_for_drill:
                next_level_nodes.extend(selected_node.children)

            # If selected nodes have no children, they are leaf nodes
            for selected_node in selected_for_drill:
                if not selected_node.children:
                    relevant_nodes.append(selected_node)

            current_nodes = next_level_nodes

            # If we're at max depth but still have unexplored nodes,
            # treat remaining selected nodes as relevant
            if depth == effective_depth - 1 and next_level_nodes:
                for node in next_level_nodes:
                    relevant_nodes.append(node)

        # Collect all relevant pages from identified nodes
        relevant_pages = self._collect_pages(relevant_nodes)

        # Calculate overall confidence
        confidence = self._calculate_confidence(reasoning_trace, relevant_nodes)

        elapsed_ms = (time.time() - start_time) * 1000

        result = SearchResult(
            relevant_pages=sorted(set(relevant_pages)),
            relevant_nodes=relevant_nodes,
            reasoning_trace=reasoning_trace,
            confidence=confidence,
        )

        logger.info(
            "tree_searcher.search.complete",
            doc_id=tree.doc_id,
            relevant_pages=len(result.relevant_pages),
            relevant_nodes=len(relevant_nodes),
            trace_steps=len(reasoning_trace),
            confidence=round(confidence, 3),
            elapsed_ms=round(elapsed_ms, 1),
        )

        return result

    # ─── Node Evaluation ───────────────────────────────

    async def _evaluate_nodes(
        self,
        query: str,
        nodes: list[TreeNode],
        context: str = "",
    ) -> list[tuple[TreeNode, str, bool, float]]:
        """
        Use LLM to evaluate which sibling nodes are relevant to the query.

        Builds a structured prompt listing all node summaries and asks the
        LLM to reason about which ones likely contain relevant information.

        Args:
            query: User's question.
            nodes: List of sibling nodes to evaluate.
            context: Path context from parent selections.

        Returns:
            List of (node, reasoning, is_selected, confidence) tuples.
        """
        # Build node list for the prompt
        node_list_parts: list[str] = []
        node_map: dict[str, TreeNode] = {}

        for i, node in enumerate(nodes):
            summary = node.summary or f"Section covering pages {node.start_page}-{node.end_page}"
            node_list_parts.append(
                f"{i + 1}. [{node.node_id}] \"{node.title}\" "
                f"(Pages {node.start_page}-{node.end_page})\n"
                f"   Summary: {summary}"
            )
            node_map[node.node_id] = node

        node_list = "\n\n".join(node_list_parts)

        context_section = ""
        if context:
            context_section = (
                f"Navigation path so far: {context}\n"
                f"(You are now looking at the children of the last section)"
            )

        prompt = _EVALUATE_NODES_PROMPT.format(
            question=query,
            context_section=context_section,
            node_list=node_list,
            max_selections=self._max_breadth,
        )

        start_time = time.time()

        response = await self._llm.agenerate(
            prompt=prompt,
            model=self._model,
            max_tokens=1024,
            temperature=0.1,
            system_prompt=(
                "You are a precise document navigation assistant. "
                "Analyze section summaries to find relevant content. "
                "Output ONLY valid JSON."
            ),
        )

        latency_ms = (time.time() - start_time) * 1000

        # Log LLM call
        if self._telemetry:
            await self._telemetry.log_llm_call(
                query_id=self._query_id,
                node_name="tree_searcher",
                model=self._model,
                latency_ms=round(latency_ms, 1),
                temperature=0.1,
            )

        # Parse LLM response
        evaluations = self._parse_evaluation_response(response, nodes, node_map)

        return evaluations

    def _parse_evaluation_response(
        self,
        response: str,
        nodes: list[TreeNode],
        node_map: dict[str, TreeNode],
    ) -> list[tuple[TreeNode, str, bool, float]]:
        """
        Parse the LLM evaluation response into structured results.

        Handles common JSON formatting issues and falls back to
        selecting all nodes if parsing fails (safe fallback).

        Args:
            response: Raw LLM response string.
            nodes: Original list of nodes for fallback.
            node_map: Mapping of node_id to TreeNode.

        Returns:
            List of (node, reasoning, is_selected, confidence) tuples.
        """
        results: list[tuple[TreeNode, str, bool, float]] = []

        try:
            # Clean response
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            # Find JSON array
            start_idx = cleaned.find("[")
            end_idx = cleaned.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                cleaned = cleaned[start_idx:end_idx]

            evaluations = json.loads(cleaned)

            if not isinstance(evaluations, list):
                raise ValueError("Expected JSON array")

            # Match evaluations to nodes
            selected_count = 0
            for eval_item in evaluations:
                node_id = eval_item.get("node_id", "")
                selected = eval_item.get("selected", False)
                reasoning = eval_item.get("reasoning", "No reasoning provided")
                confidence = float(eval_item.get("confidence", 0.5))

                node = node_map.get(node_id)
                if node is None:
                    # Try matching by index if node_id doesn't match
                    idx = evaluations.index(eval_item)
                    if idx < len(nodes):
                        node = nodes[idx]
                    else:
                        continue

                # Enforce breadth limit
                if selected and selected_count >= self._max_breadth:
                    selected = False
                    reasoning += " (breadth limit reached)"

                if selected:
                    selected_count += 1

                results.append((node, reasoning, selected, confidence))

            # If we got results for some nodes but not all, add missing ones
            result_node_ids = {r[0].node_id for r in results}
            for node in nodes:
                if node.node_id not in result_node_ids:
                    results.append(
                        (node, "Not evaluated by LLM", False, 0.0)
                    )

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "tree_searcher.parse_failed",
                error=str(exc),
                response_preview=response[:200],
            )
            # Fallback: select top nodes up to breadth limit
            for i, node in enumerate(nodes):
                selected = i < self._max_breadth
                results.append(
                    (
                        node,
                        "Fallback: parse error, selecting by position",
                        selected,
                        0.5,
                    )
                )

        return results

    # ─── Private helpers ───────────────────────────────

    @staticmethod
    def _collect_pages(nodes: list[TreeNode]) -> list[int]:
        """
        Collect all page numbers from a list of tree nodes.

        Args:
            nodes: List of TreeNode objects.

        Returns:
            List of page numbers (1-indexed, may have duplicates).
        """
        pages: list[int] = []
        for node in nodes:
            for page in range(node.start_page, node.end_page + 1):
                pages.append(page)
        return pages

    @staticmethod
    def _calculate_confidence(
        trace: list[SearchStep],
        relevant_nodes: list[TreeNode],
    ) -> float:
        """
        Calculate overall search confidence from reasoning trace.

        Factors:
        - Were nodes consistently selected at each level?
        - How many relevant nodes were found?
        - Average selection confidence from trace

        Args:
            trace: Full reasoning trace.
            relevant_nodes: Final set of relevant nodes.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not trace or not relevant_nodes:
            return 0.0

        # Base: did we find any relevant nodes?
        base = 0.3 if relevant_nodes else 0.0

        # Boost by selection consistency
        selected_steps = [s for s in trace if s.selected]
        if trace:
            selection_ratio = len(selected_steps) / len(trace)
            base += selection_ratio * 0.3

        # Boost by number of relevant nodes (diminishing returns)
        node_boost = min(len(relevant_nodes) / 5.0, 1.0) * 0.2
        base += node_boost

        # Add small fixed boost for completing the search
        base += 0.1

        return min(1.0, max(0.0, base))
