# BKK Flood Watch 🌧️
> **ระบบคาดการณ์ปริมาณฝนและเฝ้าระวังน้ำท่วมขังกรุงเทพมหานคร**
> อ้างอิงตามเกณฑ์ขีดความสามารถการระบายน้ำของสำนักการระบายน้ำ กรุงเทพมหานคร (BMA Drainage Capacity Standards: 60 มม./ชม.)

---

## 🌐 Public Live Deployment (ออนไลน์พร้อมใช้งาน)

| ช่องทาง (Stage) | สถานะ | URL | รายละเอียด |
| :--- | :--- | :--- | :--- |
| **Stage 1: Cloudflare Quick Tunnel** | 🟢 Live | [sitemap-mining-went-derived.trycloudflare.com](https://sitemap-mining-went-derived.trycloudflare.com/) | อุโมงค์ HTTPS สาธารณะฟรีระดับโลก ไม่ต้อง Login/Sign-up |
| **Stage 1: Localtunnel Backup** | 🟢 Live | [yummy-tools-brush.loca.lt](https://yummy-tools-brush.loca.lt/) | อุโมงค์สำรองสำหรับเข้าถึง API และ UI |
| **Stage 2: Permanent Vercel Serverless** | 📦 Ready to Deploy | [vercel.com](https://vercel.com/) | รองรับ `@vercel/python` ผ่าน `vercel.json` |

---

## 📌 คุณสมบัติหลัก (Key Features)

1. **เชื่อมต่อข้อมูลพยากรณ์สดแบบ Real-Time จาก Open-Meteo API**:
   - พยากรณ์ฝนล่วงหน้า 24 ชั่วโมง (`precipitation`, `precipitation_probability`)
   - อุณหภูมิ (`temperature_2m`), ความชื้นสัมพัทธ์ (`relative_humidity_2m`), รหัสสภาพอากาศ WMO (`weathercode`)
   - ไม่ต้องใช้ API Key ใช้งานได้ทันที

2. **ระบบประเมินความเสี่ยงน้ำท่วม BMA Drainage Rule Engine (`flood_engine.py`)**:
   - 🟢 **ระดับปกติ (GREEN):** ฝนสูงสุด < 10 มม./ชม. **และ** สะสม 3 ชม. < 25 มม. *(สัญจรได้ตามปกติ)*
   - 🟡 **เฝ้าระวังน้ำรอการระบาย (YELLOW):** ฝนสูงสุด 10.0 - 35.0 มม./ชม. **หรือ** สะสม 3 ชม. 25.0 - 50.0 มม. *(อาจมีน้ำขัง 5-10 ซม. ในจุดลุ่มต่ำ)*
   - 🟠 **แจ้งเตือนน้ำท่วมขัง (ORANGE):** ฝนสูงสุด 35.1 - 60.0 มม./ชม. **หรือ** สะสม 3 ชม. 50.1 - 80.0 มม. *(ใกล้เต็มท่อระบายน้ำ กทม. 60 มม. รถเล็กควรเลี่ยง)*
   - 🔴 **วิกฤตน้ำท่วมฉับพลัน (RED):** ฝนสูงสุด > 60.0 มม./ชม. **หรือ** สะสม 3 ชม. > 80.0 มม. *(เกินขีดความสามารถท่อ กทม. เสี่ยงท่วมสูงเกิน 25 ซม.)*

3. **6 พิกัดยุทธศาสตร์จุดเสี่ยงน้ำท่วมขัง กทม.**:
   - จตุจักร / ลาดพร้าว (Lat: 13.8160, Lon: 100.5610)
   - ดินแดง / รัชดาภิเษก (Lat: 13.7690, Lon: 100.5730)
   - วัฒนา / สุขุมวิท - อโศก (Lat: 13.7370, Lon: 100.5600)
   - บางกะปิ / รามคำแหง (Lat: 13.7650, Lon: 100.6440)
   - มีนบุรี (ทางระบายน้ำฝั่งตะวันออก) (Lat: 13.8130, Lon: 100.7480)
   - บางแค / เพชรเกษม (Lat: 13.7120, Lon: 100.4070)

4. **แผนที่เรดาร์คาดการณ์รัศมีน้ำท่วมขัง Google Maps & Leaflet.js (Dual Provider Map)**:
   - **Google Maps Dark Mode (Default):**
     - ผสาน Google Maps JavaScript API พร้อม Dark Mode Custom Styling
     - มีระบบ **Keyless Development Workaround** (DOM MutationObserver + CSS Override) กำจัด Error Modal อัตโนมัติ ให้ใช้งาน Vector Overlays ได้ 100%
     - วาดวงกลมรัศมีคาดการณ์ผลกระทบ (`google.maps.Circle`) พร้อมกันทั้ง 6 โซน
     - ปักหมุดเคลื่อนไหวเตือนภัย (`google.maps.Animation.BOUNCE`) สำหรับโซนสีแดง (RED)
     - มี InfoWindow แสดงข้อมูล `[Zone Name] | Peak Rain: XX mm/hr | Risk: [TIER]`
   - **Leaflet.js + CartoDB Dark Matter:**
     - มีปุ่มสลับ Map Provider (`🌐 Google Maps` / `🗺️ Leaflet Dark`)
     - รองรับการทำงานแบบออฟไลน์หรือไม่ต้องพึ่งพา Google Maps
   - **การสเกลขนาดและสีของรัศมี:**
     - 🟢 **GREEN (ปกติ):** สี `#22c55e`, รัศมี `800` เมตร
     - 🟡 **YELLOW (เฝ้าระวัง):** สี `#eab308`, รัศมี `1,500` เมตร (1.5 กม.)
     - 🟠 **ORANGE (แจ้งเตือน):** สี `#f97316`, รัศมี `2,500` เมตร (2.5 กม.)
     - 🔴 **RED (วิกฤตฉับพลัน):** สี `#ef4444`, รัศมี `3,500` เมตร (3.5 กม.)

5. **Simulation Mode (โหมดจำลองสถานการณ์ฝนตก)**:
   - ทดสอบ Rule Engine ได้ทุกสถานการณ์:
     - 🟢 จำลองสภาพปกติ (Normal < 10 มม.)
     - 🟡 จำลองฝนปานกลาง 22 มม. (Watch)
     - 🟠 จำลองฝนตกหนัก 45 มม. (Heavy Rain ใกล้เต็มท่อ 60 มม.)
     - 🔴 จำลองพายุวิกฤต 75 มม. (Extreme Storm เกินศักยภาพ กทม.)
     - 🌊 จำลองฝนแช่สะสม 3 ชม. > 80 มม. (Cumulative Red)

6. **24-Hour Rainfall Chart (กราฟแสดงแนวโน้มปริมาณฝน)**:
   - กราฟแท่งผสมเส้น (Combo Bar & Line) ด้วย Chart.js
   - แท่งกราฟเปลี่ยนสีตามระดับความเสี่ยง BMA
   - เส้นประสีแดงแนวนอนระบุขีดจำกัดความจุท่อระบายน้ำ กทม. ที่ **60 มม./ชม.**
   - เส้นสะสม 3 ชั่วโมง (3-hr Cumulative)

---

## 🛠️ โครงสร้างโปรเจกต์ (Project Structure)

```
Antigravity_project/
├── app.py                      # Flask RESTful API & Routing (WSGI Entry Point)
├── flood_engine.py             # BMA Drainage Rule Engine
├── vercel.json                 # Vercel Python Serverless Configuration
├── requirements.txt            # Strictly Pinned Dependencies
├── templates/
│   └── index.html              # Frontend UI (Tailwind + Chart.js + Google Maps & Leaflet)
├── tests/
│   ├── test_flood_engine.py    # Unit tests for BMA 4-tier rules & edge cases
│   └── test_app.py             # Unit tests for Flask API endpoints
└── README.md                   # Documentation
```

---

## 🚀 วิธีการรันระบบและ Deploy

### 1. ติดตั้ง Dependencies และทดสอบ Unit Tests
```bash
pip install -r requirements.txt
python -m pytest -v
```

### 2. รันในเครื่อง (Local Development)
```bash
python app.py
```
เปิดบราวเซอร์ที่: `http://127.0.0.1:5000/`

---

## ☁️ กลยุทธ์การ Deploy สู่ Public Internet (Dual-Stage Strategy)

### Stage 1: Instant Zero-Auth Public Tunnel (เปิดใช้งานทันที ไม่ต้องสมัคร)
ใช้ Cloudflare Quick Tunnel หรือ Localtunnel เพื่อแชร์ระบบให้ผู้อื่นเข้าชมทันทีผ่านอินเทอร์เน็ต:
```bash
# Cloudflare Quick Tunnel (เร็ว ปลอดภัย ไร้หน้าคั่น)
npx cloudflared tunnel --url http://127.0.0.1:5000

# หรือ Localtunnel
npx localtunnel --port 5000
```

### Stage 2: Permanent Free Serverless Hosting on Vercel
โปรเจกต์ได้รับการกำหนดค่า `vercel.json` สำหรับรัน Python WSGI บน Vercel Serverless Function ไว้อย่างสมบูรณ์:

1. **Deploy ผ่าน GitHub (แนะนำ):**
   - Push โค้ดขึ้น GitHub Repository
   - เข้า [Vercel Dashboard](https://vercel.com/new) -> Import Repository
   - Vercel จะตรวจพบ `vercel.json` และ `@vercel/python` แล้ว Deploy อัตโนมัติ

2. **Deploy ผ่าน Vercel CLI:**
   ```bash
   npx vercel login
   npx vercel --prod
   ```
   หรือใช้ Deploy Token:
   ```bash
   npx vercel --token <YOUR_VERCEL_TOKEN> --prod --yes
   ```

---

## 👨‍💻 ผู้พัฒนาและลิขสิทธิ์ (Author & Copyright)

- **ผู้พัฒนา (Creator):** Bank Chavalit Tirakitti
- **GitHub:** [@bank1009](https://github.com/bank1009)
- **ลิขสิทธิ์ (Copyright):** © 2026 Bank Chavalit Tirakitti. All Rights Reserved.

