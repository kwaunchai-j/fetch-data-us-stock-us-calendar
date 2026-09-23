"""
ตารางประกาศตัวเลขเศรษฐกิจสหรัฐ (เวลา ET) + ระดับผลกระทบ

ใส่วันไว้ตรง ๆ จากตารางทางการ เพราะเว็บหน่วยงานรัฐบล็อกการดึงจาก GitHub Actions
อัปเดตปีละครั้งเมื่อหน่วยงานประกาศตารางปีถัดไป (ปกติช่วง ต.ค.–ธ.ค.):
  CPI    https://www.bls.gov/schedule/news_release/cpi.htm
  NFP    https://www.bls.gov/schedule/news_release/empsit.htm
  PPI    https://www.bls.gov/schedule/news_release/ppi.htm
  JOLTS  https://www.bls.gov/schedule/news_release/jolts.htm
  ECI    https://www.bls.gov/schedule/news_release/eci.htm
  PCE / GDP  https://www.bea.gov/news/schedule
  Retail Sales  https://www.census.gov/retail/release_schedule.html
ถ้าตารางไหนใกล้หมด สคริปต์จะลง event เตือน ⚠️ ไว้ในปฏิทินให้เอง

ส่วนที่คำนวณเองตามกฎ (ไม่ต้องอัปเดต):
  ISM Manufacturing PMI = วันทำการแรกของเดือน 10:00 ET
  ISM Services PMI      = วันทำการที่ 3 ของเดือน 10:00 ET
  Initial Jobless Claims = ทุกวันพฤหัส 08:30 ET (ถ้าพฤหัสหยุด เลื่อนเป็นพุธ)
  FOMC Minutes          = 3 สัปดาห์หลังประกาศดอกเบี้ย 14:00 ET
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
HIGH, MED, LOW = "🔴", "🟡", "🟢"

# วันหยุดราชการสหรัฐ (ใช้นับ "วันทำการ" ของ ISM และเลื่อนวัน Jobless Claims)
US_HOLIDAYS = {date.fromisoformat(d) for d in [
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-05-31", "2027-06-18", "2027-07-05",
    "2027-09-06", "2027-11-25", "2027-12-24",
    "2028-01-17",
]}

# ---------------------------------------------------------------- ตารางทางการ
# (รหัส, ชื่อไทย, ระดับ, เวลา ET, ผู้ประกาศ, ลิงก์, คำอธิบาย, [(วันประกาศ, งวดข้อมูล, ระดับเฉพาะวัน|None)])
SCHEDULED = [
    ("cpi", "CPI เงินเฟ้อ", HIGH, "08:30", "BLS", "https://www.bls.gov/cpi/",
     "ดัชนีราคาผู้บริโภค ตัวชี้วัดเงินเฟ้อหลักที่ Fed ใช้ตัดสินดอกเบี้ย ออกสูงกว่าคาด = กดดันหุ้น/หนุน yield",
     [("2026-01-13", "Dec 2025", None), ("2026-02-13", "Jan 2026", None), ("2026-03-11", "Feb 2026", None),
      ("2026-04-10", "Mar 2026", None), ("2026-05-12", "Apr 2026", None), ("2026-06-10", "May 2026", None),
      ("2026-07-14", "Jun 2026", None), ("2026-08-12", "Jul 2026", None), ("2026-09-11", "Aug 2026", None),
      ("2026-10-14", "Sep 2026", None), ("2026-11-10", "Oct 2026", None), ("2026-12-10", "Nov 2026", None)]),

    ("nfp", "Non-farm Payrolls / อัตราว่างงาน", HIGH, "08:30", "BLS", "https://www.bls.gov/ces/",
     "ตัวเลขจ้างงานนอกภาคเกษตร + อัตราว่างงาน สะท้อนความแข็งแรงเศรษฐกิจ มีผลแรงต่อคาดการณ์ดอกเบี้ย",
     [("2026-01-09", "Dec 2025", None), ("2026-02-11", "Jan 2026", None), ("2026-03-06", "Feb 2026", None),
      ("2026-04-03", "Mar 2026", None), ("2026-05-08", "Apr 2026", None), ("2026-06-05", "May 2026", None),
      ("2026-07-02", "Jun 2026", None), ("2026-08-07", "Jul 2026", None), ("2026-09-04", "Aug 2026", None),
      ("2026-10-02", "Sep 2026", None), ("2026-11-06", "Oct 2026", None), ("2026-12-04", "Nov 2026", None)]),

    ("pce", "Core PCE เงินเฟ้อ (ตัวที่ Fed ใช้)", HIGH, "08:30", "BEA",
     "https://www.bea.gov/data/personal-consumption-expenditures-price-index",
     "Personal Income & Outlays — ดัชนี PCE คือเป้าเงินเฟ้อ 2% ของ Fed โดยตรง พร้อมรายได้/การใช้จ่ายครัวเรือน",
     [("2026-09-30", "Aug 2026", None), ("2026-10-29", "Sep 2026", None),
      ("2026-11-25", "Oct 2026", None), ("2026-12-23", "Nov 2026", None)]),

    ("gdp", "GDP", MED, "08:30", "BEA", "https://www.bea.gov/data/gdp/gross-domestic-product",
     "ผลิตภัณฑ์มวลรวมในประเทศ — ตัวเลขประมาณการครั้งแรก (Advance) ขยับตลาดมากที่สุด",
     [("2026-09-30", "Q2 2026 Third", None), ("2026-10-29", "Q3 2026 Advance", HIGH),
      ("2026-11-25", "Q3 2026 Second", None), ("2026-12-23", "Q3 2026 Third", None)]),

    ("ppi", "PPI ราคาผู้ผลิต", MED, "08:30", "BLS", "https://www.bls.gov/ppi/",
     "ดัชนีราคาผู้ผลิต สัญญาณล่วงหน้าของเงินเฟ้อฝั่งต้นทุน",
     [("2026-01-14", "Nov 2025", None), ("2026-01-30", "Dec 2025", None), ("2026-02-27", "Jan 2026", None),
      ("2026-03-18", "Feb 2026", None), ("2026-04-14", "Mar 2026", None), ("2026-05-13", "Apr 2026", None),
      ("2026-06-11", "May 2026", None), ("2026-07-15", "Jun 2026", None), ("2026-08-13", "Jul 2026", None),
      ("2026-09-10", "Aug 2026", None), ("2026-10-15", "Sep 2026", None), ("2026-11-13", "Oct 2026", None),
      ("2026-12-15", "Nov 2026", None)]),

    ("retail", "Retail Sales ยอดค้าปลีก", MED, "08:30", "Census",
     "https://www.census.gov/retail/index.html",
     "ยอดขายปลีก สะท้อนการบริโภคซึ่งเป็น ~70% ของ GDP สหรัฐ มีผลต่อหุ้นค้าปลีก/consumer",
     [("2026-03-06", "Jan 2026", None), ("2026-04-01", "Feb 2026", None), ("2026-04-21", "Mar 2026", None),
      ("2026-05-14", "Apr 2026", None), ("2026-06-17", "May 2026", None), ("2026-07-16", "Jun 2026", None),
      ("2026-08-14", "Jul 2026", None), ("2026-09-16", "Aug 2026", None), ("2026-10-15", "Sep 2026", None),
      ("2026-11-17", "Oct 2026", None), ("2026-12-16", "Nov 2026", None)]),

    ("jolts", "JOLTS ตำแหน่งงานว่าง", MED, "10:00", "BLS", "https://www.bls.gov/jlt/",
     "จำนวนตำแหน่งงานว่าง/การลาออก บอกความตึงตัวของตลาดแรงงาน",
     [("2026-01-07", "Nov 2025", None), ("2026-02-05", "Dec 2025", None), ("2026-03-13", "Jan 2026", None),
      ("2026-03-31", "Feb 2026", None), ("2026-05-05", "Mar 2026", None), ("2026-06-02", "Apr 2026", None),
      ("2026-06-30", "May 2026", None), ("2026-08-04", "Jun 2026", None), ("2026-09-01", "Jul 2026", None),
      ("2026-09-29", "Aug 2026", None), ("2026-11-03", "Sep 2026", None), ("2026-12-01", "Oct 2026", None)]),

    ("eci", "ECI ต้นทุนค่าจ้าง", MED, "08:30", "BLS", "https://www.bls.gov/eci/",
     "ต้นทุนค่าจ้างรายไตรมาส Fed ใช้ดูแรงกดดันเงินเฟ้อจากค่าแรง",
     [("2026-02-10", "Q4 2025", None), ("2026-04-30", "Q1 2026", None),
      ("2026-07-31", "Q2 2026", None), ("2026-10-30", "Q3 2026", None)]),
]


# ---------------------------------------------------------------- helpers
def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in US_HOLIDAYS


def nth_business_day(year: int, month: int, n: int) -> date:
    d, count = date(year, month, 1), 0
    while True:
        if is_business_day(d):
            count += 1
            if count == n:
                return d
        d += timedelta(days=1)


def at_et(d: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ET)


def _months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


# ---------------------------------------------------------------- main API
def build_macro_events(start: date, end: date, fomc_days: list[str]) -> list[dict]:
    """คืน list ของ dict: uid, title, level, start(datetime ET), minutes, desc, url"""
    out: list[dict] = []

    # 1) ตารางทางการ
    for code, name, lvl, hhmm, src, url, about, rows in SCHEDULED:
        for ds, period, override in rows:
            d = date.fromisoformat(ds)
            if not (start <= d <= end):
                continue
            level = override or lvl
            out.append(dict(uid=f"macro:{code}:{ds}", level=level,
                            title=f"{level} {name} ({period})", start=at_et(d, hhmm), minutes=30,
                            desc=f"{about}\nงวดข้อมูล: {period} | ประกาศโดย {src} เวลา {hhmm} ET",
                            url=url))
        # เตือนเมื่อตารางใกล้หมด
        last = max(date.fromisoformat(r[0]) for r in rows)
        if last < end:
            warn_day = max(start, last)
            out.append(dict(uid=f"macro:update:{code}:{last}", level=LOW, allday=warn_day,
                            title=f"⚠️ เพิ่มวันประกาศ {name} ปีถัดไปใน macro_events.py",
                            desc=f"ตาราง {name} ในสคริปต์หมดที่ {last}\nดูวันใหม่ที่ {url}\n"
                                 "แล้วเพิ่มลงใน SCHEDULED ของ macro_events.py",
                            url=url, start=None, minutes=0))

    # 2) ISM PMI (คำนวณจากกฎ)
    for y, m in _months(start, end):
        for code, name, n in (("ism-mfg", "ISM Manufacturing PMI", 1), ("ism-svc", "ISM Services PMI", 3)):
            d = nth_business_day(y, m, n)
            if start <= d <= end:
                prev = date(y, m, 1) - timedelta(days=1)
                out.append(dict(uid=f"macro:{code}:{d}", level=MED,
                                title=f"{MED} {name} ({prev:%b %Y})", start=at_et(d, "10:00"), minutes=30,
                                desc=("ดัชนีผู้จัดการฝ่ายจัดซื้อ > 50 = ขยายตัว, < 50 = หดตัว\n"
                                      + ("ภาคการผลิต — ดูองค์ประกอบ Prices Paid (เงินเฟ้อ) และ New Orders"
                                         if n == 1 else
                                         "ภาคบริการ (~80% ของเศรษฐกิจสหรัฐ) — ดู Prices และ Employment")
                                      + f"\nงวดข้อมูล: {prev:%b %Y} | ISM 10:00 ET (คำนวณจากกฎวันทำการ)"),
                                url="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/"))

    # 3) Initial Jobless Claims ทุกพฤหัส
    d = start
    while d <= end:
        if d.weekday() == 3:
            rel = d if is_business_day(d) else d - timedelta(days=1)
            if start <= rel <= end:
                out.append(dict(uid=f"macro:claims:{d}", level=LOW,
                                title=f"{LOW} Jobless Claims รายสัปดาห์", start=at_et(rel, "08:30"), minutes=15,
                                desc="จำนวนผู้ขอรับสวัสดิการว่างงานครั้งแรก (รายสัปดาห์)\n"
                                     "ปกติผลกระทบต่ำ เว้นแต่ตัวเลขพุ่งผิดปกติ (สัญญาณตลาดแรงงานอ่อนตัว)",
                                url="https://www.dol.gov/ui/data.pdf"))
        d += timedelta(days=1)

    # 4) FOMC Minutes = 3 สัปดาห์หลังประกาศดอกเบี้ย
    for ds in fomc_days:
        d = date.fromisoformat(ds) + timedelta(days=21)
        if start <= d <= end:
            out.append(dict(uid=f"macro:fomc-minutes:{d}", level=MED,
                            title=f"{MED} FOMC Minutes (รายงานการประชุม {ds})", start=at_et(d, "14:00"),
                            minutes=30,
                            desc="รายงานการประชุม Fed ครั้งก่อน ดูว่ากรรมการเอียงไปทางขึ้น/ลดดอกเบี้ยแค่ไหน",
                            url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"))
    return out
