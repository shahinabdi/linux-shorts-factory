import asyncio
import logging
import secrets
import uuid
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Header, HTTPException

from .models import Story, StoryIn, Status, TopicStatus
from .store import (put, get, update, all_stories, get_topic,
                    update_topic, all_topics)
from .telegram import (
    send_script_for_approval,
    send_selected_topic,
    send_selected_topics,
    send_control_panel,
    send_research_summary,
    send_gpt_brief,
    answer_callback_query,
    _send_message,
)
from .config import settings
from .research import run_daily_research
from .youtube_routes import router as youtube_router
from .reports import (send_daily_report, send_weekly_report, send_top_report, send_recent_shorts_report, send_compare_report, send_growth_report, send_engagement_report)
from .youtube import channel_info

logging.basicConfig(level=logging.INFO)

# Telegram API URLs contain the bot token. Never log HTTPX request URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
app = FastAPI(title="YouTube Channel Intelligence", version="0.5.0")
app.include_router(youtube_router)
scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.schedule_timezone))
research_lock = asyncio.Lock()
report_lock = asyncio.Lock()


async def execute_research(trigger: str = "manual"):
    if research_lock.locked():
        return {"topic_count": 0, "already_running": True}
    async with research_lock:
        result = await run_daily_research()
        await send_research_summary(result, trigger=trigger)
        return result


async def scheduled_research():
    try:
        logger.info("Starting scheduled topic discovery")
        await execute_research(trigger="scheduled")
    except Exception:
        logger.exception("Scheduled research failed")


async def manual_research_background():
    try:
        logger.info("Starting manual topic discovery from Telegram")
        result = await execute_research(trigger="manual")
        if result.get("already_running"):
            await _send_message("⏳ بررسی موضوعات در حال اجراست؛ کمی بعد دوباره تلاش کن.")
    except Exception:
        logger.exception("Manual research triggered from Telegram failed")
        await _send_message("⚠️ اجرای بررسی موضوعات ناموفق بود. لاگ‌های سرویس را بررسی کن.")


async def manual_report_background(report_type: str):
    if report_lock.locked():
        await _send_message("⏳ یک گزارش در حال اجراست؛ لطفاً پس از پایان آن دوباره تلاش کن.")
        return
    async with report_lock:
        try:
            logger.info("Starting manual %s YouTube report from Telegram", report_type)
            if report_type == "daily":
                await send_daily_report()
            elif report_type == "weekly":
                await send_weekly_report()
            elif report_type == "top":
                await send_top_report()
            elif report_type == "shorts":
                await send_recent_shorts_report()
            elif report_type == "compare":
                await send_compare_report()
            elif report_type == "growth":
                await send_growth_report()
            elif report_type == "engagement":
                await send_engagement_report()
        except Exception:
            logger.exception("Manual %s YouTube report failed", report_type)
            await _send_message("⚠️ ساخت گزارش ناموفق بود. اتصال YouTube و لاگ‌های سرویس را بررسی کن.")


async def send_telegram_status():
    try:
        info = await channel_info()
        channel_title = (info.get("snippet") or {}).get("title", "YouTube channel")
        youtube_status = f"✅ متصل ({channel_title})"
    except Exception as exc:
        logger.warning("Telegram status check: YouTube unavailable (%s)", type(exc).__name__)
        youtube_status = "❌ قطع یا غیرقابل‌دسترسی"

    daily_job = scheduler.get_job("youtube-daily-report")
    weekly_job = scheduler.get_job("youtube-weekly-report")
    scheduler_status = "✅ فعال" if scheduler.running else "❌ غیرفعال"
    daily_next = daily_job.next_run_time.strftime("%Y-%m-%d %H:%M %Z") if daily_job else "تنظیم نشده"
    weekly_next = weekly_job.next_run_time.strftime("%Y-%m-%d %H:%M %Z") if weekly_job else "تنظیم نشده"
    await _send_message(
        "🤖 وضعیت Channel Intelligence\n\n"
        f"YouTube: {youtube_status}\n"
        f"زمان‌بندی: {scheduler_status}\n"
        f"گزارش روزانه بعدی: {daily_next}\n"
        f"گزارش هفتگی بعدی: {weekly_next}\n"
        f"منطقه زمانی: {settings.schedule_timezone}"
    )


@app.on_event("startup")
async def startup_event():
    if settings.youtube_reports_enabled:
        scheduler.add_job(
            send_daily_report,
            CronTrigger(hour=settings.youtube_daily_report_hour, minute=0,
                        timezone=ZoneInfo(settings.schedule_timezone)),
            id="youtube-daily-report", replace_existing=True, coalesce=True, max_instances=1,
        )
        scheduler.add_job(
            send_weekly_report,
            CronTrigger(day_of_week=settings.youtube_weekly_report_day, hour=9, minute=0,
                        timezone=ZoneInfo(settings.schedule_timezone)),
            id="youtube-weekly-report", replace_existing=True, coalesce=True, max_instances=1,
        )
        logger.info("YouTube reports scheduled in %s", settings.schedule_timezone)

    if settings.research_schedule_enabled:
        trigger = CronTrigger(
            hour=settings.research_schedule_hour,
            minute=settings.research_schedule_minute,
            timezone=ZoneInfo(settings.schedule_timezone),
        )
        scheduler.add_job(
            scheduled_research, trigger=trigger, id="daily-topic-discovery",
            replace_existing=True, coalesce=True, max_instances=1,
        )
        logger.info(
            "Daily research scheduled at %02d:%02d (%s)",
            settings.research_schedule_hour, settings.research_schedule_minute,
            settings.schedule_timezone,
        )

    if settings.youtube_reports_enabled or settings.research_schedule_enabled:
        scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
def health():
    return {"ok": True, "service": "youtube-channel-intelligence", "version": "0.5.0",
            "region": settings.aws_region, "llm_api_required": False,
            "research_schedule_enabled": settings.research_schedule_enabled,
            "research_schedule": f"{settings.research_schedule_hour:02d}:{settings.research_schedule_minute:02d} {settings.schedule_timezone}"}


@app.get("/topics")
def list_topics():
    return all_topics()


@app.get("/topics/selected")
def selected_topics():
    return [t for t in all_topics() if t.status == TopicStatus.SELECTED]


@app.post("/stories")
async def create_story(payload: StoryIn):
    story = Story(id=uuid.uuid4().hex[:12], approval_token=secrets.token_urlsafe(16), **payload.model_dump())
    put(story)
    delivery = await send_script_for_approval(story)
    return {"story": story, "telegram_delivery": delivery}


@app.get("/stories")
def list_stories():
    return all_stories()


async def _handle_callback(callback: dict):
    data = callback.get("data", "")
    callback_id = callback.get("id", "")

    if data == "research_run":
        await answer_callback_query(callback_id, "بررسی موضوعات شروع شد")
        asyncio.create_task(manual_research_background())
        return {"ok": True, "action": "research_run", "started": True}

    if data in ("report_daily", "report_weekly", "report_top", "report_shorts", "report_compare", "report_growth", "report_engagement"):
        report_type = {
            "report_daily": "daily",
            "report_weekly": "weekly",
            "report_top": "top",
            "report_shorts": "shorts",
            "report_compare": "compare",
            "report_growth": "growth",
            "report_engagement": "engagement",
        }[data]
        await answer_callback_query(callback_id, "گزارش در حال آماده‌سازی است")
        asyncio.create_task(manual_report_background(report_type))
        return {"ok": True, "action": data, "started": True}

    if data == "report_status":
        await answer_callback_query(callback_id, "در حال بررسی وضعیت")
        await send_telegram_status()
        return {"ok": True, "action": "report_status"}

    if data == "show_selected":
        await answer_callback_query(callback_id, "فهرست موضوعات انتخاب‌شده")
        selected = [t for t in all_topics() if t.status == TopicStatus.SELECTED]
        await send_selected_topics(selected)
        return {"ok": True, "selected_count": len(selected)}

    if data.startswith("gpt_brief:"):
        try:
            action, topic_id, token = data.split(":", 2)
        except ValueError:
            await answer_callback_query(callback_id, "درخواست نامعتبر")
            return {"ok": False}

        topic = get_topic(topic_id)

        if (
            not topic
            or not secrets.compare_digest(topic.approval_token, token)
            or topic.status != TopicStatus.SELECTED
        ):
            await answer_callback_query(
                callback_id,
                "موضوع پیدا نشد یا دیگر انتخاب‌شده نیست"
            )
            return {"ok": False}

        await answer_callback_query(
            callback_id,
            "در حال آماده‌سازی GPT Brief..."
        )

        await send_gpt_brief(topic)

        return {
            "ok": True,
            "action": "gpt_brief",
            "topic_id": topic.id
        }

    if data.startswith("topic_"):
        try:
            action, topic_id, token = data.split(":", 2)
        except ValueError:
            await answer_callback_query(callback_id, "درخواست نامعتبر")
            raise HTTPException(status_code=400, detail="Malformed topic callback")
        topic = get_topic(topic_id)
        if not topic or not secrets.compare_digest(topic.approval_token, token):
            await answer_callback_query(callback_id, "موضوع پیدا نشد")
            raise HTTPException(status_code=404, detail="Topic or approval token not found")

        if action == "topic_select" and topic.status == TopicStatus.NEW:
            topic.status = TopicStatus.SELECTED
            update_topic(topic)
            await answer_callback_query(callback_id, "به فهرست انتخاب‌شده‌ها اضافه شد")
            await send_selected_topic(topic)
            return {"ok": True, "topic_id": topic.id, "status": topic.status}

        if action == "topic_reject" and topic.status == TopicStatus.NEW:
            topic.status = TopicStatus.REJECTED
            update_topic(topic)
            await answer_callback_query(callback_id, "موضوع رد شد")
            return {"ok": True, "topic_id": topic.id, "status": topic.status}

        if action == "topic_remove" and topic.status == TopicStatus.SELECTED:
            topic.status = TopicStatus.REJECTED
            update_topic(topic)
            await answer_callback_query(callback_id, "از فهرست انتخاب‌شده‌ها حذف شد")
            await _send_message(f"🗑 موضوع از فهرست انتخاب‌شده‌ها حذف شد:\n{topic.title}")
            return {"ok": True, "topic_id": topic.id, "status": topic.status}

        await answer_callback_query(callback_id, "این موضوع قبلاً بررسی شده یا وضعیتش تغییر کرده است")
        return {"ok": True, "status": topic.status, "message": "Already reviewed"}

    try:
        action, story_id, token = data.split(":", 2)
    except ValueError:
        await answer_callback_query(callback_id, "درخواست نامعتبر")
        raise HTTPException(status_code=400, detail="Malformed callback")
    story = get(story_id)
    if not story or not secrets.compare_digest(story.approval_token, token):
        await answer_callback_query(callback_id, "اسکریپت پیدا نشد")
        raise HTTPException(status_code=404, detail="Story or approval token not found")
    if story.status != Status.SCRIPT_READY:
        await answer_callback_query(callback_id, "این اسکریپت قبلاً بررسی شده است")
        return {"ok": True, "status": story.status, "message": "Already reviewed"}
    if action == "approve":
        story.status = Status.APPROVED
        feedback = "اسکریپت تأیید شد"
    elif action == "reject":
        story.status = Status.REJECTED
        feedback = "اسکریپت رد شد"
    elif action == "revise":
        story.status = Status.REVISION_REQUESTED
        feedback = "درخواست اصلاح ثبت شد"
    else:
        await answer_callback_query(callback_id, "عملیات ناشناخته")
        raise HTTPException(status_code=400, detail="Unknown action")
    update(story)
    await answer_callback_query(callback_id, feedback)
    return {"ok": True, "story_id": story.id, "status": story.status}


@app.post("/telegram/webhook")
async def telegram_webhook(update_payload: dict, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

    callback = update_payload.get("callback_query")
    if callback:
        # Only accept actions from the configured private Telegram chat.
        chat_id = str((callback.get("message") or {}).get("chat", {}).get("id", ""))
        if not settings.telegram_chat_id or chat_id != str(settings.telegram_chat_id):
            raise HTTPException(status_code=403, detail="Unauthorized Telegram chat")
        return await _handle_callback(callback)

    message = update_payload.get("message") or update_payload.get("edited_message")
    if message:
        chat_id = str(message.get("chat", {}).get("id", ""))
        if not settings.telegram_chat_id or chat_id != str(settings.telegram_chat_id):
            return {"ok": True}
        command = (message.get("text") or "").split()[0].split("@")[0].lower() if message.get("text") else ""
        if command in ("/start", "/menu", "/help"):
            await send_control_panel()
        elif command == "/run":
            await _send_message("🔎 اجرای دستی کشف موضوعات شروع شد...")
            asyncio.create_task(manual_research_background())
        elif command == "/selected":
            selected = [t for t in all_topics() if t.status == TopicStatus.SELECTED]
            await send_selected_topics(selected)
        elif command in ("/daily", "/weekly", "/top", "/shorts", "/compare", "/growth", "/engagement"):
            report_type = command.lstrip("/")
            labels = {"daily": "روزانه", "weekly": "هفتگی", "top": "۵ ویدیوی برتر", "shorts": "۵ شورت برتر", "compare": "مقایسه دوره‌ای", "growth": "رشد مشترکان", "engagement": "تعامل مخاطبان"}
            await _send_message(f"⏳ گزارش {labels[report_type]} در حال آماده‌سازی است...")
            asyncio.create_task(manual_report_background(report_type))
        elif command == "/status":
            await send_telegram_status()
        return {"ok": True}

    return {"ok": True}


@app.post("/research/run")
async def research_run(x_factory_admin_key: str | None = Header(default=None)):
    if settings.app_env == "production" and not settings.factory_admin_key:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")
    if settings.app_env == "production" and x_factory_admin_key != settings.factory_admin_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return await execute_research(trigger="manual")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Research pipeline failed: {type(exc).__name__}: {exc}")


@app.get("/production/queue")
def production_queue():
    return [s for s in all_stories() if s.status == Status.APPROVED]
