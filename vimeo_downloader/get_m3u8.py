import re
import requests

def extract_m3u8(url):
    print(f"[INFO] Fetching Vimeo page: {url}")
    html = requests.get(url).text

    # m3u8 の URL を探す（Vimeo の標準パターン）
    m3u8_matches = re.findall(r'https:[^"]+\.m3u8', html)

    if not m3u8_matches:
        print("[ERROR] m3u8 が見つかりません")
        return None

    # 一番最初の m3u8 を返す
    m3u8_url = m3u8_matches[0].replace("\\/", "/")
    print(f"[INFO] Found m3u8: {m3u8_url}")

    return m3u8_url


if __name__ == "__main__":
    # テスト用
    # extract_m3u8("https://vimeo.com/1087454043")
    extract_m3u8("https://vimeo.com/76979871")

