# 📖 SYNC MOVIE WATCH - PROJECT DOCUMENTATION (0-100%)
# ไฟล์สรุปโครงสร้างและระบบการทำงานทั้งหมด (AI READABLE & HUMAN CLEAR)

เอกสารฉบับนี้จัดทำขึ้นเพื่อเป็น "Master Plan" สำหรับคนหรือ AI ที่จะเข้ามาแก้ไขโปรเจคในอนาคต โดยสรุปทุกแง่มุมตั้งแต่แนวคิด (Logic) ไปจนถึงขั้นตอนการลงมือทำจริง (Implementation) แยกเป็น Part อย่างละเอียด

---

## 🏛️ OVERVIEW: โปรเจคคืออะไร?
**Sync Movie Watch** คือระบบ Web Application สำหรับดูหนังพร้อมกันแบบ Real-time โดยดึงข้อมูลหนังจากแหล่งภายนอก (DE88.me) มาทำความสะอาด (Clean) ลบโฆษณา (Ad-Block) และสร้าง "ห้องรับชม" ที่สามารถควบคุมเวลาเล่นหนังและแชทโต้ตอบกันได้แบบทันที

---

## 📂 PHASE 1: โครงสร้างไฟล์ (File Structure)
โปรเจคถูกออกแบบให้มีความเป็น **Portable & Lightweight** สูงสุด:
1.  `movie_sync.py`: **หัวใจหลัก (Backend)** - จัดการ Web Server, Proxy, API Room Management และ Cloudflare Tunnel
2.  `movie_sync_android.py`: **เวอร์ชัน Android** - สคริปต์สำหรับรันบน Termux พร้อม Wake Lock กันระบบหลับ
3.  `public/index.html`: **หน้าแรก (Lobby)** - ค้นหาหนัง, เลือกหมวดหมู่, และดูรายการห้องที่เปิดอยู่
4.  `public/room.html`: **ห้องรับชม (Cinema)** - เล่นวิดีโอ, ซิงค์เวลา, แชท, และระบบอีโมจิลอย
5.  `public/movies-api.js`: **ตัวกลางข้อมูล (Data Proxy)** - สกัดข้อมูลจากเว็บไซต์ต้นทาง และดึงไฟล์วิดีโอจริง
6.  `exe/`: **โฟลเดอร์เก็บไฟล์ cloudflared** - ระบบดาวน์โหลดและจัดเก็บให้อัตโนมัติ

---

## 🚀 PHASE 2: ขั้นตอนการพัฒนา (Implementation Passes)

### 🟢 PASS 1: ระบบจัดการ Server และระบบความปลอดภัย (Backend Infrastructure)
*   **Server:** ใช้ `ThreadingHTTPServer` ของ Python เพื่อรองรับผู้ใช้หลายคนพร้อมกัน
*   **Cloudflare Tunnel:** เชื่อมต่อกับระบบ Quick Tunnel เพื่อให้สามารถแชร์ลิงก์ผ่านเน็ตได้ทั่วโลก (ฟรี 100% ไม่จำกัดผู้ใช้)
*   **Proxy System:** สร้าง Endpoint `/proxy?url=...` เพื่อแก้ปัญหา CORS (Cross-Origin Resource Sharing) และกรอง Ad-Script
*   **Room Engine:** ใช้ `ROOMS` Dictionary ในหน่วยความจำเพื่อเก็บสถานะห้อง (isPlaying, currentTime, chat, emojis) แบบ Real-time
*   **Thread Safety:** ใช้ `ROOMS_LOCK` และ `PROXY_CACHE_LOCK` เพื่อป้องกัน Race Condition

### 🔵 PASS 2: ระบบสกัดข้อมูลและ Bypass โฆษณา (Data Scraping & Ad-Bypass)
*   **Scraping:** ใน `movies-api.js` ใช้ `DOMParser` เพื่อสกัดข้อมูลหนังจาก `de88.me`
*   **Deep Search:** ระบบ `fetchDirectVideoUrl` จะค้นหาไฟล์วิดีโอ (.mp4, .m3u8) จาก Iframe เพื่อหลีกเลี่ยงโฆษณา
*   **Ad-Filtering:** ในไฟล์ Python มีระบบ Regex สำหรับลบ Script โฆษณาที่มักจะกระเด้งเวลาดูบนมือถือ

### 🟡 PASS 3: ประสบการณ์ผู้ใช้และการซิงค์ข้อมูล (Frontend & Synchronization)
*   **Polling Sync:** ฝั่งเครื่องลูกจะดึงข้อมูลทุกๆ 0.5 - 1 วินาที เพื่อซิงค์เวลากับเจ้าของห้อง
*   **Optimistic UI:** ระบบแชทแสดงผลทันทีที่กดส่ง (ลดความรู้สึกดีเลย์) พร้อมแสดงเวลาแบบ 24 ชม. (ไทย)
*   **Emoji Blast:** ระบบกระจายอีโมจิลอย (sid-based) ให้ทุกคนในห้องเห็นพร้อมกัน
*   **Fullscreen Alert:** ระบบแจ้งเตือนแชทเมื่อผู้ใช้ดูหนังแบบเต็มจอ (Fullscreen Notification)

### 🔴 PASS 4: ความเสถียรและการเข้าถึงระดับโลก (Reliability & Global Access)
*   **Cloudflare Tunnel Integration:** ใช้ Quick Tunnel (`cloudflared tunnel --url`) เพื่อสร้าง URL สาธารณะชั่วคราว รองรับการเข้าชมแบบไม่จำกัด (Unlimited Requests) และไม่ต้องสมัครสมาชิก
*   **Auto-Install:** ระบบดาวน์โหลดและติดตั้ง cloudflared อัตโนมัติหากยังไม่มีในเครื่อง
*   **Smart Startup Logic:** ระบบตรวจสอบสถานะ URL จาก Cloudflare และเปิดเบราว์เซอร์อัตโนมัติเมื่อพร้อม
*   **Color-Coded Terminal:** แสดงผล Log แบบ Real-time พร้อมสีเพื่อช่วยให้ตรวจสอบสถานะง่ายขึ้น

### ⚪ PASS 5: การจัดระเบียบและบำรุงรักษา (Project Hygiene & Organization)
*   **Binary Isolation:** ไฟล์ cloudflared อยู่ในโฟลเดอร์ `exe/` เพื่อความเป็นระเบียบ
*   **Unified Documentation:** `README.md` และ `summary.md` สอดคล้องกันทุกจุด
*   **Clean Codebase:** ลบโค้ดซ้ำซ้อนและฟังก์ชันที่ไม่ใช้ออกทั้งหมด

---

## 🛠️ PHASE 3: ข้อมูลเชิงเทคนิคสำหรับ AI (Technical Specs for AI)

### 1. การจัดการข้อมูล (API & States)

| Endpoint | Method | ฟังก์ชัน |
|----------|--------|---------|
| `/api/rooms` | GET | ดึงรายการห้องทั้งหมด (ลบห้องหมดเวลา > 60s) |
| `/api/update_room` | POST | สร้าง/อัปเดตห้อง + heartbeat + chat + emoji |
| `/api/verify_password` | POST | ตรวจรหัสผ่านห้อง |
| `/api/delete_room` | POST | ลบห้อง (ต้องเป็นเจ้าของ) |
| `/proxy?url=` | GET | Local proxy + ad-filter + cache 30s |

- **Append Logic**: ใช้ส่ง `newChat` และ `newEmoji` เพื่อให้ข้อมูลถูกต่อท้าย ไม่ใช่การเขียนทับ
- **Expiry**: ห้องจะหายไปหากไม่มีกิจกรรมภายใน 60 วินาที เพื่อประหยัดทรัพยากร
- **Room Limit**: 1 ผู้ใช้สร้างได้ไม่เกิน 2 ห้อง (movie_sync.py)

### 2. ระบบการเล่นวิดีโอ (Video Engine)
- **HLS Support**: รองรับไฟล์ `.m3u8` ผ่านไลบรารี `hls.js`
- **Proxy Headers**: มีการส่ง `User-Agent` และ `Referer` เพื่อ Bypass ระบบป้องกันของ Server วิดีโอ

### 3. ระบบ Tunnel (Networking)
- **Quick Tunnel Mode**: ใช้ `cloudflared tunnel --url http://localhost:PORT` เพื่อสร้าง URL ชั่วคราวบน Cloudflare โดยไม่ต้อง Login
- **Process Management**: ระบบจะบันทึก process ของ Tunnel เพื่อให้สามารถปิด (terminate) ได้สะอาดเมื่อกด Ctrl+C
- **Timeout**: รอ URL จาก Cloudflare สูงสุด 40 วินาที (PC) / 45 วินาที (Android)

### 4. ระบบเมนู (Menu Flow)

**PC (`movie_sync.py`)**:
```
0 → ออกจากโปรแกรม
1 → start_server_with_cloudflare() → check_html_files → check_cloudflare → install_cloudflare(ถ้าจำเป็น) → Popen cloudflared → รอ URL → เปิด browser → serve_forever
2 → start_server() → check_html_files → find_free_port → start_local_server → เปิด browser → loop
3 → show_usage() → แสดงคำแนะนำ
4 → auto_install_adblockers() → เปิด Chrome Web Store 3 extensions
```

**Android (`movie_sync_android.py`)**:
```
0 → ออกจากโปรแกรม
1 → start_cloudflare() → apply_wake_lock → check cloudflared → Popen cloudflared → รอ URL → serve_forever
2 → apply_wake_lock → ThreadedHTTPServer(localhost:3000) → serve_forever
3 → install_system() → pkg install → create_shortcut
4 → uninstall_system() → pkg uninstall → ลบ configs
```

---

## 🏁 PHASE 4: แนวทางแก้ไขในอนาคต (Maintenance)
- หากเข้า URL Cloudflare ไม่ได้: ตรวจสอบสถานะ Log หรือลองกดรันใหม่อีกครั้ง
- หากไฟล์ cloudflared หาย: ระบบจะดาวน์โหลดให้ใหม่อัตโนมัติ หรือตรวจสอบในโฟลเดอร์ `exe/`
- หากอยากเพิ่มฟีเจอร์: ดูแนวทางในไฟล์ `doc/summary.md` นี้เป็นหลัก

**สถานะปัจจุบัน: Cloudflare Only Edition — ระบบพร้อมใช้งาน 100%**
