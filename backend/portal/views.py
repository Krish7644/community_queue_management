import csv
import io
import uuid
import zipfile
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from . import models as m, serializers as s, services
from .authentication import profile_for
from .cards import render_card, safe_image_path, LAYOUT
from .permissions import ActivePortalUser, Administrator
from .passwords import readable_password


def credentials_response(request, profile):
    account = m.User.objects.filter(source_table=profile._meta.db_table, legacy_id=profile.pk).first()
    if not account:
        raise NotFound("Login account not found.")
    password = readable_password(account)
    services.audit(request.user, "VIEW_ACCOUNT_PASSWORD", profile)
    response = Response({"name": profile.name, "login_id": account.login_id,
                         "password": password, "needs_reset": password is None})
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    return response


class AdminModelViewSet(viewsets.ModelViewSet):
    permission_classes = [Administrator]

    @action(detail=True, methods=["get"])
    def credentials(self, request, pk=None):
        instance = self.get_object()
        if not isinstance(instance, (m.Authority, m.Scanner, m.Volunteer)):
            raise NotFound()
        return credentials_response(request, instance)

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            services.audit(self.request.user, "CREATE", instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            services.audit(self.request.user, "UPDATE", instance)

    def perform_destroy(self, instance):
        # Preserve history and references instead of cascading away issued passes.
        field = "member_status" if isinstance(instance, m.Member) else "status"
        setattr(instance, field, "INACTIVE")
        instance.save(update_fields=[field])
        m.User.objects.filter(source_table=instance._meta.db_table, legacy_id=instance.pk).update(is_active=False)
        services.audit(self.request.user, "DEACTIVATE", instance)


class AuthorityViewSet(AdminModelViewSet):
    serializer_class = s.AuthorityDirectorySerializer

    def get_queryset(self):
        query = m.Authority.objects.annotate(
            assigned_passes=Count("hodpass", filter=Q(hodpass__pass_type="FIVE_MEMBER"), distinct=True),
            available_passes=Count("hodpass", filter=Q(hodpass__pass_type="FIVE_MEMBER", hodpass__status="ACTIVE", hodpass__shared_at__isnull=True), distinct=True),
            combined_passes=Count("combinedpass", filter=Q(combinedpass__status="ACTIVE"), distinct=True),
        ).order_by("-pk")
        if self.request.query_params.get("account_type") in ("HOD", "CONGREGATION"):
            query = query.filter(account_type=self.request.query_params["account_type"])
        return query

    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.validated_data["authority_id"] = serializer.validated_data.get("authority_id") or "AUTH-" + uuid.uuid4().hex[:10].upper()
            super().perform_create(serializer)
            initial = self.request.data.get("initial_passes", 0)
            if initial not in (None, "", 0, "0"):
                services.allocate(self.request.user, serializer.instance.pk, validated_count(initial))
            serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        self.get_object()
        count = validated_count(request.data.get("count"))
        services.allocate(request.user, int(pk), count)
        return Response({"created": count})

    def perform_update(self, serializer):
        with transaction.atomic():
            super().perform_update(serializer)
            additional = self.request.data.get("additional_passes", 0)
            if additional not in (None, "", 0, "0"):
                services.allocate(self.request.user, serializer.instance.pk, validated_count(additional))
            serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

    @action(detail=True, methods=["get"])
    def photo(self, request, pk=None):
        instance = self.get_object()
        if not instance.photo_path:
            raise NotFound()
        response = FileResponse(safe_image_path(instance.photo_path).open("rb"))
        response["Cache-Control"] = "private, no-store"
        return response


class ScannerViewSet(AdminModelViewSet):
    queryset = m.Scanner.objects.select_related("gate").order_by("-pk")
    serializer_class = s.ScannerSerializer


class VolunteerViewSet(AdminModelViewSet):
    queryset = m.Volunteer.objects.select_related("gate").order_by("-pk")
    serializer_class = s.VolunteerSerializer


class GateViewSet(AdminModelViewSet):
    queryset = m.Gate.objects.order_by("-pk")
    serializer_class = s.GateSerializer


def validated_count(value, maximum=500, minimum=1):
    try:
        if isinstance(value, bool) or str(value).strip() != str(int(value)):
            raise ValueError
        value = int(value)
    except (ValueError, TypeError):
        raise ValidationError("Enter a whole number.")
    if not minimum <= value <= maximum:
        raise ValidationError(f"Enter a number between {minimum} and {maximum}.")
    return value


class MemberViewSet(viewsets.ModelViewSet):
    serializer_class = s.MemberSerializer
    permission_classes = [ActivePortalUser]

    def get_queryset(self):
        user = self.request.user
        query = m.Member.objects.select_related("authority").order_by("-pk")
        if user.role == "AUTHORITY":
            query = query.filter(authority_id=user.legacy_id)
        elif user.role != "ADMIN":
            raise PermissionDenied("Only administrators and authorities can manage members.")
        if self.request.query_params.get("search"):
            term = self.request.query_params["search"][:150]
            query = query.filter(Q(name__icontains=term) | Q(devotee_id__icontains=term))
        if self.request.query_params.get("approval_status"):
            query = query.filter(approval_status=self.request.query_params["approval_status"])
        return query

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        if not serializer.validated_data.get("devotee_id"):
            # Lock a stable row to allocate identifiers safely across concurrent creators.
            m.LegacyAdmin.objects.select_for_update().first()
            numbers = [int(value) for value in m.Member.objects.values_list("devotee_id", flat=True) if value.isdigit() and len(value) == 5]
            next_id = max(numbers, default=0) + 1
            if next_id > 99999:
                raise ValidationError("The five-digit ID range is exhausted.")
            serializer.validated_data["devotee_id"] = str(next_id).zfill(5)
        if "photo" not in serializer.validated_data:
            raise ValidationError("Choose a member photo before creating the member.")
        if user.role == "AUTHORITY":
            authority = profile_for(user)
            if not authority.can_add_members:
                raise PermissionDenied("Your account cannot create members.")
            instance = serializer.save(authority=authority, created_by_authority=authority, approval_status="APPROVED")
            m.QrToken.objects.create(member=instance)
        elif user.role == "ADMIN":
            if not serializer.validated_data.get("authority"):
                raise ValidationError("Select the member's authority.")
            instance = serializer.save(approval_status="PENDING")
        else:
            raise PermissionDenied()
        services.audit(user, "CREATE_MEMBER", instance)

    def perform_update(self, serializer):
        instance = self.get_object()
        if self.request.user.role == "AUTHORITY":
            if instance.approval_status != "CORRECTION_REQUESTED":
                raise PermissionDenied("Only members returned for correction can be edited by this account.")
            if "authority" in serializer.validated_data and serializer.validated_data["authority"].pk != self.request.user.legacy_id:
                raise PermissionDenied()
        instance = serializer.save()
        services.audit(self.request.user, "UPDATE_MEMBER", instance)

    def perform_destroy(self, instance):
        if self.request.user.role != "ADMIN":
            raise PermissionDenied()
        instance.member_status = "INACTIVE"
        instance.save(update_fields=["member_status"])
        services.audit(self.request.user, "DEACTIVATE_MEMBER", instance)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def decision(self, request, pk=None):
        if request.user.role != "AUTHORITY":
            raise PermissionDenied("The assigned authority must review the member.")
        member = self.get_queryset().select_for_update().filter(pk=pk).first()
        if member is None:
            raise NotFound("Member not found.")
        decision, remarks = request.data.get("decision"), str(request.data.get("remarks", "")).strip()
        if decision not in ("APPROVED", "REJECTED", "CORRECTION_REQUESTED") or member.approval_status != "PENDING":
            raise ValidationError("Select a valid decision for a pending member.")
        if decision == "CORRECTION_REQUESTED" and not remarks:
            raise ValidationError("Explain the required correction.")
        member.approval_status = decision
        member.save(update_fields=["approval_status"])
        if decision == "APPROVED":
            m.QrToken.objects.update_or_create(member=member, defaults={"status": "ACTIVE"})
        m.ApprovalHistory.objects.create(member=member, authority_id=request.user.legacy_id, action=decision, remarks=remarks)
        services.audit(request.user, "MEMBER_DECISION", member, remarks)
        return Response(s.MemberSerializer(member).data)

    @action(detail=True, methods=["post"])
    def resubmit(self, request, pk=None):
        member = self.get_object()
        if member.approval_status != "CORRECTION_REQUESTED":
            raise ValidationError("This member is not awaiting correction.")
        member.approval_status = "PENDING"
        member.save(update_fields=["approval_status"])
        services.audit(request.user, "RESUBMIT_MEMBER", member)
        return Response({"status": "PENDING"})

    @action(detail=True, methods=["post"])
    def reset_family(self, request, pk=None):
        if request.user.role != "ADMIN" or not str(request.data.get("reason", "")).strip():
            raise ValidationError("An administrator and a reason are required.")
        member = self.get_object()
        member.guest_entry_used, member.guest_entry_used_at, member.guest_count_used = False, None, 0
        member.save(update_fields=["guest_entry_used", "guest_entry_used_at", "guest_count_used"])
        services.audit(request.user, "RESET_FAMILY_ENTRY", member, request.data["reason"])
        return Response({"reset": True})

    @action(detail=True, methods=["get"])
    def photo(self, request, pk=None):
        member = self.get_object()
        if not member.photo_path:
            raise NotFound()
        response = FileResponse(safe_image_path(member.photo_path).open("rb"))
        response["Cache-Control"] = "private, no-store"
        return response


@api_view(["GET"])
@permission_classes([Administrator])
def dashboard(request):
    user = request.user
    if user.role == "ADMIN":
        counts = {"HODs": m.Authority.objects.filter(account_type="HOD").count(), "Congregations": m.Authority.objects.filter(account_type="CONGREGATION").exclude(profile_type="BRAHMACHARI").count(),
                  "VVIP passes": m.VvipPass.objects.count(), "Volunteer passes": m.VolunteerPass.objects.count(),
                  "Immediate passes": m.ImmediatePass.objects.filter(pass_type__in=["FIVE_MEMBER", "VVIP", "VOLUNTEER"]).count(), "Scanners": m.Scanner.objects.count(), "Gates": m.Gate.objects.filter(status="ACTIVE").count(),
                  "Combined passes": m.CombinedPass.objects.count(), "Five-member passes": m.HodPass.objects.filter(pass_type="FIVE_MEMBER").count(),
                  "Pending approvals": m.Member.objects.filter(approval_status="PENDING").count()}
        entries = m.EntryLog.objects.all()
    elif user.role == "AUTHORITY":
        counts = {"Members": m.Member.objects.filter(authority_id=user.legacy_id).count(), "Pending approvals": m.Member.objects.filter(authority_id=user.legacy_id, approval_status="PENDING").count(),
                  "Five-member passes": m.HodPass.objects.filter(hod_id=user.legacy_id).count(), "Combined passes": m.CombinedPass.objects.filter(congregation_id=user.legacy_id).count()}
        entries = scoped_entries(user)
    else:
        counts = {}
        entries = scoped_entries(user)
    today = entries.filter(entry_time__date=timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date())
    counts.update({"Entries today": today.filter(result="ALLOWED").count(), "Denied today": today.filter(result="DENIED").count()})
    profile = profile_for(user)
    return Response({"counts": counts, "recent_entries": s.EntrySerializer(entries.select_related("gate", "scanner", "volunteer").order_by("-pk")[:8], many=True).data,
                     "can_add_members": bool(getattr(profile, "can_add_members", False)), "account_type": getattr(profile, "account_type", None)})


@api_view(["GET", "POST"])
@permission_classes([ActivePortalUser])
def passes(request):
    user = request.user
    if request.method == "POST":
        if user.role != "ADMIN":
            raise PermissionDenied("Pass allocations are managed by Temple Authority.")
        if request.data.get("kind") == "COMBINED":
            authority_id = request.data.get("authority_id") if user.role == "ADMIN" else user.legacy_id
            count = validated_count(request.data.get("count", 1))
            services.allocate(user, authority_id, count, str(request.data.get("name", ""))[:120], "IMMEDIATE" if user.role == "ADMIN" else "CONGREGATION")
            return Response({"created": count}, status=201)
        if user.role != "ADMIN":
            raise PermissionDenied()
        pass_type, name = request.data.get("pass_type"), str(request.data.get("name", "")).strip()
        if pass_type not in ("FIVE_MEMBER", "VVIP", "VOLUNTEER") or not 2 <= len(name) <= 160:
            raise ValidationError("Provide a name and a valid pass type.")
        limit = validated_count(request.data.get("entry_limit", 1), maximum=100000, minimum=0) if pass_type == "VOLUNTEER" else 1
        authority_id = request.data.get("authority_id") or None
        custom = str(request.data.get("custom_authority_name", "")).strip()
        if pass_type == "FIVE_MEMBER" and not (m.Authority.objects.filter(pk=authority_id, account_type="HOD", status="ACTIVE").exists() or custom):
            raise ValidationError("Select an active HOD or enter a custom authority.")
        with transaction.atomic():
            record = m.ImmediatePass.objects.create(pass_type=pass_type, holder_name=name, recipient_name=name,
                pass_code="PENDING-" + uuid.uuid4().hex, entry_limit=limit, authority_id=authority_id,
                custom_authority_name=custom, created_by_id=user.legacy_id)
            prefix = {"FIVE_MEMBER": "IP5", "VVIP": "IV5", "VOLUNTEER": "IVOL"}[pass_type]
            record.pass_code = f"{prefix}-{record.pk:06d}"
            record.save(update_fields=["pass_code"])
            services.audit(user, "CREATE_IMMEDIATE_PASS", record)
        return Response(services.describe("IMMEDIATE", record), status=201)
    rows = pass_rows(request)
    paginator = PageNumberPagination()
    paginator.page_size_query_param = "page_size"
    paginator.max_page_size = 5000
    result = paginator.paginate_queryset(rows, request)
    response = paginator.get_paginated_response(result)
    used = sum(bool(row["family_used_at"]) if row["kind"] == "COMBINED" else
               row["status"] == "USED" or (bool(row["entry_limit"]) and row["entries_used"] >= row["entry_limit"]) for row in rows)
    response.data["stats"] = {"issued": len(rows), "shared": sum(bool(row["shared_at"]) for row in rows), "unshared": sum(not row["shared_at"] for row in rows), "one_time_access_used": used, "one_time_access_available": len(rows) - used}
    return response


def pass_rows(request):
    rows = []
    user, query = request.user, request.query_params
    allowed_logs = m.EntryLog.objects.filter(result="ALLOWED")
    last_entries = {row["reference_code"]: row["last_entry"] for row in
                    allowed_logs.values("reference_code").annotate(last_entry=Max("entry_time"))}
    matching_codes = None
    if query.get("scanner_id") or query.get("gate_id"):
        for field in ("scanner_id", "gate_id"):
            if query.get(field):
                allowed_logs = allowed_logs.filter(**{field: query[field]})
        matching_codes = set(allowed_logs.values_list("reference_code", flat=True))
    kinds = [query["kind"]] if query.get("kind") in services.PASS_MODELS else ["HOD", "COMBINED", "VVIP", "VOLUNTEER", "IMMEDIATE"]
    if query.get("workspace") == "immediate":
        kinds = ["IMMEDIATE", "COMBINED"]
    elif query.get("workspace") == "shared" and user.role == "ADMIN":
        kinds = ["VVIP", "VOLUNTEER", "IMMEDIATE"]
    for kind in kinds:
        objects = services.owned_passes(user, kind)
        if kind == "HOD":
            objects = objects.select_related("hod")
        elif kind == "COMBINED":
            objects = objects.select_related("congregation")
        elif kind in ("MEMBER", "IMMEDIATE"):
            objects = objects.select_related("authority")
        if kind == "COMBINED" and query.get("workspace") == "immediate":
            objects = objects.filter(issued_source="IMMEDIATE")
        elif kind == "COMBINED" and user.role == "AUTHORITY" and query.get("shared") == "no":
            objects = objects.filter(issued_source="CONGREGATION")
        if kind in ("VVIP", "VOLUNTEER") and query.get("batch_id"):
            objects = objects.filter(batch_id=query["batch_id"])
        if query.get("shared") in ("yes", "no") and kind != "MEMBER":
            objects = objects.filter(shared_at__isnull=query["shared"] == "no")
        if query.get("status") and kind != "MEMBER":
            objects = objects.filter(status=query["status"])
        for record in objects:
            data = services.describe(kind, record)
            data["last_entry"] = last_entries.get(data["code"]) or getattr(record, "used_at", None)
            if query.get("search") and query["search"].lower() not in (data["name"] + " " + data["code"]).lower():
                continue
            if query.get("authority_id") and str(data["authority_id"]) != query["authority_id"]:
                continue
            if query.get("category") and data["category"] != query["category"]:
                continue
            if query.get("pass_type") and data["pass_type"] != query["pass_type"]:
                continue
            if matching_codes is not None and data["code"] not in matching_codes:
                continue
            rows.append(data)
    sort_field = "shared_at" if query.get("shared") == "yes" else "created_at"
    return sorted(rows, key=lambda row: (row[sort_field], row["id"]), reverse=True)


@api_view(["PATCH", "POST"])
@permission_classes([ActivePortalUser])
def pass_update(request, kind, pk):
    record = services.owned_passes(request.user, kind).filter(pk=pk).first()
    if not record or kind == "MEMBER":
        raise NotFound()
    if request.method == "POST":
        record.shared_at = record.shared_at or timezone.now()
        record.save(update_fields=["shared_at"])
        services.audit(request.user, "SHARE_PASS", record)
    else:
        if "status" in request.data:
            if request.user.role != "ADMIN" or request.data["status"] not in ("ACTIVE", "DISABLED"):
                raise PermissionDenied("Only an administrator can activate or disable a pass.")
            target = request.data["status"]
            volunteer = kind == "VOLUNTEER" or (kind == "IMMEDIATE" and record.pass_type == "VOLUNTEER")
            exhausted = (volunteer and record.entry_limit > 0 and record.entry_used >= record.entry_limit) or (not volunteer and kind != "COMBINED" and record.used_at is not None)
            if target == "ACTIVE" and exhausted:
                raise ValidationError("A consumed pass cannot be reactivated.")
            record.status = target
            record.save(update_fields=["status"])
            services.audit(request.user, "CHANGE_PASS_STATUS", record, target)
            return Response(services.describe(kind, record))
        name = str(request.data.get("name", "")).strip()
        if len(name) > 120:
            raise ValidationError("Recipient name must be at most 120 characters.")
        field = "guest_name" if kind == "VOLUNTEER" else "recipient_name"
        setattr(record, field, name)
        record.save(update_fields=[field])
        services.audit(request.user, "EDIT_RECIPIENT", record)
    return Response(services.describe(kind, record))


@api_view(["GET"])
@permission_classes([ActivePortalUser])
def card(request, kind, pk):
    record = services.owned_passes(request.user, kind).filter(pk=pk).first()
    if not record:
        raise NotFound()
    thumb = request.query_params.get("thumb") == "1"
    path = render_card(kind, record, thumb=thumb)
    download = request.query_params.get("download") == "1"
    ctype = "image/webp" if path.suffix == ".webp" else "image/png"
    filename = services.code_for(record) + path.suffix
    response = FileResponse(path.open("rb"), content_type=ctype, as_attachment=download, filename=filename)
    response["Cache-Control"] = "private, max-age=86400, stale-while-revalidate=3600"
    response["ETag"] = f'"{path.stem}"'
    return response


@api_view(["GET", "POST"])
@permission_classes([Administrator])
@transaction.atomic
def upload_batch(request):
    if request.method == "GET":
        rows = []
        for source, batch_model, pass_model in (("VVIP", m.VvipBatch, m.VvipPass), ("VOLUNTEER", m.VolunteerBatch, m.VolunteerPass)):
            for batch in batch_model.objects.all():
                rows.append({"id": batch.pk, "kind": source, "name": batch.batch_name, "created_at": batch.created_at,
                    "passes": pass_model.objects.filter(batch=batch).count(), "entry_limit": getattr(batch, "entry_limit", 1)})
        return Response(sorted(rows, key=lambda row: row["created_at"], reverse=True))
    file, kind = request.FILES.get("file"), request.data.get("kind")
    if kind not in ("VVIP", "VOLUNTEER") or not file or file.size > 2 * 1024 * 1024:
        raise ValidationError("Upload a VVIP or volunteer CSV below 2 MB.")
    try:
        reader = csv.reader(io.StringIO(file.read().decode("utf-8-sig")))
        names = []
        for index, row in enumerate(reader):
            if index > 1000:
                raise ValidationError("Upload no more than 1,000 rows.")
            name = row[0].strip() if row else ""
            if index == 0 and name.lower() == "name":
                continue
            if len(name) > 120:
                raise ValidationError(f"Row {index + 1} has a name longer than 120 characters.")
            if name and name not in names:
                names.append(name)
    except (UnicodeDecodeError, csv.Error):
        raise ValidationError("Use a UTF-8 CSV with one name per row.")
    if not names:
        raise ValidationError("No names were found.")
    batch_name = str(request.data.get("batch_name", "Imported passes")).strip()[:120] or "Imported passes"
    limit = validated_count(request.data.get("entry_limit", 1), minimum=0, maximum=100000)
    if kind == "VVIP":
        batch = m.VvipBatch.objects.create(batch_name=batch_name, created_by_id=request.user.legacy_id)
        for index, name in enumerate(names, 1):
            m.VvipPass.objects.create(batch=batch, pass_id=f"V5-{batch.pk}-{index:04d}", guest_name=name, recipient_name=name)
    else:
        batch = m.VolunteerBatch.objects.create(batch_name=batch_name, entry_limit=limit, created_by_id=request.user.legacy_id)
        for index, name in enumerate(names, 1):
            m.VolunteerPass.objects.create(batch=batch, pass_id=f"VOL-{batch.pk:04d}-{index:04d}", guest_name=name, entry_limit=limit)
    services.audit(request.user, "UPLOAD_BATCH", batch, f"{len(names)} {kind} passes")
    return Response({"created": len(names), "batch_id": batch.pk}, status=201)


def scoped_entries(user):
    query = m.EntryLog.objects.all()
    if user.role == "SCANNER":
        return query.filter(scanner_id=user.legacy_id)
    if user.role == "VOLUNTEER":
        return query.filter(volunteer_id=user.legacy_id)
    if user.role == "AUTHORITY":
        codes = list(m.HodPass.objects.filter(hod_id=user.legacy_id).values_list("pass_code", flat=True)) + list(m.CombinedPass.objects.filter(congregation_id=user.legacy_id).values_list("pass_code", flat=True))
        return query.filter(Q(member__authority_id=user.legacy_id) | Q(reference_code__in=codes))
    return query


class EntryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [Administrator]
    serializer_class = s.EntrySerializer

    def get_queryset(self):
        query = scoped_entries(self.request.user).select_related("gate", "scanner", "volunteer")
        for field in ("gate_id", "scanner_id", "result"):
            if self.request.query_params.get(field):
                query = query.filter(**{field: self.request.query_params[field]})
        term = self.request.query_params.get("search")
        if term:
            query = query.filter(Q(subject_name__icontains=term) | Q(reference_code__icontains=term))
        return query.order_by("-pk")


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [Administrator]
    serializer_class = s.AuditSerializer
    queryset = m.AuditLog.objects.order_by("-pk")


@api_view(["POST"])
@permission_classes([ActivePortalUser])
def scan_lookup(request):
    manual = bool(request.data.get("code"))
    return Response(services.lookup(request.user, str(request.data.get("code") or request.data.get("token") or ""), manual))


@api_view(["POST"])
@permission_classes([ActivePortalUser])
def scan_confirm(request):
    return Response(services.confirm_entry(request.user, request.data.get("kind"), request.data.get("id"),
        request.data.get("mode", "SINGLE"), request.data.get("method", "QR"), request.data.get("request_id")))


@api_view(["GET"])
@permission_classes([Administrator])
def own_credentials(request):
    return credentials_response(request, profile_for(request.user))


@api_view(["GET", "PATCH"])
@permission_classes([ActivePortalUser])
def profile(request):
    user = request.user
    if user.role == "SCANNER":
        raise PermissionDenied("Scanner accounts have only the entry workspace.")
    if request.method == "PATCH" and user.role != "ADMIN":
        raise PermissionDenied("Account details can only be changed by Temple Authority.")
    instance = profile_for(user)
    serializer_class = {"ADMIN": s.AdminSerializer, "AUTHORITY": s.AccountSerializer, "SCANNER": s.ScannerSerializer, "VOLUNTEER": s.VolunteerSerializer}[user.role]
    if request.method == "PATCH":
        allowed = {key: value for key, value in request.data.items() if key in ("name", "mobile", "username", "new_password", "photo")}
        serializer = serializer_class(instance, data=allowed, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            services.audit(user, "UPDATE_OWN_PROFILE", instance)
        # Retain the current session after a password change.
        if "new_password" in allowed:
            from django.contrib.auth import update_session_auth_hash
            user.refresh_from_db()
            update_session_auth_hash(request, user)
    card_member = None
    if user.role == "ADMIN":
        card_member = m.Member.objects.filter(admin_id=user.legacy_id).first()
    elif user.role == "AUTHORITY":
        card_member = m.Member.objects.filter(authority_id=user.legacy_id, notes="AUTHORITY_PROFILE_CARD").first()
    result = dict(serializer_class(instance).data)
    result.update(role=user.role, personal_card_id=card_member.pk if card_member else None)
    return Response(result)


@api_view(["GET"])
@permission_classes([Administrator])
def event_settings(request):
    event, _ = m.EventSettings.objects.get_or_create(pk=1)
    return Response(s.SettingsSerializer(event).data)


def csv_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@api_view(["GET"])
@permission_classes([ActivePortalUser])
def export_passes(request):
    rows = pass_rows(request)
    output = io.StringIO()
    writer = csv.writer(output)
    fields = ["code", "name", "pass_type", "category", "authority", "status", "shared_at", "entries_used", "entry_limit", "family_used_at", "last_entry"]
    if request.query_params.get("filetype") == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Pass report"
        worksheet.append([field.replace("_", " ").title() for field in fields])
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="641C30")
        for row in rows:
            worksheet.append([row.get(field) if isinstance(row.get(field), (int, float)) else csv_cell(row.get(field)) for field in fields])
        for column in worksheet.columns:
            worksheet.column_dimensions[column[0].column_letter].width = 24
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        content = io.BytesIO()
        workbook.save(content)
        response = HttpResponse(content.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="pass-report.xlsx"'
        return response
    writer.writerow(fields)
    for row in rows:
        writer.writerow([csv_cell(row.get(field)) for field in fields])
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="pass-report.csv"'
    return response


@api_view(["POST"])
@permission_classes([ActivePortalUser])
def download_bundle(request):
    selections = request.data.get("passes", [])
    if not isinstance(selections, list) or not 1 <= len(selections) <= 250:
        raise ValidationError("Select between 1 and 250 passes.")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for selected in selections:
            kind = selected.get("kind")
            record = services.owned_passes(request.user, kind).filter(pk=selected.get("id")).first()
            if not record:
                raise NotFound("A selected pass is unavailable.")
            archive.write(render_card(kind, record), services.code_for(record) + ".png")
    response = HttpResponse(output.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="entry-passes.zip"'
    return response


@api_view(["GET"])
@permission_classes([ActivePortalUser])
def options(request):
    user = request.user
    authority_query = m.Authority.objects.all() if user.role == "ADMIN" else m.Authority.objects.filter(pk=user.legacy_id) if user.role == "AUTHORITY" else m.Authority.objects.none()
    profile = profile_for(user)
    allocation = (m.CombinedPass.objects.filter(congregation_id=user.legacy_id, issued_source="CONGREGATION").count()
                  if getattr(profile, "account_type", "") == "CONGREGATION" else m.HodPass.objects.filter(hod_id=user.legacy_id).count()) if user.role == "AUTHORITY" else None
    return Response({"authorities": list(authority_query.values("id", "name", "account_type", "profile_type", "status")),
                     "gates": list(m.Gate.objects.values("id", "gate_name", "status")) if user.role == "ADMIN" else [],
                     "scanners": list(m.Scanner.objects.values("id", "name")) if user.role == "ADMIN" else [],
                     "assigned_gate": profile.gate.gate_name if getattr(profile, "gate_id", None) else None,
                     "assigned_passes": allocation,
                     "profile_type": getattr(profile, "profile_type", None),
                     "share_message": LAYOUT["share_message"],
                     "account_type": getattr(profile, "account_type", None), "can_add_members": bool(getattr(profile, "can_add_members", False))})


@api_view(["POST"])
@permission_classes([ActivePortalUser])
@transaction.atomic
def share_bulk(request):
    selected = request.data.get("passes", [])
    if not isinstance(selected, list) or not 1 <= len(selected) <= 24:
        raise ValidationError("Select between 1 and 24 passes.")
    records = []
    seen = set()
    for item in selected:
        if not isinstance(item, dict) or item.get("kind") == "MEMBER":
            raise ValidationError("Invalid pass selection.")
        key = (item.get("kind"), item.get("id"))
        if key in seen:
            continue
        seen.add(key)
        record = services.owned_passes(request.user, key[0]).select_for_update().filter(pk=key[1]).first()
        if not record:
            raise NotFound("One of the selected passes is unavailable.")
        records.append(record)
    for record in records:
        if record.shared_at:
            raise ValidationError("A selected pass has already been shared. Refresh the page.")
    for record in records:
        record.shared_at = timezone.now()
        record.save(update_fields=["shared_at"])
        services.audit(request.user, "SHARE_PASS", record)
    return Response({"shared": len(records)})


@api_view(["POST"])
@permission_classes([ActivePortalUser])
@transaction.atomic
def personal_card(request):
    user = request.user
    if user.role not in ("ADMIN", "AUTHORITY"):
        raise PermissionDenied()
    profile = profile_for(user)
    profile = profile.__class__.objects.select_for_update().get(pk=profile.pk)
    criteria = {"admin_id": user.legacy_id} if user.role == "ADMIN" else {"authority_id": user.legacy_id, "notes": "AUTHORITY_PROFILE_CARD"}
    member = m.Member.objects.select_for_update().filter(**criteria).first()
    photo_path = s.save_photo(request.FILES["photo"]) if request.FILES.get("photo") else getattr(profile, "photo_path", None)
    if member is None:
        member = m.Member.objects.create(**criteria, devotee_id="PERSONAL-" + uuid.uuid4().hex[:12].upper(), name=profile.name,
            mobile=getattr(profile, "mobile", None), photo_path=photo_path, approval_status="APPROVED", entry_limit=0)
    else:
        member.name, member.mobile, member.entry_limit = profile.name, getattr(profile, "mobile", None), 0
        if photo_path:
            member.photo_path = photo_path
        member.save()
    m.QrToken.objects.get_or_create(member=member)
    services.audit(user, "GENERATE_PERSONAL_CARD", member)
    return Response({"member_id": member.pk, "card_url": f"/api/passes/MEMBER/{member.pk}/card/"})


@api_view(["DELETE", "GET"])
@permission_classes([Administrator])
def batch_detail(request, kind, pk):
    if kind not in ("VVIP", "VOLUNTEER"):
        raise NotFound()
    batch_model, pass_model = (m.VvipBatch, m.VvipPass) if kind == "VVIP" else (m.VolunteerBatch, m.VolunteerPass)
    batch = batch_model.objects.filter(pk=pk).first()
    if not batch:
        raise NotFound()
    records = pass_model.objects.filter(batch=batch)
    if request.method == "DELETE":
        with transaction.atomic():
            records.update(status="DISABLED")
            services.audit(request.user, "DISABLE_PASS_BATCH", batch)
        return Response({"disabled": records.count()})
    if records.count() > 250:
        raise ValidationError("This batch exceeds 250 cards. Download selected passes in smaller groups.")
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", zipfile.ZIP_DEFLATED) as archive:
        for record in records:
            archive.write(render_card(kind, record), services.code_for(record) + ".png")
    response = HttpResponse(content.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{kind.lower()}-batch-{pk}.zip"'
    return response
