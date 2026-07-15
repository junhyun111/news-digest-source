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

        self.assertIn(".hero-title{font-size:26px!important;line-height:33px!important}", html)
        self.assertIn(".article-cell{padding:10px 14px!important}", html)
        self.assertIn(".article-title{font-size:13px!important;line-height:20px!important}", html)
        self.assertIn('class="hero-title" style="margin-top:8px;font-size:32px;line-height:40px;', html)
        self.assertIn('class="article-cell" style="padding:17px 18px 14px;"', html)
        self.assertIn("font-size:14px;line-height:24px", html)


if __name__ == "__main__":
    unittest.main()
