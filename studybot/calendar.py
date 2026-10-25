"""Economic release dates from official BLS and BEA public calendars."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import re
from html.parser import HTMLParser

import httpx

BLS_ICS = "https://www.bls.gov/schedule/news_release/bls.ics"
BEA_JSON = "https://apps.bea.gov/API/signup/release_dates.json"
FED_FOMC = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
ET = ZoneInfo("America/New_York")
TZID_ALIASES = {
    "US-Eastern": "America/New_York",
    "US-Central": "America/Chicago",
    "US-Mountain": "America/Denver",
    "US-Pacific": "America/Los_Angeles",
}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())


def _unescape_ics(value):
    return value.replace(r"\n", " ").replace(r"\,", ",").replace(r"\;", ";").replace(r"\\", "\\")


def _parse_ics_date(property_line):
    key, value = property_line.split(":", 1)
    if "VALUE=DATE" in key:
        return datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=ET)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    match = re.search(r"TZID=([^;:]+)", key)
    tzid = match.group(1) if match else None
    tz = ZoneInfo(TZID_ALIASES.get(tzid, tzid)) if tzid else ET
    fmt = "%Y%m%dT%H%M%S" if len(value) >= 15 else "%Y%m%dT%H%M"
    return datetime.strptime(value, fmt).replace(tzinfo=tz)


class EconomicCalendarService:
    def __init__(self, timeout=12, get=None):
        self.timeout = timeout
        self._get = get or httpx.get

    def _get_text(self, url):
        response = self._get(url, timeout=self.timeout, follow_redirects=True, headers={"User-Agent": "US-Stock-Study-Bot/0.1 calendar reader"})
        response.raise_for_status()
        return response.text

    def _bls_events(self):
        text = self._get_text(BLS_ICS)
        lines = []
        for raw in text.splitlines():
            if raw.startswith((" ", "\t")) and lines:
                lines[-1] += raw[1:]
            else:
                lines.append(raw)
        events, current = [], None
        for line in lines:
            if line == "BEGIN:VEVENT":
                current = {}
            elif line == "END:VEVENT" and current is not None:
                if current.get("start") and current.get("summary"):
                    events.append({"title": current["summary"], "when": current["start"], "source": "BLS", "url": current.get("url") or "https://www.bls.gov/schedule/news_release/"})
                current = None
            elif current is not None and line.startswith("DTSTART"):
                current["start"] = _parse_ics_date(line)
            elif current is not None and line.startswith("SUMMARY"):
                current["summary"] = _unescape_ics(line.split(":", 1)[1])
            elif current is not None and line.startswith("URL"):
                current["url"] = line.split(":", 1)[1]
        return events

    def _bea_events(self):
        data = json.loads(self._get_text(BEA_JSON))
        events = []
        for title, payload in data.items():
            if not isinstance(payload, dict):
                continue
            for value in payload.get("release_dates", []):
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    events.append({"title": title, "when": dt, "source": "BEA", "url": "https://www.bea.gov/news/schedule/"})
                except (TypeError, ValueError):
                    continue
        return events

    def _fed_events(self):
        parser = _TextExtractor()
        parser.feed(self._get_text(FED_FOMC))
        text = " ".join(parser.parts)
        current_year = datetime.now(ET).year
        events = []
        sections = list(re.finditer(r"(20\d{2})\s+FOMC Meetings", text))
        for index, section in enumerate(sections):
            year = int(section.group(1))
            if year < current_year:
                continue
            end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
            content = text[section.end():end]
            for month_name, first, last in re.findall(
                r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s*[-–]\s*(\d{1,2})\b",
                content,
            ):
                month = datetime.strptime(month_name, "%B").month
                # The statement is published at 2 p.m. Eastern on the second meeting day.
                when = datetime(year, month, int(last), 14, 0, tzinfo=ET)
                events.append({"title": "FOMC 정책 결정 (예정)", "when": when, "source": "Federal Reserve", "url": FED_FOMC})
        return events

    def upcoming(self, *, now=None, days=14, timezone="Asia/Seoul"):
        now = now or datetime.now(timezone_obj(timezone))
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone_obj(timezone))
        end = now + timedelta(days=days)
        events, errors = [], []
        for name, fetch in (("BLS", self._bls_events), ("BEA", self._bea_events), ("Federal Reserve", self._fed_events)):
            try:
                events.extend(fetch())
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")
        filtered = [e for e in events if now.astimezone(timezone_obj("UTC")) <= e["when"].astimezone(timezone_obj("UTC")) <= end.astimezone(timezone_obj("UTC"))]
        unique = {(e["title"], e["when"].isoformat()): e for e in filtered}
        return sorted(unique.values(), key=lambda e: e["when"]), errors


def timezone_obj(name):
    return ZoneInfo("UTC") if name == "UTC" else ZoneInfo(name)


def render_events(events, tz="Asia/Seoul"):
    zone = timezone_obj(tz)
    if not events:
        return "향후 14일 내 수집된 주요 일정이 없습니다."
    lines = [f"향후 일정 ({tz} 기준):"]
    for event in events[:15]:
        local = event["when"].astimezone(zone)
        lines.append(f"• {local:%m/%d %H:%M} · {event['title']} ({event['source']}) · {event.get('url') or ''}")
    return "\n".join(lines)
