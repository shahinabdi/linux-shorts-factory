"""Daily and weekly YouTube Channel Intelligence reports."""
from datetime import date, timedelta
from .youtube import analytics_report, channel_info
from .telegram import _send_message


def _num(value) -> str:
    try:
        return f"{int(float(value or 0)):,}"
    except (TypeError, ValueError):
        return "—"


def _minutes(value) -> str:
    try:
        minutes = float(value or 0)
        hours, remainder = divmod(round(minutes), 60)
        return f"{hours}h {remainder:02d}m" if hours else f"{remainder}m"
    except (TypeError, ValueError):
        return "—"


def _sum_rows(report: dict) -> dict:
    headers = [h.get("name") for h in report.get("columnHeaders", [])]
    totals = {name: 0 for name in headers if name}
    for row in report.get("rows", []) or []:
        for name, value in zip(headers, row):
            if name in totals:
                try:
                    totals[name] += float(value)
                except (TypeError, ValueError):
                    pass
    return totals


async def _summary(start: date, end: date, title: str, comparison: tuple[date, date] | None = None):
    report = await analytics_report(start.isoformat(), end.isoformat(), dimensions="day", sort="day")
    totals = _sum_rows(report)
    if not report.get("rows"):
        return await _send_message(
            f"📊 {title}\n\nبرای بازه {start} تا {end} هنوز داده کامل از YouTube Analytics در دسترس نیست. "
            "چند ساعت بعد دوباره امتحان کن."
        )
    info = await channel_info()
    snippet = info.get("snippet", {})
    stats = info.get("statistics", {})
    name = snippet.get("title", "@shahinabdi")
    net_subs = totals.get("subscribersGained", 0) - totals.get("subscribersLost", 0)
    lines = [
        f"📊 {title} — {name}",
        f"🗓 بازه: {start} تا {end}",
        "",
        f"👁 بازدید: {_num(totals.get('views'))}",
        f"⏱ زمان تماشا: {_minutes(totals.get('estimatedMinutesWatched'))}",
        f"➕ مشترک جدید: {_num(totals.get('subscribersGained'))}",
        f"➖ لغو اشتراک: {_num(totals.get('subscribersLost'))}",
        f"📈 تغییر خالص مشترک: {net_subs:+,.0f}",
        f"👍 لایک: {_num(totals.get('likes'))}",
        f"💬 کامنت: {_num(totals.get('comments'))}",
    ]
    if stats.get("subscriberCount"):
        lines += ["", f"👥 تعداد فعلی مشترکان کانال: {_num(stats['subscriberCount'])}"]
    if comparison:
        prev_start, prev_end = comparison
        previous = _sum_rows(await analytics_report(prev_start.isoformat(), prev_end.isoformat(), dimensions="day", sort="day"))
        old_views = previous.get("views", 0)
        new_views = totals.get("views", 0)
        if old_views:
            change = (new_views - old_views) / old_views * 100
            lines += ["", f"📉 مقایسه بازدید با دوره قبل: {change:+.1f}%"]
    lines += [
        "",
        "ℹ️ داده‌ها از YouTube Analytics API هستند؛ برخی شاخص‌ها ممکن است با تأخیر منتشر شوند.",
        "نکته: CTR و retention در این نسخه گزارش نشده‌اند و در مرحله بعد با گزارش‌های سازگار اضافه می‌شوند.",
    ]
    return await _send_message("\n".join(lines))


async def send_daily_report():
    # Analytics data can lag; request a completed date two days behind local time.
    end = date.today() - timedelta(days=2)
    start = end
    return await _summary(start, end, "گزارش روزانه کانال")


async def send_weekly_report():
    # Seven completed days ending two days ago, compared with the prior seven.
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=6)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return await _summary(start, end, "گزارش هفتگی کانال", (prev_start, prev_end))
