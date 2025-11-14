
from django.urls import path
from .views import (
    RepeaterActivityView,
    RepeaterStatusView,
    RepeaterHistoryView,
    RepeaterMetricsView,
)

urlpatterns = [
    path("api/repeater/activity/", RepeaterActivityView.as_view(), name="repeater_activity"),
    path("api/repeater/status/", RepeaterStatusView.as_view(), name="repeater_status"),
    path("api/repeater/history/", RepeaterHistoryView.as_view(), name="repeater_history"),
    path("api/repeater/metrics/", RepeaterMetricsView.as_view(), name="repeater_metrics"),
]
