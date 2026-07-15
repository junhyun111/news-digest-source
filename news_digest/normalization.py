from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def normalize_url(url: str) -> str:
    split = urlsplit(url.strip())
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(split.query, keep_blank_values=True)
            if key not in TRACKING_PARAMS
        ]
    )
    path = split.path.rstrip("/") or split.path
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), path, query, ""))


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()
