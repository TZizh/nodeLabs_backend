
from django.contrib import admin
from .models import RepeaterDevice, RepeaterStatus, RepeaterActivity

@admin.register(RepeaterDevice)
class RepeaterDeviceAdmin(admin.ModelAdmin):
    list_display = ("device", "friendly_name", "enabled", "created_at", "updated_at")
    search_fields = ("device", "friendly_name")

@admin.register(RepeaterStatus)
class RepeaterStatusAdmin(admin.ModelAdmin):
    list_display = ("device", "last_seen", "voltage", "signal_strength", "tx_power", "rx_total", "tx_total", "failed", "uptime_seconds")
    search_fields = ("device__device",)

@admin.register(RepeaterActivity)
class RepeaterActivityAdmin(admin.ModelAdmin):
    list_display = ("device", "msg_id", "action", "timestamp", "signal_strength", "tx_power", "rx_total", "tx_total", "failed")
    list_filter = ("action", "device")
    search_fields = ("device__device", "message")
