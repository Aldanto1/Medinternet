"""Тесты постановки задач в очередь и логики отправки (с моками)."""
import asyncio
from unittest.mock import AsyncMock

from app.queue.tasks import enqueue_broadcast


def test_enqueue_one_job_per_recipient():
    redis = AsyncMock()
    asyncio.run(enqueue_broadcast(redis, "bid123", [10, 20, 30]))
    assert redis.enqueue_job.await_count == 3
    redis.enqueue_job.assert_any_await("send_message_task", "bid123", 20)


def test_send_task_text_blocked_marks_and_logs():
    from app.queue import worker
    from app import bot_client, db

    worker.get_broadcast_meta = AsyncMock(return_value={"kind": "text", "caption": "hi"})
    bot_client.send = AsyncMock(return_value="blocked")
    db.mark_blocked = AsyncMock()
    db.update_log_status = AsyncMock()

    result = asyncio.run(worker.send_message_task({"redis": AsyncMock()}, "bid", 42))

    assert result == "blocked"
    db.mark_blocked.assert_awaited_once_with(42)
    db.update_log_status.assert_awaited_once_with("bid", 42, "blocked")


def test_send_task_text_sent():
    from app.queue import worker
    from app import bot_client, db

    worker.get_broadcast_meta = AsyncMock(return_value={"kind": "text", "caption": "hi"})
    bot_client.send = AsyncMock(return_value="sent")
    db.mark_blocked = AsyncMock()
    db.update_log_status = AsyncMock()

    result = asyncio.run(worker.send_message_task({"redis": AsyncMock()}, "bid", 7))

    assert result == "sent"
    db.mark_blocked.assert_not_awaited()
    db.update_log_status.assert_awaited_once_with("bid", 7, "sent")


def test_send_task_media_uploads_and_caches_file_id():
    from app.queue import worker
    from app import bot_client, db

    worker.get_broadcast_meta = AsyncMock(
        return_value={"kind": "photo", "caption": "c", "filename": "a.jpg"}
    )
    worker.get_broadcast_file_id = AsyncMock(return_value=None)
    worker.get_broadcast_data = AsyncMock(return_value=b"bytes")
    worker.set_broadcast_file_id = AsyncMock()
    bot_client.send_media = AsyncMock(return_value=("sent", "FILEID123"))
    db.mark_blocked = AsyncMock()
    db.update_log_status = AsyncMock()

    ctx = {"redis": AsyncMock()}
    result = asyncio.run(worker.send_message_task(ctx, "bid", 5))

    assert result == "sent"
    # первый файл загружен → file_id закэширован для остальных получателей
    worker.set_broadcast_file_id.assert_awaited_once_with(ctx["redis"], "bid", "FILEID123")
    db.update_log_status.assert_awaited_once_with("bid", 5, "sent")
