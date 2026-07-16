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
DRY_RUN_REJECTION_DETAIL_LIMIT = 50


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


def render_industry_diagnostics(diagnostics: list[dict[str, object]]) -> str:
    if not diagnostics:
        return "\n[업계동향 추천 진단]\n진단 후보가 없습니다."

    by_url: dict[str, dict[str, object]] = {}
    for item in diagnostics:
        key = str(item.get("url") or item.get("title"))
        previous = by_url.get(key)
        if previous is None or item.get("decision") == "선정":
            by_url[key] = item

    selected = [item for item in by_url.values() if item.get("decision") == "선정"]
    rejected = [item for item in by_url.values() if item.get("decision") != "선정"]
    selected.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    rejected.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)

    lines = [
        "",
        "[업계동향 추천 진단]",
        f"후보 {len(by_url)}건 / 선정 {len(selected)}건 / 탈락 {len(rejected)}건",
        "점수 = 기존 70% + 편집 30%",
    ]
    for heading, items in (
        ("선정", selected),
        (f"탈락 상위 {min(len(rejected), DRY_RUN_REJECTION_DETAIL_LIMIT)}건", rejected[:DRY_RUN_REJECTION_DETAIL_LIMIT]),
    ):
        lines.append(f"\n- {heading}")
        for item in items:
            lines.append(
                "  "
                f"[{item.get('decision')}] {item.get('title')} | "
                f"최종 {float(item.get('score', 0.0)):.3f} "
                f"(기존 {float(item.get('base_score', 0.0)):.3f}, "
                f"편집 {float(item.get('editorial_score', 0.0)):.3f}) | "
                f"중심성 {float(item.get('centrality', 0.0)):.3f} | "
                f"중요도 {float(item.get('importance', 0.0)):.3f} | "
                f"의도 {item.get('intent_label') or '-'} "
                f"{float(item.get('intent_score', 0.0)):.3f} | "
                f"사유: {item.get('reason')}"
            )
    if len(rejected) > DRY_RUN_REJECTION_DETAIL_LIMIT:
        lines.append(
            f"\n  나머지 탈락 {len(rejected) - DRY_RUN_REJECTION_DETAIL_LIMIT}건은 생략했습니다."
        )
    return "\n".join(lines)


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
            prepared_path = Path(send_prepared)
            articles = load_prepared_digest(prepared_path)
            send_digest(config, articles)
            prepared_path.unlink()
            LOGGER.info("Sent %s prepared articles", len(articles))
            LOGGER.info("Deleted sent prepared digest: %s", prepared_path)
            return 0

        diagnostics: list[dict[str, object]] = []
        articles = build_digest(config, diagnostic_sink=diagnostics.append if dry_run else None)
        if prepare_output:
            save_prepared_digest(prepare_output, articles)
            LOGGER.info("Prepared %s articles at %s", len(articles), prepare_output)
            return 0
        if dry_run:
            print(render_digest(articles))
            print(render_industry_diagnostics(diagnostics))
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
