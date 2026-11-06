from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from portal import auth_views, views

router = DefaultRouter()
for prefix, view, basename in [
    ("authorities", views.AuthorityViewSet, "authority"), ("scanners", views.ScannerViewSet, "scanner"),
    ("volunteers", views.VolunteerViewSet, "volunteer"), ("gates", views.GateViewSet, "gate"),
    ("members", views.MemberViewSet, "member"), ("entries", views.EntryViewSet, "entry"), ("audit", views.AuditViewSet, "audit"),
]:
    router.register(prefix, view, basename=basename)

urlpatterns = [
    path("admin/", admin.site.urls), path("api/", include(router.urls)),
    path("api/auth/session/", auth_views.session), path("api/auth/login/", auth_views.sign_in), path("api/auth/logout/", auth_views.sign_out),
    path("api/dashboard/", views.dashboard), path("api/profile/", views.profile), path("api/event/", views.event_settings),
    path("api/profile/credentials/", views.own_credentials),
    path("api/options/", views.options), path("api/profile/card/", views.personal_card),
    path("api/passes/", views.passes), path("api/passes/export/", views.export_passes), path("api/passes/bundle/", views.download_bundle),
    path("api/passes/share-bulk/", views.share_bulk),
    path("api/passes/<str:kind>/<int:pk>/", views.pass_update), path("api/passes/<str:kind>/<int:pk>/card/", views.card),
    path("api/batches/", views.upload_batch), path("api/scan/lookup/", views.scan_lookup), path("api/scan/confirm/", views.scan_confirm),
    path("api/batches/<str:kind>/<int:pk>/", views.batch_detail),
]
