from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from news_digest import cch_mmr_recommender as recommender
from news_digest import pipeline
from news_digest import semantic_embeddings
from news_digest.industry_editorial import (
    INDUSTRY_INTENTS,
    IndustryEditorialAssessment,
    assess_industry_article,
)
from news_digest.categories import (
    CATEGORY_GOVERNMENT,
    CATEGORY_INDUSTRY,
    CATEGORY_INNODEP,
    CATEGORY_LABOR,
    CATEGORY_SECURITY,
    CATEGORY_VENTURE,
)
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
    def test_target_count_stops_before_score_cliff(self) -> None:
        candidates = [
            (article("후보 1"), 0.82, {}),
            (article("후보 2"), 0.79, {}),
            (article("후보 3"), 0.76, {}),
            (article("후보 4"), 0.61, {}),
        ]

        self.assertEqual(
            recommender.target_count_for_category(candidates, maximum=22, threshold=0.5),
            3,
        )

    def test_stricter_quality_window_selects_fewer_candidates(self) -> None:
        candidates = [
            (article("후보 1"), 0.90, {}),
            (article("후보 2"), 0.855, {}),
            (article("후보 3"), 0.84, {}),
        ]

        self.assertEqual(
            recommender.target_count_for_category(
                candidates, maximum=3, threshold=0.5, quality_window=0.06
            ),
            3,
        )
        self.assertEqual(
            recommender.target_count_for_category(
                candidates, maximum=3, threshold=0.5, quality_window=0.04
            ),
            1,
        )

    def test_security_backfills_recommended_minimum_above_absolute_floor(self) -> None:
        candidates = [
            (article("후보 1"), 0.917, {}),
            (article("후보 2"), 0.7694, {}),
            (article("후보 3"), 0.7533, {}),
            (article("후보 4"), 0.61, {}),
        ]

        self.assertEqual(
            recommender.target_count_for_category(
                candidates,
                maximum=6,
                threshold=0.5,
                recommended_minimum=3,
                backfill_score_floor=0.65,
            ),
            3,
        )

    def test_security_does_not_backfill_below_absolute_floor(self) -> None:
        candidates = [
            (article("후보 1"), 0.917, {}),
            (article("후보 2"), 0.64, {}),
            (article("후보 3"), 0.63, {}),
        ]

        self.assertEqual(
            recommender.target_count_for_category(
                candidates,
                maximum=6,
                threshold=0.5,
                recommended_minimum=3,
                backfill_score_floor=0.65,
            ),
            1,
        )

    def test_every_category_has_a_selection_policy(self) -> None:
        expected = {
            CATEGORY_INNODEP: (2, 0.65),
            CATEGORY_SECURITY: (5, 0.50),
            CATEGORY_INDUSTRY: (16, 0.50),
            CATEGORY_GOVERNMENT: (3, 0.65),
            CATEGORY_VENTURE: (5, 0.65),
            CATEGORY_LABOR: (2, 0.65),
        }

        self.assertEqual(recommender.CATEGORY_SELECTION_POLICIES, expected)

    def test_requested_category_maximums_are_configured(self) -> None:
        self.assertEqual(recommender.DEFAULT_CATEGORY_RANGES[CATEGORY_SECURITY], (0, 10))
        self.assertEqual(recommender.DEFAULT_CATEGORY_RANGES[CATEGORY_INDUSTRY], (0, 22))
        self.assertEqual(recommender.DEFAULT_CATEGORY_RANGES[CATEGORY_VENTURE], (0, 9))

    def test_venture_uses_tighter_quality_window(self) -> None:
        self.assertEqual(
            recommender.CATEGORY_QUALITY_SCORE_WINDOWS[CATEGORY_VENTURE], 0.04
        )

    def test_venture_tight_window_backfills_to_target_without_filling_maximum(self) -> None:
        candidates = [
            (article("벤처 후보 1"), 0.94, {}),
            (article("벤처 후보 2"), 0.88, {}),
            (article("벤처 후보 3"), 0.84, {}),
            (article("벤처 후보 4"), 0.80, {}),
            (article("벤처 후보 5"), 0.76, {}),
            (article("벤처 후보 6"), 0.72, {}),
            (article("벤처 후보 7"), 0.68, {}),
        ]

        target = recommender.target_count_for_category(
            candidates,
            maximum=9,
            threshold=0.5,
            quality_window=recommender.CATEGORY_QUALITY_SCORE_WINDOWS[CATEGORY_VENTURE],
            recommended_minimum=5,
            backfill_score_floor=0.65,
        )

        self.assertEqual(target, 5)

    def test_government_and_labor_have_stricter_score_floor(self) -> None:
        self.assertEqual(
            recommender.selection_threshold_for_category(CATEGORY_GOVERNMENT, 0.5),
            0.7,
        )
        self.assertEqual(
            recommender.selection_threshold_for_category(CATEGORY_INDUSTRY, 0.5),
            0.5,
        )

    def test_score_distribution_reports_saturation_ratio(self) -> None:
        with self.assertLogs(recommender.LOGGER, level="INFO") as captured:
            recommender.log_score_distribution("테스트", [0.2, 0.8, 1.0, 1.1])

        self.assertIn("saturated=2(50.0%)", captured.output[0])

    def test_mmr_uses_redundancy_to_rerank_without_setting_quality_count(self) -> None:
        candidates = [
            (article("첫 기사"), 0.8, {}),
            (article("중복 기사"), 0.79, {}),
            (article("다양한 기사"), 0.7, {}),
        ]

        def redundancy(candidate: Article, _existing: Article) -> float:
            return 1.0 if candidate.title == "중복 기사" else 0.0

        with (
            patch.object(recommender, "redundancy_score", side_effect=redundancy),
            patch.object(recommender, "reason_for", return_value="test"),
            patch.object(recommender, "industry_company_key", return_value=""),
        ):
            selected = recommender.mmr_select(
                candidates,
                quota=2,
                category=CATEGORY_INDUSTRY,
                lambda_value=0.7,
                already_selected=set(),
                selected_articles=[],
                selected_industry_companies=set(),
            )

        self.assertEqual([item.title for item in selected], ["첫 기사", "다양한 기사"])

    def test_industry_mmr_limits_one_editorial_intent_to_four_articles(self) -> None:
        candidates = [
            (
                article(f"기업{index}, AI 플랫폼 신제품 {index} 공개", url=f"https://source{index}.com/{index}"),
                0.9 - index * 0.01,
                {
                    "intent": "model_platform",
                    "intent_label": "모델·플랫폼·빅테크",
                    "centrality": 0.9,
                    "importance": 0.8,
                    "intent_score": 0.85,
                    "editorial_score": 0.85,
                },
            )
            for index in range(5)
        ]
        with (
            patch.object(recommender, "is_similar_to_selected", return_value=False),
            patch.object(recommender, "redundancy_score", return_value=0.0),
        ):
            selected = recommender.mmr_select(
                candidates,
                quota=5,
                category=CATEGORY_INDUSTRY,
                lambda_value=0.7,
                already_selected=set(),
                selected_articles=[],
                selected_industry_companies=set(),
            )

        self.assertEqual(len(selected), 4)

    def test_overlapping_keywords_count_only_the_strongest_phrase(self) -> None:
        matches = recommender.strongest_keyword_matches(
            "AI 통합관제센터 구축",
            ["관제", "통합관제", "통합관제센터", "구축"],
        )

        self.assertEqual(set(matches), {"통합관제센터", "구축"})
        self.assertEqual(recommender.category_keywords(CATEGORY_INNODEP).count("이노뎁"), 1)

    def test_compound_keyword_terms_can_match_separately_in_any_order(self) -> None:
        self.assertTrue(
            recommender.keyword_matches_text("AI용 차세대 반도체 개발", "AI 반도체")
        )
        self.assertTrue(
            recommender.keyword_matches_text("반도체 산업에 AI 기술 적용", "AI 반도체")
        )
        self.assertFalse(
            recommender.keyword_matches_text("차세대 반도체 생산 확대", "AI 반도체")
        )

    def test_separated_compound_match_suppresses_its_shorter_keyword(self) -> None:
        matches = recommender.strongest_keyword_matches(
            "AI용 차세대 반도체 개발",
            ["AI", "반도체", "AI 반도체"],
        )

        self.assertEqual(matches, ["ai 반도체"])

    def test_security_actor_normalizes_local_government_office_suffix(self) -> None:
        city = article("보령시, 방범 CCTV 154대 확충")
        city_hall = article("보령시청, AI CCTV 관제 시스템 도입")

        self.assertEqual(recommender.security_actor_key(city), "보령시")
        self.assertEqual(recommender.security_actor_key(city_hall), "보령시")

    def test_security_selects_only_one_article_per_actor(self) -> None:
        candidates = [
            (article("보령시, 방범 CCTV 154대 확충"), 0.9, {}),
            (article("보령시청, AI CCTV 관제 시스템 도입"), 0.85, {}),
            (article("영덕군, 통합관제센터 CCTV 확대"), 0.8, {}),
        ]
        with (
            patch.object(recommender, "reason_for", return_value="test"),
            patch.object(recommender, "is_similar_to_selected", return_value=False),
            patch.object(recommender, "redundancy_score", return_value=0.0),
        ):
            selected = recommender.mmr_select(
                candidates,
                quota=3,
                category=CATEGORY_SECURITY,
                lambda_value=0.7,
                already_selected=set(),
                selected_articles=[],
                selected_industry_companies=set(),
                selected_security_actors=set(),
            )

        self.assertEqual(
            [item.title for item in selected],
            ["보령시, 방범 CCTV 154대 확충", "영덕군, 통합관제센터 CCTV 확대"],
        )

    def test_innodep_entity_is_a_normalized_feature_not_an_additive_bonus(self) -> None:
        candidate = replace(article("이노뎁 신제품 발표"), seed_category=CATEGORY_INNODEP)
        weights = {
            "rule": 0.38,
            "recency": 0.0,
            "source": 0.0,
            "entity": 0.15,
            "language": 0.0,
            "semantic": 0.0,
            "seed": 0.05,
        }
        with (
            patch.object(recommender, "rule_score", return_value=0.8),
            patch.object(recommender, "entity_score", return_value=1.0),
            patch.object(recommender, "semantic_category_score", return_value=None),
        ):
            score, _ = recommender.relevance_score(
                candidate,
                CATEGORY_INNODEP,
                weights=weights,
                now=candidate.pub_date,
                timezone="UTC",
            )

        self.assertAlmostEqual(score, 0.869, places=4)
        self.assertLess(score, 1.0)

    def test_government_priority_is_an_eligibility_gate_not_a_score_bonus(self) -> None:
        candidate = replace(article("정부 AI 사업 추진"), seed_category=CATEGORY_GOVERNMENT)
        weights = {
            "rule": 0.8,
            "recency": 0.0,
            "source": 0.0,
            "entity": 0.0,
            "language": 0.0,
            "semantic": 0.0,
            "seed": 0.2,
        }
        with (
            patch.object(recommender, "rule_score", return_value=0.5),
            patch.object(recommender, "semantic_category_score", return_value=None),
            patch.object(recommender, "is_government_priority_article", return_value=True),
        ):
            score, _ = recommender.relevance_score(
                candidate,
                CATEGORY_GOVERNMENT,
                weights=weights,
                now=candidate.pub_date,
                timezone="UTC",
            )

        self.assertAlmostEqual(score, 0.6)

    def test_industry_accepts_company_product_and_core_technology(self) -> None:
        candidates = [
            article("구글, 국내 기업 겨냥 풀스택 AI 플랫폼 선보인다"),
            article("SK인텔릭스, 공공 로봇 실증사업 수주"),
            article("MS와 오픈AI, AI 동맹 전략 재편"),
            article("에스트래픽, AI 지능형교통 기술 실증"),
            article("스마트팩토리 액상 공정 AI 진단장비 개발"),
        ]

        for candidate in candidates:
            with self.subTest(title=candidate.title):
                self.assertTrue(
                    recommender.is_eligible_category_candidate(
                        candidate, CATEGORY_INDUSTRY, 0.8, {"rule": 0.5}, 0.5
                    )
                )

    def test_industry_accepts_generic_ai_without_business_action(self) -> None:
        candidates = [
            article("챗GPT·제미나이에 성·마약 질문하다 걸린 메타"),
            article("장애 청소년 AI 활용·취업 돕는 LG전자"),
            article("노벨상 수상자·AI 개발자 200여명, AI 충격 대비해야"),
        ]

        for candidate in candidates:
            with self.subTest(title=candidate.title):
                self.assertTrue(
                    recommender.is_eligible_category_candidate(
                        candidate, CATEGORY_INDUSTRY, 0.8, {"rule": 0.5}, 0.5
                    )
                )

    def test_industry_business_actions_are_not_standalone_score_keywords(self) -> None:
        business_actions = {"출시", "도입", "구축", "공급", "수주", "협력"}

        self.assertTrue(
            business_actions.isdisjoint(recommender.category_keywords(CATEGORY_INDUSTRY))
        )
        self.assertTrue(
            business_actions.isdisjoint(recommender.category_title_weights(CATEGORY_INDUSTRY))
        )

    def test_industry_still_rejects_noise_without_strong_topic(self) -> None:
        candidate = article("AI 테마주 주가 급등")

        self.assertFalse(
            recommender.is_eligible_category_candidate(
                candidate, CATEGORY_INDUSTRY, 0.8, {"rule": 0.5}, 0.5
            )
        )

        stock_candidate = article("대기업 투자 기대 커진 로봇주, 피지컬 AI 테마 상승")
        self.assertTrue(recommender.is_industry_noise(stock_candidate))

    def test_ai_mentioned_only_in_body_does_not_pass_centrality_gate(self) -> None:
        candidate = Article(
            title="오세훈 서울시장, 골목상권 정책 발표",
            description="본문에서 AI와 XR 산업을 함께 언급했다.",
            originallink="https://example.com/politics",
            link="",
            pub_date=datetime(2026, 7, 14, tzinfo=timezone.utc),
            query="AI 시장",
        )
        assessment = assess_industry_article(candidate, semantic_relevance=0.9)

        self.assertLess(assessment.centrality, 0.6)

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
            "rule": 0.65,
            "recency": 0.0,
            "source": 0.0,
            "entity": 0.0,
            "language": 0.0,
            "semantic": 0.35,
            "seed": 0.0,
        }
        with (
            patch.object(recommender, "rule_score", return_value=0.4),
            patch.object(recommender, "semantic_category_score", return_value=0.8),
            patch.object(
                recommender,
                "assess_industry_article",
                return_value=IndustryEditorialAssessment(
                    centrality=0.9,
                    importance=0.8,
                    promotionality=0.0,
                    intent="semiconductor_infra",
                    intent_label=INDUSTRY_INTENTS["semiconductor_infra"],
                    intent_score=0.85,
                    editorial_score=0.9,
                    intent_scores={},
                ),
            ),
        ):
            score, components = recommender.relevance_score(
                candidate,
                CATEGORY_INDUSTRY,
                weights=weights,
                now=candidate.pub_date,
                timezone="UTC",
            )

        self.assertAlmostEqual(components["base_score"], 0.54)
        self.assertAlmostEqual(score, 0.648)
        self.assertEqual(components["semantic"], 0.8)

    def test_industry_editorial_detects_ai_intent_and_importance(self) -> None:
        candidate = replace(
            article("엔비디아, 차세대 AI GPU 공개하고 데이터센터 생산 확대"),
            query="AI 반도체",
        )

        assessment = assess_industry_article(
            candidate,
            semantic_relevance=0.75,
            semantic_intent_scores={"semiconductor_infra": 0.86},
        )

        self.assertEqual(assessment.intent, "semiconductor_infra")
        self.assertGreaterEqual(assessment.centrality, 0.8)
        self.assertGreaterEqual(assessment.importance, 0.3)

    def test_industry_editorial_rejects_low_information_promotion(self) -> None:
        candidate = replace(article("AI 체험단 이벤트"), query="기업 AI")
        assessment = assess_industry_article(candidate, semantic_relevance=0.5)
        components = {
            "editorial_score": assessment.editorial_score,
            "centrality": assessment.centrality,
            "importance": assessment.importance,
            "promotionality": assessment.promotionality,
            "intent_score": assessment.intent_score,
        }

        self.assertFalse(
            recommender.is_eligible_category_candidate(
                candidate, CATEGORY_INDUSTRY, 0.8, components, 0.5
            )
        )

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
        service.industry_intent_references = {}
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

        service.industry_intent_references["semiconductor_infra"] = expected.reshape(1, -1)
        intent_scores = service.industry_intent_scores(candidate)
        self.assertAlmostEqual(intent_scores["semiconductor_infra"], 1.0, places=6)


class PipelineSemanticDeduplicationTests(unittest.TestCase):
    def test_later_category_is_evaluated_before_global_limit(self) -> None:
        security = replace(
            article("보안 후보", CATEGORY_SECURITY, "https://example.com/security-low"),
            score=0.6,
        )
        industry = replace(
            article("산업 후보", CATEGORY_INDUSTRY, "https://example.com/industry-high"),
            score=0.9,
        )
        config = SimpleNamespace(
            max_articles=1,
            category_quotas={},
            keyword_weights={},
            min_score=0.0,
            timezone="UTC",
            recommendation_weights={},
            mmr_lambda=0.7,
        )
        collected_categories: list[str] = []

        def collect_for_category(_config, category):
            collected_categories.append(category)
            return [security] if category == CATEGORY_SECURITY else [industry]

        def select_for_category(_articles, category, **_kwargs):
            return [security] if category == CATEGORY_SECURITY else [industry]

        with (
            patch.object(pipeline, "CATEGORY_ORDER", [CATEGORY_SECURITY, CATEGORY_INDUSTRY]),
            patch.object(
                pipeline,
                "category_ranges_from_quotas",
                return_value={CATEGORY_SECURITY: (0, 1), CATEGORY_INDUSTRY: (0, 1)},
            ),
            patch.object(pipeline, "collect_category_articles", side_effect=collect_for_category),
            patch.object(pipeline, "select_category_articles", side_effect=select_for_category),
            patch.object(pipeline, "is_semantic_duplicate", return_value=False),
        ):
            selected = pipeline.build_digest(config)

        self.assertEqual(collected_categories, [CATEGORY_SECURITY, CATEGORY_INDUSTRY])
        self.assertEqual([item.title for item in selected], [industry.title])

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
