from datetime import date
import json

from studybot.daily_lesson import build_daily_lesson, day_for_date, post_to_webhook, split_discord_message


def test_daily_lesson_progression_and_permanent_track():
    start = date(2026, 10, 25)
    assert day_for_date(start, start) == (1, False)
    assert day_for_date(date(2026, 11, 21), start) == (28, False)
    assert day_for_date(date(2026, 11, 22), start) == (1, True)


def test_daily_lesson_includes_objectives_example_quiz_answers_and_review():
    text = build_daily_lesson(date(2026, 10, 25), date(2026, 10, 25))
    for expected in ("오늘의 목표", "핵심 개념", "사례", "미국 시장 연결", "헷갈리는 점", "오늘의 퀴즈", "정답과 해설", "학습 기록 / 복습", "자동으로 채점"):
        assert expected in text


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
