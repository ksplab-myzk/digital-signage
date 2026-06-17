import os
import threading
from datetime import datetime

class DailyLogger:
    def __init__(self, base_dir="logs", prefix=""):
        self.base_dir = base_dir
        self.prefix = prefix

        os.makedirs(base_dir, exist_ok=True)

        self.current_date = None
        self.lock = threading.Lock()

        self.all_file = None
        self.a_file = None
        self.b_file = None

        self._open_files()

    def _open_files(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today == self.current_date:
            return

        # 日付が変わったらファイルを開き直す
        self._close_files()
        self.current_date = today

        all_path = os.path.join(self.base_dir, f"{self.prefix}all_{today}.log")
        a_path   = os.path.join(self.base_dir, f"{self.prefix}A_{today}.log")
        b_path   = os.path.join(self.base_dir, f"{self.prefix}B_{today}.log")

        self.all_file = open(all_path, "a", encoding="utf-8")
        self.a_file   = open(a_path,   "a", encoding="utf-8")
        self.b_file   = open(b_path,   "a", encoding="utf-8")

    def _close_files(self):
        for f in (self.all_file, self.a_file, self.b_file):
            try:
                if f:
                    f.close()
            except:
                pass

        self.all_file = None
        self.a_file = None
        self.b_file = None

    def write(self, role, message):
        with self.lock:
            self._open_files()

            timestamp = datetime.now().strftime("%H:%M:%S")
            line = f"[{timestamp}] [{role}] {message}\n"

            # 統合ログ
            self.all_file.write(line)
            self.all_file.flush()

            # A/B 専用ログ
            if role == "A":
                self.a_file.write(line)
                self.a_file.flush()
            elif role == "B":
                self.b_file.write(line)
                self.b_file.flush()

    def close(self):
        self._close_files()
