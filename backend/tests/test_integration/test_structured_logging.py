"""Phase 4 (production readiness, 2026-07-21): structured JSON logging, gated on
settings.log_format == "json" (default "text" keeps the existing human-readable format).
"""
import json
import logging

from config import settings
from utils.logger import _JsonFormatter, _make_formatter, request_id_var


def _make_record(message="hello world", request_id="abc12345"):
    record = logging.LogRecord(
        name="test.logger", level=logging.INFO, pathname=__file__, lineno=1,
        msg=message, args=(), exc_info=None,
    )
    record.request_id = request_id
    return record


def test_json_formatter_produces_valid_json_with_expected_fields():
    formatter = _JsonFormatter()
    record = _make_record()
    output = formatter.format(record)

    payload = json.loads(output)  # raises if not valid JSON
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "abc12345"
    assert "timestamp" in payload


def test_json_formatter_includes_exception_info():
    formatter = _JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        record = _make_record()
        record.exc_info = sys.exc_info()

    output = formatter.format(record)
    payload = json.loads(output)
    assert "ValueError" in payload["exc_info"]
    assert "boom" in payload["exc_info"]


def test_make_formatter_selects_json_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "log_format", "json")
    formatter = _make_formatter(console=True)
    assert isinstance(formatter, _JsonFormatter)


def test_make_formatter_defaults_to_text(monkeypatch):
    monkeypatch.setattr(settings, "log_format", "text")
    formatter = _make_formatter(console=True)
    assert not isinstance(formatter, _JsonFormatter)


def test_request_id_var_defaults_to_placeholder():
    assert request_id_var.get() == "-"


def test_add_request_id_middleware_sets_context_var_during_request(client):
    """End-to-end: the middleware sets request_id_var for the duration of the request, so a log
    line emitted deep in a route handler would carry the same ID as the X-Request-ID response
    header. Asserts on the response header (the observable half from outside the process) plus
    a direct check that the var resets to the default once the request completes."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) == 8
    # Reset after the request completes -- doesn't leak into whatever runs next on this "thread".
    assert request_id_var.get() == "-"
