from datetime import date
import json

from studybot.daily_lesson import build_daily_lesson, build_daily_post, day_for_date, post_to_webhook, split_discord_message


def test_daily_lesson_progression_and_permanent_track():
    start = date(2026, 10, 25)
    assert day_for_date(start, start) == (1, False)
    assert day_for_date(date(2026, 11, 21), start) == (28, False)
    assert day_for_date(date(2026, 11, 22), start) == (1, True)


def test_daily_lesson_includes_objectives_example_quiz_answers_and_review():
    text = build_daily_lesson(date(2026, 10, 25), date(2026, 10, 25))
    for expected in ("오늘의 목표", "핵심 개념", "사례", "미국 시장 연결", "헷갈리는 점", "오늘의 퀴즈", "정답과 해설", "학습 기록 / 복습", "자동으로 채점"):
        assert expected in text


def test_daily_post_switches_from_foundation_to_news_after_28_days():
    start = date(2026, 10, 25)
    assert "28일 기초 코스 28/28" in build_daily_post(date(2026, 11, 21), start)

    class News:
        def fetch(self, max_articles):
            return ([{"title": "Fed holds rates", "source": "Test", "url": "https://example.test", "published_at": "2026-11-22T00:00:00+00:00", "summary": "Rates unchanged."}], [])

    class Market:
        def fetch(self):
            return ([{"name": "S&P 500", "date": "2026-11-20", "close": 6000, "change": 20, "percent": .33}], [])
        def render(self, data):
            return "최근 완료 거래일 종가: S&P 500 (2026-11-20)"

    class Calendar:
        def upcoming(self, timezone):
            return ([], [])

    post = build_daily_post(date(2026, 11, 22), start, news_service=News(), market_service=Market(), calendar_service=Calendar())
    assert "미국 시장 뉴스 브리핑" in post
    assert "Fed holds rates" in post
    assert "최근 완료 거래일 종가" in post
    assert "28일 기초 코스" not in post


def test_daily_lesson_splits_within_discord_limit():
    chunks = split_discord_message("문단\n\n" + ("설명 " * 900))
    assert len(chunks) > 1
    assert all(len(chunk) <= 1850 for chunk in chunks)


def test_webhook_post_sends_chunks_and_suppresses_mentions(monkeypatch):
    sent = []
    class Response:
        status = 204
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def fake_urlopen(request, timeout):
        sent.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr("studybot.daily_lesson.urlopen", fake_urlopen)
    post_to_webhook("https://discord.test/webhook/private", "lesson")
    assert sent[0]["content"] == "lesson"
    assert sent[0]["allowed_mentions"] == {"parse": []}
