#!/usr/bin/env python3
"""
cpfrx_downloader.py – Download any file through CroxyProxy shorthand domain (cpfrx) and automatically unzip.
Only dependencies are requests + bs4 + zipfile, Python >=3.7 is available.

Usage:
    python cpfrx_downloader.py <Target URL> <Local save path>
Example:
    python cpfrx_downloader.py \
        https://mirror.nyist.edu.cn/ubuntu-releases/24.04/ubuntu-24.04-desktop-amd64.iso  \
        downloads/
"""
import re
import sys
import zipfile  # Import zipfile module
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

INDEX = "https://www.a.cpfrx.info"
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=3))
SESSION.headers.update(
    {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36")
    }
)


# ---------------------------------------------------------------------------#
def get_csrf() -> str:
    """Retrieve csrf token token from homepage"""
    try:
        resp = SESSION.get(INDEX, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return soup.find("input", {"name": "csrf"})["value"]
    except requests.RequestException as e:
        print(f"Failed to retrieve CSRF token: {e}")
        sys.exit(1)


def get_real_url(target: str) -> str:
    """Submit target URL → Extract proxy direct link (universal rule)"""
    csrf = get_csrf()
    try:
        resp = SESSION.post(
            f"{INDEX}/servers",
            data={"url": target, "csrf": csrf},
            allow_redirects=False,
            timeout=15,
        )
        if resp.status_code in (301, 302):
            resp = SESSION.send(resp.next, allow_redirects=True)

        html = resp.text

        # 1. data-u segment (most common)
        if m := re.search(r'data-u="([^"]*)"', html):
            url = m.group(1).replace(r"\/", "/").replace("&quot;", "").strip('"')
            return url

        # 2. window.location.href = "..."
        if m := re.search(r'window\.location\.href\s*=\s*"([^"]*)"', html):
            return urljoin(resp.url, m.group(1).replace(r"\/", "/"))

        # 3. Any /stream/ /get/ /browser/ link
        if m := re.search(r'<a[^>]*href="(/(?:stream|get|browser)/[^"]*)"', html):
            return urljoin(resp.url, m.group(1))

        raise RuntimeError("Failed to extract direct link, possible page structure change")
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to extract direct link: {e}")


# --------------------------------------------------------------------------- #
def download(url: str, save_path: str) -> None:
    """Download in chunks + progress bar"""
    real = get_real_url(url)
    # Follow redirect once more to ensure to get the final /stream/xxx
    r0 = SESSION.head(real, allow_redirects=True)
    real = r0.url
    print("Final direct link:", real)

    try:
        with SESSION.get(real, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            with open(save_dir / "downloaded_file.zip", "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        percent = done * 100 // total
                        print(f"\r{done:,}/{total:,}  {percent}%", end="", flush=True)
            print(f"\nCompleted → {save_dir}")

    except requests.RequestException as e:
        print(f"Failed to download: {e}")
        sys.exit(1)

def unzip(save_dir: str) -> None:
    """Unzip the file"""
    save_dir_path = Path(save_dir)
    downloaded_file = save_dir_path / "downloaded_file.zip"
    try:
        with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
            zip_ref.extractall(save_dir_path)
        print(f"\nUnzipped → {save_dir}")

    except zipfile.BadZipFile as e:
        print(f"Failed to unzip: {e}")
        sys.exit(1)

# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python cpfrx_downloader.py <Target URL> <Local save path>")
        sys.exit(1)
    target, local = sys.argv[1], sys.argv[2]
    try:
        download(target, local)
        unzip(local)
    except Exception as e:
        print("Failed:", e)
        sys.exit(2)