"""RSS ingestion. Feed data is treated as untrusted and all dates retain source timezone."""
from datetime import datetime, timezone
from hashlib import sha256
from email.utils import parsedate_to_datetime
import html
import re
import feedparser
import httpx

FEEDS = {
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "BLS": "https://www.bls.gov/feed/bls_latest.rss",
    "CNBC Economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "CNBC Technology": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
}


def _date(entry):
    value = entry.get("published") or entry.get("updated")
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime(*entry.get("published_parsed")[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


class NewsService:
    def __init__(self, feeds=None, timeout=12):
        self.feeds = feeds or FEEDS
        self.timeout = timeout

    def fetch(self, max_articles=8):
        articles, errors = [], []
        for source, url in self.feeds.items():
            try:
                response = httpx.get(url, timeout=self.timeout, follow_redirects=True, headers={"User-Agent": "US-Stock-Study-Bot/0.1 (RSS reader)"})
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
                if parsed.bozo and not parsed.entries:
                    raise ValueError("RSS 파싱에 실패했습니다")
                for entry in parsed.entries:
                    link = entry.get("link", "").strip()
                    title = _clean(entry.get("title", ""))
                    if not link or not title:
                        continue
                    description = _clean(entry.get("summary", ""))
                    published = _date(entry)
                    digest = sha256((title.lower() + "|" + link.split("?")[0].lower()).encode()).hexdigest()
                    articles.append({"url": link, "title": title, "source": source, "published_at": published, "event_date": None, "summary": description[:1200], "content_hash": digest})
            except Exception as exc:
                errors.append(f"{source}: {type(exc).__name__}")
        # Preserve only the newest item for duplicate links/titles and explicitly sort undated items last.
        unique = {}
        for article in articles:
            key = article["content_hash"]
            old = unique.get(key)
            if old is None or (article["published_at"] or "") > (old["published_at"] or ""):
                unique[key] = article
        result = sorted(unique.values(), key=lambda a: a["published_at"] or "", reverse=True)
        return result[:max_articles], errors

    @staticmethod
    def render_article(article):
        published = article.get("published_at")
        date_text = published or "발행 시각 미확인"
        summary = article.get("summary") or "RSS가 요약을 제공하지 않았습니다. 원문에서 확인하세요."
        return (f"**{article['title']}**\n출처: {article.get('source') or '미확인'} · 발행: {date_text}\n"
                f"원문: {article['url']}\n요약: {summary}\n왜 중요한가: 관련 정책·수요·기업 이익에 영향을 줄 수 있어 원문과 시장 기대를 비교할 필요가 있습니다.\n"
                "관련 업종/기업: 기사 내용에 따라 확인 필요\n시장 영향: 방향은 기대와 세부 내용에 따라 달라질 수 있습니다.\n학습 개념: 뉴스와 주가, 출처 검증")


def briefing_text(articles, errors=(), market_data=None, events_text=None, ai_analysis=None):
    lines = ["**미국 시장 학습 브리핑**", market_data or "지수 종가: 데이터를 가져오지 못했습니다."]
    if events_text:
        lines.extend(["", events_text])
    if not articles:
        lines.append("주요 뉴스: 수집된 기사가 없습니다. RSS 공급원 상태를 확인해 주세요.")
    for article in articles:
        lines.extend(["", NewsService.render_article(article)])
    if ai_analysis:
        lines.extend(["", "**AI 학습 해설 (RSS 제목·요약 기준, 원문 확인 권장)**", ai_analysis])
    if errors:
        lines.extend(["", "일부 공급원에서 데이터를 가져오지 못했습니다: " + ", ".join(errors)])
    lines.append("\n교육 목적의 정보이며 투자 권유가 아닙니다. 발행일은 RSS 원문 메타데이터 기준이며 사건 발생일과 다를 수 있습니다.")
    return "\n".join(lines)
