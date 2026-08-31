"""
identity_graph_module.py — Cross-document identity reuse detection
-----------------------------------------------------------------
Stores face embeddings from each verification and flags when the same
face appears under a different ID number or name — a strong fraud signal.

Uses DeepFace ArcFace embeddings stored in a local SQLite database.
Fully self-contained; never blocks the pipeline on failure.

Usage:
    from modules.identity_graph_module import check_identity_reuse
    result = check_identity_reuse(selfie_path, id_number="1234...", name="JOHN DOE")
    # result["flagged"] -> bool
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("identity_graph")

_DB_PATH = Path(__file__).resolve().parent / "identity_graph.db"
_SIMILARITY_THRESHOLD = 0.72  # cosine similarity — same person
_MODEL_NAME = "ArcFace"
_DETECTOR = "mtcnn"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS identity_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            embedding_hash TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            id_number TEXT,
            name TEXT,
            document_hash TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_embedding_hash ON identity_nodes(embedding_hash)"
    )
    return conn


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _extract_embedding(image_path: str) -> Optional[np.ndarray]:
    try:
        from deepface import DeepFace

        reps = DeepFace.represent(
            img_path=image_path,
            model_name=_MODEL_NAME,
            detector_backend=_DETECTOR,
            enforce_detection=False,
        )
        if not reps:
            return None
        return np.asarray(reps[0]["embedding"], dtype=np.float32)
    except Exception as exc:
        logger.warning(f"Embedding extraction failed: {exc}")
        return None


def _normalize_id(id_number: Optional[str]) -> str:
    return (id_number or "").replace(" ", "").strip().upper()


def check_identity_reuse(
    selfie_path: str,
    id_number: Optional[str] = None,
    name: Optional[str] = None,
    document_hash: Optional[str] = None,
) -> dict:
    """
    Compare selfie embedding against all stored embeddings.
    Registers this verification if not flagged.

    Returns:
        {
            "flagged": bool,
            "reason": str | None,
            "matched_id_number": str | None,
            "matched_name": str | None,
            "similarity": float | None,
            "registered": bool,
        }
    """
    embedding = _extract_embedding(selfie_path)
    if embedding is None:
        return {
            "flagged": False,
            "reason": None,
            "matched_id_number": None,
            "matched_name": None,
            "similarity": None,
            "registered": False,
            "detail": "Could not extract face embedding — identity graph skipped",
        }

    norm_id = _normalize_id(id_number)
    norm_name = (name or "").strip().upper()
    emb_hash = hashlib.sha256(embedding.tobytes()).hexdigest()

    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT id_number, name, embedding_json FROM identity_nodes"
        ).fetchall()

        best_sim = 0.0
        best_row = None
        for stored_id, stored_name, emb_json in rows:
            stored_emb = np.asarray(json.loads(emb_json), dtype=np.float32)
            sim = _cosine_similarity(embedding, stored_emb)
            if sim > best_sim:
                best_sim = sim
                best_row = (stored_id, stored_name)

        if best_row and best_sim >= _SIMILARITY_THRESHOLD:
            stored_id, stored_name = best_row
            id_mismatch = norm_id and stored_id and norm_id != _normalize_id(stored_id)
            name_mismatch = norm_name and stored_name and norm_name != stored_name.strip().upper()

            if id_mismatch or name_mismatch:
                return {
                    "flagged": True,
                    "reason": "Same face seen under a different identity",
                    "matched_id_number": stored_id,
                    "matched_name": stored_name,
                    "similarity": round(best_sim, 3),
                    "registered": False,
                    "detail": (
                        f"Face match {best_sim:.0%} to prior entry "
                        f"(ID={stored_id or 'unknown'}, name={stored_name or 'unknown'})"
                    ),
                }

        # Register this verification
        conn.execute(
            """
            INSERT INTO identity_nodes (embedding_hash, embedding_json, id_number, name, document_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                emb_hash,
                json.dumps(embedding.tolist()),
                norm_id or None,
                norm_name or None,
                document_hash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()

        return {
            "flagged": False,
            "reason": None,
            "matched_id_number": None,
            "matched_name": None,
            "similarity": round(best_sim, 3) if best_row else None,
            "registered": True,
            "detail": "Face registered in identity graph — no reuse detected",
        }

    except Exception as exc:
        logger.error(f"Identity graph check failed: {exc}")
        return {
            "flagged": False,
            "reason": None,
            "matched_id_number": None,
            "matched_name": None,
            "similarity": None,
            "registered": False,
            "detail": f"Identity graph error (non-fatal): {exc}",
        }
    finally:
        conn.close()


def get_graph_stats() -> dict:
    """Return node count for health/status endpoint."""
    conn = _get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM identity_nodes").fetchone()[0]
        return {"nodes": count, "db_path": str(_DB_PATH)}
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python identity_graph_module.py <selfie.jpg> [id_number] [name]")
        sys.exit(1)
    r = check_identity_reuse(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None,
                             sys.argv[3] if len(sys.argv) > 3 else None)
    print(r)
    print(get_graph_stats())
