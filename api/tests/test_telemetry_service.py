from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.telemetry.logging import sanitize_telemetry_payload
from app.telemetry.service import TelemetryService


def test_sanitize_telemetry_payload_drops_sensitive_keys() -> None:
    sanitized = sanitize_telemetry_payload(
        {
            "event": "request_failed",
            "authorization": "Bearer abc",
            "session_token": "secret",
            "message": "Line 1\nLine 2",
            "details": {"password": "hidden", "status_code": 500},
        }
    )

    assert "authorization" not in sanitized
    assert "session_token" not in sanitized
    assert sanitized["event"] == "request_failed"
    assert sanitized["message"] == "Line 1 Line 2"
    assert sanitized["details"] == {"status_code": 500}


def test_slo_and_alert_scaffolding_detects_breaches() -> None:
    service = TelemetryService(settings=get_settings())

    for index in range(20):
        service.record_request(
            route_template="/projects/{project_id}",
            method="GET",
            status_code=500 if index < 8 else 200,
            duration_ms=1200 if index < 15 else 120,
            request_id=f"req-{index}",
            trace_id="trace-1",
            project_id="project-1",
        )

    service.record_readiness_database(duration_ms=400, success=True)
    service.record_audit_write(success=False, event_type="USER_LOGIN")

    snapshot = service.snapshot()
    slos = {item.key: item for item in service.evaluate_slos(snapshot)}

    assert slos["request_error_rate"].status == "BREACHING"
    assert slos["request_p95_latency"].status == "BREACHING"
    assert slos["db_readiness_latency"].status == "BREACHING"
    assert slos["audit_write_failure_rate"].status == "BREACHING"

    alerts, _ = service.list_alerts(state="OPEN", cursor=0, page_size=50)
    alert_keys = {alert.key for alert in alerts}
    assert "alert_request_error_rate" in alert_keys
    assert "alert_request_p95_latency" in alert_keys
    assert "alert_db_readiness_latency" in alert_keys


def test_timeline_filtering_and_pagination() -> None:
    service = TelemetryService(settings=get_settings())
    service.record_timeline(
        scope="api",
        severity="INFO",
        message="API event",
        request_id="req-1",
        trace_id="trace-1",
    )
    service.record_timeline(
        scope="auth",
        severity="WARNING",
        message="Auth event",
        request_id="req-2",
        trace_id="trace-2",
    )

    auth_events, auth_next = service.list_timeline(scope="auth", cursor=0, page_size=10)
    all_events_page_1, all_next = service.list_timeline(scope="all", cursor=0, page_size=1)
    all_events_page_2, all_next_2 = service.list_timeline(scope="all", cursor=1, page_size=1)

    assert len(auth_events) == 1
    assert auth_events[0].scope == "auth"
    assert auth_next is None
    assert len(all_events_page_1) == 1
    assert isinstance(all_next, int)
    assert len(all_events_page_2) == 1
    assert all_next_2 is None


def test_synthetic_threshold_breaches_flow_into_alert_state() -> None:
    service = TelemetryService(settings=get_settings())
    now = datetime.now(UTC)

    for index in range(8):
        service.record_job_claimed(enqueued_at=now - timedelta(minutes=15))
        service.record_job_completed(completed_at=now - timedelta(seconds=index))
    service.record_queue_depth(
        queue_depth=500,
        source="jobs-store",
        detail="Synthetic queue depth breach.",
    )

    service.record_model_request(
        deployment_unit="vlm-primary",
        model_key="model-a",
        duration_ms=7_000,
        success=False,
        fallback_invoked=True,
        request_id="req-1",
        trace_id="trace-1",
    )
    service.record_model_request(
        deployment_unit="vlm-primary",
        model_key="model-a",
        duration_ms=6_000,
        success=True,
        fallback_invoked=True,
        request_id="req-2",
        trace_id="trace-2",
    )
    service.record_export_review_latency(
        latency_ms=float(get_settings().export_request_sla_hours * 60 * 60 * 1000) * 2.0,
        request_id="req-export",
        trace_id="trace-export",
    )
    service.record_storage_operation(
        operation="READ",
        duration_ms=120,
        success=False,
        request_id="req-storage-read",
        trace_id="trace-storage-read",
        detail="synthetic-read-fail",
    )
    service.record_storage_operation(
        operation="WRITE",
        duration_ms=95,
        success=False,
        request_id="req-storage-write",
        trace_id="trace-storage-write",
        detail="synthetic-write-fail",
    )

    snapshot = service.snapshot()
    slos = {item.key: item for item in service.evaluate_slos(snapshot)}

    assert slos["queue_depth"].status == "BREACHING"
    assert slos["queue_latency_p95"].status == "BREACHING"
    assert slos["model_request_latency_p95"].status == "BREACHING"
    assert slos["model_error_rate"].status == "BREACHING"
    assert slos["model_fallback_invocation_rate"].status == "BREACHING"
    assert slos["export_review_latency_p95"].status == "BREACHING"
    assert slos["storage_error_rate"].status == "BREACHING"

    open_alerts, _ = service.list_alerts(state="OPEN", cursor=0, page_size=200)
    open_alert_keys = {item.key for item in open_alerts}
    assert "alert_queue_depth" in open_alert_keys
    assert "alert_queue_latency_p95" in open_alert_keys
    assert "alert_model_request_latency_p95" in open_alert_keys
    assert "alert_model_error_rate" in open_alert_keys
    assert "alert_model_fallback_invocation_rate" in open_alert_keys
    assert "alert_export_review_latency_p95" in open_alert_keys
    assert "alert_storage_error_rate" in open_alert_keys


def test_alert_state_transitions_to_ok_when_metrics_recover() -> None:
    service = TelemetryService(settings=get_settings())
    service.record_request(
        route_template="/healthz",
        method="GET",
        status_code=500,
        duration_ms=1_500,
        request_id="req-breach",
        trace_id="trace-breach",
        project_id=None,
    )
    breach_alerts, _ = service.list_alerts(state="OPEN", cursor=0, page_size=200)
    assert any(alert.key == "alert_request_error_rate" for alert in breach_alerts)

    service.reset_for_test()
    for index in range(10):
        service.record_request(
            route_template="/healthz",
            method="GET",
            status_code=200,
            duration_ms=100 + index,
            request_id=f"req-ok-{index}",
            trace_id=f"trace-ok-{index}",
            project_id=None,
        )
    recovered_alerts, _ = service.list_alerts(state="OK", cursor=0, page_size=200)
    recovered_alert_keys = {alert.key for alert in recovered_alerts}

    assert "alert_request_error_rate" in recovered_alert_keys
    assert "alert_request_p95_latency" in recovered_alert_keys
