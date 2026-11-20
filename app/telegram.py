import httpx
from .config import settings
from .models import Story, Topic

API = "https://api.telegram.org"


async def _telegram_call(method: str, payload: dict):
    if not settings.telegram_bot_token:
        return {"ok": False, "description": "Telegram bot token is not configured"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{API}/bot{settings.telegram_bot_token}/{method}", json=payload
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "Telegram API rejected request"))
        return data


async def _send_message(text: str, keyboard: dict | None = None):
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"sent": False, "reason": "Telegram credentials not configured"}
    payload = {"chat_id": settings.telegram_chat_id, "text": text,
               "disable_web_page_preview": True}
    if keyboard:
        payload["reply_markup"] = keyboard
    data = await _telegram_call("sendMessage", payload)
    return {"sent": True, "message_id": data.get("result", {}).get("message_id")}


async def answer_callback_query(callback_query_id: str, text: str = "انجام شد"):
    if not callback_query_id:
        return
    await _telegram_call("answerCallbackQuery", {
        "callback_query_id": callback_query_id, "text": text, "show_alert": False
    })


async def send_control_panel():
    keyboard = {"inline_keyboard": [
        [{"text": "📊 گزارش روزانه", "callback_data": "report_daily"},
         {"text": "📈 گزارش هفتگی", "callback_data": "report_weekly"}],
        [{"text": "🔌 وضعیت سرویس", "callback_data": "report_status"}],
        [{"text": "🔎 کشف موضوعات جدید", "callback_data": "research_run"}],
        [{"text": "📚 موضوعات انتخاب‌شده", "callback_data": "show_selected"}],
    ]}
    return await _send_message(
        "🎬 پنل Linux Shorts Factory\n\n"
        "از اینجا می‌توانی موضوعات جدید را دستی دریافت کنی یا فهرست انتخاب‌شده‌ها را مدیریت کنی.\n\n"
        "دستورها:\\n"
        "/daily — دریافت گزارش روزانه\\n"
        "/weekly — دریافت گزارش هفتگی\\n"
        "/status — بررسی اتصال YouTube و زمان‌بندی\\n"
        "/run — اجرای تحقیق موضوعات\\n"
        "/selected — موضوعات انتخاب‌شده\\n"
        "/menu یا /help — نمایش این پنل.",
        keyboard
    )



async def send_selected_topic(topic: Topic):
    keyboard = {"inline_keyboard": [
        [{
            "text": "🎬 Prepare GPT Brief",
            "callback_data": f"gpt_brief:{topic.id}:{topic.approval_token}"
        }],
        [{
            "text": "🗑 حذف از فهرست انتخاب‌شده‌ها",
            "callback_data": f"topic_remove:{topic.id}:{topic.approval_token}"
        }]
    ]}

    return await _send_message(
        f"✅ موضوع به فهرست انتخاب‌شده‌ها اضافه شد\n\n"
        f"دسته: {topic.category}\n"
        f"موضوع: {topic.title}\n"
        f"امتیاز: {topic.score}/100\n\n"
        "برای ساخت پرامپت کامل ChatGPT، دکمه زیر را بزن.",
        keyboard
    )


async def send_selected_topics(topics: list[Topic]):
    if not topics:
        return await _send_message("📭 در حال حاضر موضوع انتخاب‌شده‌ای نداری.")
    await _send_message(f"📚 موضوعات انتخاب‌شده: {len(topics)}")
    deliveries = []
    for topic in topics:
        deliveries.append(await send_selected_topic(topic))
    return {"count": len(topics), "deliveries": deliveries}


async def send_research_summary(result: dict, trigger: str = "manual"):
    count = result.get("topic_count", 0)
    if count == 0:
        return await _send_message(
            "🔎 بررسی موضوعات تمام شد، اما موضوع جدیدی برای ارسال پیدا نشد.\n"
            "برای جلوگیری از تکرار، موضوعات قبلی دوباره ارسال نشدند."
        )
    categories = result.get("by_category", {})
    breakdown = "\n".join(f"• {name}: {number}" for name, number in categories.items())
    label = "اجرای دستی" if trigger == "manual" else "اجرای زمان‌بندی‌شده"
    return await _send_message(
        f"✅ کشف موضوعات کامل شد ({label})\n\n"
        f"تعداد موضوعات جدید: {count}\n{breakdown}\n\n"
        "برای مدیریت موضوعات انتخاب‌شده از /selected استفاده کن.",
        {"inline_keyboard": [[
            {"text": "📚 دیدن موضوعات انتخاب‌شده", "callback_data": "show_selected"}
        ], [
            {"text": "🔎 اجرای دوباره", "callback_data": "research_run"}
        ]]}
    )


async def send_topic_for_approval(topic: Topic):
    source_label = "موضوع آموزشی / همیشه‌سبز" if topic.source_type == "evergreen" else "خبر / نیازمند بررسی منبع"
    source_text = "\n".join(topic.sources) if topic.sources else "منبع: ایده آموزشی تحریریه"
    text = (
        f"💡 ایده شورت لینوکس\n\n"
        f"دسته: {topic.category}\n"
        f"نوع: {source_label}\n"
        f"امتیاز تحریریه: {topic.score}/100\n\n"
        f"موضوع: {topic.title}\n\n"
        f"هوک پیشنهادی:\n{topic.hook_fa}\n\n"
        f"زاویه و توضیح:\n{topic.description[:900]}\n\n"
        f"{source_text}\n\n"
        "با انتخاب موضوع، آن را به فهرست تولید اسکریپت اضافه می‌کنی."
    )
    keyboard = {"inline_keyboard": [[
        {"text": "✅ انتخاب موضوع", "callback_data": f"topic_select:{topic.id}:{topic.approval_token}"},
        {"text": "❌ رد", "callback_data": f"topic_reject:{topic.id}:{topic.approval_token}"},
    ]]}
    return await _send_message(text, keyboard)


async def send_script_for_approval(story: Story):
    text = (
        "📝 بررسی موضوع و اسکریپت شورت\n\n"
        f"موضوع: {story.subject}\n"
        f"عنوان پیشنهادی: {story.proposed_title}\n"
        f"مدت تقریبی: {story.estimated_seconds} ثانیه\n\n"
        f"متن کامل:\n{story.script_fa}\n\n"
        "منابع:\n" + "\n".join(story.sources)
        + "\n\nیادداشت تحریریه:\n" + (story.editorial_notes or "—")
    )
    keyboard = {"inline_keyboard": [[
        {"text": "✅ تأیید", "callback_data": f"approve:{story.id}:{story.approval_token}"},
        {"text": "❌ رد", "callback_data": f"reject:{story.id}:{story.approval_token}"},
    ], [
        {"text": "✏️ درخواست اصلاح", "callback_data": f"revise:{story.id}:{story.approval_token}"}
    ]]}
    return await _send_message(text, keyboard)

async def send_gpt_brief(topic: Topic):
    source_text = (
        "\n".join(f"- {url}" for url in topic.sources)
        if topic.sources
        else "No external sources supplied. Research the topic using reliable sources."
    )

    source_type = (
        "Evergreen educational topic"
        if topic.source_type == "evergreen"
        else "RSS/news topic — verify the original publication and current facts."
    )

    prompt = f"""تو Creative Director، پژوهشگر فنی لینوکس و طراح سناریوی YouTube Shorts برای یک کانال فارسی‌زبان لینوکس هستی.

یک سناریوی حرفه‌ای، دقیق و جذاب برای موضوع زیر آماده کن.

## اطلاعات موضوع
عنوان: {topic.title}
دسته: {topic.category}
امتیاز تحریریه: {topic.score}/100
نوع: {source_type}

هوک پیشنهادی:
{topic.hook_fa}

توضیحات و زمینه:
{topic.description[:800]}

منابع اولیه:
{source_text}

## مخاطب
کاربران مبتدی و متوسط لینوکس. محتوا باید ساده، قابل فهم، کاربردی و از نظر فنی دقیق باشد.

## سبک تولید
- زبان: فارسی روان و طبیعی
- فرمت: YouTube Shorts عمودی
- رزولوشن: 1080x1920
- نرخ فریم: 30 FPS
- مدت هدف: 20 تا 35 ثانیه
- طراحی Visual-first؛ تصویر باید مفهوم را منتقل کند.
- بدون Voice-over، بدون narration و بدون موسیقی پس‌زمینه.
- فقط Sound Effects کوتاه و متناسب با تصویر.
- متن‌های روی تصویر فارسی و مناسب نمایش RTL باشند.
- طراحی مدرن، مینیمال و حرفه‌ای با کنتراست مناسب.
- از متن زیاد و صحنه‌های غیرضروری پرهیز کن.

## وظایف تو

1. ابتدا موضوع را از نظر فنی بررسی کن.
2. اگر موضوع خبری یا وابسته به نسخه و تاریخ است، اطلاعات را با منابع معتبر و به‌روز بررسی کن. منابع رسمی را در اولویت قرار بده.
3. اگر اطلاعات ورودی ناقص یا مشکوک است، آن را مشخص کن و حدس را به‌عنوان واقعیت ارائه نده.
4. یک زاویه خلاقانه و جذاب برای ویدیو انتخاب کن.
5. سه Hook کوتاه پیشنهاد بده و بهترین را انتخاب کن.
6. سناریوی کامل و تایم‌کدشده بساز.
7. برای هر صحنه، متن روی تصویر، عناصر بصری، حرکت دوربین یا انیمیشن و Sound Effect را مشخص کن.
8. تمام دستورات ترمینال و جزئیات فنی را بررسی کن.

## خروجی مورد انتظار

### 1. Concept
ایده اصلی، پیام و زاویه ویدیو.

### 2. Hooks
سه هوک پیشنهادی و انتخاب نهایی.

### 3. Persian Script
متن فارسی نهایی و کوتاه.

### 4. Timestamped Storyboard
برای هر صحنه:
- زمان شروع و پایان
- متن روی تصویر
- توضیح تصویر و ترکیب‌بندی
- انیمیشن و transition
- Sound Effect

### 5. Visual Direction
رنگ‌ها، تایپوگرافی، آیکون‌ها و سبک بصری.

### 6. Technical Accuracy
بررسی صحت ادعاها، دستورات و منابع.

### 7. Remotion Production Brief
یک دستورالعمل اجرایی دقیق برای Claude Code که از Remotion Skill استفاده کند:
https://github.com/haidrrrry/claude-remotion-skill

خروجی Remotion باید شامل ویدیوی نهایی MP4، کد منبع و راهنمای اجرای پروژه باشد.

هیچ narration، voice-over یا background music تولید نشود؛ فقط Sound Effects.

سناریو را جذاب نگه دار، اما برای جذابیت، دقت فنی را قربانی نکن."""

    # Keep below Telegram's 4096-character message limit.
    if len(prompt) > 3900:
        prompt = prompt[:3850] + "\n\n[Prompt shortened to fit Telegram message limit.]"

    return await _send_message(
        "📋 GPT Brief آماده است!\n\n"
        "متن زیر را کپی کن و در ChatGPT قرار بده:\n\n"
        + prompt
    )


