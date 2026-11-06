from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve
from rest_framework.routers import DefaultRouter
from portal import auth_views, views

router = DefaultRouter()
for prefix, view, basename in [
    ("authorities", views.AuthorityViewSet, "authority"), ("scanners", views.ScannerViewSet, "scanner"),
    ("volunteers", views.VolunteerViewSet, "volunteer"), ("gates", views.GateViewSet, "gate"),
    ("members", views.MemberViewSet, "member"), ("entries", views.EntryViewSet, "entry"), ("audit", views.AuditViewSet, "audit"),
]:
    router.register(prefix, view, basename=basename)

def serve_spa(request):
    dist_index = settings.BASE_DIR.parent / "frontend" / "dist" / "index.html"
    if dist_index.is_file():
        return FileResponse(dist_index.open("rb"), content_type="text/html")
    return HttpResponse(
        "<h2>Darshan Seva Portal API</h2><p>Frontend static build not detected. Build the frontend with 'npm run build' inside /frontend.</p>",
        content_type="text/html"
    )

dist_folder = settings.BASE_DIR.parent / "frontend" / "dist"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/auth/session/", auth_views.session),
    path("api/auth/login/", auth_views.sign_in),
    path("api/auth/logout/", auth_views.sign_out),
    path("api/dashboard/", views.dashboard),
    path("api/profile/", views.profile),
    path("api/event/", views.event_settings),
    path("api/profile/credentials/", views.own_credentials),
    path("api/options/", views.options),
    path("api/profile/card/", views.personal_card),
    path("api/passes/", views.passes),
    path("api/passes/export/", views.export_passes),
    path("api/passes/bundle/", views.download_bundle),
    path("api/passes/share-bulk/", views.share_bulk),
    path("api/passes/<str:kind>/<int:pk>/", views.pass_update),
    path("api/passes/<str:kind>/<int:pk>/card/", views.card),
    path("api/batches/", views.upload_batch),
    path("api/scan/lookup/", views.scan_lookup),
    path("api/scan/confirm/", views.scan_confirm),
    path("api/batches/<str:kind>/<int:pk>/", views.batch_detail),
]

# Static assets from the React production build (if built)
if dist_folder.is_dir():
    urlpatterns += [
        re_path(r"^(?P<path>(assets|brand)/.*)$", serve, {"document_root": dist_folder}),
        re_path(r"^(?P<path>favicon\.svg|icons\.svg)$", serve, {"document_root": dist_folder}),
    ]

# Catch-all: send any other non-API route to the React SPA
urlpatterns += [
    re_path(r"^(?!api/|admin/|static/|media/).*$", serve_spa),
]
