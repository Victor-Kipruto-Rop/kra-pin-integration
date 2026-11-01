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
    for secret in (
        "Example Person",
        "A123456789Z",
        "do-not-store",
        "private taxpayer result",
        "branch-secret",
    ):
        assert secret not in serialized
    assert evidence["request"]["payload_sha256"]
    assert evidence["response"]["sha256"]
    assert evidence["tenant_context"]["tin_present"] is True
    assert evidence["redaction"]["response_body_stored"] is False
    assert evidence["redaction"]["object_keys_stored"] is False
    assert evidence["request"]["payload_top_level_key_count"] == 3


def test_response_shape_never_includes_values_or_dynamic_object_keys():
    shape = response_shape({"A123456789Z": {"pin": "secret"}, "items": [{"pin": "private"}]})
    serialized = str(shape)
    assert shape["type"] == "object"
    assert "A123456789Z" not in serialized
    assert "secret" not in serialized
    assert "private" not in serialized
    assert "pin" not in serialized
    assert shape["field_shapes"][0]["type"] in {"object", "array"}
