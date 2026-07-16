from __future__ import annotations

from datetime import datetime
import unittest

from news_digest.filters import is_in_recommendation_range, recommendation_range
from news_digest.models import Article
from news_digest.timezones import get_timezone


def article_at(pub_date: datetime) -> Article:
    return Article(
        title="테스트 기사",
        description="",
        originallink="https://example.com/article",
        link="",
        pub_date=pub_date,
    )


class RecommendationRangeTests(unittest.TestCase):
    def test_regular_day_uses_previous_day_7am_to_current_day_7am(self) -> None:
        tz = get_timezone("Asia/Seoul")
        now = datetime(2026, 7, 16, 11, 30, tzinfo=tz)

        start, end = recommendation_range(now=now)

        self.assertEqual(start, datetime(2026, 7, 15, 7, 0, tzinfo=tz))
        self.assertEqual(end, datetime(2026, 7, 16, 7, 0, tzinfo=tz))

    def test_monday_uses_friday_7am_to_monday_7am(self) -> None:
        tz = get_timezone("Asia/Seoul")
        now = datetime(2026, 7, 20, 8, 0, tzinfo=tz)

        start, end = recommendation_range(now=now)

        self.assertEqual(start, datetime(2026, 7, 17, 7, 0, tzinfo=tz))
        self.assertEqual(end, datetime(2026, 7, 20, 7, 0, tzinfo=tz))

    def test_start_is_exclusive_and_end_is_inclusive(self) -> None:
        tz = get_timezone("Asia/Seoul")
        now = datetime(2026, 7, 16, 8, 0, tzinfo=tz)
        start = datetime(2026, 7, 15, 7, 0, tzinfo=tz)
        end = datetime(2026, 7, 16, 7, 0, tzinfo=tz)

        self.assertFalse(is_in_recommendation_range(article_at(start), now=now))
        self.assertTrue(is_in_recommendation_range(article_at(end), now=now))


if __name__ == "__main__":
    unittest.main()
