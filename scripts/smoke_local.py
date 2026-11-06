"""Read-only HTTP smoke checks using credentials from the local source snapshot."""
import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import MySQLdb
import MySQLdb.cursors
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
config = dotenv_values(ROOT / "backend/.env")
database = MySQLdb.connect(host="127.0.0.1", port=3306, user=config["DB_USER"], passwd=config["DB_PASSWORD"],
    db="community_scanner_legacy", charset="utf8mb4", cursorclass=MySQLdb.cursors.DictCursor)
base = os.getenv("PORTAL_API_BASE", "http://127.0.0.1:5173")
frontend_base = os.getenv("PORTAL_FRONTEND_BASE", "http://127.0.0.1:5173")
with urllib.request.urlopen(frontend_base) as response:
    assert response.status == 200 and b"Darshan Seva Portal" in response.read()
print("React preview: PASS")

for role, table, extra in [("ADMIN", "admins", ""), ("AUTHORITY", "authorities", " AND account_type='HOD'"),
                            ("AUTHORITY", "authorities", " AND account_type='CONGREGATION'"), ("SCANNER", "scanners", "")]:
    with database.cursor() as cursor:
        cursor.execute(f"SELECT username,password FROM `{table}` WHERE status='ACTIVE'" + extra + " LIMIT 1")
        account = cursor.fetchone()
    if not account:
        continue
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(path, body=None):
        headers = {"Content-Type": "application/json", "Origin": base}
        if body is not None:
            headers["X-CSRFToken"] = next(cookie.value for cookie in jar if cookie.name == "csrftoken")
        operation = urllib.request.Request(base + "/api/" + path,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with opener.open(operation) as result:
            contents = result.read()
            return json.loads(contents) if "application/json" in result.headers.get("Content-Type", "") else contents

    request("auth/session/")
    session = request("auth/login/", {"username": account["username"], "password": account["password"], "role": role})
    assert session["user"]["role"] == role
    request("options/")
    if role == "ADMIN":
        for endpoint in ("dashboard/", "profile/", "entries/", "authorities/", "scanners/", "gates/", "members/", "audit/", "event/", "batches/", "passes/export/"):
            request(endpoint)
        assert request("passes/export/?filetype=xlsx").startswith(b"PK")
        assert request("profile/credentials/")["password"] == account["password"]
        directory = request("authorities/")
        if directory["results"]:
            credentials = request("authorities/" + str(directory["results"][0]["id"]) + "/credentials/")
            assert isinstance(credentials["password"], str) and not credentials["needs_reset"]
        directory = request("scanners/")
        if directory["results"]:
            credentials = request("scanners/" + str(directory["results"][0]["id"]) + "/credentials/")
            assert isinstance(credentials["password"], str) and not credentials["needs_reset"]
        listing = request("passes/")
        with database.cursor() as cursor:
            cursor.execute("SELECT (SELECT COUNT(*) FROM hod_passes)+(SELECT COUNT(*) FROM congregation_combined_passes)+(SELECT COUNT(*) FROM volunteer_passes)+(SELECT COUNT(*) FROM immediate_passes)+(SELECT COUNT(*) FROM vvip_passes) AS total")
            baseline = cursor.fetchone()["total"]
        assert listing["count"] >= baseline, listing["count"]
        for kind in ("HOD", "COMBINED", "VOLUNTEER", "IMMEDIATE"):
            listing = request("passes/?kind=" + kind)
            assert listing["results"], kind
            image = request("passes/" + kind + "/" + str(listing["results"][0]["id"]) + "/card/")
            assert image.startswith(b"\x89PNG"), kind
    elif role == "AUTHORITY":
        request("profile/")
        request("passes/")
        for endpoint in ("dashboard/", "entries/", "audit/", "profile/credentials/"):
            try:
                request(endpoint)
                raise AssertionError("Authority must not access " + endpoint)
            except urllib.error.HTTPError as error:
                assert error.code == 403
    else:
        for endpoint in ("passes/", "profile/", "dashboard/", "entries/", "profile/credentials/"):
            try:
                request(endpoint)
                raise AssertionError("Scanner must not access " + endpoint)
            except urllib.error.HTTPError as error:
                assert error.code == 403
        with database.cursor() as cursor:
            cursor.execute("SELECT pass_code FROM hod_passes WHERE status='ACTIVE' LIMIT 1")
            code = cursor.fetchone()["pass_code"]
        checked = request("scan/lookup/", {"code": code})
        assert checked["kind"] == "HOD"
    request("auth/logout/", {})
    print(role + (" congregation" if "CONGREGATION" in extra else "") + " authentication and scoped endpoints: PASS")
database.close()
print("HTTP smoke checks complete. No pass admissions or business updates were submitted.")
