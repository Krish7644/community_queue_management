"""Pass ownership, issuance and admission rules shared by every API path."""
import uuid
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from . import models as m
from .authentication import profile_for

PASS_MODELS = {"HOD": m.HodPass, "COMBINED": m.CombinedPass, "VVIP": m.VvipPass,
               "VOLUNTEER": m.VolunteerPass, "IMMEDIATE": m.ImmediatePass, "MEMBER": m.Member}


def audit(user, action, instance, reason=""):
    if user.role in ("SCANNER", "VOLUNTEER"):
        reason = f"{reason} · {user.role} #{user.legacy_id}"
    return m.AuditLog.objects.create(admin_id=user.legacy_id if user.role == "ADMIN" else None,
        authority_id=user.legacy_id if user.role == "AUTHORITY" else None,
        action=action, entity_type=instance._meta.model_name.upper(), entity_id=instance.pk, reason=reason)


def require_staff(user):
    profile = profile_for(user)
    if user.role not in ("SCANNER", "VOLUNTEER") or not profile or profile.status != "ACTIVE":
        raise PermissionDenied("An active scanner account is required.")
    if not profile.gate_id or profile.gate.status != "ACTIVE":
        raise ValidationError("Your scanner must be assigned to an active gate.")
    return profile


def owned_passes(user, kind):
    if kind not in PASS_MODELS:
        raise NotFound("Unknown pass category.")
    query = PASS_MODELS[kind].objects.all()
    if user.role == "ADMIN":
        return query
    if user.role != "AUTHORITY":
        raise PermissionDenied("Only issuers can manage passes.")
    if kind == "HOD":
        return query.filter(hod_id=user.legacy_id)
    if kind == "COMBINED":
        return query.filter(congregation_id=user.legacy_id)
    if kind == "MEMBER":
        return query.filter(authority_id=user.legacy_id)
    return query.none()


def code_for(record):
    return getattr(record, "pass_code", None) or getattr(record, "pass_id", None) or record.devotee_id


def name_for(record):
    return (getattr(record, "recipient_name", None) or getattr(record, "holder_name", None)
            or getattr(record, "guest_name", None) or getattr(record, "name", None)
            or (record.hod.name if isinstance(record, m.HodPass) else "Unassigned"))


def describe(kind, record):
    combined = kind == "COMBINED"
    volunteer = kind == "VOLUNTEER" or (kind == "IMMEDIATE" and record.pass_type == "VOLUNTEER")
    personal = kind == "MEMBER" and (record.admin_id is not None or record.notes == "AUTHORITY_PROFILE_CARD")
    used = getattr(record, "entry_used", 0)
    limit = getattr(record, "entry_limit", 1)
    status = getattr(record, "status", None) or record.member_status
    if kind in ("HOD", "VVIP") or (kind == "IMMEDIATE" and not volunteer):
        used = int(status == "USED")
    authority = record.hod if kind == "HOD" else record.congregation if combined else getattr(record, "authority", None)
    unlimited = combined or personal or ((volunteer or kind == "MEMBER") and limit == 0)
    return {
        "id": record.pk, "kind": kind, "code": code_for(record), "name": name_for(record),
        "pass_type": "CONGREGATION_COMBINED" if combined else "FIVE_MEMBER" if kind == "HOD" else getattr(record, "pass_type", kind),
        "status": status, "authority": authority.name if authority else "Temple Authority",
        "authority_id": authority.pk if authority else None,
        "category": ("BRAHMACHARI" if authority.profile_type == "BRAHMACHARI" else authority.account_type) if authority else "TEMPLE_AUTHORITY",
        "shared_at": getattr(record, "shared_at", None), "created_at": record.created_at,
        "recipient_name": getattr(record, "recipient_name", None),
        "issued_source": getattr(record, "issued_source", None),
        "entries_used": record.single_entry_count if combined else used,
        "entry_limit": None if unlimited else limit,
        "unlimited": unlimited, "people_per_entry": 5 if kind in ("HOD", "VVIP") or (kind == "IMMEDIATE" and not volunteer) else 1,
        "family_available": (record.family_entry_used_at is None) if combined else (record.guest_entry_enabled and not record.guest_entry_used and record.guest_limit > 0) if kind == "MEMBER" else False,
        "family_people": 5 if combined else record.guest_limit if kind == "MEMBER" else 0,
        "family_configured": combined or (kind == "MEMBER" and record.guest_entry_enabled and record.guest_limit > 0),
        "single_available": (personal or (record.single_entry_enabled and (limit == 0 or used < limit))) if kind == "MEMBER" else True,
        "family_used_at": record.family_entry_used_at if combined else None,
        "card_url": f"/api/passes/{kind}/{record.pk}/card/",
        "thumb_url": f"/api/passes/{kind}/{record.pk}/card/?thumb=1",
    }


def lookup(user, value, manual=False):
    require_staff(user)
    value = value.strip()
    if not value or len(value) > 200:
        raise ValidationError("Enter a valid QR token or pass ID.")
    for kind in ("MEMBER", "COMBINED", "HOD", "VVIP", "VOLUNTEER", "IMMEDIATE"):
        model = PASS_MODELS[kind]
        if kind == "MEMBER":
            record = model.objects.filter(devotee_id__iexact=value).first() if manual else model.objects.filter(qr__token=value, qr__status="ACTIVE").first()
        else:
            field = "pass_code" if kind in ("COMBINED", "HOD", "IMMEDIATE") else "pass_id"
            record = model.objects.filter(**{field + "__iexact": value}).first() if manual else model.objects.filter(token=value).first()
        if record:
            if kind == "MEMBER" and (record.approval_status != "APPROVED" or record.member_status != "ACTIVE"):
                raise ValidationError("This member is not approved and active.")
            return describe(kind, record)
    raise NotFound("Pass not found. Check the QR code or pass ID.")


def log_entry(user, kind, record, mode, people, method, result="ALLOWED", reason=""):
    profile = profile_for(user)
    labels = {"HOD": "CONGREGATION PASS" if kind == "HOD" and record.hod.account_type == "CONGREGATION" else "HOD PASS",
              "COMBINED": "CONGREGATION COMBINED PASS", "VVIP": "VVIP PASS", "VOLUNTEER": "VOLUNTEER PASS",
              "IMMEDIATE": "IMMEDIATE " + getattr(record, "pass_type", "") + " PASS", "MEMBER": "COMMUNITY MEMBER"}
    return m.EntryLog.objects.create(member=record if kind == "MEMBER" else None, devotee_id=code_for(record),
        subject_type=labels[kind], subject_name=name_for(record), reference_code=code_for(record), entry_type=mode,
        guest_count=people if kind == "MEMBER" and mode == "FAMILY" else max(people - 1, 0),
        guest_limit_snapshot=record.guest_limit if kind == "MEMBER" else 0,
        scan_method=method, result=result, reason=reason,
        scanner_id=user.legacy_id if user.role == "SCANNER" else None,
        volunteer_id=user.legacy_id if user.role == "VOLUNTEER" else None, gate_id=profile.gate_id)


def confirm_entry(user, kind, identifier, mode, method, key):
    require_staff(user)
    try:
        uuid.UUID(str(key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid scan request ID is required.")
    if kind not in PASS_MODELS or mode not in ("SINGLE", "FAMILY") or method not in ("QR", "MANUAL_ID"):
        raise ValidationError("Invalid scan request.")
    record = None
    try:
        with transaction.atomic():
            # Serialize repeated requests from the same scanner before checking the receipt.
            m.User.objects.select_for_update().get(pk=user.pk)
            receipt = m.ScanReceipt.objects.filter(user=user, key=key).first()
            if receipt:
                original = receipt.response
                if original["pass"]["kind"] != kind or str(original["pass"]["id"]) != str(identifier) or original["mode"] != mode:
                    raise ValidationError("This scan request ID was already used for a different confirmation.")
                return receipt.response
            record = PASS_MODELS[kind].objects.select_for_update().filter(pk=identifier).first()
            if record is None:
                raise NotFound("Pass not found.")
            now = timezone.now()
            people = 1
            if kind == "MEMBER":
                if record.member_status != "ACTIVE" or record.approval_status != "APPROVED":
                    raise ValidationError("Member is not eligible for entry.")
                if not m.QrToken.objects.filter(member=record, status="ACTIVE").exists():
                    raise ValidationError("This Community Card is revoked.")
                personal = record.admin_id is not None or record.notes == "AUTHORITY_PROFILE_CARD"
                if mode == "FAMILY":
                    if user.role != "VOLUNTEER":
                        raise PermissionDenied("Community Card family entry requires a volunteer account.")
                    if not record.guest_entry_enabled or record.guest_limit < 1 or record.guest_entry_used:
                        raise ValidationError("Family entry is unavailable or already used.")
                    record.guest_entry_used = True
                    record.guest_entry_used_at = now
                    record.guest_count_used = record.guest_limit
                    people = record.guest_limit
                else:
                    if not personal and (not record.single_entry_enabled or (record.entry_limit > 0 and record.entry_used >= record.entry_limit)):
                        raise ValidationError("The single-entry limit has been reached.")
                    record.entry_used += 1
            elif kind == "COMBINED":
                if record.status != "ACTIVE":
                    raise ValidationError("This combined pass is disabled.")
                if mode == "FAMILY":
                    if record.family_entry_used_at is not None:
                        raise ValidationError("The five-member family entry has already been used. Single entry remains available.")
                    record.family_entry_used_at = now
                    people = 5
                else:
                    record.single_entry_count += 1
            else:
                if mode != "SINGLE":
                    raise ValidationError("This pass has no separate family-entry option.")
                volunteer = kind == "VOLUNTEER" or (kind == "IMMEDIATE" and record.pass_type == "VOLUNTEER")
                if volunteer:
                    unlimited = record.entry_limit == 0
                    if record.status == "DISABLED" or (not unlimited and (record.status != "ACTIVE" or record.entry_used >= record.entry_limit)):
                        raise ValidationError("All permitted entries have been used or the pass is disabled.")
                    record.entry_used += 1
                    record.status = "ACTIVE" if unlimited or record.entry_used < record.entry_limit else "USED"
                else:
                    if record.status != "ACTIVE":
                        raise ValidationError("This pass has already been used or is disabled.")
                    record.status, record.used_at, people = "USED", now, 5
            record.save()
            entry = log_entry(user, kind, record, mode, people, method)
            audit(user, "ALLOW_ENTRY", record, f"{mode}, {people} people, {method}")
            response = {"allowed": True, "entry_id": entry.pk, "people": people, "mode": mode,
                        "pass": describe(kind, record)}
            # Store JSON-safe dates for stable repeat responses.
            import json
            from django.core.serializers.json import DjangoJSONEncoder
            response = json.loads(json.dumps(response, cls=DjangoJSONEncoder))
            m.ScanReceipt.objects.create(user=user, key=key, response=response)
            return response
    except ValidationError as exc:
        if record is not None:
            log_entry(user, kind, record, mode, 0, method, "DENIED", str(exc.detail)[:250])
        raise


@transaction.atomic
def allocate(user, authority_id, count, recipient="", source="CONGREGATION"):
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 500:
        raise ValidationError("Generate between 1 and 500 passes at a time.")
    authority = m.Authority.objects.select_for_update().filter(pk=authority_id, status="ACTIVE").first()
    if not authority:
        raise ValidationError("Select an active authority.")
    if user.role != "ADMIN":
        raise PermissionDenied("You cannot allocate passes for this account.")
    if authority.account_type == "HOD" and not authority.can_add_members:
        raise ValidationError("Enable member and pass access before allocating passes.")
    combined = authority.account_type == "CONGREGATION"
    model = m.CombinedPass if combined else m.HodPass
    records = model.objects.filter(**{"congregation_id" if combined else "hod_id": authority.pk})
    numbers = [int(code.rsplit("-", 1)[-1]) for code in records.values_list("pass_code", flat=True) if code.rsplit("-", 1)[-1].isdigit()]
    start = max(numbers, default=0) + 1
    for offset in range(count):
        code = f"{'CG' if combined else 'H5'}-{authority.pk}-{start + offset:04d}"
        fields = {"pass_code": code, "recipient_name": recipient}
        if combined:
            fields.update(congregation=authority, issued_source=source, created_by_admin_id=user.legacy_id if user.role == "ADMIN" else None)
        else:
            fields.update(hod=authority)
        model.objects.create(**fields)
    if not combined:
        authority.five_member_passes = records.count()
        authority.save(update_fields=["five_member_passes"])
    audit(user, "ALLOCATE_PASSES", authority, f"{count} additional passes")
    return count
