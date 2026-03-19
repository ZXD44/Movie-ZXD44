#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 Sync Movie Watch - Android Premium Edition
รวมระบบเซิร์ฟเวอร์ และ ตัวติดตั้งในไฟล์เดียวสำหรับ Termux (Optimized)
"""

import os
import sys
import time
import socket
import threading
import subprocess
import re
import json
import urllib.parse
import urllib.request
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import signal

# ตรวจสอบว่ารันบน Termux หรือไม่
IS_TERMUX = os.path.exists("/data/data/com.termux")

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Global State
ROOMS = {}
PROXY_CACHE = {} # {url: (timestamp, content, content_type)}
ROOMS_LOCK = threading.Lock()

class CustomHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # รองรับ Directory สำหรับ Python 3.7+
        super().__init__(*args, directory='public', **kwargs)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type')
        self.end_headers()

    def do_GET(self):
        # 🟢 API: Get all rooms
        if self.path == '/api/rooms' or self.path == '/api/rooms/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            sanitized_rooms = {}
            with ROOMS_LOCK:
                now = time.time()
                # ลบห้องที่ไม่มีความเคลื่อนไหว (1 นาที)
                expired_ids = [rid for rid, rdata in ROOMS.items() if now - rdata.get('lastActive', 0) > 60]
                for rid in expired_ids:
                    del ROOMS[rid]
                
                for rid, rdata in ROOMS.items():
                    r_copy = rdata.copy()
                    r_copy['id'] = rid
                    if 'password' in r_copy: del r_copy['password']
                    sanitized_rooms[rid] = r_copy
            
            self.wfile.write(json.dumps(sanitized_rooms).encode('utf-8'))
            return

        # 🟢 Local Proxy Endpoint (Optimized)
        if self.path.startswith('/proxy?url='):
            try:
                target_url = urllib.parse.unquote(self.path.split('url=')[1])
                now = time.time()
                
                # Cache Check (30 Secs)
                if target_url in PROXY_CACHE:
                    ts, content, c_type = PROXY_CACHE[target_url]
                    if now - ts < 30:
                        self.send_response(200)
                        self.send_header('Content-Type', c_type)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('X-Proxy-Cache', 'HIT')
                        self.end_headers()
                        self.wfile.write(content)
                        return

                req = urllib.request.Request(
                    target_url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    content = response.read()
                    c_type = response.getheader('Content-Type', 'text/html')
                    
                    if 'text/html' in c_type:
                        html = content.decode('utf-8', errors='ignore')
                        # Advanced Ad-Filter Patterns
                        ad_patterns = [
                            r'<script[^>]*src="[^"]*ad[^"]*"[^>]*>.*?</script>',
                            r'<script[^>]*src="[^"]*pop[^"]*"[^>]*>.*?</script>',
                            r'<script[^>]*src="[^"]*analytics[^"]*"[^>]*>.*?</script>',
                            r'<ins[^>]*class="adsbygoogle"[^>]*>.*?</ins>',
                            r'<iframe[^>]*src="[^"]*ad[^"]*"[^>]*>.*?</iframe>',
                            r'window\.open\(', 
                            r'eval\s*\(\s*atob'
                        ]
                        for pattern in ad_patterns:
                            html = re.sub(pattern, '', html, flags=re.I|re.S)
                        
                        # บล็อกการ Redirect ไปหน้าอื่น
                        html = html.replace('window.location', '//blocked')
                        content = html.encode('utf-8')
                        
                    PROXY_CACHE[target_url] = (now, content, c_type)
                    self.send_response(200)
                    self.send_header('Content-Type', c_type)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Proxy Error: {str(e)}".encode())
            return

        if self.path == '/': self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(post_data)
        except:
            data = {}

        # 🟢 API: Update/Create Room
        if '/api/update_room' in self.path:
            rid = data.get('id')
            if not rid: return
            
            with ROOMS_LOCK:
                if rid not in ROOMS:
                    ROOMS[rid] = {
                        'participants': {}, 
                        'chat': [], 
                        'emojis': [],
                        'isLocked': False, 
                        'creator': data.get('creator', 'Unknown')
                    }
                room = ROOMS[rid]
                
                # Handle Heartbeat
                if 'heartbeat' in data:
                    user = data['heartbeat']
                    room['participants'][user] = time.time()
                    room['participants'] = {u:t for u,t in room['participants'].items() if time.time() - t < 10}
                
                # Handle Chat
                if 'newChat' in data:
                    room['chat'].append(data['newChat'])
                    if len(room['chat']) > 50: room['chat'] = room['chat'][-50:]
                
                # Handle Emojis
                if 'newEmoji' in data:
                    if 'emojis' not in room: room['emojis'] = []
                    room['emojis'].append(data['newEmoji'])
                    if len(room['emojis']) > 20: room['emojis'] = room['emojis'][-20:]
                
                # Merge States
                for k, v in data.items():
                    if k not in ['heartbeat', 'participants', 'newChat', 'newEmoji', 'chat', 'emojis']:
                        room[k] = v
                
                room['lastActive'] = time.time()
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            return

        # 🟢 API: Verify Password
        if '/api/verify_password' in self.path:
            rid = data.get('id')
            pwd = data.get('password')
            success = False
            with ROOMS_LOCK:
                if rid in ROOMS:
                    room_pwd = ROOMS[rid].get('password')
                    if not room_pwd or room_pwd == pwd:
                        success = True
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode())
            return

        # 🟢 API: Delete Room
        if '/api/delete_room' in self.path:
            rid = data.get('id')
            requester = data.get('user')
            success = False
            with ROOMS_LOCK:
                if rid in ROOMS and ROOMS[rid].get('creator') == requester:
                    del ROOMS[rid]
                    success = True
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode())
            return

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer): 
    daemon_threads = True

class AndroidMovieServer:
    def __init__(self):
        self.port = 3000
        self.server = None
        self.cf_process = None

    def install_system(self):
        """ระบบติดตั้งอัตโนมัติสำหรับ Termux"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}🚀 กำลังเริ่มการติดตั้งระบบสำหรับ Android...{Colors.ENDC}")
        cmds = [
            ("pkg update && pkg upgrade -y", "อัปเดตระบบ Termux"),
            ("pkg install cloudflared git zsh curl python nodejs -y", "ติดตั้งโปรแกรมจำเป็น"),
            ("termux-setup-storage", "ขอสิทธิ์เข้าถึงไฟล์ (กรุณากด Allow บนหน้าจอ)"),
            ("termux-wake-lock", "เปิดระบบกันระบบหลับ (Wake Lock)"),
            ("pip install requests colorama", "ติดตั้ง Python Library เสริม")
        ]
        for cmd, desc in cmds:
            print(f"📦 {Colors.BLUE}{desc}...{Colors.ENDC}")
            subprocess.run(cmd, shell=True)
        
        # ติดตั้ง Oh My Zsh & Autosuggestions (Optional)
        if not os.path.exists(os.path.expanduser("~/.oh-my-zsh")):
             print(f"🎨 {Colors.MAGENTA}กำลังตั้งค่า Shell (Zsh)...{Colors.ENDC}")
             subprocess.run('sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended', shell=True)
             
             # ติดตั้งปลั๊กอินยอดนิยม
             plugins = [
                 ("https://github.com/zsh-users/zsh-autosuggestions", "zsh-autosuggestions"),
                 ("https://github.com/zsh-users/zsh-syntax-highlighting", "zsh-syntax-highlighting")
             ]
             for url, name in plugins:
                 path = os.path.expanduser(f"~/.oh-my-zsh/custom/plugins/{name}")
                 if not os.path.exists(path):
                     subprocess.run(f"git clone {url} {path}", shell=True)
             
             zshrc = os.path.expanduser("~/.zshrc")
             if os.path.exists(zshrc):
                 with open(zshrc, 'r') as f: c = f.read()
                 new_plugins = 'plugins=(git zsh-autosuggestions zsh-syntax-highlighting)'
                 with open(zshrc, 'w') as f: f.write(c.replace('plugins=(git)', new_plugins))
        
        self.create_shortcut()
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ ติดตั้งระบบเรียบร้อย!{Colors.ENDC}")
        print(f"{Colors.BLUE}📍 ต่อไปคุณสามารถพิมพ์คำว่า '{Colors.BOLD}movie{Colors.ENDC}{Colors.BLUE}' เพื่อเข้าโปรแกรมได้ทันที!{Colors.ENDC}")

    def create_shortcut(self):
        """สร้างคำสั่งย่อเพื่อเริ่มโปรแกรมง่ายๆ"""
        print(f"🔗 {Colors.YELLOW}กำลังสร้างทางลัด (Shortcut)...{Colors.ENDC}")
        zshrc = os.path.expanduser("~/.zshrc")
        bashrc = os.path.expanduser("~/.bashrc")
        current_dir = os.getcwd()
        alias_cmd = f"\nalias movie='cd {current_dir} && python movie_sync_android.py'\n"
        
        for rc in [zshrc, bashrc]:
            if os.path.exists(rc):
                with open(rc, 'r') as f: content = f.read()
                if "alias movie=" not in content:
                    with open(rc, 'a') as f: f.write(alias_cmd)
                    print(f"✅ เพิ่มทางลัดใน: {rc}")

    def optimize_network(self):
        """ปรับแต่ง DNS และความเร็วเครือข่ายเบื้องต้น (Optional)"""
        print(f"⚡ {Colors.CYAN}กำลังปรับแต่งความเร็วเครือข่าย...{Colors.ENDC}")
        # ใน Termux เราทำอะไรไม่ได้มากนัก แต่เราสามารถแจ้งเตือนผู้ใช้ได้
        print(f"{Colors.YELLOW}💡 แนะนำ: ใช้ DNS ของ Cloudflare (1.1.1.1) เพื่อการดูหนังที่เสถียรขึ้น{Colors.ENDC}")

    def uninstall_system(self):
        """ระบบถอนการติดตั้งและล้างไฟล์ตกค้าง"""
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️ กำลังเริ่มถอนการติดตั้งและล้างข้อมูล...{Colors.ENDC}")
        confirm = input(f"{Colors.YELLOW}คุณแน่ใจหรือไม่ที่จะลบ Cloudflared, Zsh และไฟล์ตั้งค่า? (y/n): {Colors.ENDC}").lower()
        
        if confirm == 'y':
            print("📦 กำลังลบโปรแกรม...")
            subprocess.run("pkg uninstall cloudflared git zsh curl nodejs -y", shell=True)
            
            print("🗑️ กำลังลบไฟล์ Configs...")
            paths = [os.path.expanduser("~/.oh-my-zsh"), os.path.expanduser("~/.zshrc")]
            for path in paths:
                if os.path.exists(path):
                    subprocess.run(f"rm -rf {path}", shell=True)
            
            subprocess.run("pkg clean", shell=True)
            print(f"\n{Colors.GREEN}✅ ถอนการติดตั้งสำเร็จ!{Colors.ENDC}")
        else:
            print("❌ ยกเลิกการถอนการติดตั้ง")

    def start_cloudflare(self):
        """เริ่มเซิร์ฟเวอร์พร้อม Cloudflare Tunnel"""
        self.optimize_network()
        self.apply_wake_lock() # 🔒 ล็อคระบบกันหลับเมื่อเริ่มรัน
        try:
            # ตรวจสอบ cloudflared
            try:
                subprocess.run(['cloudflared', '--version'], capture_output=True)
            except:
                print(f"{Colors.RED}❌ ไม่พบ cloudflared กรุณาติดตั้งก่อน (เลือกข้อ 3){Colors.ENDC}")
                self.release_wake_lock()
                return

            self.port = 3000
            print(f"{Colors.YELLOW}🔗 กำลังเชื่อมต่อ Cloudflare Tunnel...{Colors.ENDC}")
            self.cf_process = subprocess.Popen(
                ['cloudflared', 'tunnel', '--url', f'http://localhost:{self.port}'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )

            public_url = None
            print(f"{Colors.BLUE}🔄 กำลังรอ URL สาธารณะ...{Colors.ENDC}")
            start_time = time.time()
            while time.time() - start_time < 45:
                line = self.cf_process.stdout.readline()
                if not line: break
                if "Registered" in line: print(f"{Colors.BOLD}[CF]{Colors.ENDC} {line.strip()}")
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    public_url = match.group(0)
                    break
            
            if not public_url:
                print(f"{Colors.RED}❌ ไม่สามารถขอ URL ได้ (หมดเวลา){Colors.ENDC}")
                self.release_wake_lock()
                return

            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ ได้รับ URL แล้ว!{Colors.ENDC}")
            print(f"{Colors.CYAN}🌐 ลิงก์สำหรับส่งให้เพื่อน: {Colors.BOLD}{public_url}{Colors.ENDC}")

            self.server = ThreadedHTTPServer(('localhost', self.port), CustomHandler)
            print(f"{Colors.GREEN}🏠 เซิร์ฟเวอร์ท้องถิ่นรันอยู่ที่พอร์ต {self.port}{Colors.ENDC}")
            
            server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            server_thread.start()
            
            # 🔧 ตรวจสอบความพร้อมของ URL ก่อนแจ้งว่าพร้อมใช้งาน
            print(f"{Colors.BLUE}⏳ กำลังรอให้ลิงก์พร้อมใช้งาน{Colors.ENDC}", end="", flush=True)
            url_ready = False
            for attempt in range(30):
                try:
                    resp = requests.get(public_url, timeout=3)
                    if resp.status_code == 200:
                        url_ready = True
                        break
                except:
                    pass
                print(".", end="", flush=True)
                time.sleep(1)
            
            if url_ready:
                print(f"\n{Colors.GREEN}🚀 ลิงก์พร้อมใช้งานแล้ว! คัดลอก URL ด้านบนส่งให้เพื่อนได้เลย{Colors.ENDC}")
            else:
                print(f"\n{Colors.YELLOW}⚠️ ลิงก์ใช้เวลานานกว่าปกติ ลองเปิดเองก่อนได้ที่ URL ด้านบน{Colors.ENDC}")
            
            print(f"\n{Colors.YELLOW}💡 กด Ctrl+C เพื่อหยุดเซิร์ฟเวอร์{Colors.ENDC}")
            
            while self.cf_process and self.cf_process.poll() is None:
                time.sleep(1)

        except KeyboardInterrupt: self.stop()
        except Exception as e:
            print(f"{Colors.RED}❌ เกิดข้อผิดพลาด: {e}{Colors.ENDC}")
            self.stop()

    def apply_wake_lock(self):
        """ขอสิทธิ์ไม่ให้ Android สั่งหลับแอป Termux"""
        if IS_TERMUX:
            print(f"🔒 {Colors.MAGENTA}ระบบกันหลับ (Wake Lock) ทำงาน...{Colors.ENDC}")
            subprocess.run("termux-wake-lock", shell=True)
            # แสดงคำแนะนำเรื่อง Battery Optimization
            print(f"\n{Colors.YELLOW}{'!'*40}")
            print(f"💡 {Colors.BOLD}สำคัญมากสำหรับมือถือ:{Colors.ENDC}")
            print(f"1. กรุณาปิด 'Battery Optimization' สำหรับแอป Termux")
            print(f"2. ในหน้า App Info > Battery > เลือก Unrestricted")
            print(f"เพื่อให้เซิร์ฟเวอร์ไม่หลุดเวลาพับหน้าจอไปดูหนัง")
            print(f"{'!'*40}{Colors.ENDC}\n")

    def release_wake_lock(self):
        """คืนสิทธิ์ประหยัดพลังงานเมื่อเลิกใช้งาน"""
        if IS_TERMUX:
            print(f"🔓 {Colors.BLUE}คืนการจัดการพลังงานให้ระบบ...{Colors.ENDC}")
            subprocess.run("termux-wake-unlock", shell=True)

    def stop(self):
        if self.server: self.server.shutdown()
        if self.cf_process: self.cf_process.terminate()
        self.release_wake_lock() # 🔓 ปลดล็อคระบบประหยัดพลังงาน
        print(f"\n{Colors.RED}🛑 หยุดการทำงานของเซิร์ฟเวอร์แล้ว{Colors.ENDC}")

def show_menu():
    print(f"\n{Colors.HEADER}{'='*50}{Colors.ENDC}")
    print(f"{Colors.BOLD}🎬 Sync Movie Watch - Android Premium{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*50}{Colors.ENDC}")
    print(f"{Colors.CYAN}1. 🚀 เริ่มระบบ Cloudflare (แชร์ลิงก์ให้เพื่อนได้){Colors.ENDC}")
    print(f"{Colors.BLUE}2. 🏠 เริ่มระบบ Local (ดูคนเดียว/ในบ้าน){Colors.ENDC}")
    print(f"{Colors.YELLOW}3. ⚙️  ติดตั้ง/อัปเดตระบบ Android (รันครั้งแรก){Colors.ENDC}")
    print(f"{Colors.RED}4. 🗑️  ถอนการติดตั้งและล้างข้อมูล (Cleanup){Colors.ENDC}")
    print(f"{Colors.RED}0. ❌ ออกจากโปรแกรม{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*50}{Colors.ENDC}")

if __name__ == "__main__":
    server = AndroidMovieServer()
    while True:
        try:
            show_menu()
            choice = input(f"{Colors.BOLD}เลือกเมนู: {Colors.ENDC}").strip()
            if choice == '0': break
            elif choice == '1': server.start_cloudflare()
            elif choice == '2':
                server.apply_wake_lock()
                server.server = ThreadedHTTPServer(('localhost', 3000), CustomHandler)
                print(f"{Colors.GREEN}✅ เซิร์ฟเวอร์เริ่มที่พอร์ต 3000 (Local Only){Colors.ENDC}")
                try: server.server.serve_forever()
                except KeyboardInterrupt: server.stop()
            elif choice == '3': server.install_system()
            elif choice == '4': server.uninstall_system()
            else: print(f"{Colors.RED}❌ กรุณาเลือกตัวเลข 0-4{Colors.ENDC}")
        except KeyboardInterrupt:
            print("\n👋 ลาก่อน!")
            break
