
from django.db import models
from django.utils import timezone

class RepeaterDevice(models.Model):
    device = models.CharField(primary_key=True, max_length=20)  # e.g., RPT001
    friendly_name = models.CharField(max_length=64, blank=True, default="")
    enabled = models.BooleanField(default=True)
    api_key_hash = models.CharField(max_length=128, blank=True, default="")  # hex of PBKDF2 or similar
    salt = models.CharField(max_length=32, blank=True, default="")
    # Optional location for map overlays
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "repeater_device"

    def __str__(self):
        return self.device


class RepeaterStatus(models.Model):
    device = models.OneToOneField(RepeaterDevice, on_delete=models.CASCADE, primary_key=True, related_name="status")
    last_seen = models.DateTimeField(default=timezone.now)
    voltage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    signal_strength = models.IntegerField(null=True, blank=True)  # 0..100
    tx_power = models.IntegerField(null=True, blank=True)  # 0..100
    rx_total = models.IntegerField(default=0)
    tx_total = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    uptime_seconds = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "repeater_status"


class RepeaterActivity(models.Model):
    ACTION_CHOICES = (
        ("received", "received"),
        ("retransmitted", "retransmitted"),
    )
    id = models.BigAutoField(primary_key=True)
    device = models.ForeignKey(RepeaterDevice, on_delete=models.CASCADE, related_name="activities")
    msg_id = models.IntegerField()
    message = models.TextField()
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    voltage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    signal_strength = models.IntegerField(null=True, blank=True)
    tx_power = models.IntegerField(null=True, blank=True)
    rx_total = models.IntegerField(default=0)
    tx_total = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "repeater_activity"
        indexes = [
            models.Index(fields=["device", "msg_id"], name="idx_device_msgid"),
            models.Index(fields=["timestamp"], name="idx_timestamp"),
            models.Index(fields=["device"], name="idx_device"),
        ]

    def __str__(self):
        return f"{self.device_id} #{self.msg_id} {self.action} @ {self.timestamp}"
