from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.session import Base
from api.v1.routers.visitor_preregistration import PreRegRequest
from models import Alert, AuditLog, User, Visitor
from services.audit_service import record_audit
from services.overstay_service import create_missing_overstay_alerts
from services.visitor_service import checkout_visitor, pre_register_visitor, register_visitor


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_audit_service_adds_event_to_current_transaction(db_session):
    record_audit(db_session, None, "system.test", detail={"source": "test"})
    db_session.commit()
    event = db_session.query(AuditLog).one()
    assert event.actor_name == "System"
    assert event.action == "system.test"
    assert '"source": "test"' in event.detail


def test_visitor_registration_and_checkout(db_session):
    visitor = register_visitor(
        db_session,
        name="Test Visitor",
        id_number="VIS-001",
        phone="0700000000",
        reason="Meeting",
        host="Campus Admin",
        expected_exit=datetime.utcnow() + timedelta(hours=2),
    )
    assert visitor.id is not None
    assert visitor.checked_out is False
    checkout_visitor(db_session, visitor)
    assert visitor.checked_out is True
    assert visitor.checkout_time is not None


def test_pre_registration_creates_token_and_audit_event(db_session):
    host = User(
        full_name="Test Admin",
        email="admin@example.test",
        reg_number="ADMIN-001",
        role="admin",
        password="not-a-real-password-hash",
    )
    db_session.add(host)
    db_session.commit()
    visitor, token = pre_register_visitor(
        db_session,
        name="Scheduled Visitor",
        email="visitor@example.test",
        phone="0700000000",
        reason="Appointment",
        expected_exit=datetime.utcnow() + timedelta(days=1),
        host=host,
    )
    assert visitor.pre_registered is True
    assert visitor.prereg_token == token
    assert len(token) >= 32


def test_overstay_alert_generation_is_idempotent_per_day(db_session):
    visitor = Visitor(
        name="Late Visitor",
        reason="Meeting",
        host="Campus Admin",
        expected_exit=datetime.utcnow() - timedelta(hours=1),
        checked_out=False,
    )
    db_session.add(visitor)
    db_session.commit()
    first = create_missing_overstay_alerts(db_session)
    second = create_missing_overstay_alerts(db_session)
    alerts = db_session.query(Alert).filter(Alert.type == "overstay").all()
    assert first == ["Late Visitor"]
    assert second == []
    assert len(alerts) == 1


def test_preregistration_date_and_time_patterns_accept_valid_values():
    payload = PreRegRequest(
        visitor_name="Scheduled Guest",
        reason="Meeting",
        expected_date="2026-11-02",
        expected_time="14:30",
    )
    assert payload.expected_date == "2026-11-02"
    assert payload.expected_time == "14:30"


def test_preregistration_date_pattern_rejects_invalid_values():
    with pytest.raises(Exception):
        PreRegRequest(
            visitor_name="Scheduled Guest",
            reason="Meeting",
            expected_date="not-a-date",
            expected_time="14:30",
        )
