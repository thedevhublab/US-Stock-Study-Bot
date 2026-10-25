from datetime import date, timedelta
from .curriculum import lesson_for_day, all_lessons


class LearningService:
    def __init__(self, db, timezone="Asia/Seoul"):
        self.db, self.timezone = db, timezone

    def foundation(self, user_id):
        return self.db.ensure_user(user_id, self.timezone)

    def today_lesson(self, user_id):
        user = self.foundation(user_id)
        if user["foundation_completed"]:
            return None
        return lesson_for_day(user["foundation_day"])

    def complete_lesson(self, user_id, lesson):
        return self.db.advance_foundation(user_id)

    def continuing_lesson(self, user_id, recent_titles=(), weak_concepts=()):
        # Permanent track selection rotates through concepts, prioritizing weak concepts without resetting foundation.
        user = self.foundation(user_id)
        pool = all_lessons()
        if weak_concepts:
            for lesson in pool:
                if any(w.lower() in lesson.title.lower() for w in weak_concepts):
                    return lesson
        offset = int(user["created_at"].replace("-", "").replace(":", "")[:8], 10) % len(pool)
        for i in range(len(pool)):
            candidate = pool[(offset + i) % len(pool)]
            if candidate.title not in recent_titles:
                return candidate
        return pool[offset]

    @staticmethod
    def weekly_summary(quiz_rows, studied_days=0):
        if not quiz_rows:
            return f"이번 주 학습 기록은 {studied_days}일입니다. 퀴즈 기록이 없어 정답률을 계산하지 않았습니다."
        scores = [r["score"] for r in quiz_rows if r["score"] is not None]
        accuracy = sum(scores) / len(scores) * 100 if scores else 0
        return f"이번 주 퀴즈 {len(scores)}문항, 평균 정답률 {accuracy:.0f}%, 학습 {studied_days}일입니다. 오답 개념을 복습하고 실제 뉴스에 적용해 보세요."
