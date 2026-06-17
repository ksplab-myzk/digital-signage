import json
import re

def extract_vimeo_urls(path):
    with open(path, "r", encoding="utf-8") as f:
        playlist = json.load(f)

    results = []

    for item in playlist:
        if isinstance(item, dict) and item.get("source") == "vimeo":
            url = item.get("url")
            m = re.search(r"vimeo\.com/(\d+)", url)
            if m:
                vid = m.group(1)
                results.append((vid, url))

    return results
