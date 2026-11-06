from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from . import models as m

admin.site.site_header = "Darshan Seva administration"
class PortalUserAdmin(UserAdmin):
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "password" in form.base_fields:
            form.base_fields["password"].help_text = format_html(
                'This portal stores readable passwords. <a href="{}">Change password</a>.', "../password/")
        return form


admin.site.register(m.User, PortalUserAdmin)
for model in (m.Gate, m.Authority, m.Member, m.HodPass, m.CombinedPass, m.VvipBatch, m.VvipPass,
              m.VolunteerBatch, m.VolunteerPass, m.ImmediatePass, m.Scanner, m.EntryLog, m.AuditLog, m.EventSettings):
    admin.site.register(model)
