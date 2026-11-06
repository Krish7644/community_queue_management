import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import MagicMock, patch

from PIL import Image
from PIL import ImageChops
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import models as m
from .services import confirm_entry, lookup
from .passwords import readable_password


class Fixtures:
    def seed(self):
        self.admin_profile = m.LegacyAdmin.objects.create(name="Test Temple Authority", username="temple")
        self.admin = self.account("ADMIN", self.admin_profile, "temple")
        self.gate = m.Gate.objects.create(gate_name="Test Gate", gate_code="TEST-01")
        self.scanner_profile = m.Scanner.objects.create(name="Test Scanner", username="scanner", gate=self.gate)
        self.scanner = self.account("SCANNER", self.scanner_profile, "scanner")
        self.authority = m.Authority.objects.create(authority_id="AUTH-TEST", name="Test HOD", username="hod", can_add_members=True)
        self.authority_user = self.account("AUTHORITY", self.authority, "hod")

    def account(self, role, profile, login):
        user = m.User(username=role.lower() + "." + str(profile.pk), login_id=login, display_name=profile.name,
                      role=role, source_table=profile._meta.db_table, legacy_id=profile.pk)
        user.set_password("TestPassword123!")
        user.save()
        return user

    def confirm(self, kind, record, mode="SINGLE", key=None, user=None):
        return confirm_entry(user or self.scanner, kind, record.pk, mode, "MANUAL_ID", key or str(uuid.uuid4()))


class AdmissionTests(Fixtures, TestCase):
    def setUp(self):
        self.seed()

    def volunteer_pass(self, limit):
        batch = m.VolunteerBatch.objects.create(batch_name="Test batch", entry_limit=limit, created_by=self.admin_profile)
        return m.VolunteerPass.objects.create(batch=batch, pass_id="VOL-TEST", guest_name="Volunteer", entry_limit=limit)

    def test_limited_volunteer_gets_exactly_three_entries(self):
        record = self.volunteer_pass(3)
        for expected in (1, 2, 3):
            self.assertTrue(self.confirm("VOLUNTEER", record)["allowed"])
            record.refresh_from_db()
            self.assertEqual(record.entry_used, expected)
            self.assertEqual(record.status, "USED" if expected == 3 else "ACTIVE")
        with self.assertRaises(ValidationError):
            self.confirm("VOLUNTEER", record)
        self.assertEqual(m.EntryLog.objects.filter(result="ALLOWED").count(), 3)
        self.assertEqual(m.EntryLog.objects.filter(result="DENIED").count(), 1)

    def test_unlimited_pass_keeps_counting_without_becoming_used(self):
        record = self.volunteer_pass(0)
        for _ in range(4):
            self.confirm("VOLUNTEER", record)
        record.refresh_from_db()
        self.assertEqual((record.entry_used, record.status), (4, "ACTIVE"))

    def test_combined_family_once_and_single_entries_remain_available(self):
        congregation = m.Authority.objects.create(authority_id="CG-TEST", name="Congregation", username="cg", account_type="CONGREGATION")
        record = m.CombinedPass.objects.create(congregation=congregation, pass_code="CG-1-0001", recipient_name="Family")
        self.assertEqual(self.confirm("COMBINED", record, "FAMILY")["people"], 5)
        with self.assertRaises(ValidationError):
            self.confirm("COMBINED", record, "FAMILY")
        for _ in range(3):
            self.assertEqual(self.confirm("COMBINED", record)["people"], 1)
        record.refresh_from_db()
        self.assertEqual(record.single_entry_count, 3)

    def test_retry_of_same_request_does_not_consume_another_entry(self):
        record = self.volunteer_pass(3)
        key = str(uuid.uuid4())
        first, second = self.confirm("VOLUNTEER", record, key=key), self.confirm("VOLUNTEER", record, key=key)
        self.assertEqual(first, second)
        record.refresh_from_db()
        self.assertEqual(record.entry_used, 1)
        self.assertEqual(m.EntryLog.objects.filter(result="ALLOWED").count(), 1)

    def test_request_id_cannot_be_reused_for_a_different_pass(self):
        first = self.volunteer_pass(3)
        other = m.VolunteerPass.objects.create(batch=first.batch, pass_id="VOL-OTHER", guest_name="Other", entry_limit=3)
        key = str(uuid.uuid4())
        self.confirm("VOLUNTEER", first, key=key)
        with self.assertRaises(ValidationError):
            self.confirm("VOLUNTEER", other, key=key)
        other.refresh_from_db()
        self.assertEqual(other.entry_used, 0)

    def test_member_limit_cannot_be_overridden_by_client_type(self):
        record = m.Member.objects.create(name="Limited member", devotee_id="00001", approval_status="APPROVED", entry_limit=1)
        m.QrToken.objects.create(member=record)
        self.confirm("MEMBER", record)
        with self.assertRaises(ValidationError):
            self.confirm("MEMBER", record)
        with self.assertRaises(ValidationError):
            self.confirm("UNLIMITED_MEMBER", record)
        record.refresh_from_db()
        self.assertEqual(record.entry_used, 1)

    def test_revoked_member_token_cannot_be_used(self):
        record = m.Member.objects.create(name="Revoked member", devotee_id="00002", approval_status="APPROVED", entry_limit=0)
        token = m.QrToken.objects.create(member=record, status="REVOKED")
        with self.assertRaises(ValidationError):
            self.confirm("MEMBER", record)

    def test_inactive_gate_blocks_admission(self):
        record = self.volunteer_pass(0)
        self.gate.status = "INACTIVE"
        self.gate.save()
        with self.assertRaises(ValidationError):
            self.confirm("VOLUNTEER", record)

    def test_immediate_volunteer_limit_is_exact(self):
        record = m.ImmediatePass.objects.create(pass_type="VOLUNTEER", pass_code="IVOL-000001", holder_name="Volunteer", entry_limit=2)
        self.confirm("IMMEDIATE", record)
        self.confirm("IMMEDIATE", record)
        with self.assertRaises(ValidationError):
            self.confirm("IMMEDIATE", record)

    def test_member_family_requires_volunteer_and_uses_configured_total(self):
        record = m.Member.objects.create(name="Family member", devotee_id="FAMILY-01", approval_status="APPROVED",
                                         guest_entry_enabled=True, guest_limit=4, entry_limit=2)
        m.QrToken.objects.create(member=record)
        with self.assertRaises(PermissionDenied):
            self.confirm("MEMBER", record, "FAMILY")
        record.refresh_from_db()
        self.assertFalse(record.guest_entry_used)
        profile = m.Volunteer.objects.create(volunteer_id="VOL-TEST", name="Test Volunteer", username="volunteer", gate=self.gate)
        user = self.account("VOLUNTEER", profile, "volunteer")
        result = self.confirm("MEMBER", record, "FAMILY", user=user)
        self.assertEqual(result["people"], 4)
        self.assertEqual(m.EntryLog.objects.get(pk=result["entry_id"]).guest_count, 4)
        with self.assertRaises(ValidationError):
            self.confirm("MEMBER", record, "FAMILY", user=user)
        self.assertTrue(self.confirm("MEMBER", record, user=user)["allowed"])


class ApiTests(Fixtures, TestCase):
    def setUp(self):
        self.seed()
        self.client = APIClient()
        self.client.force_login(self.admin)

    def test_readable_password_is_available_only_through_explicit_admin_view(self):
        self.assertEqual(readable_password(self.admin), "TestPassword123!")
        response = self.client.get("/api/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("password", response.data)
        self.assertNotIn("new_password", response.data)
        response = self.client.get("/api/profile/credentials/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["password"], "TestPassword123!")
        self.assertIn("no-store", response["Cache-Control"])

    def test_login_requires_csrf_and_accepts_existing_login_id(self):
        client = Client(enforce_csrf_checks=True)
        payload = {"username": "temple", "password": "TestPassword123!"}
        self.assertEqual(client.post("/api/auth/login/", data=json.dumps(payload), content_type="application/json").status_code, 403)
        client.get("/api/auth/session/")
        token = client.cookies["csrftoken"].value
        response = client.post("/api/auth/login/", data=json.dumps(payload), content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "ADMIN")

    def test_cross_role_numeric_id_collision_does_not_grant_card_access(self):
        record = m.HodPass.objects.create(hod=self.authority, pass_code="H5-1-0001")
        self.client.force_login(self.scanner)
        self.assertEqual(self.client.get(f"/api/passes/HOD/{record.pk}/card/").status_code, 403)

    def test_authority_cannot_edit_someone_elses_pass(self):
        other = m.Authority.objects.create(authority_id="AUTH-OTHER", name="Other", username="other")
        record = m.HodPass.objects.create(hod=other, pass_code="H5-2-0001")
        self.client.force_login(self.authority_user)
        self.assertEqual(self.client.patch(f"/api/passes/HOD/{record.pk}/", {"name": "Changed"}, format="json").status_code, 404)

    def test_create_authority_and_initial_allocation_are_atomic(self):
        response = self.client.post("/api/authorities/", {"name": "New HOD", "username": "new-hod", "new_password": "NewPassword123!", "account_type": "HOD", "status": "ACTIVE", "can_add_members": True, "initial_passes": 3}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        profile = m.Authority.objects.get(pk=response.data["id"])
        self.assertEqual(m.HodPass.objects.filter(hod=profile).count(), 3)
        self.assertEqual(response.data["assigned_passes"], 3)
        self.assertEqual(response.data["available_passes"], 3)
        self.assertTrue(m.User.objects.get(source_table="authorities", legacy_id=profile.pk).check_password("NewPassword123!"))

    def test_csv_creates_deduplicated_passes(self):
        file = SimpleUploadedFile("names.csv", b"name\nGuest One\nGuest Two\nGuest One\n", content_type="text/csv")
        response = self.client.post("/api/batches/", {"file": file, "kind": "VOLUNTEER", "batch_name": "Test", "entry_limit": 0}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(m.VolunteerPass.objects.filter(entry_limit=0).count(), 2)

    def test_member_creation_generates_id_and_saves_private_photo(self):
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(buffer, "PNG")
        photo = SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")
        response = self.client.post("/api/members/", {"name": "New Member", "authority": self.authority.pk, "photo": photo, "entry_limit": 2}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["devotee_id"], "00001")
        self.assertEqual(response.data["approval_status"], "PENDING")

    def test_share_and_reports_do_not_leak_qr_tokens(self):
        record = m.HodPass.objects.create(hod=self.authority, pass_code="H5-1-0002")
        response = self.client.get("/api/passes/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("token", response.data["results"][0])
        response = self.client.post("/api/passes/share-bulk/", {"passes": [{"kind": "HOD", "id": record.pk}]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        record.refresh_from_db()
        self.assertIsNotNone(record.shared_at)

    def test_administrator_can_generate_png(self):
        record = m.HodPass.objects.create(hod=self.authority, pass_code="H5-1-0003")
        response = self.client.get(f"/api/passes/HOD/{record.pk}/card/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"\x89PNG"))
        rendered = Image.open(io.BytesIO(content)).convert("RGB")
        self.assertEqual(rendered.size, (1087, 1447))
        from .cards import _template
        artwork = _template("hod-pass-template.png")
        protected = (20, 20, 800, 300)
        self.assertIsNone(ImageChops.difference(rendered.crop(protected), artwork.crop(protected)).getbbox())

    def test_excel_export_and_zero_counts(self):
        record = m.HodPass.objects.create(hod=self.authority, pass_code="H5-1-0004", recipient_name="=UnsafeFormula")
        response = self.client.get("/api/passes/export/?filetype=xlsx")
        self.assertEqual(response.status_code, 200)
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(response.content))
        values = list(workbook.active.values)
        self.assertEqual(values[1][0], record.pass_code)
        self.assertEqual(values[1][1], "'=UnsafeFormula")
        self.assertEqual(values[1][7], 0)

    def test_personal_card_creation_is_owned_and_unlimited(self):
        response = self.client.post("/api/profile/card/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        member = m.Member.objects.get(pk=response.data["member_id"])
        self.assertEqual(member.admin_id, self.admin_profile.pk)
        self.assertEqual(member.entry_limit, 0)

    def test_authority_cannot_change_pass_status(self):
        record = m.HodPass.objects.create(hod=self.authority, pass_code="H5-1-0005")
        self.client.force_login(self.authority_user)
        response = self.client.patch(f"/api/passes/HOD/{record.pk}/", {"status": "DISABLED"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_hod_has_readonly_profile_and_no_extra_workspaces(self):
        self.client.force_login(self.authority_user)
        self.assertEqual(self.client.get("/api/profile/").status_code, 200)
        for endpoint in ("dashboard/", "entries/", "audit/"):
            self.assertEqual(self.client.get("/api/" + endpoint).status_code, 403, endpoint)
        self.assertEqual(self.client.patch("/api/profile/", {"name": "Changed"}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/passes/", {"kind": "COMBINED", "count": 1}, format="json").status_code, 403)
        self.authority.refresh_from_db()
        self.assertEqual(self.authority.name, "Test HOD")

    def test_scanner_has_entry_workspace_only(self):
        self.client.force_login(self.scanner)
        for endpoint in ("profile/", "dashboard/", "entries/", "audit/", "passes/"):
            self.assertEqual(self.client.get("/api/" + endpoint).status_code, 403, endpoint)
        self.assertEqual(self.client.get("/api/options/").status_code, 200)

    def test_congregation_home_excludes_immediate_but_shared_includes_both(self):
        from django.utils import timezone
        congregation = m.Authority.objects.create(authority_id="CG-TEST", name="Congregation", username="cg", account_type="CONGREGATION")
        user = self.account("AUTHORITY", congregation, "cg")
        for source in ("CONGREGATION", "IMMEDIATE"):
            for shared in (False, True):
                m.CombinedPass.objects.create(congregation=congregation, pass_code=f"CG-{source}-{shared}",
                    issued_source=source, shared_at=timezone.now() if shared else None)
        self.client.force_login(user)
        unshared = self.client.get("/api/passes/?kind=COMBINED&shared=no").data
        self.assertEqual(unshared["count"], 1)
        self.assertEqual(unshared["results"][0]["issued_source"], "CONGREGATION")
        self.assertEqual(self.client.get("/api/passes/?kind=COMBINED&shared=yes").data["count"], 2)
        self.client.force_login(self.admin)
        immediate = self.client.get("/api/passes/?workspace=immediate").data
        self.assertEqual(immediate["count"], 2)
        self.assertTrue(all(row["issued_source"] == "IMMEDIATE" for row in immediate["results"]))

    def test_report_five_member_filter_and_last_entry(self):
        record = m.HodPass.objects.create(hod=self.authority, pass_code="H5-REPORT")
        m.ImmediatePass.objects.create(pass_code="IV5-REPORT", pass_type="VVIP", holder_name="Guest")
        self.confirm("HOD", record)
        response = self.client.get(f"/api/passes/?pass_type=FIVE_MEMBER&scanner_id={self.scanner_profile.pk}&gate_id={self.gate.pk}")
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["code"], record.pass_code)
        self.assertIsNotNone(row["last_entry"])

    def test_recipient_name_is_raw_and_sharing_preserves_first_timestamp(self):
        record = m.HodPass.objects.create(hod=self.authority, pass_code="H5-SHARE")
        self.client.force_login(self.authority_user)
        endpoint = f"/api/passes/HOD/{record.pk}/"
        self.assertIsNone(self.client.get("/api/passes/?kind=HOD").data["results"][0]["recipient_name"])
        self.assertEqual(self.client.patch(endpoint, {"name": "Family Name"}, format="json").data["recipient_name"], "Family Name")
        first = self.client.post(endpoint, {}, format="json")
        second = self.client.post(endpoint, {}, format="json")
        self.assertEqual(first.data["shared_at"], second.data["shared_at"])

    def test_gallery_pagination_and_additional_allocation(self):
        response = self.client.patch(f"/api/authorities/{self.authority.pk}/", {"additional_passes": 25}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(m.HodPass.objects.filter(hod=self.authority).count(), 25)
        self.assertEqual(response.data["assigned_passes"], 25)
        self.assertEqual(response.data["available_passes"], 25)
        self.client.force_login(self.authority_user)
        response = self.client.get("/api/passes/?kind=HOD&shared=no&page_size=24")
        self.assertEqual((response.data["count"], len(response.data["results"])), (25, 24))
        self.assertIsNotNone(response.data["next"])

    def test_event_configuration_is_readonly(self):
        self.assertEqual(self.client.patch("/api/event/", {"date_label": "Changed"}, format="json").status_code, 405)

    def test_hod_directory_counts_actual_assigned_and_available_passes(self):
        from django.utils import timezone
        self.authority.five_member_passes = 999
        self.authority.save(update_fields=["five_member_passes"])
        for number, (status, shared_at) in enumerate([
            ("ACTIVE", None), ("ACTIVE", timezone.now()), ("USED", None), ("DISABLED", None)
        ]):
            m.HodPass.objects.create(hod=self.authority, pass_code=f"H5-DIRECTORY-{number}", status=status, shared_at=shared_at)
        other = m.Authority.objects.create(authority_id="OTHER", name="Other", username="other")
        m.HodPass.objects.create(hod=other, pass_code="H5-OTHER")
        response = self.client.get(f"/api/authorities/{self.authority.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data["assigned_passes"], response.data["available_passes"]), (4, 1))
        self.assertEqual(response.data["authority_id"], self.authority.authority_id)
        self.assertTrue(response.data["can_add_members"])
        self.assertNotIn("password", response.data)

    def test_congregation_directory_counts_active_passes_across_issue_sources(self):
        from django.utils import timezone
        congregation = m.Authority.objects.create(authority_id="CG-DIRECTORY", name="Congregation", username="cg", account_type="CONGREGATION")
        for number, (source, status, shared_at) in enumerate([
            ("CONGREGATION", "ACTIVE", None), ("CONGREGATION", "ACTIVE", timezone.now()),
            ("IMMEDIATE", "ACTIVE", None), ("CONGREGATION", "DISABLED", None)
        ]):
            m.CombinedPass.objects.create(congregation=congregation, pass_code=f"CG-DIRECTORY-{number}",
                                          issued_source=source, status=status, shared_at=shared_at)
        # Legacy HOD allocations can coexist with combined passes; joins must not multiply counts.
        for number in range(2):
            m.HodPass.objects.create(hod=congregation, pass_code=f"H5-LEGACY-{number}")
        endpoint = f"/api/authorities/{congregation.pk}/"
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["combined_passes"], 3)
        self.assertEqual(response.data["assigned_passes"], 2)
        response = self.client.patch(endpoint, {"combined_passes": 999, "assigned_passes": 999}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["combined_passes"], 3)
        self.assertEqual(response.data["assigned_passes"], 2)

    def test_directory_counts_include_profiles_without_passes(self):
        response = self.client.get("/api/authorities/?account_type=HOD")
        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.data["results"] if row["id"] == self.authority.pk)
        self.assertEqual((row["assigned_passes"], row["available_passes"], row["combined_passes"]), (0, 0, 0))

    def test_administrator_shared_gallery_matches_original_sources_and_order(self):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        m.HodPass.objects.create(hod=self.authority, pass_code="H5-HIDDEN", shared_at=now)
        congregation = m.Authority.objects.create(authority_id="CG-SHARED", name="Congregation", username="cg", account_type="CONGREGATION")
        m.CombinedPass.objects.create(congregation=congregation, pass_code="CG-HIDDEN", shared_at=now)
        m.ImmediatePass.objects.create(pass_code="IP5-EARLIER", holder_name="Earlier", pass_type="FIVE_MEMBER", shared_at=now-timedelta(hours=1))
        m.ImmediatePass.objects.create(pass_code="IP5-LATEST", holder_name="Latest", pass_type="FIVE_MEMBER", shared_at=now)
        response = self.client.get("/api/passes/?shared=yes&workspace=shared")
        self.assertEqual([row["code"] for row in response.data["results"]], ["IP5-LATEST", "IP5-EARLIER"])


class PasswordManagementTests(Fixtures, TestCase):
    def setUp(self):
        self.seed()
        self.client = APIClient()
        self.client.force_login(self.admin)

    def test_credentials_require_administrator_and_do_not_leak_into_lists_or_logs(self):
        paths = [f"/api/authorities/{self.authority.pk}/credentials/", f"/api/scanners/{self.scanner_profile.pk}/credentials/", "/api/profile/credentials/"]
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response.data["password"], "TestPassword123!")
            self.assertFalse(response.data["needs_reset"])
            self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.get(f"/api/gates/{self.gate.pk}/credentials/").status_code, 404)
        self.assertNotIn("TestPassword123!", self.client.get("/api/authorities/").content.decode())
        self.assertFalse(m.AuditLog.objects.filter(reason__contains="TestPassword123!").exists())
        volunteer_profile = m.Volunteer.objects.create(volunteer_id="VOL-CREDENTIALS", name="Volunteer", username="volunteer", gate=self.gate)
        volunteer = self.account("VOLUNTEER", volunteer_profile, "volunteer")
        for user in (self.authority_user, self.scanner, volunteer):
            self.client.force_login(user)
            for path in paths:
                self.assertEqual(self.client.get(path).status_code, 403, path)
        self.client.logout()
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403, path)

    def test_editing_password_updates_readable_value_and_login(self):
        password = "  Changed$密码$1234  "
        response = self.client.patch(f"/api/authorities/{self.authority.pk}/", {"new_password": password}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.authority_user.refresh_from_db()
        self.assertEqual(readable_password(self.authority_user), password)
        self.assertIsNone(authenticate(username="hod", password="TestPassword123!", role="AUTHORITY"))
        self.assertEqual(authenticate(username="hod", password=password, role="AUTHORITY").pk, self.authority_user.pk)
        response = self.client.get(f"/api/authorities/{self.authority.pk}/credentials/")
        self.assertEqual(response.data["password"], password)

    def test_new_accounts_and_long_passwords_use_readable_storage(self):
        password = "A$" + "x" * 1022
        response = self.client.post("/api/scanners/", {"name": "New Scanner", "username": "new-scanner", "gate": self.gate.pk, "new_password": password}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        user = m.User.objects.get(source_table="scanners", legacy_id=response.data["id"])
        self.assertEqual(readable_password(user), password)
        self.assertTrue(user.check_password(password))
        response = self.client.patch(f"/api/scanners/{user.legacy_id}/", {"new_password": password+"x"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_existing_hash_is_preserved_until_correct_login(self):
        password = "Existing$Password123"
        encoded = PBKDF2PasswordHasher().encode(password, "test-original-salt")
        self.authority_user.password = encoded
        self.authority_user.save(update_fields=["password"])
        response = self.client.get(f"/api/authorities/{self.authority.pk}/credentials/")
        self.assertIsNone(response.data["password"])
        self.assertTrue(response.data["needs_reset"])
        self.assertIsNone(authenticate(username="hod", password="WrongPassword", role="AUTHORITY"))
        self.authority_user.refresh_from_db()
        self.assertEqual(self.authority_user.password, encoded)
        self.assertEqual(authenticate(username="hod", password=password, role="AUTHORITY").pk, self.authority_user.pk)
        self.authority_user.refresh_from_db()
        self.assertEqual(readable_password(self.authority_user), password)

    def test_restore_uses_only_verified_originals_and_dry_run_does_not_write(self):
        from .management.commands.restore_readable_passwords import Command
        originals = ["Original$Admin123", "Original$Hod123", "Outdated$Scanner123"]
        current = [originals[0], originals[1], "Changed$Scanner123"]
        users = [self.admin, self.authority_user, self.scanner]
        encoded = []
        for user, password in zip(users, current):
            user.password = PBKDF2PasswordHasher().encode(password, "test-backup-salt")
            user.save(update_fields=["password"])
            encoded.append(user.password)
        source = MagicMock()
        reader = source.cursor.return_value.__enter__.return_value
        rows = [[{"id": self.admin_profile.pk, "password": originals[0]}],
                [{"id": self.authority.pk, "password": originals[1]}],
                [{"id": self.scanner_profile.pk, "password": originals[2]}], []]
        reader.fetchall.side_effect = rows * 3
        output = io.StringIO()
        with patch.object(Command, "target_database", connection.settings_dict["NAME"]), patch("portal.management.commands.restore_readable_passwords.MySQLdb.connect", return_value=source):
            call_command("restore_readable_passwords", stdout=output)
            for user, value in zip(users, encoded):
                user.refresh_from_db()
                self.assertEqual(user.password, value)
            call_command("restore_readable_passwords", apply=True, stdout=output)
            call_command("restore_readable_passwords", apply=True, stdout=output)
        self.admin.refresh_from_db()
        self.authority_user.refresh_from_db()
        self.scanner.refresh_from_db()
        self.assertEqual(readable_password(self.admin), originals[0])
        self.assertEqual(readable_password(self.authority_user), originals[1])
        self.assertEqual(self.scanner.password, encoded[2])
        self.assertIn("Restored: 2", output.getvalue())
        self.assertIn("already readable: 2", output.getvalue())
        for password in originals+current:
            self.assertNotIn(password, output.getvalue())

    def test_inactive_account_does_not_authenticate_with_readable_password(self):
        self.authority.status = "INACTIVE"
        self.authority.save(update_fields=["status"])
        self.assertIsNone(authenticate(username="hod", password="TestPassword123!", role="AUTHORITY"))

    def test_django_administrator_page_supports_readable_passwords(self):
        self.admin.is_staff = self.admin.is_superuser = True
        self.admin.save(update_fields=["is_staff", "is_superuser"])
        response = self.client.get(f"/admin/portal/user/{self.authority_user.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Readable text")


class ConcurrentAdmissionTests(Fixtures, TransactionTestCase):
    def setUp(self):
        self.seed()

    def test_two_scanners_cannot_consume_the_same_single_use_pass(self):
        other_profile = m.Scanner.objects.create(name="Second Scanner", username="scanner-two", gate=self.gate)
        other = self.account("SCANNER", other_profile, "scanner-two")
        batch = m.VvipBatch.objects.create(batch_name="Concurrent", created_by=self.admin_profile)
        record = m.VvipPass.objects.create(batch=batch, pass_id="V5-CONCURRENT", guest_name="Guest")
        barrier = Barrier(2)

        def attempt(user_id):
            close_old_connections()
            user = m.User.objects.get(pk=user_id)
            barrier.wait(timeout=10)
            try:
                confirm_entry(user, "VVIP", record.pk, "SINGLE", "QR", str(uuid.uuid4()))
                return "ALLOWED"
            except ValidationError:
                return "DENIED"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, [self.scanner.pk, other.pk]))
        self.assertCountEqual(results, ["ALLOWED", "DENIED"])
        self.assertEqual(m.EntryLog.objects.filter(result="ALLOWED").count(), 1)
