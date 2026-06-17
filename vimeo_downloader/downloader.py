import re
import requests
import os

def download_vimeo(url, save_path):
    html = requests.get(url).text

    # progressive mp4 セクションを抽出
    match = re.search(r'"progressive":\s*\[(.*?)\]', html)
    if not match:
        print("mp4情報が見つかりません")
        return None

    prog = match.group(1)

    # mp4 URL を抽出
    mp4_urls = re.findall(r'"url":"(https:[^"]+\.mp4)"', prog)
    if not mp4_urls:
        print("mp4 URLが見つかりません")
        return None

    # 一番高画質を選択
    mp4_url = mp4_urls[-1].replace("\\/", "/")

    print("Downloading:", mp4_url)

    r = requests.get(mp4_url, stream=True)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    with open(save_path, "wb") as f:
        for chunk in r.iter_content(1024*1024):
            if chunk:
                f.write(chunk)

    return save_path
