# Telegram approval flow v0.3

## Topic stage
Each discovered idea is sent with category, editorial score, source type, Persian hook, short angle and source link.

- `topic_select:<topic_id>:<token>` marks the topic `SELECTED`.
- `topic_reject:<topic_id>:<token>` marks the topic `REJECTED`.

Selected ideas are listed by `GET /topics/selected`.

## Script stage
A manually prepared Persian script is submitted to `POST /stories` and sent to Telegram.

- `approve:<story_id>:<token>` marks the script `APPROVED`.
- `reject:<story_id>:<token>` marks the script `REJECTED`.
- `revise:<story_id>:<token>` marks the script `REVISION_REQUESTED`.

Only `APPROVED` scripts are returned by `GET /production/queue`.

The webhook must be configured with Telegram's secret-token header in production. Callback tokens are unguessable per record; keep the bot token and webhook secret private.
