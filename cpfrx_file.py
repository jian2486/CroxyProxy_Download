#!/usr/bin/env python3
"""
cpfrx_downloader.py – 通过 CroxyProxy 简写域名（cpfrx）下载任意文件并自动解压。
仅依赖 requests + bs4 + zipfile，Python≥3.7 可用。

用法：
    python cpfrx_downloader.py <目标URL> <本地保存路径>
示例：
    python cpfrx_downloader.py \
        https://mirror.nyist.edu.cn/ubuntu-releases/24.04/ubuntu-24.04-desktop-amd64.iso \
        downloads/
"""
import re
import sys
import zipfile  # 导入zipfile模块
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
    """取首页 csrf token token"""
    resp = SESSION.get(INDEX, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.find("input", {"name": "csrf"})["value"]


def get_real_url(target: str) -> str:
    """提交目标 URL → 提取代理直链（万能正则）"""
    csrf = get_csrf()
    resp = SESSION.post(
        f"{INDEX}/servers",
        data={"url": target, "csrf": csrf},
        allow_redirects=False,
        timeout=15,
    )
    if resp.status_code in (301, 302):
        resp = SESSION.send(resp.next, allow_redirects=True)

    html = resp.text

    # 1. data-u 字段（最常见）
    if m := re.search(r'data-u="([^"]*)"', html):
        url = m.group(1).replace(r"\/", "/").replace("&quot;", "").strip('"')
        return url

    # 2. window.location.href = "..."
    if m := re.search(r'window\.location\.href\s*=\s*"([^"]*)"', html):
        return urljoin(resp.url, m.group(1).replace(r"\/", "/"))

    # 3. 任何 /stream/ /get/ /browser/ 链接
    if m := re.search(r'<a[^>]*href="(/(?:stream|get|browser)/[^"]*)"', html):
        return urljoin(resp.url, m.group(1))

    raise RuntimeError("无法提取直链，可能页面结构变化")


# --------------------------------------------------------------------------- #
def download(url: str, save_path: str) -> None:
    """分块下载 + 进度条"""
    real = get_real_url(url)
    # 再加一次跳转，确保拿到最终 /stream/xxx
    r0 = SESSION.head(real, allow_redirects=True)
    real = r0.url
    print("最终直链：", real)

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
        print(f"\n完成 → {save_dir}")


def unzip(save_dir: str) -> None:
    """解压文件"""
    save_dir_path = Path(save_dir)
    downloaded_file = save_dir_path / "downloaded_file.zip"
    with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
        zip_ref.extractall(save_dir_path)
    print(f"\n解压完成 → {save_dir}")


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python cpfrx_downloader.py <目标URL> <本地保存路径>")
        sys.exit(1)
    target, local = sys.argv[1], sys.argv[2]
    try:
        download(target, local)
        unzip(local)
    except Exception as e:
        print("失败：", e)
        sys.exit(2)