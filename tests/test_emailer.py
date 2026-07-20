from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from news_digest.categories import CATEGORY_INDUSTRY
from news_digest.emailer import render_digest_html, send_digest
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


class EmailSenderTests(unittest.TestCase):
    @patch("news_digest.emailer.smtplib.SMTP")
    def test_sender_has_innodep_news_display_name(self, smtp_class) -> None:
        config = SimpleNamespace(
            test_mode=True,
            recipients=["recipient@example.com"],
            test_recipients=["recipient@example.com"],
            real_recipients=[],
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="sender@example.com",
            smtp_password="password",
            mail_sender="sender@example.com",
            timezone="Asia/Seoul",
        )

        send_digest(config, [])

        smtp = smtp_class.return_value.__enter__.return_value
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["From"].addresses[0].display_name, "이노뎁 뉴스")
        self.assertEqual(message["From"].addresses[0].addr_spec, "sender@example.com")


if __name__ == "__main__":
    unittest.main()
