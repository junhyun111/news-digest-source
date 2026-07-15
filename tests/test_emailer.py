from __future__ import annotations

from datetime import datetime, timezone
import unittest

from news_digest.categories import CATEGORY_INDUSTRY
from news_digest.emailer import render_digest_html
from news_digest.models import Article


class MobileEmailLayoutTests(unittest.TestCase):
    def test_mobile_styles_are_compact_without_changing_desktop_values(self) -> None:
        article = Article(
            title="AI 산업 기사",
            description="설명",
            originallink="https://example.com/article",
            link="",
            pub_date=datetime(2026, 7, 15, tzinfo=timezone.utc),
            category=CATEGORY_INDUSTRY,
        )

        html = render_digest_html([article], timezone="UTC", now=article.pub_date)

        self.assertIn(".hero-pad{padding:16px 18px!important}", html)
        self.assertIn(
            ".hero-title{margin-top:4px!important;font-size:22px!important;line-height:28px!important;font-weight:600!important}",
            html,
        )
        self.assertIn(".hero-summary{margin-top:8px!important;font-size:11px!important;line-height:17px!important;font-weight:400!important}", html)
        self.assertIn(".section-header-cell{padding:12px 14px 4px!important}", html)
        self.assertIn(".section-body-cell{padding:4px 10px 8px!important}", html)
        self.assertIn(".article-card-last{margin-bottom:0!important}", html)
        self.assertIn(".article-cell{padding:8px 12px!important}", html)
        self.assertIn(
            ".article-title{font-size:11px!important;line-height:17px!important;font-weight:600!important}",
            html,
        )
        self.assertIn(
            ".section-title{font-size:14px!important;line-height:20px!important;font-weight:700!important}",
            html,
        )
        self.assertIn(
            ".category-count{font-size:11px!important;line-height:16px!important;font-weight:600!important}",
            html,
        )
        self.assertIn('class="category-count"', html)
        self.assertIn('class="category-section"', html)
        self.assertIn('class="article-card article-card-last"', html)
        self.assertIn('class="hero-title" style="margin-top:8px;font-size:32px;line-height:40px;', html)
        self.assertIn('class="article-cell" style="padding:17px 18px 14px;"', html)
        self.assertIn("font-size:14px;line-height:24px", html)


if __name__ == "__main__":
    unittest.main()
