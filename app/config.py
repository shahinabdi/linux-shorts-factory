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
    research_schedule_enabled: bool = True
    research_schedule_hour: int = 9
    research_schedule_minute: int = 0
    schedule_timezone: str = "Europe/Paris"


settings = Settings()
