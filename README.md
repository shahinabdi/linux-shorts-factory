# Linux Shorts Factory v0.4

Persian-first, editorial-approval-gated Linux Shorts idea pipeline. **No OpenAI API key or API credits required.**

## Editorial strategy
The factory is not an RSS-only news bot. It prioritizes useful, evergreen learning content:

1. Practical Linux tips
2. Linux distributions and distro comparisons
3. How Linux works (kernel, boot, init, filesystem, permissions)
4. Desktop Linux (KDE, GNOME, Wayland, window managers)
5. Developer tools and workflows
6. News and releases (secondary; RSS is an idea source, not fact verification)

The initial editorial mix target is approximately 40% practical tips, 25% distributions, 15% how Linux works, 10% desktop, 10% developer/news combined. Adjust this using YouTube analytics and audience feedback.

## Workflow
1. Curated evergreen topic bank + public RSS feeds discover ideas, manually from Telegram or automatically every day.
2. Transparent rule-based scoring ranks ideas. Evergreen educational topics outrank routine release news.
3. Telegram sends each candidate with category, score, Persian hook, explanation and source links.
4. You select or reject topics in Telegram. Selecting a topic sends a second management message with a Remove button; use /selected to review the current list.
5. Selected topics are available at `GET /topics/selected`.
6. Use ChatGPT Go interactively with `prompts/editorial_fa.md` to develop and fact-check the Persian script. ChatGPT Go is not an API credential; no API calls are made by this project.
7. Submit a completed script to `POST /stories` for Telegram script approval.
8. Only approved scripts enter `GET /production/queue` for the future Claude Code / Remotion worker.

## Telegram controls and scheduling (v0.4)

After configuring the Telegram webhook, send `/start` or `/menu` to the bot. The control panel provides a **Discover new topics** button and a **Selected topics** button. You can also use:

- `/run` — manually run discovery now.
- `/selected` — list selected topics, each with a remove button.
- `/menu` — show the control panel.

When you select a topic, the bot sends a management message with **Remove from selected topics**. Removing changes its status to `REJECTED`; it will no longer appear in `/topics/selected`.

A daily schedule is enabled by default at **09:00 Europe/Paris**. Configure it in `.env`:

```env
RESEARCH_SCHEDULE_ENABLED=true
RESEARCH_SCHEDULE_HOUR=9
RESEARCH_SCHEDULE_MINUTE=0
SCHEDULE_TIMEZONE=Europe/Paris
```

Set `RESEARCH_SCHEDULE_ENABLED=false` to disable automatic runs. The scheduler runs inside the API process, so the machine and container must remain running at the scheduled time. If the container is stopped, that day's run is missed; this is a local development scheduler, not a durable cloud scheduler.

## Local setup
```bash
cp .env.example .env
# Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env; never commit .env.
docker compose up --build
```

Run discovery manually from Telegram with `/run` or the **Discover new topics** button. For local diagnostics, the HTTP endpoint remains available:
```bash
curl -X POST http://localhost:8000/research/run
```

Inspect topics:
```bash
curl http://localhost:8000/topics
curl http://localhost:8000/topics/selected
```

Create a script after preparing it in ChatGPT:
```bash
curl -X POST http://localhost:8000/stories \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Linux permissions","proposed_title":"فرق chmod و chown چیست؟","script_fa":"متن فارسی اسکریپت...","estimated_seconds":35,"sources":[],"editorial_notes":"Commands tested on a disposable Linux environment."}'
```

## Telegram webhook setup
The webhook endpoint is `POST /telegram/webhook`. Set `TELEGRAM_WEBHOOK_SECRET` and configure Telegram's webhook with the same secret token. The webhook accepts commands and button callbacks only from the configured `TELEGRAM_CHAT_ID`. The local research endpoint is not intended to be exposed publicly. In production, set `APP_ENV=production` and `FACTORY_ADMIN_KEY`, and put the service behind authenticated infrastructure.

## Storage and production status
The JSON store is for local testing only. It migrates the v0.2 flat story JSON format automatically, but it is not safe for multiple concurrent production workers. Before production, replace it with DynamoDB, add retry/idempotency handling, IAM-scoped Secrets Manager access, monitoring, rate limits and source verification.

## AWS target
EventBridge Scheduler (Europe/Paris) -> Step Functions -> ECS Fargate -> DynamoDB -> S3 -> Remotion Lambda -> Telegram.

## Important limitations
- The topic scorer is heuristic, not an AI ranking model.
- The evergreen bank is curated and should be expanded over time.
- RSS headlines are leads; they are not independently verified facts.
- The project does not yet deploy AWS infrastructure or render videos.
- Telegram topic approval selects an idea; it does not automatically generate a script.
- The final rendered-video review gate and YouTube publishing are future milestones.
- Never expose `/research/run` publicly without authentication.
