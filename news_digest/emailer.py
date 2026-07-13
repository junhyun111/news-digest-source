from __future__ import annotations

from datetime import datetime
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
    CATEGORY_INNODEP: ("이노뎁 소식", "IN", "#6d28d9", "#f3e8ff"),
    CATEGORY_SECURITY: ("보안 관련 기사", "S", "#1557d6", "#e8f1ff"),
    CATEGORY_INDUSTRY: ("업계 동향", "AI", "#0796a5", "#e1f7f8"),
    CATEGORY_GOVERNMENT: ("정부·공공", "G", "#2563a6", "#e8f2fb"),
    CATEGORY_VENTURE: ("벤처·금융", "V", "#b7791f", "#fff6db"),
    CATEGORY_LABOR: ("생산·임금", "L", "#c2415d", "#ffedf1"),
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
        "@media only screen and (max-width:640px){.email-shell{width:100%!important}.outer-pad{padding:0!important}.hero-pad{padding:34px 24px!important}.content-pad{padding:18px 12px!important}.article-title{font-size:17px!important}.section-title{font-size:22px!important}}",
        "</style>",
        "</head>",
        '<body style="margin:0;padding:0;background-color:#f3f5f8;font-family:Arial,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;color:#141b2d;">',
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background-color:#f3f5f8;">',
        '<tr><td class="outer-pad" align="center" style="padding:28px 12px;">',
        '<table role="presentation" class="email-shell" width="680" cellspacing="0" cellpadding="0" border="0" style="width:680px;max-width:680px;background-color:#ffffff;border-radius:22px;overflow:hidden;box-shadow:0 10px 34px rgba(15,35,70,.12);">',
        '<tr><td class="hero-pad" bgcolor="#092653" style="padding:48px 48px 42px;background-color:#092653;background-image:linear-gradient(135deg,#123c7a 0%,#061b3d 100%);">',
        '<div style="font-size:13px;line-height:20px;letter-spacing:2.4px;color:#69b8ff;font-weight:700;">INNODEP DAILY BRIEF</div>',
        '<div style="margin-top:10px;font-size:38px;line-height:46px;letter-spacing:-1px;color:#ffffff;font-weight:800;">AI NEWS BRIEF</div>',
        f'<div style="margin-top:8px;font-size:20px;line-height:30px;color:#9dccff;font-weight:600;">{localized_now.year}년 {localized_now.month}월 {localized_now.day}일</div>',
        '<div style="width:34px;height:4px;margin:24px 0 20px;background-color:#5ab5ff;border-radius:4px;"></div>',
        f'<div style="font-size:22px;line-height:32px;color:#ffffff;font-weight:700;">오늘의 주요 뉴스 <span style="font-size:32px;color:#8bc8ff;">{len(articles)}</span>건</div>',
        f'<div style="margin-top:9px;font-size:14px;line-height:23px;color:#b7d5f4;">{escape(category_summary)}</div>',
        "</td></tr>",
        '<tr><td class="content-pad" style="padding:26px 28px 36px;background-color:#ffffff;">',
    ]

    if not articles:
        parts.append(
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            'style="width:100%;border:1px solid #e2e7ef;border-radius:14px;background-color:#fafbfd;">'
            '<tr><td align="center" style="padding:44px 20px;font-size:16px;line-height:26px;color:#667085;">'
            '오늘 선별된 기사가 없습니다.</td></tr></table>'
        )

    for category in CATEGORY_ORDER:
        category_articles = grouped.get(category, [])
        if not category_articles:
            continue
        label, icon, color, pale_color = _CATEGORY_STYLES[category]
        parts.extend(
            [
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;margin:0 0 22px;border:1px solid #dfe5ed;border-top:7px solid {color};border-radius:14px;background-color:#fbfcfe;">',
                '<tr><td style="padding:22px 22px 8px;">',
                '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>',
                f'<td valign="middle"><span style="display:inline-block;min-width:34px;padding:7px 5px;border-radius:10px;background-color:{color};color:#ffffff;font-size:14px;line-height:18px;text-align:center;font-weight:800;">{icon}</span> '
                f'<span class="section-title" style="margin-left:8px;font-size:25px;line-height:32px;color:{color};font-weight:800;">{escape(label)}</span></td>',
                f'<td width="54" align="right" valign="middle" style="font-size:21px;line-height:28px;color:{color};font-weight:800;">{len(category_articles)}건</td>',
                "</tr></table>",
                "</td></tr>",
                '<tr><td style="padding:8px 18px 18px;">',
            ]
        )
        for article in category_articles:
            url = escape(article.canonical_url, quote=True)
            title = escape(article.title)
            source = escape(source_name(article))
            parts.extend(
                [
                    '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;margin:0 0 12px;border:1px solid #dfe3e8;border-radius:12px;background-color:#ffffff;">',
                    '<tr><td style="padding:17px 18px 14px;">',
                    f'<span style="display:inline-block;padding:4px 11px;border-radius:20px;background-color:{pale_color};color:{color};font-size:12px;line-height:18px;font-weight:700;">{escape(label)}</span>',
                    f'<div class="article-title" style="margin-top:9px;font-size:19px;line-height:28px;letter-spacing:-.2px;font-weight:700;"><a href="{url}" style="color:#141b2d;text-decoration:none;">{title}</a></div>',
                    '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;margin-top:13px;border-top:1px solid #e6e9ee;"><tr>',
                    f'<td style="padding-top:11px;font-size:13px;line-height:20px;color:#7a8290;">{source}</td>',
                    f'<td align="right" style="padding-top:11px;font-size:14px;line-height:20px;font-weight:700;"><a href="{url}" style="color:{color};text-decoration:none;">읽기&nbsp; →</a></td>',
                    "</tr></table>",
                    "</td></tr></table>",
                ]
            )
        parts.extend(["</td></tr></table>"])

    parts.extend(
        [
            '<div style="padding:4px 10px 0;text-align:center;font-size:12px;line-height:20px;color:#98a1b0;">이 메일은 이노뎁 뉴스 다이제스트에서 자동 발송되었습니다.</div>',
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
    message["From"] = config.mail_sender
    message["To"] = ", ".join(recipients)
    message.set_content(render_digest(articles))
    message.add_alternative(render_digest_html(articles, timezone=config.timezone), subtype="html")

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(config.smtp_username, config.smtp_password)
        smtp.send_message(message)
