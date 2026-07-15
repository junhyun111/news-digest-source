from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from news_digest import cch_mmr_recommender as recommender
from news_digest import pipeline
from news_digest import semantic_embeddings
from news_digest.categories import CATEGORY_INDUSTRY, CATEGORY_SECURITY
from news_digest.models import Article


def article(title: str, category: str = "", url: str | None = None) -> Article:
    return Article(
        title=title,
        description=f"{title} 설명",
        originallink=url or f"https://example.com/{title}",
        link="",
        pub_date=datetime(2026, 7, 14, tzinfo=timezone.utc),
        category=category,
    )


class SemanticScoringTests(unittest.TestCase):
    def test_security_accepts_video_surveillance_article(self) -> None:
        candidate = article("보령시, 방범 CCTV 확충하고 통합관제센터 연계")

        self.assertTrue(
            recommender.is_eligible_category_candidate(
                candidate, CATEGORY_SECURITY, 0.8, {"rule": 0.5}, 0.5
            )
        )

    def test_security_rejects_cybersecurity_without_video_core(self) -> None:
        candidate = article("정부, AI 사이버보안 기업에 10조원 투자")

        self.assertFalse(
            recommender.is_eligible_category_candidate(
                candidate, CATEGORY_SECURITY, 0.8, {"rule": 0.5}, 0.5
            )
        )

    def test_security_rejects_generic_ai_safety_article(self) -> None:
        candidate = article("청주시, AI 안전특별시 선언")

        self.assertFalse(
            recommender.is_eligible_category_candidate(
                candidate, CATEGORY_SECURITY, 0.8, {"rule": 0.5}, 0.5
            )
        )

    def test_unsupported_category_does_not_initialize_model(self) -> None:
        candidate = article("일반 기사")
        with patch.object(
            semantic_embeddings,
            "get_semantic_service",
            side_effect=AssertionError("model should not initialize"),
        ):
            score = semantic_embeddings.semantic_category_score(candidate, "지원하지 않는 카테고리")

        self.assertIsNone(score)

    def test_semantic_score_blends_with_existing_relevance(self) -> None:
        candidate = article("AI 반도체 투자")
        weights = {
            "rule": 1.0,
            "recency": 0.0,
            "source": 0.0,
            "entity": 0.0,
            "language": 0.0,
        }
        with (
            patch.object(recommender, "rule_score", return_value=0.4),
            patch.object(recommender, "semantic_category_score", return_value=0.8),
        ):
            score, components = recommender.relevance_score(
                candidate,
                CATEGORY_INDUSTRY,
                weights=weights,
                now=candidate.pub_date,
                timezone="UTC",
            )

        self.assertAlmostEqual(score, 0.54)
        self.assertEqual(components["semantic"], 0.8)

    def test_unsupported_semantic_score_preserves_existing_relevance(self) -> None:
        candidate = article("일반 기사")
        weights = {
            "rule": 1.0,
            "recency": 0.0,
            "source": 0.0,
            "entity": 0.0,
            "language": 0.0,
        }
        with (
            patch.object(recommender, "rule_score", return_value=0.4),
            patch.object(recommender, "semantic_category_score", return_value=None),
        ):
            score, components = recommender.relevance_score(
                candidate,
                "지원하지 않는 카테고리",
                weights=weights,
                now=candidate.pub_date,
                timezone="UTC",
            )

        self.assertAlmostEqual(score, 0.4)
        self.assertEqual(components["semantic"], 0.0)

    def test_redundancy_combines_lexical_and_semantic_similarity(self) -> None:
        left = article("왼쪽")
        right = article("오른쪽")
        with (
            patch.object(recommender, "lexical_cosine", return_value=0.2),
            patch.object(recommender, "semantic_similarity", return_value=0.87),
        ):
            score = recommender.redundancy_score(left, right)

        self.assertAlmostEqual(score, 0.65)


class SemanticEmbeddingServiceTests(unittest.TestCase):
    def test_title_summary_weighting_and_reference_score(self) -> None:
        class FakeModel:
            def __init__(self) -> None:
                self.calls = 0

            def encode(self, _texts, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    return np.array([[1.0, 0.0]], dtype=np.float32)
                return np.array([[0.0, 1.0]], dtype=np.float32)

        service = semantic_embeddings.SemanticEmbeddingService.__new__(
            semantic_embeddings.SemanticEmbeddingService
        )
        service.np = np
        service.model = FakeModel()
        service.article_cache = {}
        service.references = {}
        candidate = article("AI 반도체")

        service.prepare_articles([candidate])
        combined = service.vectors_for(candidate).combined
        expected = np.array([0.7, 0.3], dtype=np.float32)
        expected /= np.linalg.norm(expected)
        service.references[CATEGORY_INDUSTRY] = expected.reshape(1, -1)

        np.testing.assert_allclose(combined, expected, atol=1e-6)
        self.assertAlmostEqual(
            service.category_score(candidate, CATEGORY_INDUSTRY), 1.0, places=6
        )


class PipelineSemanticDeduplicationTests(unittest.TestCase):
    def test_cross_category_duplicate_uses_backfill_candidate(self) -> None:
        security = article("공통 사건 보안 기사", CATEGORY_SECURITY, "https://example.com/security")
        duplicate = article("표현이 다른 공통 사건", CATEGORY_INDUSTRY, "https://example.com/duplicate")
        replacement = article("독립적인 산업 기사", CATEGORY_INDUSTRY, "https://example.com/replacement")
        config = SimpleNamespace(
            max_articles=2,
            category_quotas={},
            keyword_weights={},
            min_score=0.0,
            timezone="UTC",
            recommendation_weights={},
            mmr_lambda=0.7,
        )

        def selected_for_category(_articles, category, **_kwargs):
            return [security] if category == CATEGORY_SECURITY else [duplicate, replacement]

        with (
            patch.object(pipeline, "CATEGORY_ORDER", [CATEGORY_SECURITY, CATEGORY_INDUSTRY]),
            patch.object(
                pipeline,
                "category_ranges_from_quotas",
                return_value={CATEGORY_SECURITY: (0, 1), CATEGORY_INDUSTRY: (0, 1)},
            ),
            patch.object(
                pipeline,
                "collect_category_articles",
                return_value=[security, duplicate, replacement],
            ),
            patch.object(pipeline, "select_category_articles", side_effect=selected_for_category),
            patch.object(
                pipeline,
                "is_semantic_duplicate",
                side_effect=lambda left, right: left is duplicate and right is security,
            ),
        ):
            selected = pipeline.build_digest(config)

        self.assertEqual([item.title for item in selected], [security.title, replacement.title])


if __name__ == "__main__":
    unittest.main()
