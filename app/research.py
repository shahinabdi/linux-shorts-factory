"""API-free editorial discovery for Linux Shorts Factory v0.3.

Combines a curated evergreen topic bank with RSS news. It ranks ideas with
transparent rules; it does not generate scripts or claim that RSS items have
been independently fact-checked.
"""
import re
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from .models import Topic, TopicStatus
from .store import all_topics, put_topic
from .telegram import send_topic_for_approval

FEEDS = [
    ("Phoronix", "https://www.phoronix.com/rss.php"),
    ("LWN", "https://lwn.net/headlines/rss"),
    ("Linux.com", "https://www.linux.com/feed/"),
    ("Ubuntu Blog", "https://ubuntu.com/blog/feed"),
    ("Fedora Magazine", "https://fedoramagazine.org/feed/"),
    ("KDE News", "https://kde.org/announcements/feed/"),
    ("GNOME News", "https://www.gnome.org/feed/"),
    ("Docker Blog", "https://www.docker.com/blog/feed/"),
    ("GitHub Blog", "https://github.blog/feed/"),
]

# Curated evergreen ideas: prioritize practical learning, distributions and
# explainers about how Linux works. Add to this list as the channel evolves.
EVERGREEN_TOPICS = [
    ("Practical Linux", "چطور بفهمیم کدام برنامه یک پورت را اشغال کرده؟", "با دستور ss و lsof پورت‌های در حال استفاده را پیدا کن.", "پیدا کردن پردازشی که روی یک پورت مثل ۸۰۸۰ گوش می‌دهد.", 96),
    ("Practical Linux", "چطور بزرگ‌ترین فایل‌های لینوکس را پیدا کنیم؟", "اگر فضای دیسکت پر شده، این دستورها کمک می‌کنند مقصر را پیدا کنی.", "استفاده از du و find برای پیدا کردن فایل‌ها و پوشه‌های حجیم.", 96),
    ("Practical Linux", "فرق df و du چیست؟", "یکی فضای فایل‌سیستم را نشان می‌دهد، دیگری مصرف پوشه‌ها را.", "تفاوت df -h و du -sh با مثال واقعی.", 94),
    ("Practical Linux", "چطور یک سرویس خراب را با systemctl بررسی کنیم؟", "قبل از ری‌استارت کردن سرویس، این سه دستور را اجرا کن.", "systemctl status، journalctl و restart برای عیب‌یابی سرویس.", 93),
    ("Practical Linux", "دستور find؛ فایل‌ها را حرفه‌ای پیدا کن", "اسم فایل، حجم، زمان تغییر و حتی نوع فایل را جست‌وجو کن.", "چند الگوی کاربردی find برای کاربران تازه‌کار.", 92),
    ("Linux Distros", "دبیان، فدورا و آرچ چه تفاوتی دارند؟", "تفاوت این سه فقط در ظاهر دسکتاپ نیست؛ فلسفه‌شان فرق دارد.", "مقایسه فلسفه انتشار، بسته‌ها و مخاطب هر خانواده.", 99),
    ("Linux Distros", "کدام توزیع لینوکس برای شروع بهتر است؟", "قرار نیست همه با آرچ شروع کنند؛ انتخاب درست به نیازت بستگی دارد.", "راهنمای انتخاب توزیع بر اساس تجربه و کاربرد.", 98),
    ("Linux Distros", "فرق Debian و Ubuntu دقیقاً چیست؟", "اوبونتو از دبیان آمده، اما این دو یک تجربه یکسان نیستند.", "رابطه دو توزیع، چرخه انتشار و تفاوت‌های مهم.", 97),
    ("Linux Distros", "چرا بعضی‌ها Arch Linux را انتخاب می‌کنند؟", "آرچ برای همه نیست؛ پس چرا این‌قدر طرفدار دارد؟", "مدل rolling release، کنترل سیستم و Arch Wiki.", 94),
    ("Linux Distros", "Fedora Workstation برای چه کسانی مناسب است؟", "اگر نرم‌افزارهای نسبتاً جدید می‌خواهی، فدورا را بشناس.", "جایگاه فدورا، چرخه انتشار و تجربه دسکتاپ.", 92),
    ("Linux Distros", "Rolling Release یعنی چه؟", "در لینوکس دو روش مهم برای دریافت آپدیت وجود دارد.", "مقایسه rolling release و fixed release با مثال.", 96),
    ("Linux Distros", "فرق Ubuntu LTS و نسخه معمولی چیست؟", "LTS فقط یک اسم نیست؛ روی مدت پشتیبانی و آپدیت‌ها اثر دارد.", "چرخه انتشار و پشتیبانی نسخه‌های اوبونتو.", 91),
    ("How Linux Works", "وقتی لینوکس بوت می‌شود چه اتفاقی می‌افتد؟", "از روشن شدن کامپیوتر تا صفحه ورود، چه مراحلی طی می‌شود؟", "Firmware، bootloader، kernel، init و سرویس‌ها.", 99),
    ("How Linux Works", "کرنل لینوکس دقیقاً چه کاری انجام می‌دهد؟", "کرنل خود سیستم‌عامل نیست؛ اما قلب سیستم‌عامل است.", "مدیریت پردازنده، حافظه، دستگاه‌ها و system calls.", 98),
    ("How Linux Works", "systemd چیست و چرا استفاده می‌شود؟", "بعد از کرنل، چه چیزی سرویس‌های لینوکس را راه می‌اندازد؟", "نقش init و مدیریت سرویس‌ها در systemd.", 97),
    ("How Linux Works", "فرق systemd، OpenRC و runit چیست؟", "همه سیستم‌های init یک کار می‌کنند، اما به یک روش نه.", "مقایسه ساده فلسفه و کاربرد init systemها.", 95),
    ("How Linux Works", "فایل‌های لینوکس کجا ذخیره می‌شوند؟", "چرا در لینوکس همه‌چیز از ریشه یا / شروع می‌شود؟", "آشنایی سریع با /etc، /home، /var، /usr و /proc.", 96),
    ("How Linux Works", "sudo دقیقاً چه کار می‌کند؟", "sudo با ورود به حساب root فرق دارد.", "مدل دسترسی مدیریتی و اجرای یک دستور با امتیاز بالاتر.", 93),
    ("How Linux Works", "فرق Wayland و X11 چیست؟", "این دو فقط اسم دو نوع نمایشگر نیستند؛ معماری متفاوتی دارند.", "مقایسه مدل نمایش و نقش compositor و display server.", 94),
    ("Desktop Linux", "KDE Plasma یا GNOME؛ کدام را انتخاب کنیم؟", "دو دسکتاپ محبوب لینوکس، دو فلسفه متفاوت دارند.", "مقایسه تجربه کاربری، شخصی‌سازی و workflow.", 96),
    ("Desktop Linux", "Window Manager با Desktop Environment چه فرقی دارد؟", "چرا بعضی‌ها به‌جای KDE سراغ Sway یا Hyprland می‌روند؟", "تفاوت مدیر پنجره و محیط دسکتاپ با مثال.", 95),
    ("Desktop Linux", "Hyprland چیست و برای چه کسی مناسب است؟", "یک دسکتاپ لینوکسی متفاوت با پنجره‌های پویا و workflow کیبوردی.", "معرفی Wayland compositor و نیازهای کاربر.", 91),
    ("Practical Linux", "فرق chmod و chown چیست؟", "یکی مجوز را تغییر می‌دهد، دیگری مالک فایل را.", "توضیح permission و ownership با مثال کوتاه.", 95),
    ("Practical Linux", "لینک سخت و سمبلیک چه تفاوتی دارند؟", "در لینوکس می‌توانی به یک فایل چند مسیر دسترسی داشته باشی.", "مقایسه hard link و symbolic link.", 90),
    ("Developer Tools", "فرق APT و DNF و Pacman چیست؟", "مدیر بسته‌ها در توزیع‌های مختلف چه تفاوتی دارد؟", "مقایسه ابزارهای نصب و به‌روزرسانی بسته‌ها.", 94),
    ("Developer Tools", "Docker روی لینوکس چطور کار می‌کند؟", "کانتینر ماشین مجازی نیست؛ پس واقعاً چیست؟", "مفهوم namespace و cgroups در حد مقدماتی.", 93),
    ("Developer Tools", "متغیر محیطی در لینوکس چیست؟", "چرا برنامه‌ها از PATH و متغیرهای محیطی استفاده می‌کنند؟", "معرفی env، export و PATH.", 90),
    ("How Linux Works", "فایل‌سیستم ext4 و Btrfs چه تفاوتی دارند؟", "انتخاب فایل‌سیستم می‌تواند روی امکانات و workflow اثر بگذارد.", "مقایسه امکانات مهم ext4 و Btrfs بدون ورود به جزئیات سنگین.", 92),
    ("Linux Distros", "NixOS چه چیزی را متفاوت انجام می‌دهد؟", "در NixOS حتی تنظیمات سیستم هم قابل بازتولید است.", "معرفی پیکربندی declarative و مدیریت بسته Nix.", 91),
    ("Linux Distros", "openSUSE Tumbleweed چیست؟", "یک توزیع rolling release با رویکرد تست و کیفیت متفاوت.", "معرفی Tumbleweed، openQA و مدل انتشار.", 89),
]


def _published(entry):
    for key in ("published", "updated"):
        value = entry.get(key)
        if value:
            try:
                return parsedate_to_datetime(value).isoformat()
            except Exception:
                return value
    return ""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def collect_news(limit_per_feed: int = 5):
    seen = set()
    candidates = []
    for source_name, feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:limit_per_feed]:
                title = re.sub(r"\s+", " ", entry.get("title", "")).strip()
                link = entry.get("link", "")
                summary = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
                summary = re.sub(r"\s+", " ", summary).strip()[:1200]
                if not title or not link or link in seen:
                    continue
                seen.add(link)
                candidates.append({
                    "source_name": source_name,
                    "title": title,
                    "url": link,
                    "published": _published(entry),
                    "summary": summary,
                })
        except Exception as exc:
            print(f"RSS source failed ({source_name}): {type(exc).__name__}")
    return candidates


def _news_score(title: str, summary: str) -> tuple[str, int]:
    text = f"{title} {summary}".lower()
    # News is deliberately secondary to practical/how-it-works/distro content.
    category = "News & Releases"
    score = 66
    if any(k in text for k in ("kernel", "systemd", "init system", "filesystem", "btrfs", "ext4")):
        category, score = "How Linux Works", 78
    if any(k in text for k in ("fedora", "debian", "ubuntu", "arch linux", "opensuse", "nixos", "distribution", "distro")):
        category, score = "Linux Distros", 82
    if any(k in text for k in ("kde", "gnome", "plasma", "wayland", "hyprland", "desktop")):
        category, score = "Desktop Linux", 76
    if any(k in text for k in ("docker", "python", "git", "developer", "github", "container")):
        category, score = "Developer Tools", 72
    if any(k in text for k in ("security", "vulnerability", "cve", "critical")):
        score = max(score, 85)
    return category, score


def discover_topics(limit: int = 12):
    existing = all_topics()
    known_titles = {_slug(t.title) for t in existing}
    known_sources = {url for t in existing for url in t.sources}
    new_topics = []

    for category, title, hook, description, score in EVERGREEN_TOPICS:
        if _slug(title) in known_titles:
            continue
        new_topics.append(Topic(
            id=uuid.uuid4().hex[:12], category=category, title=title,
            hook_fa=hook, description=description, score=score,
            source_type="evergreen", sources=[], approval_token=uuid.uuid4().hex,
        ))

    for item in collect_news():
        if item["url"] in known_sources:
            continue
        category, score = _news_score(item["title"], item["summary"])
        new_topics.append(Topic(
            id=uuid.uuid4().hex[:12], category=category, title=item["title"],
            hook_fa="این خبر چه تغییری برای کاربران لینوکس ایجاد می‌کند؟",
            description=item["summary"] or "برای بررسی بیشتر، منبع اصلی را باز کنید.",
            score=score, source_type="rss", sources=[item["url"]],
            approval_token=uuid.uuid4().hex,
        ))

    # Prioritize evergreen educational ideas; keep news in the mix, not in charge.
    category_priority = {
        "Linux Distros": 7,
        "How Linux Works": 6,
        "Practical Linux": 5,
        "Desktop Linux": 4,
        "Developer Tools": 3,
        "News & Releases": 1,
    }
    new_topics.sort(key=lambda t: (t.score, category_priority.get(t.category, 0)), reverse=True)
    selected = new_topics[:limit]
    for topic in selected:
        put_topic(topic)
    return selected


async def run_daily_research():
    topics = discover_topics(limit=12)
    deliveries = []
    for topic in topics:
        deliveries.append(await send_topic_for_approval(topic))
    return {
        "topic_count": len(topics),
        "by_category": {category: sum(1 for t in topics if t.category == category)
                        for category in sorted({t.category for t in topics})},
        "telegram_deliveries": deliveries,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "note": "Ideas are ranked by transparent rules; RSS items are leads and require source verification.",
    }
