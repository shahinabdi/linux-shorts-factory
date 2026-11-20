from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    story_db: str = "/data/stories.json"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_webhook_secret: str = ""
    factory_admin_key: str = ""
    aws_region: str = "eu-west-3"
    public_base_url: str = "http://localhost:8000"
    daily_shorts_target: int = 4
    research_schedule_enabled: bool = False
    research_schedule_hour: int = 9
    research_schedule_minute: int = 0
    schedule_timezone: str = "Europe/Paris"
    google_client_id: str = ""
    google_client_secret: str = ""
    youtube_oauth_redirect_uri: str = "https://factory.shahinabdi.com/youtube/oauth/callback"
    youtube_token_secret_id: str = "linux-shorts-factory/youtube"
    youtube_reports_enabled: bool = False
    youtube_daily_report_hour: int = 9
    youtube_weekly_report_day: str = "mon"


settings = Settings()
