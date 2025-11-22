from django.db import models

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


# NEW: per-event log for the repeater
class RepeaterActivity(models.Model):
    ACTION_CHOICES = (
        ('received', 'Received'),
        ('retransmitted', 'Retransmitted'),
    )

    timestamp = models.DateTimeField(auto_now_add=True)

    device = models.CharField(max_length=64, blank=True, default='')  # e.g. "RPT001"
    msg_id = models.IntegerField(null=True, blank=True)
    message = models.TextField(blank=True, default='')

    action = models.CharField(max_length=16, choices=ACTION_CHOICES)

    # Telemetry from firmware
    voltage = models.FloatField(null=True, blank=True)
    signal_strength = models.IntegerField(null=True, blank=True)
    tx_power = models.IntegerField(null=True, blank=True)

    # Snapshot of repeater counters
    rx_total = models.IntegerField(null=True, blank=True)
    tx_total = models.IntegerField(null=True, blank=True)
    failed = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.device} {self.action} msg#{self.msg_id} @ {self.timestamp:%Y-%m-%d %H:%M:%S}"
