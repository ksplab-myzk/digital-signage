import subprocess
import sys
import time
import psutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Windows の Chrome パス
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# 動画終了フラグ
video_finished = False


# ---------------------------------------------------------
# ★ 動画終了通知を受け取る簡易 HTTP サーバー
# ---------------------------------------------------------
class EndHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global video_finished
        if self.path == "/ended":
            print("[INFO] Received video ended signal")
            video_finished = True
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()


def start_server():
    server = HTTPServer(("0.0.0.0", 5001), EndHandler)
    print("[INFO] End-detection server started on port 5001")
    server.serve_forever()


# ---------------------------------------------------------
# ★ Chrome を kiosk モードで起動
# ---------------------------------------------------------
def show_web_chrome(url, duration_ms=30000):
    global video_finished
    video_finished = False

    print(f"[INFO] Launching Chrome: {url}")

    # ★ Chrome を必ず新規プロセスで起動するための一時プロファイル
    temp_profile = tempfile.mkdtemp(prefix="chrome_profile_")

    proc = subprocess.Popen([
        CHROME_PATH,
        "--kiosk",
        "--autoplay-policy=no-user-gesture-required",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
        f"--user-data-dir={temp_profile}",  # ★ 新規プロセス強制
        "--new-window",
        url
    ])

    # ---------------------------------------------------------
    # ★ 動画終了 or duration 超過を待つ
    # ---------------------------------------------------------
    timeout = duration_ms / 1000
    elapsed = 0

    while elapsed < timeout:
        if video_finished:
            print("[INFO] Video ended detected, closing Chrome")
            break
        time.sleep(0.5)
        elapsed += 0.5

    # ---------------------------------------------------------
    # ★ Chrome を強制終了
    # ---------------------------------------------------------
    print("[INFO] Closing Chrome")

    for p in psutil.process_iter():
        try:
            if "chrome.exe" in p.name().lower():
                p.kill()
        except:
            pass


# ---------------------------------------------------------
# ★ メイン処理
# ---------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_chrome.py <url>")
        sys.exit(1)

    url = sys.argv[1]

    # ★ 終了通知サーバーを起動
    threading.Thread(target=start_server, daemon=True).start()

    # ★ Chrome を起動
    show_web_chrome(url)
