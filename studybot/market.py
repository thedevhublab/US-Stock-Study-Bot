"""End-of-day US index closes from FRED's public graph CSV export."""
import csv
from datetime import date, datetime, time as day_time, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

import httpx


INDEXES = {
    "S&P 500": "SP500",
    "Nasdaq Composite": "NASDAQCOM",
    "Dow Jones Industrial Average": "DJIA",
}
BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


class MarketDataService:
    def __init__(self, timeout=12, get=None, clock=None):
        self.timeout = timeout
        self._get = get or httpx.get
        self._clock = clock or (lambda: datetime.now(ZoneInfo("America/New_York")))

    def _index(self, name, symbol):
        start = (self._clock().date() - timedelta(days=35)).isoformat()
        response = self._get(BASE_URL, params={"id": symbol, "cosd": start}, timeout=self.timeout, follow_redirects=True,
                             headers={"User-Agent": "US-Stock-Study-Bot/0.1 personal non-commercial learning"})
        response.raise_for_status()
        rows = list(csv.DictReader(StringIO(response.text)))
        now_et = self._clock().astimezone(ZoneInfo("America/New_York"))
        valid = []
        for row in rows:
            try:
                close = float(row[symbol])
                day = date.fromisoformat(row["observation_date"])
                # A provider can expose an in-progress daily candle. Never label it as a close.
                if day > now_et.date() or (day == now_et.date() and now_et.time().replace(tzinfo=None) < day_time(16, 30)):
                    continue
                valid.append((day, close))
            except (KeyError, TypeError, ValueError):
                continue
        valid.sort()
        if not valid:
            raise ValueError("공급원이 유효한 종가를 제공하지 않았습니다")
        day, close = valid[-1]
        prior = valid[-2][1] if len(valid) >= 2 else None
        change = close - prior if prior is not None else None
        percent = change / prior * 100 if prior else None
        return {"name": name, "symbol": symbol, "date": day.isoformat(), "close": close, "change": change, "percent": percent}

    def fetch(self):
        data, errors = [], []
        for name, symbol in INDEXES.items():
            try:
                data.append(self._index(name, symbol))
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")
        return data, errors

    @staticmethod
    def render(data):
        if not data:
            return "지수 종가: 데이터를 가져오지 못했습니다."
        lines = ["최근 완료 거래일 종가 (일간 데이터; 지수별 기준일 표시):"]
        for item in data:
            if item["percent"] is None:
                movement = "전일 대비 값 없음"
            else:
                movement = f"{item['change']:+,.2f} ({item['percent']:+.2f}%)"
            lines.append(f"• {item['name']} ({item['date']}): {item['close']:,.2f} · 전일 대비 {movement}")
        lines.append("자료: [FRED](https://fred.stlouisfed.org) 일간 종가 (원자료: S&P Dow Jones Indices LLC·Nasdaq, Inc.). Copyrighted: Pre-approval required. 개인 비상업 학습용에 한해 표시하며 출처와 저작권 표시를 유지합니다. 장중 시세가 아닙니다.")
        return "\n".join(lines)


def last_n_days(days=14):
    return date.today(), date.today() + timedelta(days=days)
