from django.contrib import admin

from .models import NotificationLog, PagerDutyIntegration, SlackIntegration

admin.site.register(SlackIntegration)
admin.site.register(PagerDutyIntegration)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('alert', 'channel', 'status', 'response_code', 'created_at')
    list_filter = ('channel', 'status')
