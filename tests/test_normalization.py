from __future__ import annotations

from datetime import timezone
import unittest

from news_digest.normalization import normalize_title, normalize_url
from news_digest.timezones import get_timezone


class NormalizationTests(unittest.TestCase):
    def test_url_normalization_removes_tracking_parameters(self) -> None:
        normalized = normalize_url(
            "HTTPS://Example.COM/news/?id=7&utm_source=mail&utm_campaign=daily#section"
        )

        self.assertEqual(normalized, "https://example.com/news?id=7")

    def test_title_normalization_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_title("  AI\n  CCTV 출시  "), "ai cctv 출시")

    def test_utc_does_not_require_external_timezone_data(self) -> None:
        self.assertIs(get_timezone("UTC"), timezone.utc)


if __name__ == "__main__":
    unittest.main()
