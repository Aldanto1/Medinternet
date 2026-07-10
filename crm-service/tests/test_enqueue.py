"""Тесты постановки задач в очередь и логики отправки (с моками)."""
import asyncio
from unittest.mock import AsyncMock

from app.queue.tasks import enqueue_broadcast


def test_enqueue_one_job_per_recipient():
    redis = AsyncMock()
    asyncio.run(enqueue_broadcast(redis, "bid123", [10, 20, 30], "привет"))
    assert redis.enqueue_job.await_count == 3
    redis.enqueue_job.assert_any_await("send_message_task", "bid123", 20, "привет")


def test_send_task_blocked_marks_and_logs():
    from app.queue import worker
    from app import bot_client, db

    bot_client.send = AsyncMock(return_value="blocked")
    db.mark_blocked = AsyncMock()
    db.update_log_status = AsyncMock()

    result = asyncio.run(worker.send_message_task({}, "bid", 42, "hi"))

    assert result == "blocked"
    db.mark_blocked.assert_awaited_once_with(42)
    db.update_log_status.assert_awaited_once_with("bid", 42, "blocked")


def test_send_task_sent_does_not_mark_blocked():
    from app.queue import worker
    from app import bot_client, db

    bot_client.send = AsyncMock(return_value="sent")
    db.mark_blocked = AsyncMock()
    db.update_log_status = AsyncMock()

    result = asyncio.run(worker.send_message_task({}, "bid", 7, "hi"))

    assert result == "sent"
    db.mark_blocked.assert_not_awaited()
    db.update_log_status.assert_awaited_once_with("bid", 7, "sent")
