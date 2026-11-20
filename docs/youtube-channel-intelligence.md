# YouTube Channel Intelligence (initial implementation)

This feature branch adds read-only OAuth access to the channel owned by the authorizing Google account, a Telegram daily/weekly summary, and a channel connection status endpoint.

## OAuth setup

1. In Google Cloud, enable YouTube Analytics API and YouTube Data API v3.
2. Create a Web application OAuth client.
3. Add this exact redirect URI:
   `https://factory.shahinabdi.com/youtube/oauth/callback`
4. Set these variables on the EC2 host (never in Git):
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `YOUTUBE_OAUTH_REDIRECT_URI=https://factory.shahinabdi.com/youtube/oauth/callback`
   - `YOUTUBE_TOKEN_SECRET_ID=linux-shorts-factory/youtube`
5. Create the Secrets Manager secret before connecting:
   `aws secretsmanager create-secret --region eu-west-3 --name linux-shorts-factory/youtube --secret-string '{"refresh_token":"PENDING"}'`
   The app replaces the placeholder after successful consent.
6. Grant the EC2 instance role `secretsmanager:GetSecretValue` and `secretsmanager:PutSecretValue` on that secret ARN. Do not broaden the role to all secrets.
7. Rebuild/restart the API, then visit:
   `https://factory.shahinabdi.com/youtube/oauth/start`
8. The OAuth start route is protected with HTTP Basic authentication. Use username `admin` and the existing `FACTORY_ADMIN_KEY` as the password when opening the URL. Ensure that key is configured in the server's `.env` before exposing the route.
9. Authorize the Google account that owns @shahinabdi. Verify:
   `https://factory.shahinabdi.com/youtube/status`

OAuth requests ask for `youtube.readonly` and `yt-analytics.readonly`. Refresh tokens are stored in Secrets Manager, not in Git. The OAuth state is held in process memory, so use one API worker for the callback flow.

## Reporting

Set:
```env
RESEARCH_SCHEDULE_ENABLED=false
YOUTUBE_REPORTS_ENABLED=true
YOUTUBE_DAILY_REPORT_HOUR=9
YOUTUBE_WEEKLY_REPORT_DAY=mon
SCHEDULE_TIMEZONE=Europe/Paris
```

The daily report uses a completed date two days behind the server date to reduce partial-day reporting. The weekly report compares seven completed days with the preceding seven-day period. YouTube Analytics can lag; a report may be empty and should be retried later.

## Current scope and limitations

- Read-only channel analytics; no upload, edit, delete, or publishing scopes.
- Current summary includes views, estimated watch minutes, subscribers gained/lost, likes and comments.
- CTR, audience retention, detailed traffic sources, and robust Shorts-vs-long-form segmentation are not yet implemented.
- The weekly comparison currently compares total views.
- Daily and weekly jobs run inside the existing FastAPI process and require the container to be running.
- The existing RSS/evergreen discovery scheduler is disabled by default in this feature branch. Existing script approval and GPT Brief code are retained.
- The Google OAuth client secret is configured as an environment secret on the server; the refresh token is stored in AWS Secrets Manager.
