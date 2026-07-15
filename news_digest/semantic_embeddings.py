from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Iterable

from .categories import CATEGORY_INDUSTRY, CATEGORY_SECURITY, CATEGORY_VENTURE
from .models import Article


LOGGER = logging.getLogger(__name__)

ENHANCED_CATEGORIES = frozenset(
    {
        CATEGORY_INDUSTRY,
        CATEGORY_SECURITY,
        CATEGORY_VENTURE,
    }
)

CATEGORY_REFERENCE_STEMS = {
    CATEGORY_INDUSTRY: "news_industry_trends",
    CATEGORY_SECURITY: "news_security",
    CATEGORY_VENTURE: "news_venture_finance",
}

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TITLE_WEIGHT = 0.7
SUMMARY_WEIGHT = 0.3
MAX_SEQ_LENGTH = 512
REFERENCE_LIMIT = 1_000
REFERENCE_TOP_K = 10


@dataclass(frozen=True)
class ArticleVectors:
    title: object
    summary: object
    combined: object


def _article_key(article: Article) -> tuple[str, str]:
    return (article.title.strip().casefold(), article.description.strip().casefold())


def _enabled_from_environment() -> bool:
    value = os.getenv("SEMANTIC_RECOMMENDATION_ENABLED", "true")
    return value.strip().casefold() in {"1", "true", "yes", "y", "on"}


def _embedding_directory() -> Path:
    configured = os.getenv("SEMANTIC_EMBEDDING_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "model" / "embeddings"


class SemanticEmbeddingService:
    """로컬 SentenceTransformer 모델과 카테고리 기준 벡터를 재사용합니다."""

    def __init__(self) -> None:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        self.np = np
        self.embedding_dir = _embedding_directory()
        self.model = SentenceTransformer(MODEL_NAME)
        self.model.max_seq_length = MAX_SEQ_LENGTH
        self.article_cache: dict[tuple[str, str], ArticleVectors] = {}
        self.references = {
            category: self._load_reference(stem)
            for category, stem in CATEGORY_REFERENCE_STEMS.items()
        }
        LOGGER.info(
            "Semantic recommendation enabled: model=%s reference_dir=%s",
            MODEL_NAME,
            self.embedding_dir,
        )

    def _load_reference(self, stem: str):
        path = self.embedding_dir / f"{stem}_embeddings.npy"
        if not path.exists():
            raise FileNotFoundError(f"Semantic reference embedding not found: {path}")
        vectors = self.np.load(path, mmap_mode="r")
        if vectors.ndim != 2 or vectors.shape[1] <= 0:
            raise ValueError(f"Invalid semantic reference shape: {path} -> {vectors.shape}")
        if len(vectors) > REFERENCE_LIMIT:
            indices = self.np.linspace(0, len(vectors) - 1, REFERENCE_LIMIT, dtype=int)
            vectors = self.np.asarray(vectors[indices], dtype=self.np.float32)
        return vectors

    def _normalize_rows(self, vectors):
        norms = self.np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / self.np.clip(norms, 1e-12, None)

    def prepare_articles(self, articles: Iterable[Article]) -> None:
        missing: dict[tuple[str, str], Article] = {}
        for article in articles:
            key = _article_key(article)
            if key not in self.article_cache:
                missing.setdefault(key, article)
        if not missing:
            return

        keys = list(missing)
        pending = [missing[key] for key in keys]
        titles = [article.title.strip() for article in pending]
        summaries = [article.description.strip() or article.title.strip() for article in pending]
        title_vectors = self.model.encode(
            titles,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(self.np.float32, copy=False)
        summary_vectors = self.model.encode(
            summaries,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(self.np.float32, copy=False)
        combined_vectors = self._normalize_rows(
            TITLE_WEIGHT * title_vectors + SUMMARY_WEIGHT * summary_vectors
        ).astype(self.np.float32, copy=False)

        for index, key in enumerate(keys):
            self.article_cache[key] = ArticleVectors(
                title=title_vectors[index],
                summary=summary_vectors[index],
                combined=combined_vectors[index],
            )

    def vectors_for(self, article: Article) -> ArticleVectors | None:
        return self.article_cache.get(_article_key(article))

    def category_score(self, article: Article, category: str) -> float | None:
        if category not in ENHANCED_CATEGORIES:
            return None
        article_vectors = self.vectors_for(article)
        references = self.references.get(category)
        if article_vectors is None or references is None or len(references) == 0:
            return None
        similarities = references @ article_vectors.combined
        top_k = min(REFERENCE_TOP_K, len(similarities))
        nearest = self.np.partition(similarities, len(similarities) - top_k)[-top_k:]
        return float(self.np.clip(nearest.mean(), 0.0, 1.0))

    def combined_similarity(self, left: Article, right: Article) -> float | None:
        left_vectors = self.vectors_for(left)
        right_vectors = self.vectors_for(right)
        if left_vectors is None or right_vectors is None:
            return None
        return float(self.np.clip(left_vectors.combined @ right_vectors.combined, 0.0, 1.0))

    def is_duplicate(self, left: Article, right: Article) -> bool:
        left_vectors = self.vectors_for(left)
        right_vectors = self.vectors_for(right)
        if left_vectors is None or right_vectors is None:
            return False
        title_similarity = float(self.np.clip(left_vectors.title @ right_vectors.title, 0.0, 1.0))
        summary_similarity = float(
            self.np.clip(left_vectors.summary @ right_vectors.summary, 0.0, 1.0)
        )
        return title_similarity >= 0.94 or (
            title_similarity >= 0.88 and summary_similarity >= 0.90
        )


_SERVICE: SemanticEmbeddingService | None = None
_INITIALIZATION_ATTEMPTED = False


def get_semantic_service() -> SemanticEmbeddingService | None:
    global _SERVICE, _INITIALIZATION_ATTEMPTED
    if not _enabled_from_environment():
        return None
    if _SERVICE is not None:
        return _SERVICE
    if _INITIALIZATION_ATTEMPTED:
        return None
    _INITIALIZATION_ATTEMPTED = True
    try:
        _SERVICE = SemanticEmbeddingService()
    except Exception:
        LOGGER.exception(
            "Semantic recommendation could not be initialized; falling back to lexical CCH-MMR"
        )
    return _SERVICE


def prepare_semantic_articles(articles: Iterable[Article]) -> None:
    service = get_semantic_service()
    if service is not None:
        service.prepare_articles(articles)


def semantic_category_score(article: Article, category: str) -> float | None:
    if category not in ENHANCED_CATEGORIES:
        return None
    service = get_semantic_service()
    return service.category_score(article, category) if service is not None else None


def semantic_similarity(left: Article, right: Article) -> float | None:
    service = _SERVICE
    return service.combined_similarity(left, right) if service is not None else None


def is_semantic_duplicate(left: Article, right: Article) -> bool:
    service = _SERVICE
    return service.is_duplicate(left, right) if service is not None else False
