import subprocess
import sys
import time
import psutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

video_finished = False
profile_dir = None


# ---------------------------------------------------------
# 動画終了通知サーバ
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

def start_file_server():
    server = ThreadingHTTPServer(("0.0.0.0", 8000), SimpleHTTPRequestHandler)
    print("[INFO] File server started on port 8000")
    server.serve_forever()

# ---------------------------------------------------------
# Chrome プロセス一覧（デバッグ用）
# ---------------------------------------------------------
def debug_list_chrome_processes(tag):
    print(f"\n===== DEBUG: Chrome processes ({tag}) =====")
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            if p.info['name'] and "chrome.exe" in p.info['name'].lower():
                print(f"PID={p.pid}")
                print(f"CMD={' '.join(p.info['cmdline'])}")
                print(f"TIME={p.info['create_time']}")
                print("----------------------------------------")
        except:
            pass
    print("========================================\n")


# ---------------------------------------------------------
# user-data-dir を使っている Chrome の “本物の親” を kill
# ---------------------------------------------------------
def kill_chrome_by_profile(profile_dir):
    print("[INFO] Searching Chrome processes using profile:", profile_dir)

    targets = []

    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            if p.info['name'] and "chrome.exe" in p.info['name'].lower():
                cmd = " ".join(p.info['cmdline'])
                if profile_dir in cmd:
                    targets.append(p)
        except:
            pass

    if not targets:
        print("[WARN] No Chrome processes found for profile")
        return

    # ★ 最も古いプロセス（=親）を特定
    parent = min(targets, key=lambda p: p.info['create_time'])
    print(f"[INFO] Parent Chrome PID={parent.pid}")

    # 子プロセス kill
    children = parent.children(recursive=True)
    for c in children:
        print(f"[INFO] Killing child PID={c.pid}")
        c.kill()

    # 親 kill
    print(f"[INFO] Killing parent PID={parent.pid}")
    parent.kill()

    print("[INFO] Chrome fully terminated")


# ---------------------------------------------------------
# Chrome 起動
# ---------------------------------------------------------
def show_web_chrome(url, duration_ms=30000):
    global video_finished, profile_dir
    video_finished = False

    print(f"[INFO] Launching Chrome: {url}")

    # 専用プロファイル
    profile_dir = tempfile.mkdtemp(prefix="chrome_profile_")

    # ★ user-data-dir を "" で囲まない
    # ★ URL は最後に置く（spawn 回避）
    subprocess.Popen([
        CHROME_PATH,
        f"--user-data-dir={profile_dir}",
        "--kiosk",
        "--autoplay-policy=no-user-gesture-required",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
        "--new-window",
        url
    ])

    # 起動直後の Chrome プロセス一覧
    time.sleep(1)
    debug_list_chrome_processes("after launch")

    timeout = duration_ms / 1000
    elapsed = 0

    while elapsed < timeout:
        if video_finished:
            print("[INFO] Video ended detected")
            break
        time.sleep(0.5)
        elapsed += 0.5

    print("[INFO] Closing Chrome")

    # kill 前の Chrome プロセス一覧
    debug_list_chrome_processes("before kill")

    kill_chrome_by_profile(profile_dir)

    # kill 後の Chrome プロセス一覧
    debug_list_chrome_processes("after kill")


# ---------------------------------------------------------
# メイン
# ---------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_chrome.py <url>")
        sys.exit(1)

    url = sys.argv[1]

    threading.Thread(target=start_file_server, daemon=True).start()
    threading.Thread(target=start_server, daemon=True).start()

    show_web_chrome(url)
