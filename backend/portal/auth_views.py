import hashlib
import json
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods


def identity(user):
    return {"id": user.pk, "name": user.display_name, "login_id": user.login_id, "role": user.role}


@ensure_csrf_cookie
@require_http_methods(["GET"])
def session(request):
    return JsonResponse({"authenticated": request.user.is_authenticated,
                         "user": identity(request.user) if request.user.is_authenticated else None})


@csrf_protect
@require_http_methods(["POST"])
def sign_in(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid login request."}, status=400)
    username, password = data.get("username", ""), data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 150 or len(password) > 1024:
        return JsonResponse({"detail": "Invalid Login ID or password."}, status=400)
    key = "login:" + hashlib.sha256((request.META.get("REMOTE_ADDR", "") + username.lower()).encode()).hexdigest()
    if cache.get(key, 0) >= 8:
        return JsonResponse({"detail": "Too many login attempts. Try again in five minutes."}, status=429)
    user = authenticate(request, username=username, password=password, role=data.get("role"))
    if user is None:
        if not cache.add(key, 1, 300):
            cache.incr(key)
        return JsonResponse({"detail": "Invalid Login ID or password."}, status=401)
    cache.delete(key)
    login(request, user)
    return JsonResponse({"authenticated": True, "user": identity(user)})


@csrf_protect
@require_http_methods(["POST"])
def sign_out(request):
    logout(request)
    return JsonResponse({"authenticated": False})
