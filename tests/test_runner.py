from __future__ import annotations

from datetime import datetime, timezone
import unittest

from news_digest.models import Article
from news_digest.runner import article_from_dict, article_to_dict


class RunnerSerializationTests(unittest.TestCase):
    def test_article_round_trip_preserves_prepared_digest_fields(self) -> None:
        original = Article(
            title="AI 산업 기사",
            description="기사 설명",
            originallink="https://example.com/original",
            link="https://example.com/naver",
            pub_date=datetime(2026, 7, 16, 7, 0, tzinfo=timezone.utc),
            query="AI 산업",
            seed_category="업계 동향 기사",
            score=0.91,
            category="업계 동향 기사",
            reason="핵심 기술 관련",
        )

        restored = article_from_dict(article_to_dict(original))

        self.assertEqual(restored, original)
