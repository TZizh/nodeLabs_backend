
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from .models import RepeaterDevice

class RepeaterAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dev = RepeaterDevice.objects.create(device="RPT001")

    def test_activity_post_and_status(self):
        payload = {
            "device": "RPT001",
            "msg_id": 42,
            "message": "Hello World",
            "action": "received",
            "voltage": "11.66",
            "signal_strength": 85,
            "tx_power": 95,
            "stats": {"rx_total": 127, "tx_total": 125, "failed": 2}
        }
        r = self.client.post("/api/repeater/activity/", payload, format="json")
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get("/api/repeater/status/?device=RPT001")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["repeaters"][0]["device"], "RPT001")
