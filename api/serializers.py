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
        fields = "__all__"
