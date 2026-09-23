# US Stocks → iPhone Calendar 📈

ปฏิทิน event ที่ขยับราคาหุ้นสหรัฐ อัปเดตเองทุกเช้าวันทำการ (06:30 เวลาไทย) แล้วเด้งเข้า iPhone Calendar ผ่านการ subscribe

## ระดับผลกระทบ (ขึ้นต้นชื่อ event)

| สี | ความหมาย | ตัวอย่าง |
|---|---|---|
| 🔴 สูง | ขยับทั้งตลาด — ควรจับตา มีเตือนล่วงหน้า | FOMC, CPI, Non-farm, งบ AAPL/MSFT/NVDA/GOOGL/AMZN/META/AVGO/TSLA, หุ้นขยับจริง ≥ 5% |
| 🟡 กลาง | ขยับกลุ่มอุตสาหกรรม/หุ้นใหญ่ | PPI, JOLTS, ECI, งบหุ้นใหญ่ตัวอื่น, วันที่มีงบ ≥ 20 บริษัท, หุ้นขยับจริง 2–5% |
| 🟢 ต่ำ | ผลเฉพาะตัว | วันที่มีงบน้อย, หุ้นขยับจริง < 2% |

งบของหุ้นใหญ่: **ก่อนประกาศ** ใช้ระดับที่คาดไว้ **หลังประกาศ** เปลี่ยนเป็นระดับตาม % ที่ราคาขยับจริง และถ้าขยับตั้งแต่ 2% ขึ้นไป จะแนบพาดหัวข่าวไว้ในโน้ตด้วย
ปรับเกณฑ์ได้ที่ `MOVE_HIGH_PCT`, `MOVE_MED_PCT`, `INDEX_MOVERS`, `DAILY_MED_COUNT` ใน `build_calendar.py`

## จะเห็นอะไรในปฏิทิน

| Event | ตัวอย่างชื่อ | เวลาไทย |
|---|---|---|
| งบหุ้นใหญ่ ~45 ตัว (รายตัว) | `💼 NVDA ประกาศงบ` → หลังประกาศจะเปลี่ยนเป็น `💼 NVDA ✅ Beat +8.1% \| หุ้น 🚀+4.20%` | BMO ≈ 18:00–19:00 / AMC ≈ 03:05–04:05 |
| งบ S&P 500 ตัวอื่น (รวมวันละ 1 event) | `📊 งบ S&P 500 (23): ORCL, FDX, ...` | ทั้งวัน |
| FOMC ประกาศดอกเบี้ย | `🏦 FOMC ประกาศดอกเบี้ย + Dot Plot` (เตือนก่อน 30 นาที) | ตี 1–2 |
| CPI / Non-farm / PPI / JOLTS / ECI | `🔴 CPI เงินเฟ้อ` (เตือนก่อน 15 นาที) | 19:30–20:30 |

ถ้าหุ้นใหญ่ขยับเกิน ±2% หลังประกาศงบ สคริปต์จะดึง **พาดหัวข่าว 3 ข่าวล่าสุด + ลิงก์** มาใส่ไว้ในโน้ตของ event นั้น

เวลาในไฟล์เก็บเป็น UTC แล้ว iPhone จะแปลงเป็นเวลาไทยให้เอง (รวมช่วงที่สหรัฐเปลี่ยน daylight saving ด้วย)

## ติดตั้ง (ประมาณ 10 นาที ทำครั้งเดียว)

1. **ขอ API key ฟรีจาก Finnhub** — สมัครที่ https://finnhub.io/register แล้วก๊อป key ในหน้า Dashboard
2. **สร้าง repo บน GitHub** แบบ **Public** (GitHub Pages ฟรีต้องเป็น public; ในไฟล์มีแค่ข้อมูลตลาด ไม่มีข้อมูลส่วนตัว) แล้วอัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้ขึ้นไป (รวมโฟลเดอร์ `.github`)
3. **ใส่ key**: Settings → Secrets and variables → Actions → New repository secret
   ชื่อ `FINNHUB_API_KEY` ค่า = key จากข้อ 1
4. **เปิด GitHub Pages**: Settings → Pages → Source: *Deploy from a branch* → Branch `main` / โฟลเดอร์ `/docs` → Save
5. **รันครั้งแรก**: แท็บ Actions → *Update US stock calendar* → **Run workflow** (รอ 1–3 นาที)
6. เปิด `https://<username>.github.io/<ชื่อ-repo>/us-stocks.ics` ในเบราว์เซอร์ ถ้าไฟล์ดาวน์โหลดได้แสดงว่าใช้ได้

## Subscribe บน iPhone

Settings → Apps → Calendar → Calendar Accounts → Add Account → Other → **Add Subscribed Calendar**
→ Server: `https://<username>.github.io/<ชื่อ-repo>/us-stocks.ics` → Next → Save

(บน iOS รุ่นเก่า เมนูอยู่ที่ Settings → Calendar → Accounts)

แนะนำให้ตั้ง **Fetch New Data** เป็น *Hourly* ที่ Settings → Apps → Calendar → Calendar Accounts → Fetch New Data
ถ้า subscribe ผ่าน iCloud บน Mac (Calendar → File → New Calendar Subscription → Location: iCloud) ปฏิทินจะ sync ไปทุกเครื่อง Apple

## ปรับแต่ง (แก้ใน `build_calendar.py`)

- `MEGA_CAPS` — หุ้นที่อยากให้แยกเป็น event ของตัวเอง
- `BIG_MOVE_PCT` — เกณฑ์ % ที่จะดึงข่าวมาแปะ (ค่าเริ่มต้น 2)
- `DAYS_AHEAD` — ลง event ล่วงหน้ากี่วัน (ค่าเริ่มต้น 35)
- `FOMC_DECISION_DAYS` — วันประชุม Fed ถึงสิ้นปี 2027 (หลังจากนั้นต้องเพิ่มเองจาก federalreserve.gov)
- เวลารัน — แก้ `cron` ใน `.github/workflows/update-calendar.yml` (เป็นเวลา UTC)

## ข้อจำกัดที่ควรรู้

- ราคาหลังงบใช้ `/quote` ของ Finnhub ซึ่งให้ % เปลี่ยนแปลงของ **วันซื้อขายล่าสุด** — ถ้าวันนั้น GitHub รันไม่ทัน/ล่ม ตัวเลขของหุ้นตัวนั้นจะไม่ถูกบันทึก (ไม่ใส่ตัวเลขผิด แค่ว่างไว้)
- ไม่ได้คิดวันหยุดตลาดสหรัฐ ถ้าวันตอบสนองงบตรงวันหยุด ตัวเลข % อาจไม่ตรง
- GitHub Actions แบบ schedule อาจช้ากว่าเวลาที่ตั้ง 5–30 นาที
- ถ้า repo ไม่มีความเคลื่อนไหว 60 วัน GitHub จะปิด schedule — แต่สคริปต์ commit ทุกวันอยู่แล้วจึงไม่น่าติด
- iPhone ดึงข้อมูลใหม่ตามรอบของมันเอง (ปกติไม่กี่ชั่วโมง) ไม่ใช่ real-time
