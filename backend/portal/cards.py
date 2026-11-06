"""Private pass rendering using the unchanged PHP application's approved artwork."""
import hashlib
import json
import math
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps
from django.conf import settings
from rest_framework.exceptions import NotFound
from .models import EventSettings, QrToken

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TEMPLATES = ASSETS / "pass-templates"
LAYOUT = json.loads((TEMPLATES / "layout.json").read_text(encoding="utf-8"))
CREAM = (255, 252, 245)
MAROON = (75, 21, 30)


def safe_image_path(relative):
    for root in (settings.MEDIA_ROOT, settings.LEGACY_PUBLIC):
        candidate = (root / str(relative)).resolve()
        if candidate.is_relative_to(root.resolve()) and candidate.is_file():
            return candidate
    raise NotFound("Image not available in this local copy.")


def font(points, condensed=False):
    name = "DejaVuSerifCondensed-Bold.ttf" if condensed else "DejaVuSerif-Bold.ttf"
    # GD's imagettftext takes typographic points at 96 DPI; Pillow takes pixels.
    return ImageFont.truetype(str(ASSETS / "fonts" / name), max(1, round(points * 96 / 72)))


def _fit(canvas, text, x, baseline, width, size, color=MAROON, minimum=11, compress=False, center=False, condensed=False):
    text = " ".join(str(text or "").split())
    def measure(value, point_size):
        box = font(point_size, condensed).getbbox(value)
        return box[2] - box[0]
    while size > minimum and measure(text, size) > width:
        size -= 1
    measured = measure(text, size)
    if center:
        x += max(0, math.floor((width - min(width, measured)) / 2))
    if measured > width and compress:
        face = font(size, condensed)
        box = face.getbbox(text, anchor="ls")
        layer = Image.new("RGBA", (measured + 8, box[3] - box[1] + 8))
        ImageDraw.Draw(layer).text((4 - box[0], 4 - box[1]), text, font=face, fill=color, anchor="ls")
        layer = layer.resize((int(width), layer.height), Image.Resampling.LANCZOS)
        canvas.paste(layer, (int(x), int(baseline + box[1] - 4)), layer)
    else:
        if measured > width:
            while len(text) > 1 and measure(text + "...", size) > width:
                text = text[:-1]
            text = text.rstrip() + "..."
        ImageDraw.Draw(canvas).text((int(x), int(baseline)), text, font=font(size, condensed), fill=color, anchor="ls")
    return min(width, measured)


def _template(name):
    source = Image.open(TEMPLATES / name).convert("RGBA")
    canvas = Image.new("RGBA", source.size, CREAM + (255,))
    canvas.alpha_composite(source)
    return canvas.convert("RGB")


def _portrait(canvas, layout):
    source = Image.open(TEMPLATES / "srila-prabhupada.png").convert("RGBA")
    source = source.crop((layout["source_x"], layout["source_y"],
                          layout["source_x"] + layout["source_width"], layout["source_y"] + layout["source_height"]))
    source = source.resize((layout["width"], layout["height"]), Image.Resampling.LANCZOS)
    canvas.paste(source, (layout["x"], layout["y"]), source)


def _qr(token, size):
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=16, border=0)
    code.add_data(token)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white").convert("RGB")
    image = ImageOps.expand(image, border=8, fill="white")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _clear(canvas, rectangle, sample=None, color=None):
    fill = color if color is not None else canvas.getpixel(tuple(sample))
    ImageDraw.Draw(canvas).rectangle(tuple(rectangle), fill=fill)


def _hod(record, event, vvip=False):
    layout = LAYOUT["hod_layout"]
    canvas = _template("hod-pass-template.png")
    _portrait(canvas, layout["portrait"])
    recipient = record.get("recipient", "")
    area = layout["recipient"]
    _clear(canvas, area["clear"], area["sample"])
    if recipient:
        width = _fit(canvas, recipient, area["x"], area["y"], area["width"], area["size"],
                     minimum=area["minimum_size"], compress=True)
        _fit(canvas, ",", area["x"] + width + area["comma_gap"], area["y"], 22, area["size"])
    values = {"pass_code": record["code"], "capacity": "5", "event_date": event.date_label, "timings": event.timings}
    for key, value in values.items():
        area = layout["details"][key]
        top, bottom = area["clear_top"], area["clear_bottom"]
        _clear(canvas, (area["x"] - 4, top, area["x"] + area["width"], bottom),
               (layout["details"]["sample_x"], top))
        _fit(canvas, value, area["x"], area["y"], area["width"], area["size"])
    area = layout["qr"]
    _clear(canvas, area["clear"], color=CREAM)
    canvas.paste(_qr(record["token"], area["width"]), (area["x"], area["y"]))
    area = layout["authority_name"]
    name = area["wide" if vvip else "normal"]
    _clear(canvas, (name["x"] - 10, area["clear_top"], name["x"] + name["width"] + 10, area["clear_bottom"]), area["sample"])
    _fit(canvas, record["authority"], name["x"], area["baseline"], name["width"], name["size"],
         minimum=name["minimum_size"], compress=vvip, center=True)
    if vvip:
        draw = ImageDraw.Draw(canvas)
        # Restore the original footer's per-row shading before replacing its wording.
        for y in range(1332, 1391):
            pixels = [canvas.getpixel((x, y)) for x in range(145, 946, 4)]
            pixels = [pixel for pixel in pixels if not (pixel[0] > 130 and pixel[1] > 80)]
            shade = tuple(sum(pixel[channel] for pixel in pixels) // max(1, len(pixels)) for channel in range(3))
            draw.line((145, y, 945, y), fill=shade)
        footer = "VVIP PASS - ENTRY AT " + event.vvip_entry_gate
        _fit(canvas, footer, 135, 1375, 820, 26, color=(198, 145, 37), minimum=14, center=True, condensed=True)
    return canvas


def _volunteer(record):
    canvas = _template("volunteer-pass-template.png")
    layout = LAYOUT["volunteer_layout"]
    _portrait(canvas, layout["portrait"])
    for key, value in (("name", record["name"]), ("pass_id", record["code"])):
        area = layout[key]
        _clear(canvas, area["clear"], area["sample"])
        _fit(canvas, value, area["x"], area["y"], area["width"], area["size"],
             minimum=area["minimum_size"], compress=True)
    area = layout["qr"]
    _clear(canvas, area["clear"], area["sample"])
    canvas.paste(_qr(record["token"], area["width"]), (area["x"], area["y"]))
    return canvas


def _community(record, token):
    canvas = _template("community-card-template.png")
    draw = ImageDraw.Draw(canvas)
    # Match card_place_prabhupada_portrait, including the preserved gold border.
    border = canvas.crop((824, 296, 1055, 368))
    draw.rectangle((824, 48, 1054, 323), fill=canvas.getpixel((820, 78)))
    portrait = Image.open(TEMPLATES / "srila-prabhupada.png").convert("RGBA").resize((160, 240), Image.Resampling.LANCZOS)
    canvas.paste(portrait, (858, 65), portrait)
    canvas.paste(border, (824, 296))
    draw.rectangle((96, 403, 446, 726), fill=CREAM)
    draw.rectangle((112, 419, 430, 710), fill=(196, 132, 33))
    try:
        if not record.photo_path:
            raise NotFound()
        photo = Image.open(safe_image_path(record.photo_path)).convert("RGB")
        canvas.paste(ImageOps.fit(photo, (308, 281), centering=(0.5, 0.5)), (117, 424))
    except (OSError, NotFound):
        draw.rectangle((117, 424, 425, 705), fill=(239, 228, 207))
        _fit(canvas, "PHOTO UNAVAILABLE", 145, 575, 250, 18, color=(89, 19, 35))
    account = "TEMPLE AUTHORITY" if record.admin_id else "BRAHMACHARI" if record.authority and record.authority.profile_type == "BRAHMACHARI" else "CONGREGATION" if record.authority and record.authority.account_type == "CONGREGATION" else "HOD"
    for label, value, top, baseline in (("NAME", record.name, 445, 489), ("DEVOTEE ID", record.devotee_id, 548, 579), ("ACCOUNT", account, 638, 669)):
        draw.rectangle((525, top, 695, top + 46), fill=CREAM)
        draw.rectangle((700, top, 1032, top + 46), fill=CREAM)
        _fit(canvas, label + " :", 540, baseline, 145, 17, color=(184, 123, 37))
        _fit(canvas, value, 700, baseline, 320, 20, color=(89, 19, 35))
    draw.rectangle((420, 770, 700, 1052), fill=CREAM)
    canvas.paste(_qr(token, 270), (426, 776))
    return canvas.crop((40, 40, 1082, 1362))


def render_card(kind, record, thumb=False):
    event, _ = EventSettings.objects.get_or_create(pk=1)
    if kind == "MEMBER":
        qr = QrToken.objects.filter(member=record, status="ACTIVE").first()
        if not qr or record.approval_status != "APPROVED":
            raise NotFound("An approved member with an active QR token is required.")
        token = qr.token
    else:
        token = record.token
    code = getattr(record, "pass_code", None) or getattr(record, "pass_id", None) or record.devotee_id
    authority = ""
    recipient = getattr(record, "recipient_name", "") or ""
    name = getattr(record, "guest_name", None) or getattr(record, "holder_name", "")
    if kind == "HOD":
        authority = record.hod.name
    elif kind == "COMBINED":
        authority = record.congregation.name
    elif kind == "IMMEDIATE":
        authority = record.custom_authority_name or (record.authority.name if record.authority else "Temple Authority")
        recipient = recipient or record.holder_name
    vvip = kind == "VVIP" or (kind == "IMMEDIATE" and record.pass_type == "VVIP")
    volunteer = kind == "VOLUNTEER" or (kind == "IMMEDIATE" and record.pass_type == "VOLUNTEER")
    if vvip:
        authority = LAYOUT["vvip_scanner_name"]
        recipient = recipient or name
    photo_path = None
    if kind == "MEMBER" and record.photo_path:
        try:
            photo_path = safe_image_path(record.photo_path)
        except NotFound:
            pass
    assets = [(path.name, path.stat().st_mtime_ns, path.stat().st_size)
              for path in sorted(TEMPLATES.iterdir()) if path.is_file()]
    payload = ["original-templates-v1", kind, code, token, recipient, name, authority,
               event.date_label, event.timings, event.vvip_entry_gate,
               record.name if kind == "MEMBER" else None,
               record.devotee_id if kind == "MEMBER" else None,
               record.authority_id if kind == "MEMBER" else None,
               str(photo_path), photo_path.stat().st_mtime_ns if photo_path else None, assets]
    digest = hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()
    directory = settings.MEDIA_ROOT / "private-cards"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / (digest + ".png")
    if not output.exists():
        data = {"token": token, "code": code, "recipient": recipient, "name": name, "authority": authority}
        image = _community(record, token) if kind == "MEMBER" else _volunteer(data) if volunteer else _hod(data, event, vvip)
        image.save(output, "PNG", compress_level=6)

    if thumb:
        thumb_output = directory / (digest + "-thumb.webp")
        if not thumb_output.exists():
            image = Image.open(output)
            w, h = image.size
            tw = 320
            th = int(h * (tw / w))
            thumb_img = image.resize((tw, th), Image.Resampling.LANCZOS)
            thumb_img.save(thumb_output, "WEBP", quality=85)
        return thumb_output

    return output
