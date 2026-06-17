import subprocess
import sys
import time
import psutil
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# CHROMIUM_PATH = "/usr/bin/chromium-browser"  # Raspberry Pi OS の標準パス
CHROME_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"  # windows の標準パス

video_finished = False

class EndHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global video_finished
        if self.path == "/ended":
            video_finished = True
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_server():
    server = HTTPServer(("0.0.0.0", 5001), EndHandler)
    server.serve_forever()

def show_web_chrome(url, duration_ms=30000):
    print(f"[INFO] Launching Chromium: {url}")

    # ★ 毎回ユニークな user-data-dir を作る（新規プロセス強制）
    temp_profile = tempfile.mkdtemp(prefix="chrome_profile_")

    # Chrome/Chromium を kiosk モードで起動
    proc = subprocess.Popen([
        CHROME_PATH,
        "--kiosk",
        "--autoplay-policy=no-user-gesture-required",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
        f"--user-data-dir={temp_profile}",   # ★ これが重要
        "--new-window",                      # ★ 新規ウィンドウ強制
        url
    ])
    # duration 経過したら Chromium を強制終了
    time.sleep(duration_ms / 1000)

    print("[INFO] Closing Chromium")

    for p in psutil.process_iter():
        try:
            if "chromium" in p.name().lower():
                p.kill()
        except:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_chrome.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    show_web_chrome(url)
