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
