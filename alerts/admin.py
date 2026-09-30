from django.contrib import admin

from alerts.models import Alert, WebhookEndpoint

admin.site.register(Alert)
admin.site.register(WebhookEndpoint)
