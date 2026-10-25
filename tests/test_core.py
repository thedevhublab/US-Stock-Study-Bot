from datetime import datetime, timezone
from datetime import date, timedelta
from zoneinfo import ZoneInfo
import pytest

from studybot.config import Settings
from studybot.curriculum import all_lessons, lesson_for_day
from studybot.db import Database
from studybot.grading import grade_short_answer
from studybot.learning import LearningService
from studybot.news import NewsService, briefing_text
from studybot.market import MarketDataService
from studybot.calendar import EconomicCalendarService, render_events
from studybot.ai import AIService


def test_curriculum_has_28_days_and_content_fields():
    lessons = all_lessons()
    assert len(lessons) == 28
    assert [x.day for x in lessons] == list(range(1, 29))
    assert all(x.goal and x.concept and x.example and x.market_link and x.confusion and len(x.quiz) == 3 and len(x.answers) == 3 and x.review for x in lessons)


def test_foundation_completion_does_not_restart_continuing_stays_active(tmp_path):
    db = Database(str(tmp_path / "data.sqlite"))
    db.ensure_user("a")
    first = db.advance_foundation("a", "2026-01-01")
    second = db.advance_foundation("a", "2026-01-01")
    assert first["foundation_day"] == second["foundation_day"] == 2
    for day in range(28):
        result = db.advance_foundation("a", (date(2026, 1, 2) + timedelta(days=day)).isoformat())
    assert result["foundation_completed"] == 1
    assert result["foundation_day"] == 28
    assert result["continuing_active"] == 1
    assert db.advance_foundation("a")["foundation_completed"] == 1
    assert db.user("a")["foundation_day"] == 28


def test_users_are_isolated_and_persistent(tmp_path):
    path = str(tmp_path / "persist.sqlite")
    db = Database(path)
    db.ensure_user("one")
    db.ensure_user("two")
    db.advance_foundation("one", "2026-01-01")
    db = Database(path)
    assert db.user("one")["foundation_day"] == 2
    assert db.user("two")["foundation_day"] == 1


def test_quiz_grading_and_weak_concept_dedupe(tmp_path):
    db = Database(str(tmp_path / "q.sqlite"))
    db.ensure_user("u")
    db.record_quiz("u", "q1", "금리", "질문", "금리와 채권")
    first = db.answer_quiz("u", "q1", "모름", 0, "틀림")
    again = db.answer_quiz("u", "q1", "금리", 1, "정답")
    assert first["score"] == again["score"] == 0
    assert db.weak_list("u")[0]["misses"] == 1
    assert grade_short_answer("금리 채권 가격 수익률", "금리와 채권 가격은 반대") [0] >= .6


def test_news_duplicate_and_briefing_dedupe(tmp_path):
    db = Database(str(tmp_path / "n.sqlite"))
    db.ensure_user("u")
    item = dict(url="https://example.test/1", title="title", source="src", published_at=None, event_date=None, summary="summary", content_hash="hash")
    assert db.add_article(item) is True
    assert db.add_article(item) is False
    assert db.record_briefing("u", "2026-10-25") is True
    assert db.record_briefing("u", "2026-10-25") is False


def test_rss_failures_and_empty_are_nonfatal(monkeypatch):
    class Broken:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, *a, **kw): raise TimeoutError()
    monkeypatch.setattr("studybot.news.httpx.get", lambda *a, **kw: (_ for _ in ()).throw(TimeoutError()))
    articles, errors = NewsService({"broken": "https://example.test"}).fetch()
    assert articles == [] and errors == ["broken: TimeoutError"]
    assert "수집된 기사가 없습니다" in briefing_text(articles, errors)


def test_old_news_publish_time_is_not_fabricated():
    item = dict(url="https://example.test", title="old", source="src", published_at="2020-01-01T00:00:00+00:00", summary="")
    rendered = NewsService.render_article(item)
    assert "2020-01-01" in rendered
    assert "사건 발생일과 다를 수" in briefing_text([item])


def test_settings_validate_timezone_and_missing_token(monkeypatch):
    monkeypatch.setattr("studybot.config.load_dotenv", lambda: None)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        Settings.from_env()
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TIMEZONE", "Unknown/Zone")
    with pytest.raises(ValueError, match="TIMEZONE"):
        Settings.from_env()


def test_ai_missing_key_does_not_prevent_bot_settings(monkeypatch):
    monkeypatch.setattr("studybot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings.from_env()
    assert settings.ai_enabled and settings.openai_api_key is None
    assert AIService(settings.ai_enabled, settings.openai_api_key).grade_answer("q", "a", "e") is None


def test_timezone_schedule_configuration(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake")
    monkeypatch.setenv("TIMEZONE", "Asia/Seoul")
    monkeypatch.setenv("DAILY_BRIEFING_TIME", "08:00")
    cfg = Settings.from_env()
    assert cfg.timezone == "Asia/Seoul" and cfg.briefing_time == "08:00"


def test_continuing_track_independent_of_foundation(tmp_path):
    db = Database(str(tmp_path / "track.sqlite"))
    db.ensure_user("u")
    for day in range(28): db.advance_foundation("u", (date(2026, 1, 1) + timedelta(days=day)).isoformat())
    selected = LearningService(db).continuing_lesson("u", recent_titles=["미국 주식시장 구조"])
    assert selected is not None
    assert db.user("u")["foundation_completed"] == 1


def test_market_quotes_use_last_two_closes_and_actual_date():
    class Response:
        def __init__(self, symbol): self.text = f"observation_date,{symbol}\n2026-10-23,100\n2026-10-26,102.5\n"
        def raise_for_status(self): pass
    service = MarketDataService(get=lambda *a, **kw: Response(kw["params"]["id"]), clock=lambda: datetime(2026, 10, 26, 17, tzinfo=ZoneInfo("America/New_York")))
    rows, errors = service.fetch()
    assert not errors and len(rows) == 3
    assert rows[0]["date"] == "2026-10-26"
    assert rows[0]["close"] == 102.5 and rows[0]["change"] == 2.5 and rows[0]["percent"] == 2.5
    assert "2026-10-26" in service.render(rows)


def test_market_bad_provider_data_is_reported_not_invented():
    class Response:
        text = "observation_date,SP500\n2026-10-22,.\n"
        def raise_for_status(self): pass
    service = MarketDataService(get=lambda *a, **kw: Response())
    rows, errors = service.fetch()
    assert rows == [] and len(errors) == 3
    assert "데이터를 가져오지 못했습니다" in service.render(rows)


def test_economic_calendar_filters_and_formats_timezone():
    service = EconomicCalendarService()
    service._bls_events = lambda: [{"title": "Employment Situation", "when": datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc), "source": "BLS", "url": "https://bls.gov"}]
    service._bea_events = lambda: [{"title": "Past release", "when": datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc), "source": "BEA", "url": "https://bea.gov"}]
    service._fed_events = lambda: []
    events, errors = service.upcoming(now=datetime(2026, 10, 25, tzinfo=timezone.utc), days=14, timezone="UTC")
    assert not errors and [x["title"] for x in events] == ["Employment Situation"]
    assert "10/26 21:30" in render_events(events, "Asia/Seoul")


def test_calendar_parses_ics_datetime_and_bea_json():
    service = EconomicCalendarService()
    service._get_text = lambda url: """BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;TZID=America/New_York:20261028T083000\nSUMMARY:Consumer Price Index\nURL:https://www.bls.gov/news.release/cpi.htm\nEND:VEVENT\nEND:VCALENDAR"""
    events = service._bls_events()
    assert events[0]["title"] == "Consumer Price Index"
    assert events[0]["when"].hour == 8 and events[0]["when"].utcoffset().total_seconds() == -4 * 3600
    service._get_text = lambda url: '{"Gross Domestic Product":{"release_dates":["2026-10-29T12:30:00+00:00"]}}'
    bea_events = service._bea_events()
    assert bea_events[0]["source"] == "BEA" and bea_events[0]["when"].day == 29


def test_calendar_handles_legacy_us_eastern_timezone_and_metadata_fields():
    service = EconomicCalendarService()
    service._get_text = lambda url: '{"metadata":"not an event list","U.S. GDP":{"release_dates":["2026-10-29T12:30:00+00:00"]}}'
    bea = service._bea_events()
    assert len(bea) == 1
    service._get_text = lambda url: "BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;TZID=US-Eastern:20261028T083000\nSUMMARY:Jobs report\nEND:VEVENT\nEND:VCALENDAR"
    bls = service._bls_events()
    assert bls[0]["when"].hour == 8 and bls[0]["when"].utcoffset().total_seconds() == -4 * 3600


def test_fed_meeting_parser_returns_scheduled_statement_day():
    year = datetime.now(ZoneInfo("America/New_York")).year
    service = EconomicCalendarService()
    service._get_text = lambda url: f"<h3>{year} FOMC Meetings</h3><p>October 27-28 Statement: PDF</p><h3>{year-1} FOMC Meetings</h3>"
    events = service._fed_events()
    assert any(e["when"].year == year and e["when"].month == 10 and e["when"].day == 28 and e["when"].hour == 14 for e in events)


def test_ai_grader_works_and_falls_back_on_api_error():
    class Result:
        output_text = '{"score":0.75,"explanation":"핵심 원리를 이해했습니다."}'
    class Responses:
        def create(self, **kwargs):
            assert "신뢰할 수 없는 데이터" in kwargs["instructions"]
            return Result()
    class Client:
        responses = Responses()
    ai = AIService(True, "dummy-key", "test-model", client=Client())
    assert ai.grade_answer("질문", "답", "정답") == (0.75, "핵심 원리를 이해했습니다.")
    class BrokenResponses:
        def create(self, **kwargs): raise TimeoutError()
    class BrokenClient:
        responses = BrokenResponses()
    assert AIService(True, "dummy-key", client=BrokenClient()).grade_answer("q", "a", "e") is None


def test_ai_article_explanation_uses_given_rss_metadata_only():
    class Result:
        output_text = "주어진 RSS 정보로만 판단한 해설입니다."
    class Responses:
        def create(self, **kwargs):
            assert "기사 제목" in kwargs["input"]
            return Result()
    class Client:
        responses = Responses()
    ai = AIService(True, "dummy-key", client=Client())
    result = ai.explain_article({"title": "기사 제목", "summary": "요약", "source": "원문", "published_at": "2026-10-25", "url": "https://example.test"})
    assert "RSS 정보" in result
