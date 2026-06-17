"""
Semantic search for medical services using sentence-transformers.

Integrates A8 retrieval/embedding patterns into the production Django context.
Primary model: all-MiniLM-L6-v2 (local, public, ~80 MB, no API key required).

Architecture:
    User Query → Sentence Embedding → Cosine Similarity → Ranked Services

Design notes:
- Model is lazy-loaded on first request to avoid slowing Django startup.
- Embeddings are cached in memory; call `invalidate_index()` after bulk DB changes.
- Falls back gracefully if sentence-transformers is unavailable (ImportError).
"""

from __future__ import annotations

from typing import Any

import numpy as np

EMBEDDING_MODEL_ID = "all-MiniLM-L6-v2"

# Module-level cache — rebuilt on first call or after invalidation.
_model = None
_service_embeddings: np.ndarray | None = None  # shape (N, dim), L2-normalised
_service_ids: list[int] | None = None           # parallel list of MedService PKs

# Template used to build one text chunk per service record.
# Richer text → better semantic discrimination.
_SERVICE_TEMPLATE = (
    "{name}. {location}. {description} Services offered: {services_offered}."
)


# ── Model loader ──────────────────────────────────────────────────────────────

def _get_model():
    """Lazy-load the sentence-transformer model (downloads once, cached locally)."""
    global _model
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        ) from exc

    _model = SentenceTransformer(EMBEDDING_MODEL_ID)
    return _model


# ── Index builder ─────────────────────────────────────────────────────────────

def _build_service_text(svc) -> str:
    """Compose a single descriptive string for one MedService record."""
    return _SERVICE_TEMPLATE.format(
        name=svc.name or "",
        location=svc.location or "",
        description=(svc.description or "").strip(),
        services_offered=(svc.services_offered or "").strip(),
    )


def build_service_index() -> None:
    """
    Encode every MedService record and store L2-normalised embeddings in memory.
    Called automatically on the first semantic search request.
    """
    global _service_embeddings, _service_ids

    from .models import MedService  # Django ORM — safe here (app already loaded)

    model = _get_model()
    services = list(MedService.objects.all().order_by("id"))

    if not services:
        _service_embeddings = np.empty((0, 384), dtype="float32")
        _service_ids = []
        return

    texts = [_build_service_text(s) for s in services]
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    )
    _service_embeddings = np.array(embeddings, dtype="float32")
    _service_ids = [s.id for s in services]


def invalidate_index() -> None:
    """
    Drop the in-memory index so it is rebuilt on the next query.
    Call this after creating, updating, or deleting MedService records.
    """
    global _service_embeddings, _service_ids
    _service_embeddings = None
    _service_ids = None


# ── Public API ────────────────────────────────────────────────────────────────

def semantic_recommend_services(
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Return the `top_k` MedService records most semantically similar to `query`.

    Similarity is cosine distance between the query embedding and each service
    embedding (computed exactly — feasible for a clinic-scale DB).

    Returns an empty list if sentence-transformers is unavailable or the
    database contains no services.
    """
    global _service_embeddings, _service_ids

    if not query or not query.strip():
        return []

    # Build index lazily.
    if _service_embeddings is None or _service_ids is None:
        build_service_index()

    if not _service_ids:
        return []

    model = _get_model()

    # Encode and L2-normalise the query.
    query_emb = model.encode(
        [query.strip()],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]
    query_emb = np.array(query_emb, dtype="float32")

    # Cosine similarity = dot product when both sides are unit vectors.
    scores: np.ndarray = _service_embeddings @ query_emb  # shape (N,)

    # Rank descending, keep only as many as we need.
    top_indices = np.argsort(scores)[::-1][:top_k]

    from .models import MedService
    from django.urls import reverse

    candidate_ids = [_service_ids[int(i)] for i in top_indices]
    svc_map = {s.id: s for s in MedService.objects.filter(id__in=candidate_ids)}

    results: list[dict[str, Any]] = []
    for idx in top_indices:
        svc_id = _service_ids[int(idx)]
        svc = svc_map.get(svc_id)
        if svc is None:
            continue  # stale index entry — skip
        results.append(
            {
                "id": svc.id,
                "name": svc.name,
                "location": svc.location,
                "appointments_required": svc.appointments_required,
                "google_rating": float(svc.google_rating) if svc.google_rating else None,
                "hours": svc.hours,
                "description": svc.description,
                "services_offered": svc.services_offered,
                "url": reverse("service-detail", kwargs={"pk": svc.id}),
                "similarity_score": round(float(scores[int(idx)]), 4),
            }
        )

    return results
