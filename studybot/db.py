import sqlite3
from datetime import date
from pathlib import Path
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, timezone TEXT NOT NULL DEFAULT 'Asia/Seoul', foundation_day INTEGER NOT NULL DEFAULT 1 CHECK(foundation_day BETWEEN 1 AND 28), foundation_completed INTEGER NOT NULL DEFAULT 0, foundation_completed_at TEXT, foundation_last_studied_date TEXT, continuing_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id), day INTEGER NOT NULL, concept TEXT NOT NULL, studied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, day, studied_at));
CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id), quiz_key TEXT NOT NULL, concept TEXT NOT NULL, question TEXT NOT NULL, answer TEXT, expected_answer TEXT NOT NULL, score REAL, explanation TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, answered_at TEXT, UNIQUE(user_id, quiz_key));
CREATE TABLE IF NOT EXISTS weak_concepts (user_id TEXT NOT NULL REFERENCES users(user_id), concept TEXT NOT NULL, misses INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, concept));
CREATE TABLE IF NOT EXISTS articles (url TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT, published_at TEXT, event_date TEXT, summary TEXT, content_hash TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS briefings (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id), briefing_date TEXT NOT NULL, sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, status TEXT NOT NULL, UNIQUE(user_id, briefing_date));
CREATE TABLE IF NOT EXISTS weekly_summaries (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id), week_start TEXT NOT NULL, summary TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, week_start));
CREATE INDEX IF NOT EXISTS idx_quizzes_user_created ON quizzes(user_id, created_at);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            # Additive migrations preserve existing learner records.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
            if "foundation_last_studied_date" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN foundation_last_studied_date TEXT")

    def ensure_user(self, user_id: str, timezone: str = "Asia/Seoul"):
        with self.connect() as c:
            c.execute("INSERT INTO users(user_id, timezone) VALUES(?, ?) ON CONFLICT(user_id) DO NOTHING", (str(user_id), timezone))
            return dict(c.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),)).fetchone())

    def user(self, user_id: str):
        with self.connect() as c:
            row = c.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),)).fetchone()
            return dict(row) if row else None

    def advance_foundation(self, user_id: str, study_date: str | None = None):
        study_date = study_date or date.today().isoformat()
        with self.connect() as c:
            row = c.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),)).fetchone()
            if row is None:
                raise KeyError(user_id)
            if row["foundation_completed"]:
                return dict(row)
            if row["foundation_last_studied_date"] == study_date:
                return dict(row)
            day = row["foundation_day"]
            c.execute("INSERT INTO lessons(user_id, day, concept) VALUES(?,?,?)", (str(user_id), day, f"기초 {day}일차"))
            if day == 28:
                c.execute("UPDATE users SET foundation_completed=1, foundation_completed_at=CURRENT_TIMESTAMP, foundation_last_studied_date=? WHERE user_id=?", (study_date, str(user_id)))
            else:
                c.execute("UPDATE users SET foundation_day=foundation_day+1, foundation_last_studied_date=? WHERE user_id=?", (study_date, str(user_id)))
            return dict(c.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),)).fetchone())

    def restart_foundation(self, user_id: str):
        with self.connect() as c:
            c.execute("UPDATE users SET foundation_day=1, foundation_completed=0, foundation_completed_at=NULL WHERE user_id=?", (str(user_id),))

    def record_quiz(self, user_id: str, quiz_key: str, concept: str, question: str, expected_answer: str):
        with self.connect() as c:
            c.execute("INSERT INTO quizzes(user_id,quiz_key,concept,question,expected_answer) VALUES(?,?,?,?,?) ON CONFLICT(user_id,quiz_key) DO NOTHING", (str(user_id), quiz_key, concept, question, expected_answer))
            return c.execute("SELECT * FROM quizzes WHERE user_id=? AND quiz_key=?", (str(user_id), quiz_key)).fetchone()

    def answer_quiz(self, user_id: str, quiz_key: str, answer: str, score: float, explanation: str):
        with self.connect() as c:
            row = c.execute("SELECT * FROM quizzes WHERE user_id=? AND quiz_key=?", (str(user_id), quiz_key)).fetchone()
            if row is None:
                return None
            if row["answered_at"]:
                return dict(row)
            c.execute("UPDATE quizzes SET answer=?,score=?,explanation=?,answered_at=CURRENT_TIMESTAMP WHERE id=?", (answer, score, explanation, row["id"]))
            if score < 0.6:
                c.execute("INSERT INTO weak_concepts(user_id,concept,misses) VALUES(?,?,1) ON CONFLICT(user_id,concept) DO UPDATE SET misses=misses+1,updated_at=CURRENT_TIMESTAMP", (str(user_id), row["concept"]))
            return dict(c.execute("SELECT * FROM quizzes WHERE id=?", (row["id"],)).fetchone())

    def add_article(self, article: dict) -> bool:
        with self.connect() as c:
            try:
                c.execute("INSERT INTO articles(url,title,source,published_at,event_date,summary,content_hash) VALUES(?,?,?,?,?,?,?)", tuple(article[k] for k in ("url", "title", "source", "published_at", "event_date", "summary", "content_hash")))
                return True
            except sqlite3.IntegrityError:
                return False

    def record_briefing(self, user_id: str, briefing_date: str, status: str = "sent") -> bool:
        with self.connect() as c:
            try:
                c.execute("INSERT INTO briefings(user_id,briefing_date,status) VALUES(?,?,?)", (str(user_id), briefing_date, status))
                return True
            except sqlite3.IntegrityError:
                return False

    def users(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM users WHERE continuing_active=1")]

    def quiz_stats(self, user_id):
        with self.connect() as c:
            row = c.execute("SELECT COUNT(*) n, AVG(score) avg FROM quizzes WHERE user_id=? AND answered_at IS NOT NULL", (str(user_id),)).fetchone()
            return dict(row)

    def weak_list(self, user_id):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM weak_concepts WHERE user_id=? ORDER BY misses DESC, updated_at DESC", (str(user_id),))]

    def pending_quiz(self, user_id):
        with self.connect() as c:
            row = c.execute("SELECT * FROM quizzes WHERE user_id=? AND answered_at IS NULL ORDER BY id DESC LIMIT 1", (str(user_id),)).fetchone()
            return dict(row) if row else None

    def recent_quizzes(self, user_id, limit=100):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM quizzes WHERE user_id=? ORDER BY id DESC LIMIT ?", (str(user_id), limit))]

    def recent_lesson_concepts(self, user_id, limit=7):
        with self.connect() as c:
            return [r[0] for r in c.execute("SELECT concept FROM lessons WHERE user_id=? ORDER BY id DESC LIMIT ?", (str(user_id), limit))]

    def delete_orphaned(self):
        """Reserved for future maintenance; migrations intentionally never purge learner data."""
        return 0
