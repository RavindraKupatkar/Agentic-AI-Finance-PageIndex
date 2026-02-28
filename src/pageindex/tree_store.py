"""
Tree Store — Persistent Storage for PageIndex Tree Structures

Manages storage and retrieval of generated tree indexes using
JSON files for tree data and SQLite for metadata/indexing.

Replaces the vector store (Qdrant/ChromaDB) from traditional RAG:
    Vector DB  →  JSON Tree Store + SQLite Metadata

Storage layout:
    data/trees/{doc_id}.json         — Full tree structure
    data/pageindex_metadata.db       — SQLite metadata index

Design decisions:
    - Synchronous operations (file I/O + SQLite are not async-friendly)
    - Parameterized queries only (SQL injection prevention)
    - WAL mode for SQLite (concurrent read safety)
    - JSON files separate from metadata DB (enables independent backup)
    - Context managers for all DB connections (prevent resource leaks)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dataclasses import dataclass

from .tree_generator import DocumentTree, TreeNode
from ..core.config import settings
from ..observability.logging import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DocumentMetadata:
    """
    Metadata record for an indexed document.

    Attributes:
        doc_id: Unique document identifier (derived from filename hash).
        filename: Original PDF filename.
        title: Document title from PDF metadata or LLM extraction.
        total_pages: Number of pages in the PDF.
        tree_depth: Maximum depth of the generated tree.
        node_count: Total number of nodes in the tree.
        tree_path: Absolute path to the tree JSON file.
        pdf_path: Absolute path to the source PDF.
        created_at: ISO timestamp of indexing.
        updated_at: ISO timestamp of last update.
        status: Processing status (pending, completed, failed).
    """

    doc_id: str
    filename: str
    title: str
    total_pages: int
    tree_depth: int
    node_count: int
    tree_path: str
    pdf_path: str
    created_at: str
    updated_at: str
    status: str = "completed"


# ──────────────────────────────────────────────────────────────
# SQL schema (parameterized, no string concatenation ever)
# ──────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id      TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    total_pages INTEGER NOT NULL,
    tree_depth  INTEGER NOT NULL DEFAULT 0,
    node_count  INTEGER NOT NULL DEFAULT 0,
    tree_path   TEXT NOT NULL,
    pdf_path    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'completed'
);
"""

_INSERT_OR_REPLACE_SQL = """
INSERT OR REPLACE INTO documents
    (doc_id, filename, title, total_pages, tree_depth, node_count,
     tree_path, pdf_path, created_at, updated_at, status)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_SELECT_BY_ID_SQL = "SELECT * FROM documents WHERE doc_id = ?;"
_SELECT_ALL_SQL = "SELECT * FROM documents ORDER BY created_at DESC;"
_DELETE_BY_ID_SQL = "DELETE FROM documents WHERE doc_id = ?;"
_COUNT_SQL = "SELECT COUNT(*) FROM documents;"


# ──────────────────────────────────────────────────────────────
# Core store
# ──────────────────────────────────────────────────────────────


class TreeStore:
    """
    Persistent storage for PageIndex tree structures.

    Provides CRUD operations for document trees:
        - Save tree index as JSON + register in SQLite
        - Load tree by document ID
        - List all indexed documents
        - Delete tree indexes
        - Health check for storage connectivity

    Storage architecture:
        - JSON files in data/trees/ for full tree structures
        - SQLite database for fast metadata lookup and listing
        - WAL mode enabled for concurrent read safety

    Security:
        - All SQL queries use parameterized statements (no string concat)
        - File paths are canonicalized before I/O
        - JSON writes use atomic rename (write to temp → rename)

    Usage:
        store = TreeStore()
        store.save_tree(document_tree, pdf_path="/path/to/report.pdf")
        tree = store.load_tree("doc_123")
        documents = store.list_documents()
    """

    def __init__(self, storage_dir: Optional[str | Path] = None) -> None:
        """
        Initialize TreeStore with storage directory and SQLite database.

        Creates the storage directory and initializes the SQLite metadata
        table if they don't already exist.

        Args:
            storage_dir: Directory for tree JSON files.
                         Defaults to settings.trees_dir_absolute.

        Raises:
            OSError: If the storage directory cannot be created.
        """
        self._storage_dir: Path = (
            Path(storage_dir).resolve()
            if storage_dir
            else settings.trees_dir_absolute
        )
        self._db_path: Path = settings.metadata_db_absolute

        # Ensure directories exist
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite with WAL mode
        self._init_database()

        logger.info(
            "tree_store.initialized",
            storage_dir=str(self._storage_dir),
            db_path=str(self._db_path),
        )

    def save_tree(
        self,
        tree: DocumentTree,
        pdf_path: str | Path,
    ) -> str:
        """
        Save a document tree to persistent storage.

        Writes the full tree structure as JSON and registers metadata
        in SQLite. Uses INSERT OR REPLACE for idempotent saves (re-ingesting
        the same document overwrites the previous tree).

        Args:
            tree: The DocumentTree to save.
            pdf_path: Absolute path to the source PDF file.

        Returns:
            The doc_id of the saved tree.

        Raises:
            IOError: If the tree cannot be written to disk.
            ValueError: If the tree has no doc_id.
        """
        if not tree.doc_id:
            raise ValueError("DocumentTree must have a non-empty doc_id")

        tree_json_path = self._storage_dir / f"{tree.doc_id}.json"

        # Serialize tree to JSON
        tree_dict = tree.to_dict()
        json_content = json.dumps(tree_dict, indent=2, ensure_ascii=False)

        # Atomic write: write to temp file, then rename
        temp_path = tree_json_path.with_suffix(".json.tmp")
        try:
            temp_path.write_text(json_content, encoding="utf-8")
            temp_path.replace(tree_json_path)
        except OSError as exc:
            # Clean up temp file on failure
            temp_path.unlink(missing_ok=True)
            logger.error(
                "tree_store.save_tree.write_failed",
                doc_id=tree.doc_id,
                error=str(exc),
            )
            raise IOError(
                f"Failed to write tree JSON for {tree.doc_id}: {exc}"
            ) from exc

        # Calculate tree stats
        tree_depth = self._calculate_tree_depth(tree.root_nodes)
        node_count = self._count_nodes(tree.root_nodes)

        now = datetime.now(timezone.utc).isoformat()
        pdf_resolved = str(Path(pdf_path).resolve())

        # Insert/update metadata in SQLite
        self._execute_write(
            _INSERT_OR_REPLACE_SQL,
            (
                tree.doc_id,
                tree.filename,
                tree.title,
                tree.total_pages,
                tree_depth,
                node_count,
                str(tree_json_path),
                pdf_resolved,
                now,
                now,
                "completed",
            ),
        )

        logger.info(
            "tree_store.save_tree.complete",
            doc_id=tree.doc_id,
            tree_depth=tree_depth,
            node_count=node_count,
            json_path=str(tree_json_path),
            json_size_bytes=len(json_content),
        )

        return tree.doc_id

    def load_tree(self, doc_id: str) -> Optional[DocumentTree]:
        """
        Load a document tree from storage by document ID.

        Args:
            doc_id: Unique document identifier.

        Returns:
            DocumentTree if found, None if not indexed or if the
            underlying JSON file was deleted (stale entry auto-cleaned).
        """
        if not doc_id:
            raise ValueError("doc_id must be a non-empty string")

        metadata = self.get_metadata(doc_id)
        if metadata is None:
            logger.debug("tree_store.load_tree.not_found", doc_id=doc_id)
            return None

        tree_path = Path(metadata.tree_path)
        if not tree_path.exists():
            # ── Auto-clean stale metadata entry ──
            logger.warning(
                "tree_store.load_tree.json_missing.auto_cleanup",
                doc_id=doc_id,
                expected_path=str(tree_path),
            )
            self._execute_write(_DELETE_BY_ID_SQL, (doc_id,))
            logger.info(
                "tree_store.stale_entry_removed",
                doc_id=doc_id,
                reason="JSON file missing on disk",
            )
            return None

        try:
            json_content = tree_path.read_text(encoding="utf-8")
            tree_dict = json.loads(json_content)
            tree = DocumentTree.from_dict(tree_dict)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error(
                "tree_store.load_tree.parse_failed",
                doc_id=doc_id,
                error=str(exc),
            )
            raise IOError(
                f"Failed to parse tree JSON for {doc_id}: {exc}"
            ) from exc

        logger.debug(
            "tree_store.load_tree.complete",
            doc_id=doc_id,
            node_count=metadata.node_count,
        )

        return tree

    def get_metadata(self, doc_id: str) -> Optional[DocumentMetadata]:
        """
        Get metadata for a single document.

        Args:
            doc_id: Unique document identifier.

        Returns:
            DocumentMetadata if found, None otherwise.
        """
        row = self._execute_read_one(_SELECT_BY_ID_SQL, (doc_id,))
        if row is None:
            return None
        return self._row_to_metadata(row)

    def list_documents(self, validate: bool = False) -> list[DocumentMetadata]:
        """
        List all indexed documents with their metadata.

        Args:
            validate: If True, filters out documents whose tree JSON
                      files no longer exist on disk (stale entries).
                      Stale entries are automatically cleaned up.

        Returns:
            List of DocumentMetadata records, ordered by created_at descending.
        """
        rows = self._execute_read_all(_SELECT_ALL_SQL)
        documents = [self._row_to_metadata(row) for row in rows]

        if validate:
            valid_docs = []
            for doc in documents:
                tree_path = Path(doc.tree_path)
                if tree_path.exists():
                    valid_docs.append(doc)
                else:
                    logger.warning(
                        "tree_store.list_documents.stale_entry",
                        doc_id=doc.doc_id,
                        missing_path=str(tree_path),
                    )
                    self._execute_write(_DELETE_BY_ID_SQL, (doc.doc_id,))
                    logger.info(
                        "tree_store.stale_entry_removed",
                        doc_id=doc.doc_id,
                        reason="JSON file missing on disk (list_documents validate)",
                    )
            documents = valid_docs

        logger.debug(
            "tree_store.list_documents",
            count=len(documents),
        )

        return documents

    def delete_tree(self, doc_id: str) -> bool:
        """
        Delete a document tree and its metadata.

        Removes both the JSON file and the SQLite metadata row.

        Args:
            doc_id: Unique document identifier.

        Returns:
            True if deleted, False if not found.
        """
        metadata = self.get_metadata(doc_id)
        if metadata is None:
            logger.debug("tree_store.delete_tree.not_found", doc_id=doc_id)
            return False

        # Delete JSON file
        tree_path = Path(metadata.tree_path)
        if tree_path.exists():
            tree_path.unlink()
            logger.debug(
                "tree_store.delete_tree.json_deleted",
                doc_id=doc_id,
                path=str(tree_path),
            )

        # Delete SQLite row
        self._execute_write(_DELETE_BY_ID_SQL, (doc_id,))

        logger.info(
            "tree_store.delete_tree.complete",
            doc_id=doc_id,
        )

        return True

    def get_document_count(self) -> int:
        """
        Get the total number of indexed documents.

        Returns:
            Number of documents in the store.
        """
        row = self._execute_read_one(_COUNT_SQL)
        return row[0] if row else 0

    def document_exists(self, doc_id: str) -> bool:
        """
        Check if a document is already indexed.

        Args:
            doc_id: Unique document identifier.

        Returns:
            True if the document exists in the store.
        """
        return self.get_metadata(doc_id) is not None

    def purge_stale_entries(self) -> int:
        """
        Scan all metadata rows and remove any whose tree JSON file
        no longer exists on disk.

        Returns:
            Number of stale entries removed.
        """
        all_docs = self.list_documents(validate=False)
        removed = 0
        for doc in all_docs:
            tree_path = Path(doc.tree_path)
            if not tree_path.exists():
                self._execute_write(_DELETE_BY_ID_SQL, (doc.doc_id,))
                logger.info(
                    "tree_store.purge_stale_entries.removed",
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    missing_path=str(tree_path),
                )
                removed += 1
        if removed:
            logger.warning(
                "tree_store.purge_stale_entries.complete",
                removed=removed,
                remaining=len(all_docs) - removed,
            )
        return removed

    def health_check(self) -> bool:
        """
        Check if the tree store is healthy and accessible.

        Also purges any stale metadata entries on startup.

        Returns:
            True if storage directory exists and SQLite is accessible.
        """
        try:
            if not self._storage_dir.exists():
                return False
            # Test SQLite connectivity
            self.get_document_count()
            # Purge stale entries on health check
            self.purge_stale_entries()
            return True
        except Exception as exc:
            logger.error(
                "tree_store.health_check.failed",
                error=str(exc),
            )
            return False

    # ─── Private: Database operations ──────────────────────

    def _init_database(self) -> None:
        """
        Initialize the SQLite database and create the documents table.

        Enables WAL mode for concurrent read safety.
        """
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()

    def _execute_write(self, sql: str, params: tuple = ()) -> None:
        """
        Execute a write SQL statement with parameterized query.

        Args:
            sql: SQL statement with ? placeholders.
            params: Tuple of parameter values.
        """
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(sql, params)
            conn.commit()

    def _execute_read_one(
        self, sql: str, params: tuple = ()
    ) -> Optional[tuple]:
        """
        Execute a read SQL statement and return one row.

        Args:
            sql: SQL statement with ? placeholders.
            params: Tuple of parameter values.

        Returns:
            Single result row or None.
        """
        with sqlite3.connect(str(self._db_path)) as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()

    def _execute_read_all(self, sql: str, params: tuple = ()) -> list[tuple]:
        """
        Execute a read SQL statement and return all rows.

        Args:
            sql: SQL statement with ? placeholders.
            params: Tuple of parameter values.

        Returns:
            List of result rows.
        """
        with sqlite3.connect(str(self._db_path)) as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    # ─── Private: Helpers ──────────────────────────────────

    @staticmethod
    def _row_to_metadata(row: tuple) -> DocumentMetadata:
        """
        Convert a SQLite row tuple to a DocumentMetadata object.

        Args:
            row: Tuple matching the documents table column order.

        Returns:
            DocumentMetadata instance.
        """
        return DocumentMetadata(
            doc_id=row[0],
            filename=row[1],
            title=row[2],
            total_pages=row[3],
            tree_depth=row[4],
            node_count=row[5],
            tree_path=row[6],
            pdf_path=row[7],
            created_at=row[8],
            updated_at=row[9],
            status=row[10],
        )

    @staticmethod
    def _calculate_tree_depth(nodes: list[TreeNode], current_depth: int = 1) -> int:
        """
        Calculate the maximum depth of a tree.

        Args:
            nodes: List of tree nodes at the current level.
            current_depth: Current depth level (1-indexed).

        Returns:
            Maximum depth of the tree.
        """
        if not nodes:
            return 0

        max_depth = current_depth
        for node in nodes:
            if node.children:
                child_depth = TreeStore._calculate_tree_depth(
                    node.children, current_depth + 1
                )
                max_depth = max(max_depth, child_depth)
        return max_depth

    @staticmethod
    def _count_nodes(nodes: list[TreeNode]) -> int:
        """
        Count the total number of nodes in a tree.

        Args:
            nodes: List of root-level tree nodes.

        Returns:
            Total node count (including all descendants).
        """
        count = 0
        for node in nodes:
            count += 1
            if node.children:
                count += TreeStore._count_nodes(node.children)
        return count
