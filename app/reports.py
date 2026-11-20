"""Daily and weekly YouTube Channel Intelligence reports."""
from datetime import date, timedelta

from .youtube import analytics_report, channel_info
from .youtube_content import top_videos, recent_shorts, latest_long_video
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


def _date_label(value: str) -> str:
    return value[:10] if value else "تاریخ نامشخص"


def _video_line(index: int, video: dict, short: bool = False) -> str:
    title = video.get("title", "بدون عنوان").replace("\n", " ").strip()
    if len(title) > 75:
        title = title[:72] + "..."
    views = _num(video.get("views"))
    avg = video.get("averageViewPercentage")
    retention = f" | میانگین تماشا: {float(avg):.1f}%" if avg not in (None, "") else ""
    label = "Short" if short else "ویدیو"
    return f"{index}. {title}\n   👁 {views}{retention}\n   {video.get('url', '')}"


async def _send_content_sections(start: date, end: date):
    # Each section is sent separately to stay below Telegram's 4096-char limit.
    try:
        videos = await top_videos(start, end, limit=5)
        if videos:
            lines = [f"🏆 ۵ ویدیوی برتر ({start} تا {end})"]
            lines.extend(_video_line(i, video) for i, video in enumerate(videos, 1))
            await _send_message("\n\n".join(lines))
        else:
            await _send_message("🏆 در این بازه ویدیویی با داده قابل‌نمایش پیدا نشد.")
    except Exception as exc:
        await _send_message(f"⚠️ دریافت ۵ ویدیوی برتر ناموفق بود ({type(exc).__name__}).")

    try:
        shorts = await top_videos(start, end, content_type="SHORTS", limit=5)
        if shorts:
            lines = [f"🔥 ۵ شورت برتر ({start} تا {end})"]
            lines.extend(_video_line(i, video, short=True) for i, video in enumerate(shorts, 1))
            await _send_message("\n\n".join(lines))
        else:
            await _send_message("🔥 در این بازه شورت دارای داده آماری پیدا نشد.")
    except Exception as exc:
        await _send_message(f"⚠️ دریافت شورت‌های برتر ناموفق بود ({type(exc).__name__}).")

    try:
        shorts = await recent_shorts(5)
        if shorts:
            lines = ["🔥 ۵ شورت برتر ۲۸ روز اخیر"]
            for i, video in enumerate(shorts, 1):
                lines.append(
                    f"{i}. {video['title'][:75]}\n"
                    f"   📅 {_date_label(video.get('published_at', ''))} | 👁 {_num(video.get('views'))}\n"
                    f"   {video['url']}"
                )
            await _send_message("\n\n".join(lines))
        else:
            await _send_message("🆕 شورت اخیر قابل‌تشخیصی در داده‌های Analytics پیدا نشد.")
    except Exception as exc:
        await _send_message(f"⚠️ دریافت شورت‌های اخیر ناموفق بود ({type(exc).__name__}).")

    try:
        video = await latest_long_video()
        if video:
            await _send_message(
                "🎬 آخرین ویدیوی بلند\n\n"
                f"{video['title']}\n"
                f"📅 {_date_label(video.get('published_at', ''))}\n"
                f"👁 بازدید در ۲۸ روز اخیر: {_num(video.get('views'))}\n"
                f"📊 میانگین درصد تماشا: "
                f"{float(video['averageViewPercentage']):.1f}%\n"
                f"{video['url']}"
            )
        else:
            await _send_message("🎬 ویدیوی بلند اخیر با داده Analytics پیدا نشد.")
    except Exception as exc:
        await _send_message(f"⚠️ دریافت آخرین ویدیوی بلند ناموفق بود ({type(exc).__name__}).")


async def _summary(start: date, end: date, title: str,
                   comparison: tuple[date, date] | None = None):
    report = await analytics_report(
        start.isoformat(), end.isoformat(), dimensions="day", sort="day"
    )
    totals = _sum_rows(report)
    info = await channel_info()
    snippet = info.get("snippet", {})
    stats = info.get("statistics", {})
    name = snippet.get("title", "YouTube channel")
    net_subs = totals.get("subscribersGained", 0) - totals.get("subscribersLost", 0)

    if not report.get("rows"):
        lines = [
            f"📊 {title} — {name}",
            f"🗓 بازه: {start} تا {end}",
            "",
            "هنوز داده روزانه برای این بازه از YouTube Analytics دریافت نشده است.",
            "ممکن است انتشار آمار با تأخیر انجام شود؛ بخش ویدیوها در ادامه جداگانه بررسی می‌شود.",
        ]
    else:
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
        lines += ["", f"👥 تعداد فعلی مشترکان: {_num(stats['subscriberCount'])}"]
    if comparison:
        prev_start, prev_end = comparison
        previous = _sum_rows(await analytics_report(
            prev_start.isoformat(), prev_end.isoformat(), dimensions="day", sort="day"
        ))
        old_views = previous.get("views", 0)
        new_views = totals.get("views", 0)
        if old_views:
            change = (new_views - old_views) / old_views * 100
            lines += ["", f"📉 تغییر بازدید نسبت به دوره قبل: {change:+.1f}%"]
        else:
            lines += ["", "📉 داده کافی برای مقایسه بازدید با دوره قبل وجود ندارد."]
    lines += [
        "",
        "ℹ️ داده‌ها از YouTube Analytics و YouTube Data API دریافت می‌شوند.",
        "Retention در صورت پشتیبانی گزارش برای هر ویدیو نمایش داده می‌شود؛ CTR در این نسخه اضافه نشده است.",
    ]
    await _send_message("\n".join(lines))
    insight_start = end - timedelta(days=6)
    await _send_content_sections(insight_start, end)


async def send_daily_report():
    # YouTube Analytics data may lag; use a completed day two days behind.
    end = date.today() - timedelta(days=2)
    start = end
    # Daily overview, with top content ranked over the last seven completed days.
    await _summary(start, end, "گزارش روزانه کانال")


async def send_weekly_report():
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=6)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    await _summary(start, end, "گزارش هفتگی کانال", (prev_start, prev_end))



async def send_top_report():
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=27)
    videos = await top_videos(start, end, limit=5)
    if not videos:
        return await _send_message("🏆 در ۲۸ روز اخیر ویدیویی با داده آماری پیدا نشد.")
    lines = [f"🏆 پنج ویدیوی برتر کانال | {start} تا {end}"]
    lines.extend(_video_line(i, video) for i, video in enumerate(videos, 1))
    return await _send_message("\n\n".join(lines))


async def send_recent_shorts_report():
    shorts = await recent_shorts(5)
    if not shorts:
        return await _send_message("🆕 شورت اخیر قابل‌تشخیصی در داده‌های Analytics پیدا نشد.")
    lines = ["🔥 پنج شورت برتر ۲۸ روز اخیر"]
    for i, video in enumerate(shorts, 1):
        avg = video.get("averageViewPercentage")
        retention = f" | میانگین درصد تماشا: {float(avg):.1f}%" if avg not in (None, "") else ""
        lines.append(
            f"{i}. {video['title'][:75]}\n"
            f"   📅 {_date_label(video.get('published_at', ''))} | 👁 {_num(video.get('views'))}{retention}\n"
            f"   {video['url']}"
        )
    return await _send_message("\n\n".join(lines))


async def send_compare_report():
    """Compare the latest 7 complete Analytics days with the previous 7."""
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=6)
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    metrics = "views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes,comments"
    current = _sum_rows(await analytics_report(
        start.isoformat(), end.isoformat(), dimensions="day", metrics=metrics, sort="day"
    ))
    previous = _sum_rows(await analytics_report(
        previous_start.isoformat(), previous_end.isoformat(),
        dimensions="day", metrics=metrics, sort="day"
    ))
    labels = [
        ("بازدید", "views"), ("زمان تماشا (دقیقه)", "estimatedMinutesWatched"),
        ("مشترک جدید", "subscribersGained"), ("لایک", "likes"), ("کامنت", "comments"),
    ]
    lines = ["⚖️ مقایسه عملکرد کانال", f"دوره جدید: {start} تا {end}",
             f"دوره قبل: {previous_start} تا {previous_end}", ""]
    for label, key in labels:
        new = float(current.get(key, 0) or 0)
        old = float(previous.get(key, 0) or 0)
        change = f"{(new-old)/old*100:+.1f}%" if old else ("—" if not new else "دوره قبل صفر")
        lines.append(f"{label}: {_num(new)} در برابر {_num(old)} ({change})")
    new_net = current.get("subscribersGained", 0) - current.get("subscribersLost", 0)
    old_net = previous.get("subscribersGained", 0) - previous.get("subscribersLost", 0)
    lines += ["", f"📈 رشد خالص مشترک: {new_net:+,.0f} در برابر {old_net:+,.0f}"]
    return await _send_message("\n".join(lines))


async def send_growth_report():
    """Show daily subscriber gains/losses and net growth for 14 complete days."""
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=13)
    report = await analytics_report(
        start.isoformat(), end.isoformat(), dimensions="day",
        metrics="subscribersGained,subscribersLost,views", sort="day", max_results=20,
    )
    headers = [h.get("name") for h in report.get("columnHeaders", [])]
    rows = [dict(zip(headers, row)) for row in report.get("rows", []) or []]
    if not rows:
        return await _send_message("📈 برای بازه رشد مشترکان داده‌ای از YouTube Analytics دریافت نشد.")
    gained = sum(float(row.get("subscribersGained") or 0) for row in rows)
    lost = sum(float(row.get("subscribersLost") or 0) for row in rows)
    views = sum(float(row.get("views") or 0) for row in rows)
    lines = ["📈 گزارش رشد کانال — ۱۴ روز کامل", f"بازه: {start} تا {end}",
             f"مشترک جدید: {_num(gained)}", f"لغو اشتراک: {_num(lost)}",
             f"رشد خالص: {gained-lost:+,.0f}", f"بازدید: {_num(views)}", "",
             "روند روزانه (➕ جدید / ➖ لغو):"]
    for row in rows[-14:]:
        lines.append(f"{str(row.get('day', ''))}: +{_num(row.get('subscribersGained'))} / -{_num(row.get('subscribersLost'))}")
    return await _send_message("\n".join(lines))


async def send_engagement_report():
    """Summarize likes, comments and interaction rate over 28 complete days."""
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=27)
    report = await analytics_report(
        start.isoformat(), end.isoformat(), dimensions="day",
        metrics="views,likes,comments,estimatedMinutesWatched", sort="day", max_results=35,
    )
    totals = _sum_rows(report)
    views = float(totals.get("views", 0) or 0)
    likes = float(totals.get("likes", 0) or 0)
    comments = float(totals.get("comments", 0) or 0)
    interactions = likes + comments
    rate = interactions / views * 100 if views else 0
    return await _send_message(
        "💬 گزارش تعامل مخاطبان — ۲۸ روز کامل\n"
        f"بازه: {start} تا {end}\n\n"
        f"👁 بازدید: {_num(views)}\n👍 لایک: {_num(likes)}\n"
        f"💬 کامنت: {_num(comments)}\n🤝 مجموع تعامل ثبت‌شده: {_num(interactions)}\n"
        f"📊 نرخ تعامل ساده (لایک + کامنت ÷ بازدید): {rate:.2f}%\n"
        f"⏱ زمان تماشا: {_minutes(totals.get('estimatedMinutesWatched'))}\n\n"
        "این نرخ، شاخص ساده تعامل است و با نرخ تعامل رسمی YouTube یکسان نیست."
    )
