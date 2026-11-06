from rest_framework.permissions import BasePermission
from .authentication import profile_for


class ActivePortalUser(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.is_active:
            return False
        profile = profile_for(request.user)
        return profile is not None and profile.status == "ACTIVE"


class Administrator(ActivePortalUser):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == "ADMIN"
