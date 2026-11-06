import uuid
from pathlib import Path
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from . import models as m


def save_photo(photo):
    from PIL import Image
    if photo.size > 5 * 1024 * 1024:
        raise serializers.ValidationError("Photo must be below 5 MB.")
    path = settings.MEDIA_ROOT / "member-photos" / (uuid.uuid4().hex + ".jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        image = Image.open(photo)
        image.thumbnail((1600, 1600))
        image.convert("RGB").save(path, "JPEG", quality=90)
    except (ValueError, OSError) as exc:
        raise serializers.ValidationError("Upload a valid image.") from exc
    return "member-photos/" + path.name


class AccountSerializer(serializers.ModelSerializer):
    new_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, max_length=1024)
    photo = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = m.Authority
        exclude = ["password"]
        read_only_fields = ["created_at", "updated_at", "photo_path", "five_member_passes"]
        extra_kwargs = {"authority_id": {"required": False}}

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("new_password"):
            raise serializers.ValidationError({"new_password": "A password is required for a new account."})
        if attrs.get("gate") and attrs["gate"].status != "ACTIVE":
            raise serializers.ValidationError({"gate": "Select an active gate."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("new_password")
        photo = validated_data.pop("photo", None)
        if photo and hasattr(self.Meta.model, "photo_path"):
            validated_data["photo_path"] = save_photo(photo)
        instance = super().create(validated_data)
        role = {m.Authority: "AUTHORITY", m.Scanner: "SCANNER", m.Volunteer: "VOLUNTEER", m.LegacyAdmin: "ADMIN"}[self.Meta.model]
        user = m.User(username=f"{role.lower()}.{instance.pk}.{uuid.uuid4().hex[:8]}", login_id=instance.username,
                      display_name=instance.name, role=role, source_table=instance._meta.db_table, legacy_id=instance.pk,
                      is_active=instance.status == "ACTIVE", is_staff=role == "ADMIN")
        user.set_password(password)
        user.save()
        return instance

    def update(self, instance, validated_data):
        password = validated_data.pop("new_password", None)
        photo = validated_data.pop("photo", None)
        if photo and hasattr(instance, "photo_path"):
            validated_data["photo_path"] = save_photo(photo)
        instance = super().update(instance, validated_data)
        user = m.User.objects.filter(source_table=instance._meta.db_table, legacy_id=instance.pk).first()
        if user:
            user.login_id, user.display_name, user.is_active = instance.username, instance.name, instance.status == "ACTIVE"
            if password:
                user.set_password(password)
            user.save()
        return instance


class AuthorityDirectorySerializer(AccountSerializer):
    assigned_passes = serializers.IntegerField(read_only=True, default=0)
    available_passes = serializers.IntegerField(read_only=True, default=0)
    combined_passes = serializers.IntegerField(read_only=True, default=0)


class ScannerSerializer(AccountSerializer):
    class Meta(AccountSerializer.Meta):
        model = m.Scanner
        read_only_fields = ["created_at"]


class VolunteerSerializer(AccountSerializer):
    gate_name = serializers.CharField(source="gate.gate_name", read_only=True)

    class Meta(AccountSerializer.Meta):
        model = m.Volunteer
        read_only_fields = ["created_at", "updated_at"]


class AdminSerializer(AccountSerializer):
    class Meta(AccountSerializer.Meta):
        model = m.LegacyAdmin
        read_only_fields = ["created_at", "updated_at"]


class GateSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Gate
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class MemberSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(write_only=True, required=False)
    authority_name = serializers.CharField(source="authority.name", read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = m.Member
        fields = "__all__"
        read_only_fields = ["photo_path", "created_at", "updated_at", "entry_used", "guest_entry_used", "guest_entry_used_at", "guest_count_used", "admin", "created_by_authority", "approval_status"]
        extra_kwargs = {"devotee_id": {"required": False, "allow_blank": True}}

    def get_photo_url(self, obj):
        return f"/api/members/{obj.pk}/photo/" if obj.photo_path else None

    def create(self, validated_data):
        photo = validated_data.pop("photo", None)
        if photo:
            validated_data["photo_path"] = save_photo(photo)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        photo = validated_data.pop("photo", None)
        if photo:
            validated_data["photo_path"] = save_photo(photo)
        return super().update(instance, validated_data)


class EntrySerializer(serializers.ModelSerializer):
    gate_name = serializers.CharField(source="gate.gate_name", read_only=True)
    scanner_name = serializers.CharField(source="scanner.name", read_only=True)
    volunteer_name = serializers.CharField(source="volunteer.name", read_only=True)

    class Meta:
        model = m.EntryLog
        fields = "__all__"


class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.AuditLog
        fields = "__all__"


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.EventSettings
        fields = "__all__"
