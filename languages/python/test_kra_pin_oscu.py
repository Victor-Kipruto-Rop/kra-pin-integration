import pytest
import httpx

from kra_pin_oscu import DirectOscuClient


def client():
    return DirectOscuClient("consumer", "secret", "app-id")


def test_registry_has_23_operations():
    instance = client()
    try:
        assert len(instance._operations) == 23
    finally:
        instance.close()


def test_unknown_operation_fails_before_network():
    instance = client()
    try:
        with pytest.raises(ValueError, match="Unknown OSCU"):
            instance.invoke("not-real", {}, {})
    finally:
        instance.close()


def test_mutating_operation_requires_explicit_confirmation():
    instance = client()
    try:
        with pytest.raises(ValueError, match="mutate"):
            instance.invoke("save-item", {}, {"tin": "P123", "bhfId": "00", "cmcKey": "x"})
    finally:
        instance.close()


def test_initialization_manifest_requires_only_app_id_header():
    instance = client()
    try:
        operation = instance._operations["oscu-initialization"]
        assert operation["headers"] == ["apigee_app_id"]
        assert operation["mutates"] is True
    finally:
        instance.close()


@pytest.mark.parametrize(
    "operation_response",
    [
        httpx.Response(503, json={"error": "temporary"}),
        httpx.Response(200, text="not-json"),
    ],
)
def test_mutation_ambiguous_response_is_marked_unknown(operation_response):
    import httpx

    def handler(request):
        if request.url.path == "/v1/token/generate":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        return operation_response

    instance = DirectOscuClient(
        "consumer", "secret", "app-id",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(Exception) as error:
            instance.invoke(
                "save-item", {"itemCd": "item-1"},
                {"tin": "P123", "bhfId": "00", "cmcKey": "x"},
                confirm_mutation=True,
            )
        assert getattr(error.value, "code", None) == "oscu_outcome_unknown"
        assert getattr(error.value, "outcome_unknown", False) is True
    finally:
        instance.close()
