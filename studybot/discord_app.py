import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
from discord import app_commands
from discord.ext import commands

from .curriculum import lesson_for_day
from .grading import grade_multiple_choice, grade_short_answer
from .news import NewsService, briefing_text
from .market import MarketDataService
from .calendar import EconomicCalendarService, render_events
from .ai import AIService

log = logging.getLogger(__name__)


def split_message(text, limit=1900):
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


class StudyBot(commands.Bot):
    def __init__(self, settings, db):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.settings, self.db = settings, db
        self.news = NewsService()
        self.market = MarketDataService()
        self.calendar = EconomicCalendarService()
        self.ai = AIService(settings.ai_enabled, settings.openai_api_key, settings.openai_model)

    async def setup_hook(self):
        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        log.info("Discord 연결 완료: %s", self.user)


def register_commands(bot: StudyBot):
    db = bot.db
    zone = ZoneInfo(bot.settings.timezone)

    async def get_briefing(max_articles):
        articles, news_errors = await asyncio.to_thread(bot.news.fetch, max_articles)
        market_data, market_errors = await asyncio.to_thread(bot.market.fetch)
        events, calendar_errors = await asyncio.to_thread(bot.calendar.upcoming, timezone=bot.settings.timezone)
        ai_analysis = await asyncio.to_thread(bot.ai.explain_articles, articles)
        errors = news_errors + market_errors + calendar_errors
        return briefing_text(articles, errors, bot.market.render(market_data), render_events(events, bot.settings.timezone), ai_analysis)

    @bot.tree.command(name="help", description="학습 봇 명령어 안내")
    async def help_cmd(interaction: discord.Interaction):
        await interaction.response.send_message("`/briefing` 시장 브리핑 · `/news` 주요 뉴스 · `/article` 기사 해설 · `/lesson` 오늘 학습 · `/quiz` 퀴즈 · `/answer` 답변 채점 · `/review` 복습 · `/progress` 진도 · `/foundation` 28일 코스 · `/foundation_review` 코스 복습 · `/weekly` 주간 요약 · `/settings` 학습 설정", ephemeral=True)

    @bot.tree.command(name="briefing", description="최신 시장·경제 브리핑")
    async def briefing_cmd(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        text = await get_briefing(bot.settings.news_max_articles)
        for i, chunk in enumerate(split_message(text)):
            if i == 0: await interaction.followup.send(chunk)
            else: await interaction.followup.send(chunk)

    @bot.tree.command(name="news", description="최신 주요 경제 뉴스")
    async def news_cmd(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        text = await get_briefing(min(5, bot.settings.news_max_articles))
        for chunk in split_message(text): await interaction.followup.send(chunk)

    @bot.tree.command(name="article", description="최근 기사 한 건의 한국어 학습 해설")
    async def article_cmd(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        articles, errors = await asyncio.to_thread(bot.news.fetch, 1)
        if not articles:
            await interaction.followup.send("기사를 가져오지 못했습니다. " + ", ".join(errors))
            return
        explanation = await asyncio.to_thread(bot.ai.explain_article, articles[0])
        if explanation:
            article = articles[0]
            header = f"**{article['title']}**\n출처: {article.get('source') or '미확인'} · 발행: {article.get('published_at') or '발행시각 미확인'}\n원문: {article['url']}"
            await interaction.followup.send(header + "\n\n" + explanation)
        else:
            await interaction.followup.send(bot.news.render_article(articles[0]))

    @bot.tree.command(name="lesson", description="오늘의 기초 또는 계속 학습 콘텐츠")
    async def lesson_cmd(interaction: discord.Interaction):
        user = db.ensure_user(interaction.user.id, bot.settings.timezone)
        today = datetime.now(zone).date().isoformat()
        current_day = user["foundation_day"]
        if not user["foundation_completed"] and user["foundation_last_studied_date"] == today:
            current_day = max(1, current_day - 1)
        lesson = None if user["foundation_completed"] else lesson_for_day(current_day)
        continued = user["foundation_completed"]
        if continued:
            weak = [x["concept"] for x in db.weak_list(interaction.user.id)]
            recent = db.recent_lesson_concepts(interaction.user.id)
            lesson = __import__("studybot.learning", fromlist=["LearningService"]).LearningService(db, bot.settings.timezone).continuing_lesson(interaction.user.id, recent_titles=recent, weak_concepts=weak)
        body = (f"**{lesson.day}일차: {lesson.title}**\n학습 목표: {lesson.goal}\n\n핵심 개념: {lesson.concept}\n\n사례: {lesson.example}\n\n미국 시장 연결: {lesson.market_link}\n\n혼동 주의: {lesson.confusion}\n\n복습: {lesson.review}" if not continued else f"**계속 학습: {lesson.title}**\n학습 목표: {lesson.goal}\n\n핵심 개념: {lesson.concept}\n\n사례: {lesson.example}\n\n미국 시장 연결: {lesson.market_link}\n\n혼동 주의: {lesson.confusion}\n\n복습: {lesson.review}")
        body += "\n\n퀴즈는 `/quiz`에서 풀 수 있습니다. 학습 기록을 반영했습니다."
        if not continued and user["foundation_last_studied_date"] != today:
            db.advance_foundation(interaction.user.id, today)
        else:
            with db.connect() as conn:
                conn.execute("INSERT INTO lessons(user_id,day,concept) VALUES(?,?,?)", (str(interaction.user.id), lesson.day, lesson.title))
        await interaction.response.send_message(body)

    @bot.tree.command(name="quiz", description="오늘의 3문항 중 답할 퀴즈를 출제")
    async def quiz_cmd(interaction: discord.Interaction):
        db.ensure_user(interaction.user.id, bot.settings.timezone)
        pending = db.pending_quiz(interaction.user.id)
        if pending:
            await interaction.response.send_message(f"아직 답하지 않은 문제입니다. `/answer`에 답을 제출하세요.\n{pending['question']}", ephemeral=True)
            return
        user = db.user(interaction.user.id)
        day = max(1, min(28, user["foundation_day"] - (1 if user["foundation_completed"] else 0)))
        lesson = lesson_for_day(day)
        rows = db.recent_quizzes(interaction.user.id)
        index = sum(1 for r in rows if r["concept"] == lesson.title) % 3
        key = f"{datetime.now(zone).date()}:{lesson.day}:{index}"
        q = lesson.quiz[index]
        expected = lesson.answers[index]
        row = db.record_quiz(interaction.user.id, key, lesson.title, q, expected)
        if row["answered_at"]:
            key += f":{datetime.now(zone).timestamp()}"
            db.record_quiz(interaction.user.id, key, lesson.title, q, expected)
        kind = "객관식 · A/B/C/D" if index == 0 else "짧은 서술형"
        await interaction.response.send_message(f"**퀴즈 {index+1}/3 · {kind} · {lesson.title}**\n{q}\n\n`/answer`에 답을 제출해 주세요.")

    @bot.tree.command(name="answer", description="현재 퀴즈 답변 제출 및 채점")
    @app_commands.describe(text="답변 내용")
    async def answer_cmd(interaction: discord.Interaction, text: str):
        quiz = db.pending_quiz(interaction.user.id)
        if not quiz:
            await interaction.response.send_message("답변 대기 중인 문제가 없습니다. 먼저 `/quiz`를 실행하세요.", ephemeral=True)
            return
        is_choice = "\nA) " in quiz["question"]
        if is_choice:
            score, explanation = grade_multiple_choice(text, "A")
            explanation += "\n모범 해설: " + quiz["expected_answer"]
        else:
            ai_grade = await asyncio.to_thread(bot.ai.grade_answer, quiz["question"], text, quiz["expected_answer"])
            score, explanation = ai_grade or grade_short_answer(text, quiz["expected_answer"])
        result = db.answer_quiz(interaction.user.id, quiz["quiz_key"], text, score, explanation)
        await interaction.response.send_message(f"채점: {score*100:.0f}점\n{explanation}\n모범 해설: {quiz['expected_answer']}")

    @bot.tree.command(name="review", description="오답과 취약 개념 복습")
    async def review_cmd(interaction: discord.Interaction):
        weak = db.weak_list(interaction.user.id)
        wrong = [x for x in db.recent_quizzes(interaction.user.id) if x["score"] is not None and x["score"] < .6][:5]
        text = "**취약 개념**\n" + ("\n".join(f"• {x['concept']}: 오답 {x['misses']}회" for x in weak[:8]) or "아직 취약 개념이 없습니다.")
        text += "\n\n**최근 오답 해설**\n" + ("\n".join(f"• {x['question']}\n  {x['expected_answer']}" for x in wrong) or "최근 오답이 없습니다.")
        await interaction.response.send_message(text, ephemeral=True)

    @bot.tree.command(name="progress", description="학습 진도와 퀴즈 정답률")
    async def progress_cmd(interaction: discord.Interaction):
        user = db.ensure_user(interaction.user.id, bot.settings.timezone)
        stats = db.quiz_stats(interaction.user.id)
        result = "완료" if user["foundation_completed"] else f"{user['foundation_day']}/28일차"
        accuracy = f"{stats['avg']*100:.0f}%" if stats["avg"] is not None else "기록 없음"
        await interaction.response.send_message(f"기초 코스: {result}\n완료일: {user['foundation_completed_at'] or '미완료'}\n계속 학습: {'활성' if user['continuing_active'] else '비활성'}\n채점된 문항: {stats['n']} · 정답률: {accuracy}", ephemeral=True)

    @bot.tree.command(name="foundation", description="28일 기초 코스 상태 확인")
    async def foundation_cmd(interaction: discord.Interaction):
        user = db.ensure_user(interaction.user.id, bot.settings.timezone)
        today = datetime.now(zone).date().isoformat()
        day = max(1, user["foundation_day"] - 1) if user["foundation_last_studied_date"] == today and not user["foundation_completed"] else user["foundation_day"]
        text = f"기초 코스: {'완료' if user['foundation_completed'] else str(day) + '일차'}\n"
        text += f"완료일: {user['foundation_completed_at'] or '아직 완료하지 않았습니다.'}\n완료 후 자동 재시작되지 않습니다."
        await interaction.response.send_message(text, ephemeral=True)

    @bot.tree.command(name="foundation_review", description="완료한 28일 코스의 오늘 복습")
    async def foundation_review_cmd(interaction: discord.Interaction):
        user = db.ensure_user(interaction.user.id, bot.settings.timezone)
        day = user["foundation_day"] if not user["foundation_completed"] else min(28, (datetime.now(zone).timetuple().tm_yday % 28) + 1)
        l = lesson_for_day(day)
        await interaction.response.send_message(f"**기초 복습 {day}일차 · {l.title}**\n핵심 개념: {l.concept}\n다시 설명해 볼 질문: {l.quiz[0]}", ephemeral=True)

    @bot.tree.command(name="weekly", description="최근 학습 주간 요약")
    async def weekly_cmd(interaction: discord.Interaction):
        rows = [x for x in db.recent_quizzes(interaction.user.id) if x["answered_at"]]
        start = (datetime.now(zone).date()).isoformat()
        text = f"이번 주 학습 요약\n" + __import__("studybot.learning", fromlist=["LearningService"]).LearningService.weekly_summary(rows[:21])
        text += "\n취약 개념: " + (", ".join(x["concept"] for x in db.weak_list(interaction.user.id)[:5]) or "없음")
        await interaction.response.send_message(text, ephemeral=True)

    @bot.tree.command(name="settings", description="개인 학습 설정 확인")
    async def settings_cmd(interaction: discord.Interaction):
        user = db.ensure_user(interaction.user.id, bot.settings.timezone)
        await interaction.response.send_message(f"시간대: {user['timezone']}\n계속 학습 트랙: {'활성' if user['continuing_active'] else '비활성'}\n브리핑 기본 시간: {bot.settings.briefing_time} ({bot.settings.timezone})\n설정 변경은 운영자 환경변수로 관리됩니다.", ephemeral=True)

