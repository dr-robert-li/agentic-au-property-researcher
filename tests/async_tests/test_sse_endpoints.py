"""
Async tests for SSE endpoints and server health/status APIs.

Uses httpx.AsyncClient with ASGITransport to test the FastAPI app
without starting a real server.
"""
import asyncio
import json
import queue

import pytest
import httpx

from src.ui.web.server import app, progress_queues, sse_connections, sse_connections_lock


@pytest.fixture
def async_client():
    """Create an httpx async client bound to the app."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    """GET /health returns 200 with status: healthy."""
    async with async_client as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_sse_stream_not_found_run(async_client):
    """GET /api/progress/nonexistent/stream returns error SSE event."""
    async with async_client as client:
        async with client.stream("GET", "/api/progress/nonexistent-run/stream") as resp:
            assert resp.status_code == 200
            body = b""
            async for chunk in resp.aiter_bytes():
                body += chunk
                # SSE error events are short, break after first data
                if b"Run not found" in body:
                    break

    body_text = body.decode()
    assert "Run not found" in body_text


@pytest.mark.asyncio
async def test_sse_stream_delivers_progress_events(async_client):
    """SSE stream delivers progress events and completion sentinel."""
    run_id = "test-sse-progress-run"
    pq = queue.Queue(maxsize=100)
    progress_queues[run_id] = pq

    # Add 3 progress messages plus completion sentinel
    for i in range(3):
        pq.put({
            "message": f"Progress {i}",
            "percent": (i + 1) * 30,
            "timestamp": "2026-02-16T00:00:00",
        })
    pq.put(None)  # completion sentinel

    try:
        async with async_client as client:
            async with client.stream(
                "GET", f"/api/progress/{run_id}/stream"
            ) as resp:
                assert resp.status_code == 200
                body = b""
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if b"complete" in body:
                        break

        body_text = body.decode()
        # Should contain progress events
        progress_count = body_text.count("event: progress")
        assert progress_count >= 3, f"Expected >= 3 progress events, got {progress_count}"
        # Should contain completion event
        assert "event: complete" in body_text
    finally:
        progress_queues.pop(run_id, None)


@pytest.mark.asyncio
async def test_sse_connection_cleanup(async_client):
    """SSE connections are cleaned up after client disconnect.

    With ASGI transport, true client disconnect is not fully simulated,
    so we verify cleanup by sending a completion sentinel and confirming
    the sse_connections entry is removed after the stream ends.
    """
    run_id = "test-sse-cleanup-run"
    pq = queue.Queue(maxsize=100)
    progress_queues[run_id] = pq

    # Put 1 message then sentinel so stream terminates cleanly
    pq.put({
        "message": "Step 1",
        "percent": 10,
        "timestamp": "2026-02-16T00:00:00",
    })
    pq.put(None)  # completion sentinel triggers cleanup in finally block

    try:
        async with async_client as client:
            body = b""
            async with client.stream(
                "GET", f"/api/progress/{run_id}/stream"
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if b"complete" in body:
                        break

        # After stream ends, give the server a moment to run finally block
        await asyncio.sleep(0.3)

        # Verify cleanup: sse_connections should not have active tasks for this run
        with sse_connections_lock:
            if run_id in sse_connections:
                # If still present, the set should be empty
                assert len(sse_connections[run_id]) == 0, (
                    f"Expected empty connections set, got {len(sse_connections[run_id])} tasks"
                )
    finally:
        progress_queues.pop(run_id, None)
        with sse_connections_lock:
            sse_connections.pop(run_id, None)


@pytest.mark.asyncio
async def test_api_status_not_found(async_client):
    """GET /api/status/nonexistent returns error JSON."""
    async with async_client as client:
        resp = await client.get("/api/status/nonexistent-run-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("error") == "Run not found"


@pytest.mark.asyncio
async def test_cache_stats_endpoint(async_client):
    """GET /cache/stats returns cache statistics."""
    async with async_client as client:
        resp = await client.get("/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_entries" in data
