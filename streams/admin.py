from django.contrib import admin
from django.utils.html import format_html

from streams.models import Stream, Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'stream_count', 'created_at']
    search_fields = ['name', 'slug']
    readonly_fields = ['created_at']

    @admin.display(description='Streams')
    def stream_count(self, obj):
        return obj.streams.count()


@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    list_display = ['name', 'workspace', 'source_type', 'detector_type',
                    'status_badge', 'sampling_interval', 'created_at']
    list_filter = ['status', 'detector_type', 'source_type']
    search_fields = ['name', 'workspace__slug']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['pause_streams', 'resume_streams', 'trigger_lstm_training']

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            Stream.STATUS_ACTIVE: 'green',
            Stream.STATUS_PAUSED: 'orange',
            Stream.STATUS_ERROR: 'red',
        }
        return format_html(
            '<span style="color:{};font-weight:500">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status,
        )

    @admin.action(description='Pause selected streams')
    def pause_streams(self, request, queryset):
        updated = queryset.update(status=Stream.STATUS_PAUSED)
        self.message_user(request, f'{updated} stream(s) paused.')

    @admin.action(description='Resume selected streams')
    def resume_streams(self, request, queryset):
        updated = queryset.update(status=Stream.STATUS_ACTIVE)
        self.message_user(request, f'{updated} stream(s) resumed.')

    @admin.action(description='Trigger LSTM training for selected streams')
    def trigger_lstm_training(self, request, queryset):
        from detection.tasks import train_lstm_for_stream
        count = 0
        for stream in queryset.filter(detector_type=Stream.DETECTOR_LSTM):
            train_lstm_for_stream.delay(stream.id)
            count += 1
        self.message_user(request, f'LSTM training triggered for {count} stream(s).')
