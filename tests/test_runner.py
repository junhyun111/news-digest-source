from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from news_digest import runner
from news_digest.models import Article
from news_digest.runner import (
    article_from_dict,
    article_to_dict,
    render_industry_diagnostics,
    save_prepared_digest,
)


class RunnerSerializationTests(unittest.TestCase):
    def prepared_article(self) -> Article:
        return Article(
            title="AI 산업 기사",
            description="기사 설명",
            originallink="https://example.com/original",
            link="https://example.com/naver",
            pub_date=datetime(2026, 7, 16, 7, 0, tzinfo=timezone.utc),
            category="업계 동향 기사",
        )

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

    def test_dry_run_diagnostics_show_editorial_scores_and_rejection_reason(self) -> None:
        output = render_industry_diagnostics(
            [
                {
                    "title": "AI 반도체 기사",
                    "url": "https://example.com/1",
                    "decision": "탈락",
                    "reason": "산업 중요도 부족",
                    "score": 0.61,
                    "base_score": 0.7,
                    "editorial_score": 0.4,
                    "centrality": 0.9,
                    "importance": 0.2,
                    "intent_label": "반도체·인프라",
                    "intent_score": 0.8,
                }
            ]
        )

        self.assertIn("기존 70% + 편집 30%", output)
        self.assertIn("중심성 0.900", output)
        self.assertIn("중요도 0.200", output)
        self.assertIn("의도 반도체·인프라", output)
        self.assertIn("산업 중요도 부족", output)

    def test_send_prepared_deletes_json_after_successful_send(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prepared.json"
            save_prepared_digest(path, [self.prepared_article()])

            with (
                patch.object(runner.Config, "from_env", return_value=object()),
                patch.object(runner, "send_digest") as send_digest,
            ):
                exit_code = runner.run_digest(send_prepared=str(path))

            self.assertEqual(exit_code, 0)
            send_digest.assert_called_once()
            self.assertFalse(path.exists())

    def test_send_prepared_keeps_json_when_send_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prepared.json"
            save_prepared_digest(path, [self.prepared_article()])

            with (
                patch.object(runner.Config, "from_env", return_value=object()),
                patch.object(runner, "send_digest", side_effect=RuntimeError("SMTP failure")),
            ):
                exit_code = runner.run_digest(send_prepared=str(path))

            self.assertEqual(exit_code, 1)
            self.assertTrue(path.exists())
