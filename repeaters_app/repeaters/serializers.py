
from rest_framework import serializers
from .models import RepeaterActivity, RepeaterStatus, RepeaterDevice

class ActivityStatsSerializer(serializers.Serializer):
    rx_total = serializers.IntegerField()
    tx_total = serializers.IntegerField()
    failed = serializers.IntegerField()

class RepeaterActivityCreateSerializer(serializers.Serializer):
    device = serializers.CharField(max_length=20)
    msg_id = serializers.IntegerField()
    message = serializers.CharField()
    action = serializers.ChoiceField(choices=["received", "retransmitted"])
    voltage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    signal_strength = serializers.IntegerField(required=False, min_value=0, max_value=100)
    tx_power = serializers.IntegerField(required=False, min_value=0, max_value=100)
    stats = ActivityStatsSerializer()

class RepeaterStatusSerializer(serializers.ModelSerializer):
    device = serializers.CharField(source="device.device")
    class Meta:
        model = RepeaterStatus
        fields = ["device", "last_seen", "voltage", "signal_strength", "tx_power", "rx_total", "tx_total", "failed", "uptime_seconds"]

class RepeaterDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepeaterDevice
        fields = ["device", "friendly_name", "enabled", "latitude", "longitude", "created_at", "updated_at"]
