import requests, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin

INDEX = "https://www.a.cpfrx.info"
s = requests.Session()

# 1. 拿 csrf
r = s.get(INDEX)
csrf = BeautifulSoup(r.text, "html.parser").find("input", {"name": "csrf"})["value"]
print("csrf =", csrf)

# 2. 请求目标
target = sys.argv[1] if len(sys.argv) > 1 else \
         "https://releases.ubuntu.com/24.04/ubuntu-24.04-desktop-amd64.iso"
print("target =", target)
resp = s.post(f"{INDEX}/servers",
              data={"url": target, "csrf": csrf},
              allow_redirects=True)
html = resp.text
print("\n==== 返回前 20 kB ====")
print(html[:20_000])