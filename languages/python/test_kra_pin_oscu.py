import pytest

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
