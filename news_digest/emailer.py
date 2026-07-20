from __future__ import annotations

from datetime import datetime
from email.headerregistry import Address
from email.message import EmailMessage
from html import escape
import smtplib

from .categories import (
    CATEGORY_GOVERNMENT,
    CATEGORY_INDUSTRY,
    CATEGORY_INNODEP,
    CATEGORY_LABOR,
    CATEGORY_ORDER,
    CATEGORY_SECURITY,
    CATEGORY_VENTURE,
    source_name,
)
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


_CATEGORY_STYLES = {
    CATEGORY_INNODEP: ("이노뎁 소식", "#1D2545"),
    CATEGORY_SECURITY: ("보안 관련 기사", "#1D2545"),
    CATEGORY_INDUSTRY: ("업계 동향 기사", "#1D2545"),
    CATEGORY_GOVERNMENT: ("정부·공공 기사", "#1D2545"),
    CATEGORY_VENTURE: ("벤처·금융 기사", "#1D2545"),
    CATEGORY_LABOR: ("생산·임금 기사", "#1D2545"),
}


def render_digest_html(
    articles: list[Article],
    timezone: str = "Asia/Seoul",
    now: datetime | None = None,
) -> str:
    tz = get_timezone(timezone)
    localized_now = (now or datetime.now(tz)).astimezone(tz)
    grouped = {category: [] for category in CATEGORY_ORDER}
    for article in articles:
        grouped.setdefault(article.category, []).append(article)

    active_categories = [category for category in CATEGORY_ORDER if grouped.get(category)]
    category_summary = " · ".join(
        f"{_CATEGORY_STYLES[category][0]} {len(grouped[category])}건"
        for category in active_categories
    )
    if not category_summary:
        category_summary = "오늘 선별된 기사가 없습니다"

    parts = [
        "<!doctype html>",
        '<html lang="ko">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<style>",
        "@media only screen and (max-width:640px){.email-shell{width:100%!important}.outer-pad{padding:0!important}.hero-pad{padding:16px 18px!important}.content-pad{padding:10px 8px!important}.hero-kicker{font-size:9px!important;line-height:13px!important;letter-spacing:1.7px!important;font-weight:500!important}.hero-title{margin-top:4px!important;font-size:22px!important;line-height:28px!important;font-weight:600!important}.hero-date{margin-top:2px!important;font-size:10px!important;line-height:15px!important;font-weight:400!important}.hero-summary{margin-top:8px!important;font-size:11px!important;line-height:17px!important;font-weight:400!important}.category-section{margin-bottom:12px!important}.section-header-cell{padding:12px 14px 4px!important}.section-body-cell{padding:4px 10px 8px!important}.article-card{margin-bottom:7px!important}.article-card-last{margin-bottom:0!important}.article-cell{padding:8px 12px!important}.article-title{font-size:11px!important;line-height:17px!important;font-weight:600!important}.section-title{font-size:14px!important;line-height:20px!important;font-weight:700!important}.category-count{font-size:11px!important;line-height:16px!important;font-weight:600!important}}",
        "</style>",
        "</head>",
        '<body style="margin:0;padding:0;background-color:#f3f5f8;font-family:Arial,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;color:#141b2d;">',
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background-color:#f3f5f8;">',
        '<tr><td class="outer-pad" align="center" style="padding:28px 12px;">',
        '<table role="presentation" class="email-shell" width="760" cellspacing="0" cellpadding="0" border="0" style="width:760px;max-width:760px;background-color:#ffffff;border:1px solid #dfe5ed;box-shadow:0 8px 24px rgba(15,35,70,.10);">',
        '<tr><td class="hero-pad" bgcolor="#092653" style="padding:36px 48px 32px;background-color:#092653;background-image:linear-gradient(135deg,#123c7a 0%,#061b3d 100%);">',
        '<div class="hero-kicker" style="font-size:11px;line-height:18px;letter-spacing:2.2px;color:#69b8ff;font-weight:600;">INNODEP DAILY BRIEF</div>',
        '<div class="hero-title" style="margin-top:8px;font-size:32px;line-height:40px;letter-spacing:-.8px;color:#ffffff;font-weight:700;">TODAY NEWS BRIEF</div>',
        f'<div class="hero-date" style="margin-top:6px;font-size:12px;line-height:25px;color:#9dccff;font-weight:500;">{localized_now.year}년 {localized_now.month}월 {localized_now.day}일</div>',
        f'<div class="hero-summary" style="margin-top:16px;font-size:13px;line-height:21px;color:#b7d5f4;font-weight:400;">{escape(category_summary)}</div>',
        "</td></tr>",
        '<tr><td class="content-pad" style="padding:26px 28px 36px;background-color:#ffffff;">',
    ]

    if not articles:
        parts.append(
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            'style="width:100%;border:1px solid #e2e7ef;background-color:#fafbfd;">'
            '<tr><td align="center" style="padding:44px 20px;font-size:14px;line-height:23px;color:#667085;font-weight:400;">'
            '오늘 선별된 기사가 없습니다.</td></tr></table>'
        )

    for category in CATEGORY_ORDER:
        category_articles = grouped.get(category, [])
        if not category_articles:
            continue
        label, color = _CATEGORY_STYLES[category]
        parts.extend(
            [
                f'<table role="presentation" class="category-section" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;margin:0 0 22px;border:1px solid #dfe5ed;border-top:7px solid {color};background-color:#fbfcfe;">',
                '<tr><td class="section-header-cell" style="padding:22px 22px 8px;">',
                '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>',
                f'<td class="section-title" valign="middle" style="font-size:20px;line-height:28px;color:{color};font-weight:700;">{escape(label)}</td>',
                f'<td class="category-count" width="54" align="right" valign="middle" style="font-size:17px;line-height:25px;color:{color};font-weight:600;">{len(category_articles)}건</td>',
                "</tr></table>",
                "</td></tr>",
                '<tr><td class="section-body-cell" style="padding:8px 18px 18px;">',
            ]
        )
        for article_index, article in enumerate(category_articles):
            url = escape(article.canonical_url, quote=True)
            title = escape(article.title)
            card_class = "article-card article-card-last" if article_index == len(category_articles) - 1 else "article-card"
            parts.extend(
                [
                    f'<table role="presentation" class="{card_class}" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;margin:0 0 12px;border:1px solid #dfe3e8;background-color:#ffffff;">',
                    '<tr><td class="article-cell" style="padding:17px 18px 14px;">',
                    f'<div class="article-title" style="font-family:\'Malgun Gothic\',\'맑은 고딕\',Arial,sans-serif;font-size:14px;line-height:24px;letter-spacing:-.1px;font-weight:600;white-space:normal;overflow:visible;text-overflow:clip;word-break:keep-all;overflow-wrap:anywhere;"><a href="{url}" style="display:block;color:#141b2d;text-decoration:none;white-space:normal;overflow:visible;text-overflow:clip;">{title}</a></div>',
                    "</td></tr></table>",
                ]
            )
        parts.extend(["</td></tr></table>"])

    parts.extend(
        [
            "</td></tr>",
            "</table>",
            "</td></tr></table>",
            "</body>",
            "</html>",
        ]
    )
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
    message["From"] = Address(display_name="이노뎁 뉴스", addr_spec=config.mail_sender)
    message["To"] = ", ".join(recipients)
    message.set_content(render_digest(articles))
    message.add_alternative(render_digest_html(articles, timezone=config.timezone), subtype="html")

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(config.smtp_username, config.smtp_password)
        smtp.send_message(message)
