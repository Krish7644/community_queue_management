"""Generate synthetic Python fixtures and compare unchanged artwork with the PHP reference."""
import os
import sys
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from portal import models as m
from portal.cards import render_card, TEMPLATES

output = ROOT / "backend/media/template-comparison/python"
output.mkdir(parents=True, exist_ok=True)
token = "a" * 64
authority = m.Authority(pk=99991, name="Sample HOD", account_type="HOD")
congregation = m.Authority(pk=99992, name="Sample Congregation", account_type="CONGREGATION")
fixtures = {
    "hod": ("HOD", m.HodPass(pk=99991, hod=authority, pass_code="H5-99991-0001", recipient_name="Sample Devotee", token=token)),
    "combined": ("COMBINED", m.CombinedPass(pk=99992, congregation=congregation, pass_code="CG-99991-0001", recipient_name="Sample Devotee", token=token)),
    "vvip": ("VVIP", m.VvipPass(pk=99992, pass_id="V5-99991-0001", guest_name="Sample Devotee", recipient_name="Sample Devotee", token=token)),
    "volunteer": ("VOLUNTEER", m.VolunteerPass(pk=99992, pass_id="VOL-99991-0001", guest_name="Sample Devotee", token=token)),
    "member": ("MEMBER", m.Member(pk=99993, name="Sample Devotee", devotee_id="99993", authority=authority, approval_status="APPROVED")),
}
event = SimpleNamespace(date_label="4th Sep 2026", timings="10:00 AM to 3:00 PM", vvip_entry_gate="BVMS SCHOOL")
report = {}
for name, (kind, record) in fixtures.items():
    with patch("portal.cards.EventSettings.objects.get_or_create", return_value=(event, False)), patch("portal.cards.QrToken.objects.filter") as query:
        query.return_value.first.return_value = SimpleNamespace(token=token)
        image_path = render_card(kind, record)
    target = output / (name + ".png")
    target.write_bytes(image_path.read_bytes())
    image = Image.open(target).convert("RGB")
    original = Image.open(output.parent / "php" / (name + ".png")).convert("RGB")
    assert image.size == original.size, name
    # A large unchanged band containing the actual logos/header lettering must remain exact.
    protected = (20, 20, 800, 300) if name != "member" else (0, 0, 760, 250)
    exact = ImageChops.difference(image.crop(protected), original.crop(protected)).getbbox() is None
    assert exact, name + " changed protected header artwork"
    report[name] = {"dimensions": image.size, "original_header_pixels_match": exact}
legacy = ROOT / "readonly-source-review/iskcontirupati_community_scanner-main/public/assets/images"
for filename in ("community-card-template.png", "hod-pass-template.png", "volunteer-pass-template.png", "srila-prabhupada.png"):
    assert hashlib.sha256((TEMPLATES / filename).read_bytes()).digest() == hashlib.sha256((legacy / filename).read_bytes()).digest(), filename
report["repository_assets_byte_identical"] = True
(output.parent / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
