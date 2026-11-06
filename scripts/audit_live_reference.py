"""Inspect the existing portal's role screens without submitting business forms."""
import html
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
import MySQLdb
import MySQLdb.cursors
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "backend/media/live-reference"
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = "https://rajputsagai.com/janmashtami_qline_scanner"
config = dotenv_values(ROOT / "backend/.env")
database = MySQLdb.connect(host="127.0.0.1", user=config["DB_USER"], passwd=config["DB_PASSWORD"],
                          db="community_scanner_legacy", charset="utf8mb4", cursorclass=MySQLdb.cursors.DictCursor)


def text(markup):
    return html.unescape(re.sub(r"<[^>]+>", " ", markup)).strip()


def summary(markup):
    headings = [text(match[1]) for match in re.findall(r"<(title|h[1-6])\b[^>]*>(.*?)</\1>", markup, re.S | re.I)]
    forms = []
    for attributes, content in re.findall(r"<form\b([^>]*)>(.*?)</form>", markup, re.S | re.I):
        action = re.search(r'action="([^"]*)"', attributes)
        method = re.search(r'method="([^"]*)"', attributes)
        forms.append({"action": action.group(1).replace(BASE, "") if action else "same page", "method": method.group(1) if method else "GET",
                      "fields": re.findall(r'<(?:input|select|textarea)\b[^>]*name="([^"]+)"', content),
                      "buttons": [text(value) for value in re.findall(r'<button\b[^>]*>(.*?)</button>', content, re.S)]})
    navs = re.findall(r'<nav\b[^>]*>(.*?)</nav>', markup, re.S | re.I)
    navigation = list(dict.fromkeys((text(label), html.unescape(url).replace(BASE, "")) for content in navs for url, label in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', content, re.S)))
    labels = list(dict.fromkeys(text(value) for value in re.findall(r'<label\b[^>]*>(.*?)</label>', markup, re.S)))
    return {"headings": headings, "navigation": navigation, "labels": labels, "forms": forms[:8],
            "has_pass_grid": 'pass-card-preview' in markup, "has_table": '<table' in markup,
            "images": len(re.findall(r'<img\b', markup))}


roles = [
    ("admin", "SELECT username,password FROM admins WHERE status='ACTIVE' LIMIT 1"),
    ("hod", "SELECT username,password FROM authorities WHERE status='ACTIVE' AND account_type='HOD' AND COALESCE(profile_type,'')<>'BRAHMACHARI' AND EXISTS(SELECT 1 FROM hod_passes WHERE hod_id=authorities.id) ORDER BY id LIMIT 1"),
    ("congregation", "SELECT username,password FROM authorities WHERE status='ACTIVE' AND account_type='CONGREGATION' ORDER BY id LIMIT 1"),
    ("brahmachari", "SELECT username,password FROM authorities WHERE status='ACTIVE' AND profile_type='BRAHMACHARI' ORDER BY id LIMIT 1"),
    ("scanner", "SELECT username,password FROM scanners WHERE status='ACTIVE' ORDER BY id LIMIT 1"),
    ("volunteer", "SELECT username,password FROM volunteers WHERE status='ACTIVE' ORDER BY id LIMIT 1"),
]
report = {}
for role, sql in roles:
    with database.cursor() as cursor:
        cursor.execute(sql)
        account = cursor.fetchone()
    if not account:
        report[role] = {"available": False, "reason": "No active account in supplied snapshot."}
        continue
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "Mozilla/5.0"), ("Accept", "text/html,application/xhtml+xml,image/png,*/*;q=0.8")]
    with opener.open(BASE + "/index.php", timeout=30) as response:
        login = response.read().decode("utf-8")
    csrf = re.search(r'name="csrf" value="([^"]+)"', login).group(1)
    data = urllib.parse.urlencode({"csrf": csrf, "role": "common", "username": account["username"], "password": account["password"]}).encode()
    with opener.open(urllib.request.Request(BASE + "/login", data=data), timeout=30) as response:
        markup = response.read().decode("utf-8")
        home_url = response.geturl()
    if 'name="username"' in markup and 'data-clear-login-fields' in markup:
        report[role] = {"available": False, "reason": "Supplied snapshot login did not authenticate on the live portal."}
        continue
    pages = {"home": summary(markup)}
    links = [html.unescape(value) for value in re.findall(r'href="([^"]+)"', markup)]
    profile_link = next((link for link in links if '/profile' in link and link.startswith(BASE)), None)
    if profile_link:
        with opener.open(profile_link, timeout=30) as response:
            pages["profile"] = summary(response.read().decode("utf-8"))
    shared_link = next((link for link in links if 'shared-passes' in link and link.startswith(BASE)), None)
    if shared_link:
        with opener.open(shared_link, timeout=30) as response:
            pages["shared"] = summary(response.read().decode("utf-8"))
    image = next((html.unescape(src) for src in re.findall(r'<img\b[^>]*src="([^"]+)"', markup) if '/image' in src or '/uploads/cards/' in src), None)
    if image:
        with opener.open(image, timeout=30) as response:
            (OUTPUT / (role + "-pass.png")).write_bytes(response.read())
    report[role] = {"available": True, "home": home_url.replace(BASE, ""), "pages": pages, "reference_image": bool(image)}
    print(role + ": live login and page inspection complete.", flush=True)

for asset in ("app.css", "components.css"):
    with opener.open(BASE + "/assets/css/" + asset, timeout=30) as response:
        (OUTPUT / asset).write_bytes(response.read())
database.close()
(OUTPUT / "role-audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
for role, result in report.items():
    print(json.dumps({"role": role, **result}, ensure_ascii=False))
