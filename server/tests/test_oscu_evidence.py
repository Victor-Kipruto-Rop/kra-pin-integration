from app.oscu_evidence import build_evidence, response_shape


def test_evidence_contains_hashes_and_shape_but_not_sensitive_values():
    payload = {"custNm": "Example Person", "custPin": "A123456789Z", "secret": "do-not-store"}
    response = {"message": "private taxpayer result", "taxpayer": {"pin": "A123456789Z"}}
    context = {"tin": "P051234567X", "bhfId": "00", "cmcKey": "branch-secret"}
    evidence = build_evidence(
        operation_id="customer-pin-info",
        endpoint_path="/customerPinInfo",
        payload=payload,
        response=response,
        tenant_context=context,
        change_reference=None,
        timestamp="2026-11-01T00:00:00+00:00",
    )
    serialized = str(evidence)
    for secret in ("Example Person", "A123456789Z", "do-not-store", "private taxpayer result", "branch-secret"):
        assert secret not in serialized
    assert evidence["request"]["payload_sha256"]
    assert evidence["response"]["sha256"]
    assert evidence["tenant_context"]["tin_present"] is True
    assert evidence["redaction"]["response_body_stored"] is False


def test_response_shape_never_includes_values():
    shape = response_shape({"token": "abc", "items": [{"pin": "secret"}]})
    assert shape["type"] == "object"
    assert "abc" not in str(shape)
    assert "secret" not in str(shape)
    assert shape["fields"]["items"]["type"] == "array"
