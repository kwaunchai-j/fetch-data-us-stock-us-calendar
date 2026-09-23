#!/usr/bin/env python3
"""
สร้างไฟล์ docs/us-stocks.ics สำหรับ subscribe บน iPhone Calendar

แหล่งข้อมูล
- Finnhub (ฟรี): ปฏิทินงบ, ราคา (quote), ข่าวรายบริษัท
- Federal Reserve: วันประชุม FOMC (ใส่ไว้ในโค้ด)
- BLS: ตารางประกาศ CPI / PPI / Non-farm payrolls / JOLTS (ไฟล์ .ics ทางการ)

ไม่ต้องติดตั้ง library เพิ่ม ใช้แค่ Python 3.9+
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_ICS = os.path.join(ROOT, "docs", "us-stocks.ics")
STATE_FILE = os.path.join(ROOT, "data", "reactions.json")

API_KEY = os.environ.get("FINNHUB_API_KEY", "")
DAYS_BACK = 10          # เก็บ event ย้อนหลัง (เพื่ออัปเดตผลงบ/ราคา)
DAYS_AHEAD = 35         # ลง event ล่วงหน้า
BIG_MOVE_PCT = 3.0      # ขยับเกินเท่านี้ถึงดึงข่าวมาแปะ
USER_AGENT = "us-stock-calendar/1.0 (personal use)"

# หุ้นใหญ่ที่จะแยกเป็น event ของตัวเอง (ที่เหลือใน S&P 500 จะรวมเป็นสรุปรายวัน)
MEGA_CAPS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK.B",
    "JPM", "LLY", "V", "MA", "WMT", "XOM", "UNH", "ORCL", "COST", "HD", "PG",
    "JNJ", "NFLX", "BAC", "ABBV", "KO", "CRM", "AMD", "CVX", "MRK", "PEP",
    "ADBE", "CSCO", "WFC", "MCD", "QCOM", "IBM", "INTU", "TXN", "GS", "MU",
    "PLTR", "NKE", "DIS", "INTC", "BA",
]

# FOMC (วันที่ 2 ของการประชุม = วันประกาศดอกเบี้ย 14:00 ET)
# ที่มา: federalreserve.gov/monetarypolicy/fomccalendars.htm  (* = มี dot plot / SEP)
FOMC_DECISION_DAYS = [
    ("2026-10-28", False), ("2026-12-09", True),
    ("2027-01-27", False), ("2027-03-17", True), ("2027-04-28", False),
    ("2027-06-09", True), ("2027-07-28", False), ("2027-09-15", True),
    ("2027-10-27", False), ("2027-12-08", True),
]

# คำใน SUMMARY ของ BLS ที่เราสนใจ -> (ชื่อไทย, ระดับผลกระทบ)
BLS_KEEP = [
    (r"Consumer Price Index", "CPI เงินเฟ้อ", "🔴"),
    (r"Employment Situation", "Non-farm Payrolls / ตัวเลขจ้างงาน", "🔴"),
    (r"Producer Price Index", "PPI ราคาผู้ผลิต", "🟠"),
    (r"Job Openings and Labor Turnover", "JOLTS ตำแหน่งงานว่าง", "🟠"),
    (r"Employment Cost Index", "ECI ต้นทุนค่าจ้าง", "🟠"),
]


# ---------------------------------------------------------------- HTTP
def http_get(url: str, params: dict | None = None, retries: int = 3) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed {url.split('token=')[0]}: {last}")


def finnhub(path: str, **params):
    params["token"] = API_KEY
    time.sleep(1.1)  # free tier = 60 calls/min
    return json.loads(http_get(f"https://finnhub.io/api/v1{path}", params))


# ---------------------------------------------------------------- data sources
def load_sp500() -> dict[str, str]:
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    try:
        rows = csv.DictReader(io.StringIO(http_get(url).decode("utf-8")))
        return {r["Symbol"].strip(): r["Security"].strip() for r in rows}
    except Exception as e:  # noqa: BLE001
        print("WARN: โหลดรายชื่อ S&P 500 ไม่ได้:", e, file=sys.stderr)
        return {}


def load_earnings(start: date, end: date) -> list[dict]:
    data = finnhub("/calendar/earnings", **{"from": start.isoformat(), "to": end.isoformat()})
    return data.get("earningsCalendar", []) or []


def load_bls_events(start: date, end: date) -> list[dict]:
    try:
        raw = http_get("https://www.bls.gov/schedule/news_release/bls.ics").decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        print("WARN: โหลดปฏิทิน BLS ไม่ได้:", e, file=sys.stderr)
        return []
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"\n[ \t]", "", raw)  # unfold
    events = []
    for block in raw.split("BEGIN:VEVENT")[1:]:
        summary = re.search(r"^SUMMARY[^:]*:(.*)$", block, re.M)
        dtstart = re.search(r"^DTSTART([^:]*):(\S+)$", block, re.M)
        if not summary or not dtstart:
            continue
        s = summary.group(1).replace("\\,", ",").strip()
        match = next((k for k in BLS_KEEP if re.search(k[0], s, re.I)), None)
        if not match:
            continue
        params, val = dtstart.group(1), dtstart.group(2)
        try:
            if len(val) == 8:  # date only -> 08:30 ET (เวลาปกติของ BLS)
                dt = datetime.strptime(val, "%Y%m%d").replace(hour=8, minute=30, tzinfo=ET)
            elif val.endswith("Z"):
                dt = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            else:
                tz = ET
                m = re.search(r"TZID=([^;:]+)", params)
                if m:
                    try:
                        tz = ZoneInfo(m.group(1).strip('"'))
                    except Exception:  # noqa: BLE001
                        tz = ET
                dt = datetime.strptime(val, "%Y%m%dT%H%M%S").replace(tzinfo=tz)
        except ValueError:
            continue
        if start <= dt.astimezone(ET).date() <= end:
            events.append({"dt": dt, "name_th": match[1], "icon": match[2], "summary_en": s})
    return events


# ---------------------------------------------------------------- helpers
def last_closed_session(now_et: datetime) -> date:
    """วันซื้อขายล่าสุดที่ปิดตลาดแล้ว (ไม่คิดวันหยุดนักขัตฤกษ์)"""
    d = now_et.date()
    if now_et.hour < 16 or d.weekday() >= 5:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def reaction_day(report: date, hour: str) -> date:
    """วันที่ราคาหุ้นตอบสนองต่องบ: bmo = วันเดียวกัน, amc = วันทำการถัดไป"""
    if hour == "amc":
        return next_weekday(report)
    return report


def fmt_money(x) -> str:
    if x is None:
        return "-"
    x = float(x)
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(x) >= div:
            return f"${x/div:,.2f}{unit}"
    return f"${x:,.0f}"


def surprise(actual, est) -> tuple[str, float | None]:
    if actual is None or est in (None, 0):
        return "", None
    pct = (float(actual) - float(est)) / abs(float(est)) * 100
    tag = "✅ Beat" if pct > 0.5 else ("❌ Miss" if pct < -0.5 else "➖ In-line")
    return tag, pct


# ---------------------------------------------------------------- ICS writer
def esc(t: str) -> str:
    return (t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
             .replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line: str) -> str:
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > 73:
            out.append(cur.decode("utf-8"))
            cur = b" " + b
        else:
            cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


def utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def vevent(uid, summary, desc, start=None, end=None, allday: date | None = None, url=None, alarm_min=None):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VEVENT", f"UID:{uid}@us-stock-calendar", f"DTSTAMP:{stamp}"]
    if allday:
        lines += [f"DTSTART;VALUE=DATE:{allday:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{allday + timedelta(days=1):%Y%m%d}",
                  "TRANSP:TRANSPARENT"]
    else:
        lines += [f"DTSTART:{utc(start)}", f"DTEND:{utc(end)}", "TRANSP:TRANSPARENT"]
    lines += [f"SUMMARY:{esc(summary)}", f"DESCRIPTION:{esc(desc)}"]
    if url:
        lines.append(f"URL:{url}")
    if alarm_min is not None:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(summary)}",
                  f"TRIGGER:-PT{alarm_min}M", "END:VALARM"]
    lines.append("END:VEVENT")
    return "\r\n".join(fold(l) for l in lines)


# ---------------------------------------------------------------- main
def main() -> int:
    if not API_KEY:
        print("ERROR: ตั้งค่า FINNHUB_API_KEY ก่อน", file=sys.stderr)
        return 1

    now_et = datetime.now(ET)
    today = now_et.date()
    start, end = today - timedelta(days=DAYS_BACK), today + timedelta(days=DAYS_AHEAD)
    session = last_closed_session(now_et)

    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)

    sp500 = load_sp500()
    mega = set(MEGA_CAPS)
    earnings = load_earnings(start, end)
    if sp500:
        earnings = [e for e in earnings if e.get("symbol") in sp500]
    print(f"earnings (S&P 500) in window: {len(earnings)}")

    events: list[str] = []
    daily: dict[date, list[dict]] = {}

    for e in earnings:
        sym, hour = e["symbol"], (e.get("hour") or "").lower()
        rdate = date.fromisoformat(e["date"])
        name = sp500.get(sym, sym)
        tag, spct = surprise(e.get("epsActual"), e.get("epsEstimate"))
        key = f"{sym}:{e['date']}"

        # บันทึกราคาหลังประกาศงบ (เฉพาะหุ้นใหญ่ และวันที่ตลาดตอบสนอง = session ล่าสุด)
        if sym in mega and reaction_day(rdate, hour) == session and key not in state:
            try:
                q = finnhub("/quote", symbol=sym)
                if q.get("c"):
                    rec = {"close": q["c"], "pct": q.get("dp"), "session": session.isoformat()}
                    if q.get("dp") is not None and abs(q["dp"]) >= BIG_MOVE_PCT:
                        news = finnhub("/company-news", symbol=sym,
                                       **{"from": (rdate - timedelta(days=1)).isoformat(),
                                          "to": session.isoformat()})
                        rec["news"] = [{"h": n.get("headline", ""), "u": n.get("url", ""),
                                        "s": n.get("source", "")} for n in news[:3]]
                    state[key] = rec
            except Exception as ex:  # noqa: BLE001
                print("WARN quote", sym, ex, file=sys.stderr)

        if sym not in mega:
            daily.setdefault(rdate, []).append({**e, "name": name, "tag": tag, "spct": spct})
            continue

        # ----- event รายตัว (หุ้นใหญ่)
        react = state.get(key)
        title = f"💼 {sym} ประกาศงบ"
        if tag:
            title = f"💼 {sym} {tag} {spct:+.1f}%"
        if react and react.get("pct") is not None:
            arrow = "🚀" if react["pct"] >= 0 else "🔻"
            title += f" | หุ้น {arrow}{react['pct']:+.2f}%"

        when = {"bmo": "ก่อนตลาดเปิด (BMO)", "amc": "หลังตลาดปิด (AMC)"}.get(hour, "ยังไม่ระบุเวลา")
        d = [f"{name} ({sym}) — ไตรมาส Q{e.get('quarter')}/{e.get('year')}",
             f"เวลา: {when}",
             f"EPS คาด: {e.get('epsEstimate') if e.get('epsEstimate') is not None else '-'}"
             + (f" | จริง: {e['epsActual']}" if e.get("epsActual") is not None else ""),
             f"รายได้คาด: {fmt_money(e.get('revenueEstimate'))}"
             + (f" | จริง: {fmt_money(e['revenueActual'])}" if e.get("revenueActual") else "")]
        if react:
            d.append(f"ราคาปิดวันตอบสนองงบ ({react['session']}): ${react['close']:.2f} ({react['pct']:+.2f}%)")
            for n in react.get("news", []):
                d.append(f"📰 {n['h']} — {n['s']}\n{n['u']}")
        url = f"https://finance.yahoo.com/quote/{sym.replace('.', '-')}"

        if hour == "bmo":
            s = datetime.combine(rdate, datetime.min.time(), ET).replace(hour=7)
            events.append(vevent(key, title, "\n".join(d), s, s + timedelta(minutes=30), url=url))
        elif hour == "amc":
            s = datetime.combine(rdate, datetime.min.time(), ET).replace(hour=16, minute=5)
            events.append(vevent(key, title, "\n".join(d), s, s + timedelta(minutes=30), url=url))
        else:
            events.append(vevent(key, title, "\n".join(d), allday=rdate, url=url))

    # ----- สรุปรายวันของ S&P 500 ที่เหลือ
    for d_, rows in sorted(daily.items()):
        rows.sort(key=lambda r: -(r.get("revenueEstimate") or 0))
        lines = [f"บริษัทใน S&P 500 ที่ประกาศงบวันนี้ {len(rows)} ราย (เรียงตามรายได้คาด)", ""]
        for label, code in (("ก่อนตลาดเปิด (BMO)", "bmo"), ("หลังตลาดปิด (AMC)", "amc"), ("ไม่ระบุเวลา", "")):
            grp = [r for r in rows if (r.get("hour") or "").lower() == code
                   or (code == "" and (r.get("hour") or "").lower() not in ("bmo", "amc"))]
            if not grp:
                continue
            lines.append(f"— {label} —")
            for r in grp:
                res = f" {r['tag']} {r['spct']:+.1f}%" if r["tag"] else ""
                lines.append(f"{r['symbol']} {r['name']} | EPS คาด {r.get('epsEstimate', '-')}{res}")
            lines.append("")
        top = ", ".join(r["symbol"] for r in rows[:6])
        events.append(vevent(f"sp500-daily:{d_}", f"📊 งบ S&P 500 ({len(rows)}): {top}",
                             "\n".join(lines), allday=d_))

    # ----- FOMC
    for ds, sep in FOMC_DECISION_DAYS:
        d_ = date.fromisoformat(ds)
        if not (start <= d_ <= end + timedelta(days=60)):
            continue
        s = datetime.combine(d_, datetime.min.time(), ET).replace(hour=14)
        title = "🏦 FOMC ประกาศดอกเบี้ย" + (" + Dot Plot" if sep else "")
        desc = ("Fed ประกาศมติอัตราดอกเบี้ย 14:00 ET และแถลงข่าว 14:30 ET\n"
                + ("มี Summary of Economic Projections (dot plot)\n" if sep else "")
                + "ผลกระทบสูงต่อทั้งตลาด (ดัชนี, bond yield, USD)")
        events.append(vevent(f"fomc:{ds}", title, desc, s, s + timedelta(minutes=60),
                             url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                             alarm_min=30))

    # ----- BLS macro
    for b in load_bls_events(start, end + timedelta(days=30)):
        s = b["dt"]
        events.append(vevent(f"bls:{utc(s)}:{b['name_th']}", f"{b['icon']} {b['name_th']}",
                             f"{b['summary_en']}\nประกาศโดย BLS — ตัวเลขมหภาคที่ขยับตลาดทั้งกระดาน",
                             s, s + timedelta(minutes=30), url="https://www.bls.gov/schedule/",
                             alarm_min=15))

    cal = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//us-stock-calendar//TH",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:US Stocks 📈", "X-WR-TIMEZONE:Asia/Bangkok",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H",
        *events, "END:VCALENDAR", ""])
    os.makedirs(os.path.dirname(OUT_ICS), exist_ok=True)
    with open(OUT_ICS, "w", encoding="utf-8", newline="") as f:
        f.write(cal)

    # ตัด state เก่าทิ้ง
    cutoff = (today - timedelta(days=120)).isoformat()
    state = {k: v for k, v in state.items() if k.split(":", 1)[1] >= cutoff}
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)

    print(f"wrote {len(events)} events -> {OUT_ICS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
