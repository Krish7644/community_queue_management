import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def new_token():
    return secrets.token_hex(32)


STATUS = [(x, x.title()) for x in ("ACTIVE", "INACTIVE")]
PASS_STATUS = [(x, x.title()) for x in ("ACTIVE", "USED", "DISABLED")]


class Created(models.Model):
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True


class Profile(Created):
    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    username = models.CharField(max_length=80, unique=True)
    # Legacy compatibility column; portal credentials are managed on User.
    password = models.CharField(max_length=255, default="!managed-by-django", editable=False)
    status = models.CharField(max_length=8, choices=STATUS, default="ACTIVE")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LegacyAdmin(Profile):
    class Meta:
        db_table = "admins"


class Gate(Created):
    gate_code = models.CharField(max_length=30, unique=True)
    gate_name = models.CharField(max_length=100)
    status = models.CharField(max_length=8, choices=STATUS, default="ACTIVE")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gates"


class Authority(Profile):
    authority_id = models.CharField(max_length=30, unique=True)
    photo_path = models.CharField(max_length=255, blank=True, null=True)
    can_add_members = models.BooleanField(default=False)
    five_member_passes = models.PositiveIntegerField(default=0)
    account_type = models.CharField(max_length=12, choices=[("HOD", "HOD"), ("CONGREGATION", "Congregation")], default="HOD")
    profile_type = models.CharField(max_length=12, choices=[("CONGREGATION", "Congregation"), ("BRAHMACHARI", "Brahmachari")], blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "authorities"


class Volunteer(Profile):
    volunteer_id = models.CharField(max_length=30, unique=True)
    gate = models.ForeignKey(Gate, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=10, choices=[("SCANNER", "Scanner"), ("SUPERVISOR", "Supervisor")], default="SCANNER")

    class Meta:
        db_table = "volunteers"


class Scanner(Created):
    name = models.CharField(max_length=120)
    username = models.CharField(max_length=80, unique=True)
    password = models.CharField(max_length=255, default="!managed-by-django", editable=False)
    gate = models.ForeignKey(Gate, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=8, choices=STATUS, default="ACTIVE")

    class Meta:
        db_table = "scanners"


class User(AbstractUser):
    password = models.CharField(max_length=1100)
    role = models.CharField(max_length=12, choices=[(r, r.title()) for r in ("ADMIN", "AUTHORITY", "VOLUNTEER", "SCANNER")])
    legacy_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_table = models.CharField(max_length=30, blank=True)
    login_id = models.CharField(max_length=80, db_index=True)
    display_name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source_table", "legacy_id"], name="unique_legacy_account")]


class Member(Created):
    devotee_id = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    photo_path = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    authority = models.ForeignKey(Authority, on_delete=models.SET_NULL, null=True, blank=True, related_name="members")
    admin = models.OneToOneField(LegacyAdmin, on_delete=models.SET_NULL, null=True, blank=True)
    created_by_authority = models.ForeignKey(Authority, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_members")
    member_category = models.CharField(max_length=12, choices=[("CONGREGATION", "Congregation"), ("VVIP", "VVIP")], default="CONGREGATION")
    guest_limit = models.PositiveSmallIntegerField(default=0)
    guest_entry_enabled = models.BooleanField(default=True)
    guest_entry_used = models.BooleanField(default=False)
    guest_entry_used_at = models.DateTimeField(null=True, blank=True)
    guest_count_used = models.PositiveSmallIntegerField(default=0)
    single_entry_enabled = models.BooleanField(default=True)
    entry_mode = models.CharField(max_length=6, default="SINGLE", choices=[("SINGLE", "Single"), ("FAMILY", "Family")])
    entry_limit = models.PositiveIntegerField(default=1)
    entry_used = models.PositiveIntegerField(default=0)
    approval_status = models.CharField(max_length=20, default="PENDING", choices=[(x, x.replace("_", " ").title()) for x in ("PENDING", "APPROVED", "REJECTED", "CORRECTION_REQUESTED")])
    member_status = models.CharField(max_length=8, choices=STATUS, default="ACTIVE")
    notes = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "community_members"


class QrToken(Created):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name="qr")
    token = models.CharField(max_length=64, unique=True, default=new_token)
    status = models.CharField(max_length=7, choices=[("ACTIVE", "Active"), ("REVOKED", "Revoked")], default="ACTIVE")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "qr_tokens"


class PassBase(Created):
    token = models.CharField(max_length=64, unique=True, default=new_token)
    shared_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=PASS_STATUS, default="ACTIVE")

    class Meta:
        abstract = True


class HodPass(PassBase):
    hod = models.ForeignKey(Authority, on_delete=models.CASCADE)
    pass_type = models.CharField(max_length=12, default="FIVE_MEMBER", choices=[("FIVE_MEMBER", "Five member")])
    pass_code = models.CharField(max_length=40, unique=True)
    recipient_name = models.CharField(max_length=120, null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hod_passes"


class CombinedPass(PassBase):
    congregation = models.ForeignKey(Authority, on_delete=models.CASCADE)
    pass_code = models.CharField(max_length=40, unique=True)
    recipient_name = models.CharField(max_length=120, blank=True)
    issued_source = models.CharField(max_length=12, default="CONGREGATION", choices=[("CONGREGATION", "Congregation"), ("IMMEDIATE", "Immediate")])
    created_by_admin = models.ForeignKey(LegacyAdmin, on_delete=models.SET_NULL, null=True, blank=True)
    single_entry_count = models.PositiveIntegerField(default=0)
    family_entry_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "congregation_combined_passes"


class VvipBatch(Created):
    batch_name = models.CharField(max_length=120)
    created_by = models.ForeignKey(LegacyAdmin, db_column="created_by", on_delete=models.PROTECT)

    class Meta:
        db_table = "vvip_batches"


class VvipPass(PassBase):
    batch = models.ForeignKey(VvipBatch, on_delete=models.CASCADE)
    pass_id = models.CharField(max_length=40, unique=True)
    guest_name = models.CharField(max_length=160)
    recipient_name = models.CharField(max_length=120, null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "vvip_passes"


class VolunteerBatch(Created):
    batch_name = models.CharField(max_length=120)
    entry_limit = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(LegacyAdmin, db_column="created_by", on_delete=models.PROTECT)

    class Meta:
        db_table = "volunteer_pass_batches"


class VolunteerPass(PassBase):
    batch = models.ForeignKey(VolunteerBatch, on_delete=models.CASCADE)
    pass_id = models.CharField(max_length=40, unique=True)
    guest_name = models.CharField(max_length=160)
    entry_limit = models.PositiveIntegerField(default=1)
    entry_used = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "volunteer_passes"


class ImmediatePass(PassBase):
    pass_type = models.CharField(max_length=12, choices=[("FIVE_MEMBER", "Five member"), ("VVIP", "VVIP"), ("VOLUNTEER", "Volunteer")])
    pass_code = models.CharField(max_length=40, unique=True)
    holder_name = models.CharField(max_length=160)
    recipient_name = models.CharField(max_length=120, blank=True, null=True)
    authority = models.ForeignKey(Authority, on_delete=models.SET_NULL, blank=True, null=True)
    custom_authority_name = models.CharField(max_length=120, blank=True, null=True)
    entry_limit = models.PositiveIntegerField(default=1)
    entry_used = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(LegacyAdmin, db_column="created_by", on_delete=models.SET_NULL, blank=True, null=True)
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "immediate_passes"


class EntryLog(Created):
    member = models.ForeignKey(Member, on_delete=models.SET_NULL, blank=True, null=True)
    devotee_id = models.CharField(max_length=40, blank=True, null=True)
    entry_type = models.CharField(max_length=6, default="SINGLE")
    guest_count = models.PositiveSmallIntegerField(default=0)
    guest_limit_snapshot = models.PositiveSmallIntegerField(default=0)
    guest_forfeited_count = models.PositiveSmallIntegerField(default=0)
    volunteer = models.ForeignKey(Volunteer, on_delete=models.SET_NULL, blank=True, null=True)
    scanner = models.ForeignKey(Scanner, on_delete=models.SET_NULL, blank=True, null=True)
    gate = models.ForeignKey(Gate, on_delete=models.SET_NULL, blank=True, null=True)
    scan_method = models.CharField(max_length=10, default="QR")
    result = models.CharField(max_length=7, default="ALLOWED")
    reason = models.CharField(max_length=255, blank=True, null=True)
    subject_type = models.CharField(max_length=40, blank=True, null=True)
    subject_name = models.CharField(max_length=160, blank=True, null=True)
    reference_code = models.CharField(max_length=40, blank=True, null=True, db_index=True)
    entry_time = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "entry_logs"


class ApprovalHistory(Created):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    authority = models.ForeignKey(Authority, on_delete=models.CASCADE)
    action = models.CharField(max_length=20)
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "approval_history"


class ProfileEditRequest(Created):
    user_type = models.CharField(max_length=10)
    user_id = models.PositiveIntegerField()
    requested_name = models.CharField(max_length=120)
    requested_mobile = models.CharField(max_length=20, blank=True, null=True)
    requested_username = models.CharField(max_length=80)
    reason = models.TextField(blank=True, null=True)
    request_status = models.CharField(max_length=8, default="PENDING")
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        db_table = "profile_edit_requests"


class AuditLog(Created):
    admin = models.ForeignKey(LegacyAdmin, on_delete=models.SET_NULL, blank=True, null=True)
    authority = models.ForeignKey(Authority, on_delete=models.SET_NULL, blank=True, null=True)
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=80)
    entity_id = models.IntegerField()
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "audit_logs"


class ScanReceipt(Created):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=64)
    response = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="unique_scan_request")]


class EventSettings(models.Model):
    name = models.CharField(max_length=160, default="SRI KRISHNA JANMASHTAMI FESTIVAL")
    date_label = models.CharField(max_length=80, default="4th Sep 2026")
    timings = models.CharField(max_length=100, default="10:00 AM to 3:00 PM")
    entry_gate = models.CharField(max_length=100, default="PUSHKARINI GATE NO.2")
    vvip_entry_gate = models.CharField(max_length=100, default="BVMS SCHOOL")
    share_message = models.TextField(default="Hare Krishna! ISKCON Tirupati welcomes you. Keep your pass safe and enter through the gate printed on your pass.")
