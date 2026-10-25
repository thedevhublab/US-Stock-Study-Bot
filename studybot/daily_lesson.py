"""Build and optionally post one scheduled course lesson through a Discord webhook."""
from datetime import date, datetime
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .curriculum import lesson_for_day
from .news import NewsService, briefing_text
from .market import MarketDataService
from .calendar import EconomicCalendarService, render_events

SEOUL = ZoneInfo("Asia/Seoul")


def day_for_date(today: date, start_date: date) -> tuple[int, bool]:
    """Return a one-based rotating lesson number and whether the 28-day foundation is done."""
    elapsed = (today - start_date).days
    if elapsed < 0:
        raise ValueError("학습 시작 날짜가 오늘보다 미래입니다.")
    if elapsed < 28:
        return elapsed + 1, False
    return ((elapsed - 28) % 28) + 1, True


def build_daily_lesson(today: date, start_date: date) -> str:
    day, _continuing = day_for_date(today, start_date)
    lesson = lesson_for_day(day)
    heading = f"28일 기초 코스 {day}/28 · {lesson.title}"
    lines = [
        f"🇺🇸 **오늘의 미국 주식 학습 · {today.isoformat()}**",
        f"**{heading}**",
        f"**1. 오늘의 목표**\n{lesson.goal}",
        f"**2. 핵심 개념**\n{lesson.concept}",
        f"**3. 사례**\n{lesson.example}",
        f"**4. 미국 시장 연결**\n{lesson.market_link}",
        f"**5. 자주 헷갈리는 점**\n{lesson.confusion}",
        "**6. 오늘의 퀴즈**",
        f"1) {lesson.quiz[0]}",
        f"2) {lesson.quiz[1]}",
        f"3) {lesson.quiz[2]}",
        "**정답과 해설** (눌러서 확인)",
        f"1) ||{lesson.answers[0]}||",
        f"2) ||{lesson.answers[1]}||",
        f"3) ||{lesson.answers[2]}||",
        f"**학습 기록 / 복습**\n오늘 배운 내용을 한 문장으로 설명해 보고, 어려웠던 점을 적어 두세요. 복습할 내용: {lesson.review}",
        "자동 학습 게시물입니다. 퀴즈 답변을 자동으로 채점하거나 개인 진도에 저장하지 않습니다. 교육 목적이며 투자 권유가 아닙니다.",
    ]
    return "\n\n".join(lines)


def build_daily_news_briefing(*, news_service=None, market_service=None, calendar_service=None, today=None):
    """Fetch a fresh news and market briefing for the post-course daily workflow."""
    news_service = news_service or NewsService()
    market_service = market_service or MarketDataService()
    calendar_service = calendar_service or EconomicCalendarService()
    articles, errors = news_service.fetch(max_articles=5)
    market_data, market_errors = market_service.fetch()
    events, calendar_errors = calendar_service.upcoming(timezone="Asia/Seoul")
    heading = f"🇺🇸 **미국 시장 뉴스 브리핑 · {today or datetime.now(SEOUL).date()}**\n"
    body = briefing_text(
        articles,
        errors + market_errors + calendar_errors,
        market_service.render(market_data),
        render_events(events, "Asia/Seoul"),
    )
    return heading + body + "\n\n**오늘의 학습 연결:** 기사에서 시장 예상과 실제 발표가 어떻게 다른지 찾아보세요. 뉴스 요약은 학습 참고용이며 투자 권유가 아닙니다."


def build_daily_post(today: date, start_date: date, **news_services) -> str:
    """Post foundation lessons for its 28 days, then switch permanently to news."""
    elapsed = (today - start_date).days
    if elapsed < 0:
        raise ValueError("학습 시작 날짜가 오늘보다 미래입니다.")
    if elapsed < 28:
        return build_daily_lesson(today, start_date)
    return build_daily_news_briefing(today=today, **news_services)


def split_discord_message(text: str, limit: int = 1850) -> list[str]:
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def post_to_webhook(webhook_url: str, text: str) -> None:
    for chunk in split_discord_message(text):
        payload = json.dumps({"content": chunk, "allowed_mentions": {"parse": []}}).encode("utf-8")
        request = Request(webhook_url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "US-Stock-Study-Bot/0.1"}, method="POST")
        try:
            with urlopen(request, timeout=20) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Discord webhook returned HTTP {response.status}")
        except HTTPError as exc:
            raise RuntimeError(f"Discord webhook returned HTTP {exc.code}") from None
        except URLError as exc:
            raise RuntimeError(f"Discord webhook network error: {type(exc.reason).__name__}") from None


def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    start_value = os.environ.get("FOUNDATION_START_DATE", "").strip()
    if not webhook:
        raise SystemExit("DISCORD_WEBHOOK_URL GitHub Secret을 설정하세요.")
    if not start_value:
        raise SystemExit("FOUNDATION_START_DATE GitHub Repository Variable을 YYYY-MM-DD 형식으로 설정하세요.")
    try:
        start = date.fromisoformat(start_value)
    except ValueError:
        raise SystemExit("FOUNDATION_START_DATE는 YYYY-MM-DD 형식이어야 합니다.") from None
    today = datetime.now(SEOUL).date()
    message = build_daily_post(today, start)
    post_to_webhook(webhook, message)
    print(f"일일 게시 완료: {today.isoformat()}")


if __name__ == "__main__":
    main()
