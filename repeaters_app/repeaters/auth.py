
import hmac, hashlib
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import AuthenticationFailed
from .models import RepeaterDevice

def verify_api_key(device: RepeaterDevice, presented_key: str) -> bool:
    if not device.api_key_hash or not device.salt:
        # If no key set, allow (useful for POC)
        return True
    dk = hashlib.pbkdf2_hmac('sha256', presented_key.encode('utf-8'), bytes.fromhex(device.salt), 120000, dklen=32).hex()
    return hmac.compare_digest(dk, device.api_key_hash)

def require_device_key(request, device_id: str):
    # Header names: X-Device and X-Device-Key (or 'device' in JSON body for POSTs)
    key = request.headers.get("X-Device-Key") or request.META.get("HTTP_X_DEVICE_KEY")
    device = None
    try:
        device = RepeaterDevice.objects.get(pk=device_id)
    except RepeaterDevice.DoesNotExist:
        raise AuthenticationFailed("Unknown device")
    if not verify_api_key(device, key or ""):
        raise AuthenticationFailed("Invalid device key")
    if not device.enabled:
        raise AuthenticationFailed("Device disabled")
    return device
