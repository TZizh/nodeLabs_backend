
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Count, Q

from .models import Transmission, RepeaterActivity
from .serializers import TransmissionSerializer, RepeaterActivitySerializer

VALID_ROLES = {"TX", "RX", "RELAY"}

@api_view(["GET"])  # unchanged
def health(request):
    return Response({"ok": True, "app": "api"}, status=200)

# ---------- Web UI queues TX ----------
@api_view(['POST'])
def tx_message(request):
    msg = (request.data.get('message') or "").strip()
    dev = request.data.get('device', 'WebUI')
    if not msg:
        return Response({'error': 'Message cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)

    tx = Transmission.objects.create(
        device=dev,
        role='TX',
        message=msg,
        status='PENDING'
    )
    
    # CRITICAL: Set msg_id to the auto-generated ID so RX can match it later
    tx.msg_id = tx.id
    tx.save()
    
    print(f"📤 Queued TX message #{tx.id} (msg_id={tx.msg_id}): {msg[:50]}")

    return Response({
        'status': 'ok',
        'id': tx.id,
        'msg_id': tx.msg_id,
        'message': 'Message queued for transmission'
    }, status=201)


# ---------- ESP32 TX pulls one pending ----------
@api_view(['GET'])
def tx_pending(request):
    pending = (Transmission.objects.filter(role='TX', status='PENDING')
               .order_by('timestamp').first())
    if not pending:
        return Response({'status': 'no_messages', 'message': None}, status=200)
    
    # Ensure msg_id is set (backwards compatibility)
    if not pending.msg_id:
        pending.msg_id = pending.id
        pending.save()
    
    return Response({
        'id': pending.id,
        'msg_id': pending.msg_id,  # Include msg_id in response
        'message': pending.message,
        'timestamp': pending.timestamp.isoformat() if pending.timestamp else None,
    }, status=200)


# ---------- ESP32 RX posts received ----------
@api_view(['POST'])
def rx_message(request):
    """
    RX endpoint does TWO things:
    1. Logs the received RF message as an RX record (for the Dashboard).
    2. Marks the matching TX message as SENT (to stop TX from retrying).
    """
    msg = (request.data.get('message') or "").strip()
    dev = request.data.get('device', 'RX001')
    msg_id = request.data.get('msg_id')

    if not msg:
        return Response({'error': 'Message cannot be empty'}, status=400)

    # STEP 1: Create RX record showing we received this message
    rx = Transmission.objects.create(
        device=dev,
        role='RX',
        message=msg,
        msg_id=msg_id,
        status='RECEIVED',
        received_at=timezone.now()
    )
    
    print(f"📥 RX received msg_id={msg_id}: {msg[:50]}")

    # STEP 2: Mark the matching TX message as SENT (so TX stops retrying)
    updated = 0
    if msg_id is not None:
        try:
            msg_id_int = int(msg_id)
            
            # Try matching by msg_id first
            updated = Transmission.objects.filter(
                role='TX',
                status='PENDING',
                msg_id=msg_id_int
            ).update(
                status='SENT',
                sent_at=timezone.now()
            )
            
            # If msg_id didn't work, try matching by id (backwards compatibility)
            if updated == 0:
                updated = Transmission.objects.filter(
                    role='TX',
                    status='PENDING',
                    id=msg_id_int
                ).update(
                    status='SENT',
                    sent_at=timezone.now(),
                    msg_id=msg_id_int  # Set msg_id if it was missing
                )
            
            if updated > 0:
                print(f"✅ Marked TX message #{msg_id_int} as SENT (RX confirmed)")
            else:
                print(f"⚠️ No matching PENDING TX found for msg_id={msg_id_int}")
                # Debug: Show what TX records exist
                all_tx = Transmission.objects.filter(role='TX').values('id', 'msg_id', 'status')[:5]
                print(f"   Recent TX records: {list(all_tx)}")
                
        except (TypeError, ValueError) as e:
            print(f"⚠️ Invalid msg_id format: {msg_id} - {e}")

    return Response({
        'status': 'ok',
        'id': rx.id,
        'message': 'Message received and logged',
        'tx_updated': updated
    }, status=201)


# ---------- List recent messages ----------
@api_view(['GET'])
def list_messages(request):
    role = request.query_params.get('role')
    status_filter = request.query_params.get('status')

    raw_limit = request.query_params.get('limit', 50)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))

    try:
        qs = Transmission.objects.all()

        if role:
            r = role.upper().strip()
            if r in VALID_ROLES:
                qs = qs.filter(role=r)

        if status_filter:
            qs = qs.filter(status=str(status_filter).upper().strip())

        qs = qs.order_by('-timestamp')[:limit]
        data = TransmissionSerializer(qs, many=True).data
        return Response(data, status=200)

    except Exception as e:
        return Response({'detail': f'messages endpoint error: {str(e)}'}, status=400)

# ---------- Stats for dashboards ----------
@api_view(['GET'])
def stats(request):
    try:
        today = timezone.now().date()
        qs = Transmission.objects.all()

        total_messages = qs.count()
        sent_today = qs.filter(role='TX', timestamp__date=today).count()
        received_today = qs.filter(role='RX', timestamp__date=today).count()

        pending_tx = qs.filter(role='TX').filter(
            Q(status='PENDING') | Q(status__isnull=True)
        ).count()

        by_role = dict(qs.values('role').annotate(count=Count('id')).values_list('role', 'count'))
        by_status = dict(qs.values('status').annotate(count=Count('id')).values_list('status', 'count'))

        return Response({
            'total_messages': total_messages,
            'sent_today': sent_today,
            'received_today': received_today,
            'pending_tx': pending_tx,
            'by_role': by_role,
            'by_status': by_status,
        }, status=200)

    except Exception as e:
        return Response({'detail': f'stats endpoint error: {str(e)}'}, status=400)

# ================== NEW: Repeater Endpoints ==================

@api_view(['POST'])
def repeater_activity(request):
    try:
        ser = RepeaterActivityCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        device, _ = RepeaterDevice.objects.get_or_create(device=data['device'])

        activity = RepeaterActivity.objects.create(
            device=device,
            msg_id=data['msg_id'],
            message=data['message'],
            action=data['action'],
            voltage=data.get('voltage'),
            signal_strength=data.get('signal_strength'),
            tx_power=data.get('tx_power'),
            rx_total=data['stats']['rx_total'],
            tx_total=data['stats']['tx_total'],
            failed=data['stats']['failed'],
        )

        status_obj, _ = RepeaterStatus.objects.get_or_create(device=device)
        status_obj.last_seen = timezone.now()
        if data.get('voltage') is not None: status_obj.voltage = data.get('voltage')
        if data.get('signal_strength') is not None: status_obj.signal_strength = data.get('signal_strength')
        if data.get('tx_power') is not None: status_obj.tx_power = data.get('tx_power')
        status_obj.rx_total = data['stats']['rx_total']
        status_obj.tx_total = data['stats']['tx_total']
        status_obj.failed = data['stats']['failed']
        status_obj.uptime_seconds = (status_obj.uptime_seconds or 0) + 2
        status_obj.save()

        return Response({'status': 'success', 'activity_id': activity.id, 'timestamp': activity.timestamp.isoformat()})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=400)


@api_view(['GET'])
def repeater_status(request):
    device_id = request.GET.get('device')
    def pack(s):
        online = (timezone.now() - s.last_seen).total_seconds() < 120
        return {
            'device': s.device.device,
            'online': online,
            'last_seen': s.last_seen.isoformat(),
            'voltage': float(s.voltage) if s.voltage is not None else None,
            'signal_strength': s.signal_strength,
            'tx_power': s.tx_power,
            'stats': {
                'rx_total': s.rx_total,
                'tx_total': s.tx_total,
                'failed': s.failed,
                'success_rate': round((s.tx_total / s.rx_total * 100), 1) if s.rx_total > 0 else 0.0
            },
            'uptime_seconds': s.uptime_seconds or 0,
        }

    if device_id:
        try:
            s = RepeaterStatus.objects.select_related('device').get(device__device=device_id)
            return Response({'repeaters': [pack(s)]})
        except RepeaterStatus.DoesNotExist:
            return Response({'repeaters': []})
    else:
        items = [pack(s) for s in RepeaterStatus.objects.select_related('device').all()]
        return Response({'repeaters': items})


@api_view(['GET'])
def repeater_history(request):
    device_id = request.GET.get('device')
    if not device_id:
        return Response({'detail': "Missing required 'device' parameter"}, status=400)
    try:
        device = RepeaterDevice.objects.get(pk=device_id)
    except RepeaterDevice.DoesNotExist:
        return Response({'detail': 'Device not found'}, status=404)

    try:
        limit = min(int(request.GET.get('limit', 50)), 200)
        offset = int(request.GET.get('offset', 0))
    except ValueError:
        limit, offset = 50, 0

    qs = RepeaterActivity.objects.filter(device=device).order_by('-timestamp')
    total = qs.count()
    items = list(qs[offset:offset+limit])

    by_msg = {}
    for a in sorted(items, key=lambda x: x.timestamp):
        d = by_msg.setdefault(a.msg_id, {'received': None, 'retransmitted': None})
        if a.action == 'received' and d['received'] is None:
            d['received'] = a
        elif a.action == 'retransmitted' and d['retransmitted'] is None:
            d['retransmitted'] = a

    history = []
    for msg_id, pair in by_msg.items():
        rec = pair['received']
        ret = pair['retransmitted']
        received_at = rec.timestamp if rec else None
        retransmitted_at = ret.timestamp if ret else None
        relay_ms = None
        status_txt = 'pending'
        voltage = (rec.voltage if rec and rec.voltage is not None else (ret.voltage if ret else None))
        sig = (rec.signal_strength if rec and rec.signal_strength is not None else (ret.signal_strength if ret else None))
        txp = (rec.tx_power if rec and rec.tx_power is not None else (ret.tx_power if ret else None))
        msg = (rec.message if rec else (ret.message if ret else ''))
        if received_at and retransmitted_at and retransmitted_at >= received_at:
            relay_ms = int((retransmitted_at - received_at).total_seconds() * 1000)
            status_txt = 'success'
        elif received_at and not retransmitted_at:
            status_txt = 'pending'
        elif retransmitted_at and not received_at:
            status_txt = 'unknown'

        history.append({
            'id': rec.id if rec else ret.id,
            'msg_id': msg_id,
            'message': msg,
            'received_at': received_at.isoformat() if received_at else None,
            'retransmitted_at': retransmitted_at.isoformat() if retransmitted_at else None,
            'relay_time_ms': relay_ms,
            'voltage': float(voltage) if voltage is not None else None,
            'signal_strength': sig,
            'tx_power': txp,
            'status': status_txt,
        })

    history.sort(key=lambda x: (x['received_at'] or x['retransmitted_at'] or ''), reverse=True)
    return Response({'device': device_id, 'total': total, 'history': history})


@api_view(['GET'])
def repeater_metrics(request):
    device_id = request.GET.get('device')
    period = request.GET.get('period', '24h')
    now = timezone.now()
    mapping = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    delta = mapping.get(period, timedelta(hours=24))
    start = now - delta

    qs = RepeaterActivity.objects.filter(timestamp__gte=start, timestamp__lte=now)
    if device_id:
        qs = qs.filter(device__device=device_id)

    messages_received = qs.filter(action='received').count()
    messages_retransmitted = qs.filter(action='retransmitted').count()

    failed_by_device = (qs.order_by('device', '-timestamp').distinct('device').values('device', 'failed'))
    messages_failed = sum(d.get('failed', 0) or 0 for d in failed_by_device)

    agg = qs.aggregate(
        avg_voltage=Avg('voltage'),
        avg_signal_strength=Avg('signal_strength'),
        avg_tx_power=Avg('tx_power'),
    )
    success_rate = round((messages_retransmitted / messages_received * 100), 1) if messages_received > 0 else 0.0

    bucket = TruncMinute if delta <= timedelta(hours=6) else TruncHour
    tl = (qs.annotate(ts=bucket('timestamp'))
            .values('ts')
            .annotate(
                received=Count('id', filter=Q(action='received')),
                retransmitted=Count('id', filter=Q(action='retransmitted')),
                failed_avg=Avg('failed'),
                voltage=Avg('voltage'),
                signal_strength=Avg('signal_strength'),
            )
            .order_by('ts'))
    timeline = [{
        'timestamp': row['ts'].isoformat() if row['ts'] else None,
        'received': row['received'],
        'retransmitted': row['retransmitted'],
        'failed': int(row['failed_avg'] or 0),
        'voltage': float(row['voltage']) if row['voltage'] is not None else None,
        'signal_strength': int(row['signal_strength']) if row['signal_strength'] is not None else None,
    } for row in tl]

    total_buckets = len(timeline) or 1
    active_buckets = sum(1 for r in timeline if (r['received'] or r['retransmitted']))
    uptime_percentage = round(active_buckets / total_buckets * 100.0, 1) if total_buckets > 0 else 0.0

    return Response({
        'device': device_id if device_id else None,
        'period': period if period in mapping else '24h',
        'metrics': {
            'messages_received': messages_received,
            'messages_retransmitted': messages_retransmitted,
            'messages_failed': messages_failed,
            'success_rate': success_rate,
            'avg_relay_time_ms': None,
            'avg_voltage': float(agg['avg_voltage']) if agg['avg_voltage'] is not None else None,
            'avg_signal_strength': float(agg['avg_signal_strength']) if agg['avg_signal_strength'] is not None else None,
            'avg_tx_power': float(agg['avg_tx_power']) if agg['avg_tx_power'] is not None else None,
            'uptime_percentage': uptime_percentage,
        },
        'timeline': timeline
    })


@api_view(['POST'])
def repeater_config(request):
    device_id = request.data.get('device')
    cfg = request.data.get('config')
    if not device_id:
        return Response({'detail': "Missing 'device'"}, status=400)
    if not isinstance(cfg, dict):
        return Response({'detail': "Missing or invalid 'config' (object)"}, status=400)
    device, _ = RepeaterDevice.objects.get_or_create(device=device_id)
    device.config = cfg
    device.save(update_fields=['config', 'updated_at'])
    return Response({'status': 'ok'})

@api_view(["POST", "GET"])
def repeater_activity(request):
    """
    POST  /api/repeater/activity/   (called by ESP32 repeater)
    GET   /api/repeater/activity/?limit=50   (optional: list recent events)
    """

    if request.method == "POST":
        device = request.data.get("device", "RPT001")
        msg_id = request.data.get("msg_id")
        message = (request.data.get("message") or "").strip()
        action = (request.data.get("action") or "received").lower().strip()

        if action not in ("received", "retransmitted"):
            action = "received"

        # optional nested stats dict
        stats_payload = request.data.get("stats") or {}
        rx_total = stats_payload.get("rx_total")
        tx_total = stats_payload.get("tx_total")
        failed = stats_payload.get("failed")

        activity = RepeaterActivity.objects.create(
            device=device,
            msg_id=msg_id,
            message=message,
            action=action,
            voltage=request.data.get("voltage"),
            signal_strength=request.data.get("signal_strength"),
            tx_power=request.data.get("tx_power"),
            rx_total=rx_total,
            tx_total=tx_total,
            failed=failed,
        )

        return Response(
            {"status": "success", "activity_id": activity.id, "timestamp": activity.timestamp},
            status=201,
        )

    # GET: list recent activity
    raw_limit = request.query_params.get("limit", 50)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))

    qs = RepeaterActivity.objects.all().order_by("-timestamp")[:limit]
    data = RepeaterActivitySerializer(qs, many=True).data
    return Response(data, status=200)

@api_view(['GET'])
def stats(request):
    try:
        today = timezone.now().date()
        qs = Transmission.objects.all()

        total_messages = qs.count()
        sent_today = qs.filter(role='TX', timestamp__date=today).count()
        received_today = qs.filter(role='RX', timestamp__date=today).count()

        pending_tx = qs.filter(role='TX').filter(
            Q(status='PENDING') | Q(status__isnull=True)
        ).count()

        by_role = dict(qs.values('role').annotate(count=Count('id')).values_list('role', 'count'))
        by_status = dict(qs.values('status').annotate(count=Count('id')).values_list('status', 'count'))

        # NEW: repeater summary
        rpt_qs = RepeaterActivity.objects.all()
        repeater = {
            "events": rpt_qs.count(),
            "received": rpt_qs.filter(action="received").count(),
            "retransmitted": rpt_qs.filter(action="retransmitted").count(),
        }

        return Response({
            'total_messages': total_messages,
            'sent_today': sent_today,
            'received_today': received_today,
            'pending_tx': pending_tx,
            'by_role': by_role,
            'by_status': by_status,
            'repeater': repeater,
        }, status=200)

    except Exception as e:
        return Response({'detail': f'stats endpoint error: {str(e)}'}, status=400)
