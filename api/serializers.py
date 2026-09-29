from rest_framework import serializers

from ingestion.models import DataPoint
from streams.models import Stream, Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ['id', 'name', 'slug', 'owner', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']


class StreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stream
        fields = [
            'id',
            'workspace',
            'name',
            'source_type',
            'source_config',
            'sampling_interval',
            'detector_type',
            'detector_config',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class DataPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataPoint
        fields = ['id', 'stream', 'timestamp', 'value', 'metadata']
        read_only_fields = ['id', 'stream']
