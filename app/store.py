import json
from pathlib import Path
from .config import settings

DB = Path(settings.story_db)


def load() -> dict:
    DB.parent.mkdir(parents=True, exist_ok=True)
    if not DB.exists():
        return {"stories": {}, "topics": {}}
    data = json.loads(DB.read_text(encoding="utf-8"))
    # Migrate the v0.2 flat story dictionary without losing existing records.
    if "stories" not in data or "topics" not in data:
        data = {"stories": data, "topics": {}}
    data.setdefault("stories", {})
    data.setdefault("topics", {})
    return data


def save(items: dict) -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DB)


def put(story) -> None:
    items = load()
    items["stories"][story.id] = story.model_dump(mode="json")
    save(items)


def get(story_id: str):
    from .models import Story
    raw = load()["stories"].get(story_id)
    return Story.model_validate(raw) if raw else None


def update(story) -> None:
    put(story)


def all_stories():
    from .models import Story
    return [Story.model_validate(v) for v in load()["stories"].values()]


def put_topic(topic) -> None:
    items = load()
    items["topics"][topic.id] = topic.model_dump(mode="json")
    save(items)


def get_topic(topic_id: str):
    from .models import Topic
    raw = load()["topics"].get(topic_id)
    return Topic.model_validate(raw) if raw else None


def update_topic(topic) -> None:
    put_topic(topic)


def all_topics():
    from .models import Topic
    return [Topic.model_validate(v) for v in load()["topics"].values()]
