from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import sys

from .config import Config
from .emailer import render_digest, send_digest
from .models import Article
from .pipeline import build_digest


LOGGER = logging.getLogger(__name__)


def configure_console(verbose: bool = False) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def article_to_dict(article: Article) -> dict[str, object]:
    return {
        "title": article.title,
        "description": article.description,
        "originallink": article.originallink,
        "link": article.link,
        "pub_date": article.pub_date.isoformat(),
        "query": article.query,
        "seed_category": article.seed_category,
        "score": article.score,
        "category": article.category,
        "reason": article.reason,
    }


def article_from_dict(data: dict[str, object]) -> Article:
    return Article(
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        originallink=str(data.get("originallink", "")),
        link=str(data.get("link", "")),
        pub_date=datetime.fromisoformat(str(data["pub_date"])),
        query=str(data.get("query", "")),
        seed_category=str(data.get("seed_category", "")),
        score=float(data.get("score", 0.0)),
        category=str(data.get("category", "")),
        reason=str(data.get("reason", "")),
    )


def save_prepared_digest(path: str | Path, articles: list[Article]) -> None:
    payload = [article_to_dict(article) for article in articles]
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_prepared_digest(path: str | Path) -> list[Article]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Prepared digest file must contain a list of articles.")
    return [article_from_dict(item) for item in payload]


def run_digest(
    *,
    dry_run: bool = False,
    prepare_output: str | None = None,
    send_prepared: str | None = None,
    verbose: bool = False,
) -> int:
    """Collect, select, render, or send a digest for the local CLI."""
    configure_console(verbose)

    try:
        if prepare_output and send_prepared:
            raise ValueError("--prepare-output and --send-prepared cannot be used together.")

        config = Config.from_env()
        if send_prepared:
            articles = load_prepared_digest(send_prepared)
            send_digest(config, articles)
            LOGGER.info("Sent %s prepared articles", len(articles))
            return 0

        articles = build_digest(config)
        if prepare_output:
            save_prepared_digest(prepare_output, articles)
            LOGGER.info("Prepared %s articles at %s", len(articles), prepare_output)
            return 0
        if dry_run:
            print(render_digest(articles))
            return 0

        send_digest(config, articles)
        LOGGER.info("Sent %s articles", len(articles))
        return 0
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user")
        return 130
    except Exception:
        LOGGER.exception("News digest run failed")
        return 1
