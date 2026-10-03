"""Regression tests for service targeting and per-call upload results."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import translation

from custom_components.open_epaper_link import services
from custom_components.open_epaper_link.const import DOMAIN


@pytest.fixture
async def service_env(monkeypatch):
    queues = services.create_upload_queues()
    for queue in queues:
        queue._cooldown = 0
    monkeypatch.setattr(services, "create_upload_queues", lambda: queues)
    hass = MagicMock()
    # Localization is outside the service behavior under test.
    monkeypatch.setattr(translation, "async_get_hass", lambda: hass)
    monkeypatch.setattr(translation, "async_get_cached_translations", lambda *_: {})
    handlers = {}
    hass.services.async_register.side_effect = lambda domain, name, handler: handlers.update({name: handler})
    devices = {
        "a": SimpleNamespace(id="a", identifiers=[("other", "wrong"), (DOMAIN, "AABB")]),
        "b": SimpleNamespace(id="b", identifiers={(DOMAIN, "ble_CCDD")}),
        "foreign": SimpleNamespace(id="foreign", identifiers={("other", "a")}),
        "empty": SimpleNamespace(id="empty", identifiers=set()),
    }
    registry = MagicMock()
    registry.async_get.side_effect = devices.get
    monkeypatch.setattr(services.dr, "async_get", lambda _: registry)
    monkeypatch.setattr(services.dr, "async_entries_for_label", lambda *_: [devices["a"], devices["b"]])
    monkeypatch.setattr(services.dr, "async_entries_for_area", lambda *_: [devices["b"]])
    hub = SimpleNamespace(online=True, send_tag_cmd=AsyncMock())
    monkeypatch.setattr(services, "get_hub_from_hass", lambda _: hub)
    generator = MagicMock()
    generator.get_tag_dimensions = AsyncMock(return_value=(296, 128, "red"))
    generator.generate_custom_image = AsyncMock(return_value=b"image")
    monkeypatch.setattr(services, "ImageGen", lambda _: generator)
    monkeypatch.setattr(services, "is_ble_device", lambda *_: False)
    monkeypatch.setattr(services, "async_dispatcher_send", MagicMock())
    yield SimpleNamespace(hass=hass, handlers=handlers, hub=hub, generator=generator)
    for queue in queues:
        if queue._processor_task is not None:
            await asyncio.wait_for(queue._processor_task, 3)


@pytest.mark.parametrize("device_id,entity_id", [("a", f"{DOMAIN}.aabb"), ("b", f"{DOMAIN}.ccdd")])
async def test_matching_identifier_and_ble_prefix(service_env, device_id, entity_id):
    await services.async_setup_services(service_env.hass)
    await service_env.handlers["clear_pending"](SimpleNamespace(data={"device_id": device_id}))
    service_env.hub.send_tag_cmd.assert_awaited_once_with(entity_id, "clear")


@pytest.mark.parametrize("target", ["missing", "foreign", "empty", []])
async def test_invalid_target(service_env, target):
    await services.async_setup_services(service_env.hass)
    with pytest.raises(ServiceValidationError):
        await service_env.handlers["clear_pending"](SimpleNamespace(data={"device_id": target}))
    service_env.hub.send_tag_cmd.assert_not_awaited()


async def test_expansion_deduplicates_without_mutating_call(service_env):
    await services.async_setup_services(service_env.hass)
    data = {"device_id": ["a"], "label_id": "label", "area_id": "area"}
    await service_env.handlers["clear_pending"](SimpleNamespace(data=data))
    assert data["device_id"] == ["a"]
    assert service_env.hub.send_tag_cmd.await_count == 2


async def test_all_targets_enqueued_before_waiting(service_env, monkeypatch):
    completions = []

    async def enqueue(*args):
        completion = asyncio.get_running_loop().create_future()
        completions.append(completion)
        if len(completions) == 2:
            for future in completions:
                future.set_result(None)
        return completion

    queue = SimpleNamespace(add_to_queue=enqueue)
    monkeypatch.setattr(services, "create_upload_queues", lambda: (queue, queue))
    await services.async_setup_services(service_env.hass)
    await asyncio.wait_for(service_env.handlers["drawcustom"](
        SimpleNamespace(data={"device_id": ["a", "b"]})
    ), 1)
    assert len(completions) == 2


async def test_operational_failure_does_not_skip_remaining_targets(service_env, monkeypatch):
    uploaded = []

    async def upload(hub, entity_id, *args):
        uploaded.append(entity_id)
        if entity_id.endswith("aabb"):
            raise HomeAssistantError("first upload failed")

    monkeypatch.setattr(services, "upload_to_hub", upload)
    await services.async_setup_services(service_env.hass)
    with pytest.raises(ServiceValidationError) as exc:
        await service_env.handlers["drawcustom"](SimpleNamespace(data={"device_id": ["a", "b"]}))
    assert uploaded == [f"{DOMAIN}.aabb", f"{DOMAIN}.ccdd"]
    assert "a: first upload failed" in exc.value.translation_placeholders["errors"]


async def test_simultaneous_calls_keep_errors_separate(service_env, monkeypatch):
    async def upload(hub, entity_id, *args):
        if entity_id.endswith("aabb"):
            raise HomeAssistantError("failed a")

    monkeypatch.setattr(services, "upload_to_hub", upload)
    await services.async_setup_services(service_env.hass)
    results = await asyncio.gather(
        *(service_env.handlers["drawcustom"](SimpleNamespace(data={"device_id": target})) for target in ("a", "b")),
        return_exceptions=True,
    )
    assert isinstance(results[0], ServiceValidationError)
    assert results[1] is None


async def test_invalid_payload_and_dry_run_do_not_upload(service_env, monkeypatch):
    queue = SimpleNamespace(add_to_queue=AsyncMock())
    monkeypatch.setattr(services, "create_upload_queues", lambda: (queue, queue))
    await services.async_setup_services(service_env.hass)
    await service_env.handlers["drawcustom"](SimpleNamespace(data={"device_id": "a", "dry-run": True}))

    async def invalid_image(**kwargs):
        kwargs["error_collector"].append("invalid element")
        return b"image"

    service_env.generator.generate_custom_image.side_effect = invalid_image
    with pytest.raises(ServiceValidationError):
        await service_env.handlers["drawcustom"](SimpleNamespace(data={"device_id": "a"}))
    queue.add_to_queue.assert_not_awaited()


async def test_cancelled_caller_does_not_cancel_accepted_upload(service_env, monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    uploaded = []

    async def upload(hub, entity_id, *args):
        started.set()
        await release.wait()
        uploaded.append(entity_id)

    ble_queue, hub_queue = services.create_upload_queues()
    monkeypatch.setattr(services, "create_upload_queues", lambda: (ble_queue, hub_queue))
    monkeypatch.setattr(services, "upload_to_hub", upload)
    await services.async_setup_services(service_env.hass)
    caller = asyncio.create_task(service_env.handlers["drawcustom"](SimpleNamespace(data={"device_id": "a"})))
    try:
        await asyncio.wait_for(started.wait(), 1)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
    finally:
        release.set()
        await asyncio.wait_for(hub_queue._processor_task, 2)
    assert uploaded == [f"{DOMAIN}.aabb"]


async def test_generation_error_does_not_skip_second_device(service_env, monkeypatch):
    uploaded = []

    async def dimensions(entity_id, **kwargs):
        if entity_id.endswith("aabb"):
            raise HomeAssistantError("dimensions unavailable")
        return 296, 128, "red"

    async def upload(hub, entity_id, *args):
        uploaded.append(entity_id)

    service_env.generator.get_tag_dimensions.side_effect = dimensions
    monkeypatch.setattr(services, "upload_to_hub", upload)
    await services.async_setup_services(service_env.hass)
    with pytest.raises(ServiceValidationError):
        await service_env.handlers["drawcustom"](SimpleNamespace(data={"device_id": ["a", "b"]}))
    assert uploaded == [f"{DOMAIN}.ccdd"]
