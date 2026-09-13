import os
import threading
from datetime import datetime
from pathlib import Path

class DailyLogger:
    LEVELS = {"error": 0, "info": 1, "debug": 2}

    def __init__(self, base_dir="logs", prefix="", level="info"):
        self.base_dir = Path(base_dir)
        if not self.base_dir.is_absolute():
            self.base_dir = Path(__file__).resolve().parent / self.base_dir
        self.prefix = prefix
        self.level = level.lower() if level.lower() in self.LEVELS else "info"

        os.makedirs(self.base_dir, exist_ok=True)

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

        all_path = self.base_dir / f"{self.prefix}all_{today}.log"
        a_path   = self.base_dir / f"{self.prefix}A_{today}.log"
        b_path   = self.base_dir / f"{self.prefix}B_{today}.log"

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

    def _get_message_level(self, role, message, level=None):
        if level and level.lower() in self.LEVELS:
            return level.lower()

        message_lower = str(message).lower()
        if str(role).upper() == "ERROR" or "error" in message_lower:
            return "error"
        if "[debug]" in message_lower:
            return "debug"
        return "info"

    def _clean_level_tag(self, message, message_level):
        prefix = f"[{message_level}]"
        if str(message).lstrip().lower().startswith(prefix.lower()):
            return str(message).lstrip()[len(prefix):].lstrip()
        return str(message)

    def write(self, role, message, level=None):
        message_level = self._get_message_level(role, message, level)
        if self.LEVELS[message_level] > self.LEVELS[self.level]:
            return

        with self.lock:
            self._open_files()

            timestamp = datetime.now().strftime("%H:%M:%S")
            clean_message = self._clean_level_tag(message, message_level)
            role_text = "" if str(role).upper() == message_level.upper() else str(role)
            role_prefix = f" [{role_text}]" if role_text else ""
            line = f"[{timestamp}] [{message_level.upper()}]{role_prefix} {clean_message}\n"

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
