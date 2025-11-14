
# Repeaters Django App

Drop this Django app into your existing project and wire the URLs.

## Install
```
pip install djangorestframework
```

Add to `settings.py`:
```python
INSTALLED_APPS += ["rest_framework", "repeaters"]
```

Project `urls.py`:
```python
from django.urls import path, include
urlpatterns += [ path("", include("repeaters.urls")) ]
```

Create tables:
```
python manage.py makemigrations repeaters
python manage.py migrate
```

Create device + API key (optional but recommended):
```
python manage.py create_repeater_device RPT001 --friendly "Lab Repeater"
```

This prints an API key; configure the ESP32 to send it in the `X-Device-Key` header.

## Endpoints
- POST `/api/repeater/activity/`
- GET  `/api/repeater/status/` (optional `?device=RPT001`)
- GET  `/api/repeater/history/?device=RPT001&limit=50&offset=0`
- GET  `/api/repeater/metrics/?device=RPT001&period=24h`

## Example: ESP32 POST (Arduino)
```cpp
HTTPClient http;
http.begin(String(API_BASE) + "/api/repeater/activity/");
http.addHeader("Content-Type", "application/json");
http.addHeader("X-Device-Key", DEVICE_API_KEY); // from management command
StaticJsonDocument<512> doc;
doc["device"] = "RPT001";
doc["msg_id"] = msgId;
doc["message"] = payloadStr;
doc["action"] = actionStr; // "received" or "retransmitted"
doc["voltage"] = measuredVoltage;
doc["signal_strength"] = signalPct; // 0..100
doc["tx_power"] = txPowerPct; // 0..100
JsonObject stats = doc.createNestedObject("stats");
stats["rx_total"] = rxTotal;
stats["tx_total"] = txTotal;
stats["failed"] = failedTotal;
String body;
serializeJson(doc, body);
int code = http.POST(body);
String resp = http.getString();
http.end();
```

## Notes
- History pairs `received`/`retransmitted` heuristically per `msg_id` within the result window.
- Metrics aggregate per minute if `period <= 6h`, otherwise per hour.
- `uptime_seconds` increments by +2s per activity (POC). Replace with a heartbeat endpoint if you need precise uptime.
```

