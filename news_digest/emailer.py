from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from html import escape
import smtplib

from .categories import CATEGORY_ORDER, source_name
from .config import Config
from .models import Article
from .timezones import get_timezone


def render_digest(articles: list[Article]) -> str:
    if not articles:
        return "\uc120\ubcc4\ub41c \uae30\uc0ac\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."

    lines: list[str] = []
    grouped = {category: [] for category in CATEGORY_ORDER}
    for article in articles:
        grouped.setdefault(article.category, []).append(article)

    for category in CATEGORY_ORDER:
        category_articles = grouped.get(category, [])
        if not category_articles:
            continue
        lines.extend([f"\u25cb {category}", ""])
        for article in category_articles:
            url = article.canonical_url
            source = source_name(article)
            lines.extend([f"[{article.title}]({url})  [[{source}]]({url})", ""])

    return "\n".join(lines).rstrip()


def render_digest_html(articles: list[Article]) -> str:
    if not articles:
        return "<p>선별된 기사가 없습니다.</p>"

    parts = [
        "<!doctype html>",
        '<html lang="ko">',
        "<body>",
    ]
    grouped = {category: [] for category in CATEGORY_ORDER}
    for article in articles:
        grouped.setdefault(article.category, []).append(article)

    for category in CATEGORY_ORDER:
        category_articles = grouped.get(category, [])
        if not category_articles:
            continue
        parts.append(f'<h3 style="margin:24px 0 12px;">○ {escape(category)}</h3>')
        parts.append('<ul style="margin:0 0 20px 0;padding-left:22px;">')
        for article in category_articles:
            url = escape(article.canonical_url, quote=True)
            title = escape(article.title)
            source = escape(source_name(article))
            parts.append(
                '<li style="margin:0 0 14px 0;line-height:1.55;">'
                f'<a href="{url}" style="color:#0b57d0;text-decoration:underline;font-size:17px;">{title}</a> '
                f'<a href="{url}" style="color:#555;text-decoration:none;font-size:14px;">[[{source}]]</a>'
                '</li>'
            )
        parts.append("</ul>")

    parts.extend(["</body>", "</html>"])
    return "\n".join(parts)


def validate_recipients(config: Config) -> list[str]:
    recipients = config.recipients
    if config.test_mode:
        real = set(config.real_recipients)
        overlap = real.intersection(recipients)
        if overlap:
            raise RuntimeError("TEST_MODE=true cannot send to REAL_RECIPIENTS.")
        if not recipients:
            raise RuntimeError("TEST_MODE=true requires TEST_RECIPIENTS.")
    elif not recipients:
        raise RuntimeError("REAL_RECIPIENTS is required.")
    return recipients


def build_subject(timezone: str = "Asia/Seoul", now: datetime | None = None) -> str:
    tz = get_timezone(timezone)
    localized_now = (now or datetime.now(tz)).astimezone(tz)
    return f"[이노뎁] {localized_now.month}월 {localized_now.day}일 오늘의 뉴스"


def send_digest(config: Config, articles: list[Article]) -> None:
    recipients = validate_recipients(config)
    if not all([config.smtp_host, config.smtp_username, config.smtp_password, config.mail_sender]):
        raise RuntimeError("SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and MAIL_SENDER are required.")

    message = EmailMessage()
    message["Subject"] = build_subject(config.timezone)
    message["From"] = config.mail_sender
    message["To"] = ", ".join(recipients)
    message.set_content(render_digest(articles))
    message.add_alternative(render_digest_html(articles), subtype="html")

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(config.smtp_username, config.smtp_password)
        smtp.send_message(message)
