
from django.db import models
from django.utils import timezone

# ===== Existing =====
ROLE_CHOICES = (
    ('TX', 'Transmitter'),
    ('RX', 'Receiver'),
    ('RELAY', 'Relay'),
)

STATUS_CHOICES = (
    ('PENDING', 'Pending'),
    ('SENT', 'Sent'),
    ('RECEIVED', 'Received'),
    ('FAILED', 'Failed'),
)

class Transmission(models.Model):
    device = models.CharField(max_length=64, blank=True, default='')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    message = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    # Optional but useful fields (dashboards tolerate if null)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    msg_id = models.IntegerField(null=True, blank=True)  # RF message id (1..255)

    def __str__(self):
        return f"[{self.role}] {self.device} @ {self.timestamp:%Y-%m-%d %H:%M:%S}"

# ===== New: Repeater models =====

class RepeaterDevice(models.Model):
    device = models.CharField(primary_key=True, max_length=20)  # e.g., RPT001
    friendly_name = models.CharField(max_length=64, blank=True, default="")
    enabled = models.BooleanField(default=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    config = models.JSONField(null=True, blank=True)  # future use
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
