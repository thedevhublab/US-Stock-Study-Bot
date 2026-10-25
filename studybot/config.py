from dataclasses import dataclass
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    guild_id: int | None
    database_path: str
    timezone: str
    briefing_time: str
    news_max_articles: int
    ai_enabled: bool
    openai_api_key: str | None
    openai_model: str = "gpt-5.5"

    @classmethod
    def from_env(cls, *, require_token: bool = True) -> "Settings":
        load_dotenv()
        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        if require_token and (not token or token == "replace_me"):
            raise ValueError("DISCORD_BOT_TOKEN이 설정되지 않았습니다. .env 또는 배포 환경변수를 확인하세요.")
        guild = os.getenv("DISCORD_GUILD_ID", "").strip()
        zone = os.getenv("TIMEZONE", "Asia/Seoul").strip()
        try:
            ZoneInfo(zone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"알 수 없는 TIMEZONE입니다: {zone}") from exc
        time = os.getenv("DAILY_BRIEFING_TIME", "08:00").strip()
        try:
            hour, minute = map(int, time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError as exc:
            raise ValueError("DAILY_BRIEFING_TIME은 HH:MM 형식이어야 합니다.") from exc
        try:
            max_articles = int(os.getenv("NEWS_MAX_ARTICLES", "8"))
            if not 1 <= max_articles <= 20:
                raise ValueError
        except ValueError as exc:
            raise ValueError("NEWS_MAX_ARTICLES는 1~20 사이 정수여야 합니다.") from exc
        enabled = os.getenv("AI_ENABLED", "false").lower() in {"1", "true", "yes"}
        key = os.getenv("OPENAI_API_KEY") or None
        return cls(token, int(guild) if guild else None, os.getenv("DATABASE_PATH", "data/studybot.sqlite3"), zone, time, max_articles, enabled, key, os.getenv("OPENAI_MODEL", "gpt-5.5").strip())
