
from datetime import timedelta
from django.db.models.functions import TruncHour, TruncMinute
from django.db.models import Avg, Count, Q, F
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny  # swap to IsAuthenticated if using JWT
from rest_framework.exceptions import ValidationError, NotFound
from .models import RepeaterActivity, RepeaterStatus, RepeaterDevice
from .serializers import RepeaterActivityCreateSerializer, RepeaterStatusSerializer
from .auth import require_device_key

class RepeaterActivityView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RepeaterActivityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        device_id = data["device"]
        # Optional device key check (POC-friendly: only checks if present in DB)
        device = require_device_key(request, device_id)

        # Create activity
        activity = RepeaterActivity.objects.create(
            device=device,
            msg_id=data["msg_id"],
            message=data["message"],
            action=data["action"],
            voltage=data.get("voltage"),
            signal_strength=data.get("signal_strength"),
            tx_power=data.get("tx_power"),
            rx_total=data["stats"]["rx_total"],
            tx_total=data["stats"]["tx_total"],
            failed=data["stats"]["failed"],
        )

        # Update status
        status, _ = RepeaterStatus.objects.get_or_create(device=device)
        status.last_seen = timezone.now()
        if data.get("voltage") is not None:
            status.voltage = data.get("voltage")
        if data.get("signal_strength") is not None:
            status.signal_strength = data.get("signal_strength")
        if data.get("tx_power") is not None:
            status.tx_power = data.get("tx_power")
        status.rx_total = data["stats"]["rx_total"]
        status.tx_total = data["stats"]["tx_total"]
        status.failed = data["stats"]["failed"]
        # naive uptime bump: assume 2 seconds per activity if online
        status.uptime_seconds = (status.uptime_seconds or 0) + 2
        status.save()

        return Response({
            "status": "success",
            "activity_id": activity.id,
            "timestamp": activity.timestamp.isoformat()
        })


class RepeaterStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        device_id = request.GET.get("device")
        if device_id:
            try:
                s = RepeaterStatus.objects.select_related("device").get(device__device=device_id)
            except RepeaterStatus.DoesNotExist:
                return Response({"repeaters": []})
            online = (timezone.now() - s.last_seen).total_seconds() < 120
            payload = {
                "device": s.device.device,
                "online": online,
                "last_seen": s.last_seen.isoformat(),
                "voltage": float(s.voltage) if s.voltage is not None else None,
                "signal_strength": s.signal_strength,
                "tx_power": s.tx_power,
                "stats": {
                    "rx_total": s.rx_total,
                    "tx_total": s.tx_total,
                    "failed": s.failed,
                    "success_rate": round((s.tx_total / s.rx_total * 100), 1) if s.rx_total > 0 else 0.0
                },
                "uptime_seconds": s.uptime_seconds or 0,
            }
            return Response({"repeaters": [payload]})
        else:
            items = []
            for s in RepeaterStatus.objects.select_related("device").all():
                online = (timezone.now() - s.last_seen).total_seconds() < 120
                items.append({
                    "device": s.device.device,
                    "online": online,
                    "last_seen": s.last_seen.isoformat(),
                    "voltage": float(s.voltage) if s.voltage is not None else None,
                    "signal_strength": s.signal_strength,
                    "tx_power": s.tx_power,
                    "stats": {
                        "rx_total": s.rx_total,
                        "tx_total": s.tx_total,
                        "failed": s.failed,
                        "success_rate": round((s.tx_total / s.rx_total * 100), 1) if s.rx_total > 0 else 0.0
                    },
                    "uptime_seconds": s.uptime_seconds or 0,
                })
            return Response({"repeaters": items})


class RepeaterHistoryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        device_id = request.GET.get("device")
        if not device_id:
            raise ValidationError("Missing required 'device' parameter")
        limit = min(int(request.GET.get("limit", 50)), 200)
        offset = int(request.GET.get("offset", 0))
        try:
            device = RepeaterDevice.objects.get(pk=device_id)
        except RepeaterDevice.DoesNotExist:
            raise NotFound("Device not found")

        qs = RepeaterActivity.objects.filter(device=device).order_by("-timestamp")
        total = qs.count()
        items = list(qs[offset:offset+limit])

        # Pair received/retransmitted by msg_id to compute relay_time_ms
        # We'll build a map of first 'received' and first subsequent 'retransmitted'
        history = []
        # Build lookup of retransmit times by msg_id (first occurring after received)
        # For speed, we can prefetch both; here, we compute per item window
        by_msg = {}
        # We traverse reverse chronological; build dict of last seen timestamps
        for a in sorted(items, key=lambda x: x.timestamp):
            d = by_msg.setdefault(a.msg_id, {"received": None, "retransmitted": None})
            if a.action == "received" and d["received"] is None:
                d["received"] = a
            elif a.action == "retransmitted" and d["retransmitted"] is None:
                d["retransmitted"] = a
        for msg_id, pair in by_msg.items():
            rec = pair["received"]
            ret = pair["retransmitted"]
            if not rec and not ret:
                continue
            received_at = rec.timestamp if rec else None
            retransmitted_at = ret.timestamp if ret else None
            relay_ms = None
            status = "pending"
            voltage = (rec.voltage if rec and rec.voltage is not None else (ret.voltage if ret else None))
            sig = (rec.signal_strength if rec and rec.signal_strength is not None else (ret.signal_strength if ret else None))
            txp = (rec.tx_power if rec and rec.tx_power is not None else (ret.tx_power if ret else None))
            msg = (rec.message if rec else (ret.message if ret else ""))
            if received_at and retransmitted_at and retransmitted_at >= received_at:
                relay_ms = int((retransmitted_at - received_at).total_seconds() * 1000)
                status = "success"
            elif received_at and not retransmitted_at:
                status = "pending"
            elif retransmitted_at and not received_at:
                status = "unknown"

            history.append({
                "id": rec.id if rec else ret.id,
                "msg_id": msg_id,
                "message": msg,
                "received_at": received_at.isoformat() if received_at else None,
                "retransmitted_at": retransmitted_at.isoformat() if retransmitted_at else None,
                "relay_time_ms": relay_ms,
                "voltage": float(voltage) if voltage is not None else None,
                "signal_strength": sig,
                "tx_power": txp,
                "status": status,
            })

        # Sort newest first
        history.sort(key=lambda x: (x["received_at"] or x["retransmitted_at"] or ""), reverse=True)
        return Response({
            "device": device_id,
            "total": total,
            "history": history,
        })


class RepeaterMetricsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        device_id = request.GET.get("device")
        period = request.GET.get("period", "24h")
        now = timezone.now()
        mapping = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
        delta = mapping.get(period, timedelta(hours=24))
        start = now - delta

        qs = RepeaterActivity.objects.filter(timestamp__gte=start, timestamp__lte=now)
        if device_id:
            qs = qs.filter(device__device=device_id)

        messages_received = qs.filter(action="received").count()
        messages_retransmitted = qs.filter(action="retransmitted").count()
        # failed is tricky; we approximate as sum of 'failed' deltas on any activity rows
        # or simply average failed and multiply by unique device count; for POC, sum of last 'failed' seen per device in period
        failed_by_device = (
            qs.order_by("device", "-timestamp")
              .distinct("device")
              .values("device", "failed")
        )
        messages_failed = sum(d.get("failed", 0) or 0 for d in failed_by_device)

        # averages
        agg = qs.aggregate(
            avg_voltage=Avg("voltage"),
            avg_signal_strength=Avg("signal_strength"),
            avg_tx_power=Avg("tx_power"),
        )
        success_rate = round((messages_retransmitted / messages_received * 100), 1) if messages_received > 0 else 0.0

        # compute timeline buckets
        bucket = TruncMinute if delta <= timedelta(hours=6) else TruncHour
        tl = (
            qs.annotate(ts=bucket("timestamp"))
              .values("ts")
              .annotate(
                  received=Count("id", filter=Q(action="received")),
                  retransmitted=Count("id", filter=Q(action="retransmitted")),
                  failed_avg=Avg("failed"),
                  voltage=Avg("voltage"),
                  signal_strength=Avg("signal_strength"),
              )
              .order_by("ts")
        )
        timeline = [{
            "timestamp": row["ts"].isoformat() if row["ts"] else None,
            "received": row["received"],
            "retransmitted": row["retransmitted"],
            "failed": int(row["failed_avg"] or 0),
            "voltage": float(row["voltage"]) if row["voltage"] is not None else None,
            "signal_strength": int(row["signal_strength"]) if row["signal_strength"] is not None else None,
        } for row in tl]

        # uptime percentage: approximate as percentage of buckets with any activity
        total_buckets = len(timeline) or 1
        active_buckets = sum(1 for r in timeline if (r["received"] or r["retransmitted"]))
        uptime_percentage = round(active_buckets / total_buckets * 100.0, 1) if total_buckets > 0 else 0.0

        device_field = device_id if device_id else None

        return Response({
            "device": device_field,
            "period": period if period in ["1h", "24h", "7d", "30d"] else "24h",
            "metrics": {
                "messages_received": messages_received,
                "messages_retransmitted": messages_retransmitted,
                "messages_failed": messages_failed,
                "success_rate": success_rate,
                "avg_relay_time_ms": None,  # not tracked directly; could be derived in future
                "avg_voltage": float(agg["avg_voltage"]) if agg["avg_voltage"] is not None else None,
                "avg_signal_strength": float(agg["avg_signal_strength"]) if agg["avg_signal_strength"] is not None else None,
                "avg_tx_power": float(agg["avg_tx_power"]) if agg["avg_tx_power"] is not None else None,
                "uptime_percentage": uptime_percentage,
            },
            "timeline": timeline
        })
