#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 ดูหนังออนไลน์ฟรี - คนทำเว็บ ZXD44
รวมทุกอย่างในไฟล์เดียว - เซิร์ฟเวอร์, เว็บไซต์, และ tunnel
ไฟล์: mv_pc.py
"""

import os
import sys
import time
import json
import socket
import threading
import subprocess
import urllib.parse
import urllib.request
import re
import platform
import webbrowser
import pathlib
import signal
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime
from typing import Optional, Any, Dict, List

# ตรวจสอบ Python version
if sys.version_info < (3, 6):
    print("❌ ต้องใช้ Python 3.6 ขึ้นไป")
    sys.exit(1)

class Colors:
    """สีสำหรับ terminal"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class CustomHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='public', **kwargs)
    
    def do_GET(self):
        # 🟢 API: Get all rooms
        if self.path == '/api/rooms':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            sanitized_rooms = {}
            with ROOMS_LOCK:
                # ลบห้องที่ไม่มีความเคลื่อนไหวนานกว่า 30 วินาที
                now = time.time()
                expired_ids = [rid for rid, rdata in ROOMS.items() if now - rdata.get('lastActive', 0) > 30]
                for rid in expired_ids:
                    print(f"{Colors.RED}[DEBUG] 🗑️ ลบห้องอัตโนมัติ (หมดเวลา): {rid} ({ROOMS[rid].get('roomName')}){Colors.ENDC}")
                    ROOMS.pop(rid, None)
                
                # Sanitize data (Hide Password)
                for rid, rdata in ROOMS.items():
                    r_copy = rdata.copy()
                    r_copy['id'] = rid # 🛠️ Force include ID in response
                    if 'password' in r_copy:
                        del r_copy['password']
                    sanitized_rooms[rid] = r_copy

            self.wfile.write(json.dumps(sanitized_rooms).encode('utf-8'))
            return
            
        # 🟢 API: SSE Stream for Real-time Updates (Alternative to WebSockets)
        if self.path.startswith('/api/stream?id='):
            try:
                parsed_path = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed_path.query)
                rid = query.get('id', [''])[0]
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                last_state = ""
                while True:
                    with ROOMS_LOCK:
                        if rid not in ROOMS:
                            self.wfile.write(b"event: close\ndata: {}\n\n")
                            break
                        
                        r_copy = ROOMS[rid].copy()
                        r_copy['id'] = rid
                        if 'password' in r_copy:
                            del r_copy['password']
                        
                        current_state = json.dumps(r_copy)
                        
                    if current_state != last_state:
                        self.wfile.write(f"data: {current_state}\n\n".encode('utf-8'))
                        self.wfile.flush()
                        last_state = current_state
                    
                    time.sleep(0.5) # Check for changes every 500ms
            except Exception:
                pass # Client disconnected
            return

        # Local Proxy Endpoint
        if self.path.startswith('/proxy?url='):
            try:
                parsed_path = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed_path.query)
                target_url = query.get('url', [None])[0]
                
                if target_url:
                    val: str = urllib.parse.unquote(str(target_url))
                    target_url = val
                    display_url = "{:.60s}".format(val)
                    print(f"{Colors.BLUE}[DEBUG] 🌐 Proxy Request: {display_url}...{Colors.ENDC}")
                    
                    # 🚀 Cache check
                    now = time.time()
                    with PROXY_CACHE_LOCK:
                        if target_url in PROXY_CACHE:
                            ts, cached_content, c_type = PROXY_CACHE[target_url]
                            if now - ts < 30: # เก็บ 30 วิ
                                self.send_response(200)
                                self.send_header('Content-Type', c_type)
                                self.send_header('Access-Control-Allow-Origin', '*')
                                self.send_header('X-Proxy-Cache', 'HIT')
                                self.end_headers()
                                self.wfile.write(cached_content)
                                return

                    target_domain = urllib.parse.urlparse(target_url).netloc
                    
                    req = urllib.request.Request(
                        target_url,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Referer': target_url,
                            'Host': target_domain
                        }
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=10) as response:
                            content = response.read()
                            content_type = response.getheader('Content-Type', 'text/html')
                            
                            # 🛡️ Ad-Filter: ถ้าเป็น HTML ให้ลบพวก Ad-Scripts ออก
                            if 'text/html' in content_type:
                                try:
                                    html_text = content.decode('utf-8', errors='ignore')
                                    # ลบสคริปต์โฆษณาที่พบบ่อย (Enhanced)
                                    ad_patterns = [
                                        r'<script[^>]*src="[^"]*ad[^"]*"[^>]*>.*?</script>',
                                        r'<script[^>]*src="[^"]*pop[^"]*"[^>]*>.*?</script>',
                                        r'<script[^>]*src="[^"]*analytics[^"]*"[^>]*>.*?</script>',
                                        r'<script[^>]*src="[^"]*click[^"]*"[^>]*>.*?</script>',
                                        r'<script[^>]*src="[^"]*tracking[^"]*"[^>]*>.*?</script>',
                                        r'<script[^>]*src="[^"]*doubleclick[^"]*"[^>]*>.*?</script>',
                                        r'<script[^>]*src="[^"]*google-analytics[^"]*"[^>]*>.*?</script>',
                                        r'<script[^>]*src="[^"]*googletagmanager[^"]*"[^>]*>.*?</script>',
                                        r'<ins[^>]*class="adsbygoogle"[^>]*>.*?</ins>',
                                        r'<iframe[^>]*src="[^"]*ad[^"]*"[^>]*>.*?</iframe>',
                                        r'<div[^>]*class="[^"]*ad[^"]*"[^>]*>.*?</div>',
                                        r'<div[^>]*id="[^"]*ad[^"]*"[^>]*>.*?</div>',
                                        r'window\.open\(', # บล็อก popup บางส่วน
                                        r'eval\s*\(\s*atob', # ป้องกันสคริปต์หลบหลีก
                                        r'location\.href\s*=\s*[\'"][^#][^\'"]+[\'"]', # บล็อกการ redirect นอกเหนือจาก anchor
                                        r'addEventListener\(\s*[\'"]click[\'"]\s*,\s*function\s*\(\s*\)\s*\{\s*window\.open', # บล็อก popup on click
                                    ]
                                    for pattern in ad_patterns:
                                        html_text = re.sub(pattern, '', html_text, flags=re.IGNORECASE | re.DOTALL)
                                    
                                    # บล็อกการ Redirect ไปหน้าอื่นผ่าน Javascript
                                    html_text = html_text.replace('window.location', '//blocked_location')
                                    html_text = html_text.replace('top.location', '//blocked_top')
                                    html_text = html_text.replace('self.location', '//blocked_self')
                                    
                                    # ลบพวก Overlay ที่บังหน้าจอ
                                    html_text = html_text.replace('display:block', 'display:block !important') # รักษาการแสดงผลหลัก
                                    html_text = re.sub(r'z-index\s*:\s*\d{5,}', 'z-index: -1', html_text) # กด z-index สูงๆ ลงไปข้างหลัง
                                    
                                    # เพิ่ม CSS ซ่อนโฆษณาที่อาจหลงเหลือ
                                    ad_css = '<style>.adsbygoogle, .ad-unit, [id*="google_ads"], [class*="google_ads"] { display: none !important; }</style>'
                                    html_text = html_text.replace('</head>', ad_css + '</head>')

                                    content = html_text.encode('utf-8')
                                except:
                                    pass

                            # 🚀 Save to cache
                            with PROXY_CACHE_LOCK:
                                PROXY_CACHE[target_url] = (now, content, content_type)
                            
                            self.send_response(200)
                            self.send_header('Content-Type', content_type)
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                            self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type')
                            self.send_header('X-Proxy-Cache', 'MISS')
                            self.end_headers()
                            self.wfile.write(content)
                            return
                    except socket.timeout:
                        self.send_response(504)
                        self.end_headers()
                        self.wfile.write(b"Proxy error: Target URL timeout")
                        return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(f"Proxy error: {str(e)}".encode('utf-8'))
                return

        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()
    
    def do_POST(self):
        # 🟢 API: Verify Password
        if '/api/verify_password' in self.path:
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                rid = data.get('id')
                pwd = data.get('password')
                
                success = False
                with ROOMS_LOCK:
                    if rid in ROOMS:
                        # ถ้าไม่มีรหัสผ่าน (None/Empty) ถือว่าผ่าน
                        room_pwd = ROOMS[rid].get('password')
                        if not room_pwd or room_pwd == pwd:
                            success = True
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": success}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                return

        # 🟢 API: Create/Update room
        if '/api/update_room' in self.path:
            try:
                content_length = int(self.headers['Content-Length'])
                self.connection.settimeout(5)
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                room_id = data.get('id')
                creator = data.get('creator', 'Unknown')
                if not room_id:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Missing room ID")
                    return

                with ROOMS_LOCK:
                    # 🛡️ ระบบจำกัดห้อง: 1 คนสร้างได้ไม่เกิน 2 ห้อง
                    if room_id not in ROOMS and creator != 'Unknown':
                        user_rooms = [r for r in ROOMS.values() if r.get('creator') == creator]
                        if len(user_rooms) >= 2:
                            self.send_response(403)
                            self.send_header('Content-Type', 'application/json')
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            self.wfile.write(json.dumps({
                                "success": False, 
                                "message": f"คุณ {creator} สร้างห้องครบ 2 ห้องแล้วครับ รบกวนกด 'ลบห้อง' เดิมออกก่อนเพื่อสร้างห้องใหม่นะครับ"
                            }).encode('utf-8'))
                            return

                    if room_id not in ROOMS:
                        ROOMS[room_id] = {
                            'participants': {},
                            'chat': [],
                            'isLocked': False,
                            'creator': data.get('creator', 'Unknown')
                        }
                    
                    room = ROOMS[room_id]
                    
                    # 1. Handle Heartbeat (Update Presence Only)
                    if 'heartbeat' in data:
                        user = data['heartbeat']
                        if 'participants' not in room: room['participants'] = {}
                        room['participants'][user] = time.time()
                        
                        # Clean up old participants (> 10s)
                        now = time.time()
                        room['participants'] = {u:t for u,t in room['participants'].items() if now - t < 10}
                        
                        room['lastActive'] = time.time()
                        
                        # Only return success for heartbeat to avoid heavy processing
                        if len(data) == 2: # id + heartbeat only
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                            return

                    # 2. Handle Chat (Append instead of Replace)
                    if 'newChat' in data:
                        if 'chat' not in room: room['chat'] = []
                        room['chat'].append(data['newChat'])
                        # Keep only last 50 messages
                        if len(room['chat']) > 50: room['chat'] = room['chat'][-50:]

                    # 3. Handle Emoji (Sync across all users)
                    if 'newEmoji' in data:
                        if 'emojis' not in room: room['emojis'] = []
                        room['emojis'].append(data['newEmoji'])
                        # Keep only last 20 emojis
                        if len(room['emojis']) > 20: room['emojis'] = room['emojis'][-20:]

                    # 4. Handle State Updates (Merge other fields)
                    for k, v in data.items():
                        if k not in ['heartbeat', 'participants', 'newChat', 'newEmoji', 'chat']:
                            room[k] = v
                    
                    # Ensure ID is always in the object
                    room['id'] = room_id

                    room['lastActive'] = time.time()
                    
                    # Debug Log (Only for important actions, skip heartbeats)
                    if 'heartbeat' not in data or len(data) > 2:
                            action = "อัปเดตสถานะ"
                            # print(f"{Colors.GREEN}[DEBUG] ✨ {action}: {room.get('roomName', room_id)}{Colors.ENDC}")
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                return

        # 🟢 API: Delete Room (Close Room)
        if '/api/delete_room' in self.path:
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                rid = data.get('id')
                requester = data.get('user')
                
                success = False
                message = "ไม่สามารถลบห้องได้"

                with ROOMS_LOCK:
                    if rid in ROOMS:
                        room = ROOMS[rid]
                        # ตรวจสอบว่าเป็นเจ้าของห้องหรือไม่
                        if room.get('creator') == requester:
                            print(f"{Colors.RED}[DEBUG] 🗑️ เจ้าของปิดห้อง: {rid} ({room.get('roomName')}){Colors.ENDC}")
                            ROOMS.pop(rid, None)
                            success = True
                            message = "ปิดห้องเรียบร้อยแล้ว"
                        else:
                            message = "คุณไม่ใช่เจ้าของห้องนี้ ไม่สามารถปิดได้"
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": success, "message": message}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                return

        print(f"{Colors.RED}[DEBUG] ❌ Unknown POST Path: {self.path}{Colors.ENDC}")
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        # ปรับการแสดงผล Log ให้สวยงามและมีสี
        msg = format % args
        color = Colors.ENDC
        if "POST" in msg: color = Colors.GREEN
        if "GET" in msg: color = Colors.BLUE
        if "404" in msg: color = Colors.RED
        print(f"{Colors.BOLD}[LOG]{Colors.ENDC} {color}{msg}{Colors.ENDC}")

# Global Storage
ROOMS = {}
PROXY_CACHE = {} # {url: (timestamp, content, content_type)}
ROOMS_LOCK = threading.Lock()
PROXY_CACHE_LOCK = threading.Lock()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP Server ที่รองรับ multi-threading"""
    pass

class SyncMovieServer:
    port: int
    server: Any
    cf_process: Any
    default_port: int

    def __init__(self):
        self.port = 3000
        self.server = None
        self.cf_process = None # Cloudflare process
        self.default_port = 3000
        self.load_env_config()
        
    def load_env_config(self):
        """โหลดการตั้งค่าจาก .env file"""
        self.default_port = 3000
        
        try:
            if os.path.exists('.env'):
                with open('.env', 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip()
                                
                                if key == 'DEFAULT_PORT':
                                    try:
                                        self.default_port = int(value)
                                    except ValueError:
                                        pass
                                        
                print(f"{Colors.GREEN}✅ โหลดการตั้งค่าจาก .env file{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}⚠️  ไม่พบไฟล์ .env{Colors.ENDC}")
                
        except Exception as e:
            print(f"{Colors.RED}❌ เกิดข้อผิดพลาดในการอ่าน .env: {e}{Colors.ENDC}")
        
    def find_free_port(self):
        """หาพอร์ตที่ว่าง"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def check_html_files(self):
        """ตรวจสอบไฟล์ HTML"""
        # สร้างโฟลเดอร์ public ถ้าไม่มี
        os.makedirs('public', exist_ok=True)
        
        # ตรวจสอบว่ามีไฟล์ HTML อยู่แล้วหรือไม่
        index_path = Path('public/index.html')
        room_path = Path('public/room.html')
        
        if index_path.exists() and room_path.exists():
            print(f"{Colors.GREEN}✅ ใช้ไฟล์ HTML ที่มีอยู่แล้ว{Colors.ENDC}")
            return True
        else:
            print(f"{Colors.RED}❌ ไม่พบไฟล์ HTML ที่จำเป็น{Colors.ENDC}")
            print(f"{Colors.YELLOW}📝 กรุณาตรวจสอบไฟล์ public/index.html และ public/room.html{Colors.ENDC}")
            return False
    def start_server(self):
        """เริ่มเซิร์ฟเวอร์ท้องถิ่น"""
        try:
            if not self.check_html_files():
                return
            self.port = self.find_free_port()
            self.start_local_server()
            local_ip = self.get_local_ip()
            print(f"\n{Colors.GREEN}✅ เซิร์ฟเวอร์เริ่มทำงานแล้ว{Colors.ENDC}")
            print(f"{Colors.BLUE}🌐 ดูในเครื่องนี้: http://localhost:{self.port}{Colors.ENDC}")
            print(f"{Colors.YELLOW}📱 ดูในวง LAN เดียวกัน: http://{local_ip}:{self.port}{Colors.ENDC}")
            sys.stdout.flush()
            webbrowser.open(f"http://localhost:{self.port}")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_server()
        except Exception as e:
            print(f"{Colors.RED}❌ เกิดข้อผิดพลาด: {e}{Colors.ENDC}")

    def start_server_with_cloudflare(self):
        """เริ่มเซิร์ฟเวอร์พร้อม Cloudflare Tunnel"""
        try:
            if not self.check_html_files():
                return
            
            cf_path = self.check_cloudflare()
            if not cf_path:
                print(f"{Colors.RED}❌ ไม่พบ cloudflared กรุณาติดตั้งก่อน{Colors.ENDC}")
                self.install_cloudflare()
                cf_path = self.check_cloudflare()
                if not cf_path: return

            self.port = self.find_free_port()
            
            print(f"{Colors.YELLOW}🔗 กำลังเริ่ม Cloudflare Tunnel...{Colors.ENDC}")
            self.cf_process = subprocess.Popen(
                [cf_path, 'tunnel', '--url', f'http://localhost:{self.port}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )

            public_url = None
            is_ready = False
            print(f"{Colors.BLUE}🔄 กำลังรอการเชื่อมต่อและ URL จาก Cloudflare...{Colors.ENDC}")
            
            start_time = time.time()
            timeout = 40

            while time.time() - start_time < timeout:
                proc_stdout = self.cf_process.stdout
                if self.cf_process and proc_stdout:
                    line = proc_stdout.readline()
                    if not line: break
                    
                    # print(f"{Colors.BLUE}[CF] {line.strip()}{Colors.ENDC}")
                    
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        public_url = match.group(0)
                        print(f"\n{Colors.GREEN}{Colors.BOLD}🌍 URL สาธารณะของคุณคือ: {public_url}{Colors.ENDC}")
                        is_ready = True
                        break
            
            if not is_ready:
                print(f"{Colors.RED}❌ ไม่สามารถขอ URL จาก Cloudflare ได้ (หมดเวลา){Colors.ENDC}")
                print(f"{Colors.YELLOW}💡 ลองใหม่อิกครั้ง หรือใช้เซิร์ฟเวอร์ท้องถิ่นแทน{Colors.ENDC}")
                proc_to_kill = self.cf_process
                if proc_to_kill: proc_to_kill.terminate()
                return

            self.server = ThreadedHTTPServer(('localhost', self.port), CustomHandler)
            print(f"{Colors.GREEN}✅ เซิร์ฟเวอร์เริ่มทำงานที่พอร์ต {self.port} (ผ่าน CF Tunnel){Colors.ENDC}")
            
            server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            server_thread.start()
            
            # 🔧 ตรวจสอบความพร้อมของ URL ก่อนเปิดเบราว์เซอร์ (ป้องกัน Site not found)
            print(f"{Colors.BLUE}⏳ กำลังรอให้ลิงก์พร้อมใช้งาน{Colors.ENDC}", end="", flush=True)
            url_ready = False
            if public_url:
                for attempt in range(30):
                    try:
                        with urllib.request.urlopen(str(public_url), timeout=3) as resp:
                            if resp.status == 200:
                                url_ready = True
                                break
                    except:
                        pass
                    print(".", end="", flush=True)
                    time.sleep(1)
            
            if url_ready and public_url:
                print(f"\n{Colors.GREEN}🚀 ลิงก์พร้อมใช้งานแล้ว! กำลังเปิดเบราว์เซอร์...{Colors.ENDC}")
                webbrowser.open(str(public_url))
            else:
                print(f"\n{Colors.YELLOW}⚠️ ลิงก์ใช้เวลานานกว่าปกติ ลองเปิดเองได้ที่: {public_url}{Colors.ENDC}")
            
            # The original code had a redundant open here. Keeping it for faithful edit, but it's likely not intended.
            if public_url:
                webbrowser.open(str(public_url))
            print(f"\n{Colors.YELLOW}💡 กด Ctrl+C เพื่อหยุดเซิร์ฟเวอร์{Colors.ENDC}")
            
            proc_poll = self.cf_process
            while proc_poll and proc_poll.poll() is None:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop_server()
        except Exception as e:
            print(f"{Colors.RED}❌ เกิดข้อผิดพลาด: {e}{Colors.ENDC}")
            self.stop_server()


    def check_cloudflare(self):
        """ตรวจสอบไฟล์ cloudflared"""
        import platform
        system = platform.system().lower()
        if system == "windows":
            path = "exe/cloudflared.exe"
        else:
            path = "exe/cloudflared"
            
        import os
        if os.path.exists(path):
            return path
        return None

    def get_local_ip(self):
        """ดึง IP เครื่อง"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'

    def start_local_server(self):
        """เริ่มเซิร์ฟเวอร์แบบธรรมดาวนเครื่อง"""
        import threading
        self.server = ThreadedHTTPServer(('', self.port), CustomHandler)
        if self.server: # Added explicit None check for self.server
            server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            server_thread.start()
        

    def install_cloudflare(self):
        """ดาวน์โหลดและติดตั้ง cloudflared"""
        print(f"\n{Colors.YELLOW}📥 กำลังดาวน์โหลด cloudflared... (ฟรีและไม่มีขีดจำกัด){Colors.ENDC}")
        try:
            system = platform.system().lower()
            
            if system == "windows":
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
                filename = "exe/cloudflared.exe"
            elif system == "darwin": # macOS
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
                filename = "exe/cloudflared.tgz"
            else: # Linux
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                filename = "exe/cloudflared"

            os.makedirs('exe', exist_ok=True)
            print(f"{Colors.BLUE}🔗 จาก: {url}{Colors.ENDC}")
            urllib.request.urlretrieve(url, filename)
            
            if system != "windows":
                os.chmod(filename, 0o755)
                if filename.endswith('.tgz'):
                    subprocess.run(['tar', '-xzf', filename, '-C', 'exe'])
                    os.remove(filename)
            
            print(f"{Colors.GREEN}✅ ติดตั้ง cloudflared สำเร็จ!{Colors.ENDC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ ดาวน์โหลดไม่สำเร็จ: {e}{Colors.ENDC}")
            return False
    
    def stop_server(self):
        """หยุดเซิร์ฟเวอร์และ tunnel ทั้งหมด"""
        srv = self.server
        if srv:
            try:
                srv.shutdown()
            except:
                pass
            self.server = None
            print(f"\n{Colors.YELLOW}🛑 หยุดเซิร์ฟเวอร์แล้ว{Colors.ENDC}")
        
        proc = self.cf_process
        if proc:
            try:
                proc.terminate()
            except:
                pass
            self.cf_process = None
            print(f"{Colors.YELLOW}🛑 หยุด Cloudflare Tunnel แล้ว{Colors.ENDC}")


def show_menu():
    """แสดงเมนูหลัก"""
    print(f"\n{Colors.YELLOW}============================================================{Colors.ENDC}")
    print(f"{Colors.YELLOW}🎬 ดูหนังออนไลน์ฟรี - คนทำเว็บ ZXD44:{Colors.ENDC}")
    print(f"{Colors.CYAN}1. 🚀 เริ่มเซิร์ฟเวอร์ + Cloudflare (เสถียรสุด แนะนำ){Colors.ENDC}")
    print(f"{Colors.BLUE}2. 🏠 เริ่มเซิร์ฟเวอร์ท้องถิ่น (ดูเฉพาะในเครื่อง/WiFi เดียวกัน){Colors.ENDC}")
    print(f"{Colors.YELLOW}3. 📖 วิธีใช้งาน (คำแนะนำ){Colors.ENDC}")
    print(f"{Colors.YELLOW}4. 🛡️  ติดตั้ง AdBlocker (บล็อกโฆษณาในเว็บ){Colors.ENDC}")
    print(f"{Colors.RED}0. ❌ ออกจากโปรแกรม{Colors.ENDC}")
    print(f"{Colors.YELLOW}============================================================{Colors.ENDC}")

def show_usage():
    """แสดงวิธีใช้งาน"""
    print(f"\n{Colors.BLUE}📖 วิธีใช้งาน:{Colors.ENDC}")
    print(f"{Colors.YELLOW}1. เลือกตัวเลือก 1 เพื่อเริ่มเซิร์ฟเวอร์ + Cloudflare (แนะนำที่สุด! ฟรี ไม่มีขีดจำกัด){Colors.ENDC}")
    print(f"{Colors.YELLOW}2. เลือกตัวเลือก 2 เพื่อเริ่มเซิร์ฟเวอร์ท้องถิ่น (ดูคนเดียว/ในบ้าน){Colors.ENDC}")
    print(f"{Colors.YELLOW}3. เลือกตัวเลือก 4 เพื่อติดตั้ง AdBlocker สำหรับป้องกันโฆษณา{Colors.ENDC}")
    print(f"{Colors.YELLOW}4. เบราว์เซอร์จะเปิดอัตโนมัติพร้อมลิงก์ที่แชร์ให้เพื่อนได้{Colors.ENDC}")
    print(f"{Colors.YELLOW}5. เลือกหนังที่ต้องการ สร้างห้อง และส่งลิงก์ให้เพื่อน!{Colors.ENDC}")
    
    print(f"\n{Colors.BLUE}🎥 คุณสมบัติหลัก:{Colors.ENDC}")
    print(f"• {Colors.GREEN}Real-time Sync:{Colors.ENDC} ดูหนังพร้อมกัน")
    print(f"• {Colors.GREEN}Ad-Block Engine:{Colors.ENDC} บล็อกโฆษณาจากแหล่งที่มาอัตโนมัติ")
    print(f"• {Colors.GREEN}Interactive Chat:{Colors.ENDC} แชทและส่งอีโมจิเรียลไทม์")
    
    print(f"\n{Colors.BLUE}💡 เคล็ดลับ:{Colors.ENDC}")
    print(f"• {Colors.GREEN}แนะนำ Cloudflare (ข้อ 1):{Colors.ENDC} เพราะเสถียรกว่าและไม่ต้องสมัครสมาชิกใดๆ")
    print(f"• {Colors.GREEN}สำหรับมือถือ:{Colors.ENDC} ใช้สคริปต์ mv_apk.py ในแอป Termux")

def auto_install_adblockers():
    """เมนูเลือกติดตั้ง AdBlocker"""
    extensions = [
        {"name": "AdBlock (ยอดนิยม/บล็อกเรียบ)", "url": "https://chromewebstore.google.com/detail/adblock-%E2%80%94-block-ads-acros/gighmmpiobklfepjocnamgkkbiglidom"},
        {"name": "uBlock Origin Lite (เบาแรง/ประหยัดสเปกเครื่อง)", "url": "https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh"},
        {"name": "Ghostery (ความเป็นส่วนตัวสูง/บล็อกสคริปต์แฝง)", "url": "https://chromewebstore.google.com/detail/ghostery-privacy-adblocke/mlomiejdfkolichcflejclcbmpeaniij"}
    ]
    
    while True:
        print(f"\n{Colors.YELLOW}============================================================{Colors.ENDC}")
        print(f"{Colors.BLUE}🛡️  เมนูติดตั้ง AdBlocker (เพื่อกำจัดโฆษณาในเว็บหนัง):{Colors.ENDC}")
        for i, ext in enumerate(extensions):
            print(f"{Colors.CYAN}{i+1}. ติดตั้ง {ext['name']}{Colors.ENDC}")
        print(f"{Colors.GREEN}4. 🚀 ติดตั้งทั้งหมด (แนะนำที่สุด - รอบเดียวจบ!){Colors.ENDC}")
        print(f"{Colors.RED}0. 🔙 กลับสู่เมนูหลัก{Colors.ENDC}")
        print(f"{Colors.YELLOW}============================================================{Colors.ENDC}")
        print(f"{Colors.BOLD}📱 สำหรับมือถือ:{Colors.ENDC} แนะนำ брауเซอร์ {Colors.GREEN}Brave{Colors.ENDC} หรือ {Colors.GREEN}Kiwi{Colors.ENDC} แทนครับ")
        
        choice = input(f"\n{Colors.BOLD}กรุณาเลือก (0-4): {Colors.ENDC}").strip()
        
        if choice == '0':
            break
        elif choice in ['1', '2', '3']:
            ext = extensions[int(choice)-1]
            print(f"🚀 กำลังเปิดหน้าติดตั้ง {ext['name']}...")
            webbrowser.open(ext['url'])
        elif choice == '4':
            print(f"{Colors.GREEN}🚀 กำลังเปิดทุกตัวเพื่อการบล็อกขั้นสุด...{Colors.ENDC}")
            for ext in extensions:
                webbrowser.open(ext['url'])
                time.sleep(0.5)
            print(f"{Colors.GREEN}✅ เปิดหน้าติดตั้งครบทุกตัวแล้ว! กด 'เพิ่มใน Chrome' ได้เลย{Colors.ENDC}")
            break
        else:
            print(f"{Colors.RED}❌ กรุณาเลือก 0-4{Colors.ENDC}")

def main():
    """ฟังก์ชันหลัก"""
    server = SyncMovieServer()
    
    def signal_handler(sig, frame):
        print(f"\n{Colors.RED}{Colors.BOLD}🛑 กำลังปิดโปรแกรมและออกทันที...{Colors.ENDC}")
        try:
            if server:
                threading.Thread(target=server.stop_server, daemon=True).start()
        except:
            pass
        time.sleep(0.5)
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # 🔄 เริ่มระบบ Auto-Restart (เหมือน nodemon - เฝ้าดูทั้งไฟล์ Python และหน้าเว็บ)
    def auto_reloader():
        def get_project_mtime():
            max_m = 0
            for root, dirs, files in os.walk('.'):
                if any(p in root for p in ['.git', 'exe', '__pycache__', '.gemini']): continue
                for f in files:
                    if f.endswith(('.py', '.html', '.js', '.css')):
                        try:
                            m = os.path.getmtime(os.path.join(root, f))
                            if m > max_m: max_m = m
                        except: pass
            return max_m

        initial_mtime = get_project_mtime()
        while True:
            try:
                time.sleep(1)
                current_mtime = get_project_mtime()
                mtime_val = float(current_mtime) if current_mtime else 0.0
                init_mtime_val = float(initial_mtime) if initial_mtime else 0.0
                
                if mtime_val > init_mtime_val:
                    print(f"\n{Colors.YELLOW}🔄 [Auto-Restart] พบการเปลี่ยนแปลงในโปรเจกต์! กำลังเริ่มระบบใหม่...{Colors.ENDC}")
                    # หยุดซิงค์เมฆก่อนรีสตาร์ท
                    try: 
                        if server: server.stop_server()
                    except: pass
                    time.sleep(0.3)
                    # ใช้ Popen + exit แทน execv เพื่อความเสถียรบน Windows
                    creation_flags = 0
                    if platform.system().lower() == "windows" and sys.stdin.isatty():
                        creation_flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
                    
                    subprocess.Popen([sys.executable] + sys.argv, creationflags=creation_flags)
                    os._exit(0)
            except:
                pass
    
    # รัน Reloader ใน Background
    threading.Thread(target=auto_reloader, daemon=True).start()
    
    while True:
        try:
            show_menu()
            choice = input(f"\n{Colors.BOLD}เลือกตัวเลือก (0-4): {Colors.ENDC}").strip()
            
            if choice == '0':
                print(f"{Colors.GREEN}👋 ขอบคุณที่ใช้งาน!{Colors.ENDC}")
                break
            elif choice == '1':
                print(f"\n{Colors.CYAN}🚀 เริ่มเซิร์ฟเวอร์ + Cloudflare Tunnel...{Colors.ENDC}")
                server.start_server_with_cloudflare()
            elif choice == '2':
                print(f"\n{Colors.BLUE}🏠 เริ่มเซิร์ฟเวอร์ท้องถิ่น...{Colors.ENDC}")
                server.start_server()
            elif choice == '3':
                show_usage()
            elif choice == '4':
                auto_install_adblockers()
            else:
                print(f"{Colors.RED}❌ กรุณาเลือกตัวเลือก 0-4{Colors.ENDC}")
                
        except KeyboardInterrupt:
            server.stop_server()
            break
        except Exception as e:
            print(f"{Colors.RED}❌ เกิดข้อผิดพลาด: {e}{Colors.ENDC}")

if __name__ == "__main__":
    main()
