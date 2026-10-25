import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .news import briefing_text
from .calendar import render_events

log = logging.getLogger(__name__)


def create_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(bot.settings.timezone))

    async def send_daily():
        now = datetime.now(ZoneInfo(bot.settings.timezone))
        date_key = now.date().isoformat()
        articles, news_errors = await asyncio.to_thread(bot.news.fetch, bot.settings.news_max_articles)
        market_data, market_errors = await asyncio.to_thread(bot.market.fetch)
        events, calendar_errors = await asyncio.to_thread(bot.calendar.upcoming, timezone=bot.settings.timezone)
        ai_analysis = await asyncio.to_thread(bot.ai.explain_articles, articles)
        message = briefing_text(
            articles,
            news_errors + market_errors + calendar_errors,
            bot.market.render(market_data),
            render_events(events, bot.settings.timezone),
            ai_analysis,
        )
        for user in bot.db.users():
            # Reserve through this unique daily key only after successful delivery so transient
            # Discord failures can be retried on the next scheduler run.
            if not bot.db.record_briefing(user["user_id"], date_key, "sending"):
                continue
            try:
                target = await bot.fetch_user(int(user["user_id"]))
                for part in __import__("studybot.discord_app", fromlist=["split_message"]).split_message(message):
                    await target.send(part)
            except Exception:
                with bot.db.connect() as conn:
                    conn.execute("DELETE FROM briefings WHERE user_id=? AND briefing_date=?", (user["user_id"], date_key))
                log.exception("일일 브리핑 전송 실패 (사용자 ID 일부 생략)")

    hour, minute = map(int, bot.settings.briefing_time.split(":"))
    scheduler.add_job(send_daily, "cron", hour=hour, minute=minute, id="daily-briefing", replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=3600)
    return scheduler
