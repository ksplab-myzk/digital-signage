import sys
import configparser
import psutil   # pip install psutil
import platform
import subprocess
import os
import json
from pathlib import Path

def load_config():

    config = configparser.ConfigParser()
    with open("config.ini", "r", encoding="utf-8") as f:
        config.read_file(f)

    return {
        "mode": config.get("display", "mode", fallback="dual").strip().lower(),
        "fallback_to_single": config.getboolean("display", "fallback_to_single", fallback=True),

        "playlist_folder": config.get("playlist", "folder", fallback="playlists"),

        "pairs_a": config.get("playlist", "pairs_a", fallback="pairsA"),
        "pairs_b": config.get("playlist", "pairs_b", fallback="pairsB"),
        "path_a": config.get("playlist", "path_a", fallback="playlistA"),
        "path_b": config.get("playlist", "path_b", fallback="playlistB"),

        "allow_single_when_b_missing": config.getboolean(
            "playlist", "allow_single_when_b_missing", fallback=True
        ),

        "enable_time_control" : config.getboolean("system", "enable_time_control"),
        "start_time" : config.get("system", "start_time"),
        "end_time" : config.get("system", "end_time"),

        "shared_mode" : config.get("shared", "shared_mode"),
        "shared_path" : config.get("shared", "shared_path"),
        "shared_host" : config.get("shared", "shared_host"),
        "shared_share" : config.get("shared", "shared_share"),
        "shared_user" : config.get("shared", "shared_user"),
        "shared_pass" : config.get("shared", "shared_pass"),
        "shared_mount" : config.get("shared", "shared_mount"),
        "shared_drive" : config.get("shared", "shared_drive")

    }

# 多重起動チェック
LOCK_FILE = "digital_signage.lock"

def check_single_instance():
    if os.path.exists(LOCK_FILE):
        # 既存の PID を読む
        with open(LOCK_FILE, "r") as f:
            pid = int(f.read().strip())

        # PID が生きているか確認
        if psutil.pid_exists(pid):
            print("[WARN] 既に起動しています → 多重起動を終了します")
            sys.exit(0)
        else:
            # 死んでいる PID → ロックファイルを削除して再作成
            os.remove(LOCK_FILE)

    # 新しい PID を書き込む
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def cleanup_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def detect_shared_role(cfg):
    mode = cfg["shared_mode"]

    if mode == "single":
        role = "single"
    elif mode == "shared_main":
        role = "shared_main"
    elif mode == "shared_sub":
        role = "shared_sub"
    else:
        role = "single"

    print(f"[SharedMode] role={role}")

    return(role)

def connect_shared(logger, cfg):
    ### --- 共有フォルダに接続する（Mac / Windows 両対応）
    ### --- config.ini の設定に基づいて OS ごとに処理を切り替える

    # shared_type = self.config.get("shared_type", "smb_windows")
    host = cfg["shared_host"]
    share = cfg["shared_share"]
    user = cfg["shared_user"]
    password = cfg["shared_pass"]
    mount_point = cfg["shared_mount"]

    os_name = platform.system()  # 'Darwin' or 'Windows'

    # --- すでにマウント済みならスキップ ---
    if os_name == "Darwin":
        if os.path.ismount(mount_point):
            logger.write("", f"SMB already mounted: {mount_point}")
            return True

    if os_name == "Windows":
        # Windows は UNC パスが認証済みならそのまま使える
        test_path = f"\\\\{host}\\{share}"
        if os.path.exists(test_path):
            logger.write("", f"SMB already accessible: {test_path}")
            return True

    # --- OSごとの接続処理 ---
    if os_name == "Darwin":
        # --- Mac の場合 ---
        logger.write("", "connect_shared(): macOS → mount_smbfs")

        # マウントポイント作成
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)

        cmd = f"mount_smbfs //{user}:{password}@{host}/{share} {mount_point}"

        try:
            subprocess.run(cmd, shell=True, check=True)
            logger.write("", f"SMB mounted: {mount_point}")
            return True
        except Exception as e:
            logger.write("ERROR", f"SMB mount failed: {e}")
            return False

    elif os_name == "Windows":
        # --- Windows の場合 ---
        logger.write("", "connect_shared(): Windows → net use")

        # UNC パス
        unc_path = f"\\\\{host}\\{share}"

        # ドライブレターを固定（任意）
        drive_letter = cfg["shared_drive"]

        # 既存の接続を削除（安全策）
        subprocess.run(f"net use {drive_letter}: /delete", shell=True)

        # 接続コマンド
        cmd = f'net use {drive_letter}: {unc_path} /user:{user} {password}'

        try:
            subprocess.run(cmd, shell=True, check=True)
            logger.write("", f"SMB connected: {drive_letter}: → {unc_path}")
            return True
        except Exception as e:
            logger.write("ERROR", f"SMB connect failed: {e}")
            return False

    else:
        logger.write("ERROR", f"Unsupported OS: {os_name}")
        return False


def load_playlist(path: str, playlist_folder: str):
    # playlist_folder/path を絶対パス化
    base_dir = Path(__file__).resolve().parent
    playlist_dir = base_dir / playlist_folder
    p = playlist_dir / path

    if not p.exists():
        return {"items": [], "overlay": None}

    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)

        # プレイリストは list 前提
        if not isinstance(data, list):
            return {"items": [], "overlay": None}

        items = []
        overlay = None

        for entry in data:
            if "overlay" in entry:
                overlay = entry["overlay"]
            else:
                items.append(entry)

        return {
            "items": items,
            "overlay": overlay
        }

    except Exception:
        return {"items": [], "overlay": None}


def load_playlist_pair(base_a: str, base_b: str, pair_number: int, playlist_folder: str):
    # file_a = f"{base_a}{pair_number}.json"
    # file_b = f"{base_b}{pair_number}.json"

    playlistA = load_playlist(base_a, playlist_folder)
    playlistB = load_playlist(base_b, playlist_folder)

    if not playlistA:
        return None, None  # A が無いならこのペアは存在しない

    # B が無い場合は None のまま返す（fallback ロジックが後で処理）
    return playlistA, playlistB
