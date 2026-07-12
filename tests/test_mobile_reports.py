"""Phase 11 Plan 02: /m/reports/expiry (reuses batches.expiring_batches unchanged)."""

from datetime import datetime, timedelta

from app.routes import mobile_reports


def test_expiry_report_empty_state(mobile_client_factory, session):
    client = mobile_client_factory(mobile_reports.router)
    response = client.get("/m/reports/expiry")

    assert response.status_code == 200
    assert "Партий со сроком годности нет." in response.text


def test_expiry_report_shows_overdue_marker_for_past_batch(
    mobile_client_factory, session, batch
):
    past = (datetime.now().date() - timedelta(days=5)).isoformat()
    batch.expiry = past
    batch.quantity = 5
    session.commit()

    client = mobile_client_factory(mobile_reports.router)
    response = client.get("/m/reports/expiry")

    assert response.status_code == 200
    assert "просрочено" in response.text


def test_expiry_report_no_marker_for_future_batch(mobile_client_factory, session, batch):
    future = (datetime.now().date() + timedelta(days=30)).isoformat()
    batch.expiry = future
    batch.quantity = 5
    session.commit()

    client = mobile_client_factory(mobile_reports.router)
    response = client.get("/m/reports/expiry")

    assert response.status_code == 200
    assert "просрочено" not in response.text
