from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import User, LegacyAdmin, Authority, Volunteer, Scanner

PROFILE_MODELS = {"ADMIN": LegacyAdmin, "AUTHORITY": Authority, "VOLUNTEER": Volunteer, "SCANNER": Scanner}


def profile_for(user):
    model = PROFILE_MODELS.get(user.role)
    return model.objects.filter(pk=user.legacy_id).first() if model else None


class PortalBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, role=None, **kwargs):
        if not username or not password:
            return None
        candidates = User.objects.filter(Q(login_id=username.strip()) | Q(username=username.strip()), is_active=True)
        if role and role != "COMMON":
            candidates = candidates.filter(role=role)
        for user in candidates.order_by("pk"):
            profile = profile_for(user)
            if user.check_password(password) and profile and profile.status == "ACTIVE":
                return user
        return None
