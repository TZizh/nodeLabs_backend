from rest_framework import serializers
from .models import Transmission, RepeaterActivity


class TransmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transmission
        fields = [
            "id",
            "timestamp",
            "device",
            "role",
            "message",
            "status",
            "sent_at",
            "received_at",
            "msg_id",
        ]
        read_only_fields = fields


class RepeaterActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RepeaterActivity
        fields = [
            "id",
            "timestamp",
            "device",
            "msg_id",
            "message",
            "action",
            "voltage",
            "signal_strength",
            "tx_power",
            "rx_total",
            "tx_total",
            "failed",
        ]
        read_only_fields = fields
