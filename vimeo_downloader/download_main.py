import sys
from playlist_processor import extract_vimeo_urls
from downloader import download_vimeo
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python download_main.py <playlist.json>")
        return

    playlist_path = sys.argv[1]

    print(f"[INFO] Processing {playlist_path}")

    # playlist から Vimeo URL を抽出（あなたの processor が担当）
    vimeo_items = extract_vimeo_urls(playlist_path)

    if not vimeo_items:
        print("[INFO] No Vimeo items found.")
        return

    # すべての Vimeo URL をダウンロード
    for vid, url in vimeo_items:
        save_path = f"videos/{vid}.mp4"

        # 既に存在するならスキップ
        if os.path.exists(save_path):
            print(f"[INFO] Already exists: {save_path}")
            continue

        print(f"[INFO] Downloading {url} → {save_path}")
        download_vimeo(url, save_path)

    print("[INFO] Done.")

if __name__ == "__main__":
    main()
