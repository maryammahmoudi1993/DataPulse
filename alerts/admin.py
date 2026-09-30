from django.contrib import admin

from alerts.models import Alert, WebhookEndpoint


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'stream', 'severity', 'status', 'anomaly_score',
                    'detector_type', 'created_at']
    list_filter = ['severity', 'status', 'detector_type']
    search_fields = ['stream__name']
    readonly_fields = ['created_at']
    actions = ['acknowledge_alerts', 'resolve_alerts']

    @admin.action(description='Acknowledge selected alerts')
    def acknowledge_alerts(self, request, queryset):
        updated = queryset.update(status=Alert.STATUS_ACKNOWLEDGED)
        self.message_user(request, f'{updated} alert(s) acknowledged.')

    @admin.action(description='Resolve selected alerts')
    def resolve_alerts(self, request, queryset):
        updated = queryset.update(status=Alert.STATUS_RESOLVED)
        self.message_user(request, f'{updated} alert(s) resolved.')


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'workspace', 'min_severity', 'is_active']
    list_filter = ['is_active', 'min_severity']
