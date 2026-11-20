# AWS deployment target

Target region: eu-west-3 (Paris), configurable.

Planned resources:
- EventBridge Scheduler (Europe/Paris)
- Step Functions state machine
- ECS Fargate tasks for RSS/evergreen discovery and Telegram dispatch
- DynamoDB topics/stories tables with status + idempotency keys
- S3 bucket for scripts, licensed assets and renders
- Remotion Lambda deployment (future production stage)
- Secrets Manager for Telegram bot credentials and webhook/admin secrets
- CloudWatch logs, alarms and DLQ

No OpenAI API key is required by the v0.3 research workflow. ChatGPT Go is used interactively by the editor for script development; it is not an API credential and is not called by AWS.

Do not deploy until account, region, budget limits, domain/webhook URL and secret values are configured.
Use least-privilege IAM roles and S3 lifecycle policies. Keep Telegram topic and script approval mandatory.
