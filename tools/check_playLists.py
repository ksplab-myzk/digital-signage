import os
import json
import glob
import re
from jinja2 import Template
from PIL import Image

# -----------------------------
# playlist*.json を自動検出
# -----------------------------
def find_playlists():
    files = glob.glob("playlist*.json")
    pattern = re.compile(r"playlist([AB])(\d+)\.json")

    playlists = {}  # { pair_number: { "A": file, "B": file } }

    for f in files:
        m = pattern.match(os.path.basename(f))
        if not m:
            continue

        role = m.group(1)  # "A" or "B"
        pair = int(m.group(2))

        if pair not in playlists:
            playlists[pair] = {}

        playlists[pair][role] = f

    return playlists


# -----------------------------
# JSON 読み込み
# -----------------------------
def load_playlist(path):
    if not os.path.exists(path):
        return None, [f"ファイルが存在しません: {path}"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), []
    except Exception as e:
        return None, [f"JSON 読み込みエラー: {path} ({e})"]


# -----------------------------
# サムネイル生成
# -----------------------------
def get_thumbnail(item):
    t = item.get("type")

    if t == "image":
        path = item.get("path")
        if path and os.path.exists(path):
            return path
        return "assets/error_icon.png"

    elif t == "pdf_images":
        folder = item.get("folder")
        if folder and os.path.exists(folder):
            pngs = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
            if pngs:
                return os.path.join(folder, pngs[0])
        return "assets/error_icon.png"

    elif t == "video":
        return "assets/video_icon.png"

    elif t == "web":
        return "assets/web_icon.png"

    return "assets/error_icon.png"


# -----------------------------
# 各アイテムのチェック
# -----------------------------
def check_item(item):
    errors = []
    t = item.get("type")

    # type チェック
    if t not in ("image", "pdf_images", "video", "web"):
        errors.append(f"未知の type: {t}")
        return errors

    # duration チェック
    if "duration" in item and not isinstance(item["duration"], int):
        errors.append(f"duration が整数ではありません: {item.get('duration')}")

    # type 別チェック
    if t == "image":
        path = item.get("path")
        if not path or not os.path.exists(path):
            errors.append(f"画像が存在しません: {path}")

    elif t == "pdf_images":
        folder = item.get("folder")
        if not folder or not os.path.exists(folder):
            errors.append(f"PDFフォルダが存在しません: {folder}")
        else:
            pngs = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
            if not pngs:
                errors.append(f"PDFフォルダに PNG がありません: {folder}")

    elif t == "video":
        path = item.get("path")
        if not path or not os.path.exists(path):
            errors.append(f"動画ファイルが存在しません: {path}")

    elif t == "web":
        url = item.get("url")
        if not url or not url.startswith(("http://", "https://")):
            errors.append(f"URL が不正です: {url}")

    return errors


# -----------------------------
# playlist 全体のチェック
# -----------------------------
def check_playlist(filename):
    playlist, load_errors = load_playlist(filename)
    results = []

    if load_errors:
        return [(filename, load_errors)], []

    thumbnails = []

    if not isinstance(playlist, list) or len(playlist) == 0:
        return [(filename, ["playlist が空です"])], []

    for i, item in enumerate(playlist):
        item_errors = check_item(item)
        if item_errors:
            results.append((f"{filename} の item[{i}]", item_errors))

        thumbnails.append(get_thumbnail(item))

    return results, thumbnails


# -----------------------------
# メイン処理
# -----------------------------
def main():
    playlists = find_playlists()
    all_errors = []
    report_data = []

    # ペア番号の欠番チェック
    if playlists:
        min_pair = min(playlists.keys())
        max_pair = max(playlists.keys())

        for p in range(min_pair, max_pair + 1):
            if p not in playlists:
                all_errors.append((f"pair{p}", [f"pair{p} が欠番です（playlistA{p}.json / playlistB{p}.json がありません）"]))

    # A/B チェック
    for pair in sorted(playlists.keys()):
        pair_data = playlists[pair]

        for role in ("A", "B"):
            if role not in pair_data:
                all_errors.append((f"pair{pair} {role}", [f"playlist{role}{pair}.json が存在しません"]))
                continue

            filename = pair_data[role]
            errors, thumbs = check_playlist(filename)

            report_data.append({
                "pair": pair,
                "role": role,
                "filename": filename,
                "errors": errors,
                "thumbnails": thumbs
            })

            all_errors.extend(errors)

    # HTML 出力
    with open("templates/report.html", "r", encoding="utf-8") as f:
        template = Template(f.read())

    html = template.render(report_data=report_data, all_errors=all_errors)

    with open("playlist_check_result.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("チェック完了: playlist_check_result.html を開いてください")


if __name__ == "__main__":
    main()
