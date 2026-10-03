"""Regression tests for upload concurrency and isolated completion futures."""
import asyncio

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.open_epaper_link.upload import UploadQueueHandler


@pytest.mark.parametrize("limit", [1, 2])
async def test_queue_respects_capacity_and_drains(limit):
    queue = UploadQueueHandler(max_concurrent=limit, cooldown=0)
    release = asyncio.Event()
    at_capacity = asyncio.Event()
    active = peak = 0
    uploaded = []

    async def upload(entity_id):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == limit:
            at_capacity.set()
        await release.wait()
        uploaded.append(entity_id)
        active -= 1

    completions = [await queue.add_to_queue(upload, f"open_epaper_link.{i}") for i in range(5)]
    try:
        await asyncio.wait_for(at_capacity.wait(), 1)
        assert queue._active_uploads == limit
    finally:
        release.set()
        assert await asyncio.wait_for(asyncio.gather(*completions), 3) == [None] * 5
        await queue._processor_task
    assert peak == limit
    assert len(uploaded) == 5
    assert queue._active_uploads == 0
    assert not queue._processing
    await asyncio.wait_for(queue._queue.join(), 1)


async def test_back_to_back_enqueues_start_one_processor():
    queue = UploadQueueHandler(cooldown=0)

    async def upload():
        pass

    first = await queue.add_to_queue(upload)
    processor = queue._processor_task
    second = await queue.add_to_queue(upload)
    assert queue._processor_task is processor
    assert await asyncio.gather(first, second) == [None, None]
    await processor
    third = await queue.add_to_queue(upload)
    assert queue._processor_task is not processor
    assert await third is None
    await queue._processor_task


@pytest.mark.parametrize("error", [HomeAssistantError("offline"), ValueError("broken")])
async def test_failure_belongs_to_upload_and_queue_continues(error):
    queue = UploadQueueHandler(cooldown=0)

    async def fail():
        raise error

    async def succeed():
        pass

    failed = await queue.add_to_queue(fail)
    successful = await queue.add_to_queue(succeed)
    results = await asyncio.gather(failed, successful)
    await queue._processor_task
    assert isinstance(results[0], HomeAssistantError)
    assert results[1] is None
    assert queue._active_uploads == 0


def test_invalid_capacity_rejected():
    with pytest.raises(ValueError):
        UploadQueueHandler(max_concurrent=0)
