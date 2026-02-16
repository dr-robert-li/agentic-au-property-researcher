"""
Thread safety tests for cache, server state, and queue operations.

Tests that concurrent access to shared state produces no corruption,
lost entries, or race conditions.
"""
import copy
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

import pytest

from research.cache import ResearchCache, CacheConfig, get_cache, reset_cache_instance


# ---------------------------------------------------------------------------
# Cache concurrent write tests
# ---------------------------------------------------------------------------

@pytest.mark.concurrent
def test_concurrent_cache_writes(research_cache):
    """10 concurrent cache writes produce no corruption or lost entries."""
    barrier = threading.Barrier(10)
    errors = []

    def worker(thread_id):
        try:
            barrier.wait(timeout=5)
            key = f"thread_{thread_id}"
            data = {"thread_id": thread_id, "value": f"data_{thread_id}"}
            research_cache.put("research", data, suburb_name=key, state="qld", dwelling_type="house")
            # Read it back
            result = research_cache.get("research", suburb_name=key, state="qld", dwelling_type="house")
            if result is None:
                errors.append(f"Thread {thread_id}: get returned None after put")
            elif result["thread_id"] != thread_id:
                errors.append(f"Thread {thread_id}: data mismatch, got {result}")
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(10)]
        for f in as_completed(futures):
            f.result()  # re-raise any exceptions

    assert errors == [], f"Concurrent write errors: {errors}"

    # Verify all 10 entries are retrievable
    for i in range(10):
        key = f"thread_{i}"
        result = research_cache.get("research", suburb_name=key, state="qld", dwelling_type="house")
        assert result is not None, f"Entry for thread_{i} not found"
        assert result["thread_id"] == i


@pytest.mark.concurrent
def test_concurrent_reads_during_writes(research_cache):
    """Concurrent reads and writes don't corrupt data."""
    # Pre-populate with 5 entries
    for i in range(5):
        research_cache.put(
            "research",
            {"id": i, "original": True},
            suburb_name=f"existing_{i}", state="qld", dwelling_type="house",
        )

    barrier = threading.Barrier(10)
    read_results = {}
    read_lock = threading.Lock()
    errors = []

    def reader(thread_id):
        """Read existing entries."""
        try:
            barrier.wait(timeout=5)
            idx = thread_id % 5  # read from existing_0..4
            result = research_cache.get(
                "research",
                suburb_name=f"existing_{idx}", state="qld", dwelling_type="house",
            )
            with read_lock:
                read_results[thread_id] = result
            # Result should be valid data or None, never partial/corrupted
            if result is not None:
                assert "id" in result, f"Reader {thread_id}: corrupted data"
        except Exception as e:
            errors.append(f"Reader {thread_id}: {e}")

    def writer(thread_id):
        """Write new entries."""
        try:
            barrier.wait(timeout=5)
            research_cache.put(
                "research",
                {"id": thread_id + 100, "new": True},
                suburb_name=f"new_{thread_id}", state="nsw", dwelling_type="house",
            )
        except Exception as e:
            errors.append(f"Writer {thread_id}: {e}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        # 5 readers + 5 writers
        for i in range(5):
            futures.append(executor.submit(reader, i))
        for i in range(5):
            futures.append(executor.submit(writer, i))
        for f in as_completed(futures):
            f.result()

    assert errors == [], f"Concurrent read/write errors: {errors}"

    # Readers should have gotten valid data or None
    for tid, result in read_results.items():
        if result is not None:
            assert isinstance(result, dict), f"Reader {tid} got non-dict: {type(result)}"


@pytest.mark.concurrent
def test_concurrent_cache_invalidation(research_cache):
    """Concurrent invalidation of different keys all succeed."""
    # Pre-populate with 10 entries
    for i in range(10):
        research_cache.put(
            "research",
            {"id": i},
            suburb_name=f"inv_{i}", state="qld", dwelling_type="house",
        )

    barrier = threading.Barrier(10)
    errors = []

    def invalidator(thread_id):
        try:
            barrier.wait(timeout=5)
            result = research_cache.invalidate(
                "research",
                suburb_name=f"inv_{thread_id}", state="qld", dwelling_type="house",
            )
            if not result:
                errors.append(f"Thread {thread_id}: invalidate returned False")
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(invalidator, i) for i in range(10)]
        for f in as_completed(futures):
            f.result()

    assert errors == [], f"Invalidation errors: {errors}"

    stats = research_cache.stats()
    assert stats["total_entries"] == 0, f"Expected 0 entries, got {stats['total_entries']}"


# ---------------------------------------------------------------------------
# Server state concurrent access
# ---------------------------------------------------------------------------

@pytest.mark.concurrent
def test_server_state_concurrent_access():
    """Active/completed runs dicts are safe under concurrent lock access."""
    from src.ui.web.server import (
        active_runs, active_runs_lock,
        completed_runs, completed_runs_lock,
    )

    barrier = threading.Barrier(10)
    errors = []

    def worker(thread_id):
        try:
            barrier.wait(timeout=5)
            run_id = f"concurrent-run-{thread_id}"

            # Add to active_runs
            with active_runs_lock:
                active_runs[run_id] = {
                    "run_id": run_id,
                    "status": "running",
                    "thread": thread_id,
                }

            # Move to completed_runs
            with active_runs_lock:
                run_data = active_runs.pop(run_id)
            run_data["status"] = "completed"
            with completed_runs_lock:
                completed_runs[run_id] = run_data
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")

    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for f in as_completed(futures):
                f.result()

        assert errors == [], f"Server state errors: {errors}"

        with active_runs_lock:
            assert len(active_runs) == 0, f"Active runs not empty: {active_runs}"
        with completed_runs_lock:
            assert len(completed_runs) >= 10, f"Expected >= 10 completed, got {len(completed_runs)}"
    finally:
        # Clean up
        with active_runs_lock:
            for key in [k for k in active_runs if k.startswith("concurrent-run-")]:
                del active_runs[key]
        with completed_runs_lock:
            for key in [k for k in completed_runs if k.startswith("concurrent-run-")]:
                del completed_runs[key]


# ---------------------------------------------------------------------------
# Queue thread safety
# ---------------------------------------------------------------------------

@pytest.mark.concurrent
def test_progress_queue_thread_safety():
    """Multiple producers and one consumer process all messages."""
    q = queue.Queue(maxsize=200)
    barrier = threading.Barrier(6)  # 5 producers + 1 consumer
    received = []
    received_lock = threading.Lock()

    def producer(producer_id):
        barrier.wait(timeout=5)
        for i in range(20):
            q.put({"producer": producer_id, "msg": i}, timeout=5)

    def consumer():
        barrier.wait(timeout=5)
        count = 0
        while count < 100:
            try:
                msg = q.get(timeout=5)
                with received_lock:
                    received.append(msg)
                count += 1
            except queue.Empty:
                break

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = []
        for i in range(5):
            futures.append(executor.submit(producer, i))
        futures.append(executor.submit(consumer))
        for f in as_completed(futures):
            f.result()

    assert len(received) == 100, f"Expected 100 messages, got {len(received)}"


# ---------------------------------------------------------------------------
# Deepcopy isolation
# ---------------------------------------------------------------------------

@pytest.mark.concurrent
def test_deepcopy_isolation():
    """Deepcopy prevents cross-thread mutation of shared state."""
    shared_state = {
        "runs": {
            "run-1": {"status": "running", "data": [1, 2, 3]},
        }
    }
    lock = threading.Lock()
    barrier = threading.Barrier(2)
    mutations_leaked = []

    def mutator():
        """Read with deepcopy, mutate the copy."""
        barrier.wait(timeout=5)
        with lock:
            snapshot = copy.deepcopy(shared_state)
        # Mutate the copy
        snapshot["runs"]["run-1"]["status"] = "MUTATED"
        snapshot["runs"]["run-1"]["data"].append(999)

    def verifier():
        """Read with deepcopy, verify original is unchanged."""
        barrier.wait(timeout=5)
        import time
        time.sleep(0.05)  # Let mutator finish
        with lock:
            snapshot = copy.deepcopy(shared_state)
        if snapshot["runs"]["run-1"]["status"] != "running":
            mutations_leaked.append("status was mutated")
        if 999 in snapshot["runs"]["run-1"]["data"]:
            mutations_leaked.append("data list was mutated")

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(mutator)
        f2 = executor.submit(verifier)
        f1.result()
        f2.result()

    assert mutations_leaked == [], f"Mutations leaked: {mutations_leaked}"
    assert shared_state["runs"]["run-1"]["status"] == "running"
    assert 999 not in shared_state["runs"]["run-1"]["data"]


# ---------------------------------------------------------------------------
# Singleton cache thread safety
# ---------------------------------------------------------------------------

@pytest.mark.concurrent
def test_singleton_cache_thread_safety(temp_cache_dir):
    """get_cache() from 10 simultaneous threads returns the same instance."""
    reset_cache_instance()

    # Patch settings attributes at the config.settings module level
    # (cache.py imports settings lazily inside get_cache())
    import config.settings as _settings
    orig_cache_dir = _settings.CACHE_DIR
    orig_disc_ttl = _settings.CACHE_DISCOVERY_TTL
    orig_res_ttl = _settings.CACHE_RESEARCH_TTL
    orig_enabled = _settings.CACHE_ENABLED
    orig_max_size = _settings.CACHE_MAX_SIZE_MB

    _settings.CACHE_DIR = temp_cache_dir
    _settings.CACHE_DISCOVERY_TTL = 60
    _settings.CACHE_RESEARCH_TTL = 120
    _settings.CACHE_ENABLED = True
    _settings.CACHE_MAX_SIZE_MB = 100

    try:
        barrier = threading.Barrier(10)
        instances = []
        instances_lock = threading.Lock()

        def worker():
            barrier.wait(timeout=5)
            instance = get_cache()
            with instances_lock:
                instances.append(id(instance))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            for f in as_completed(futures):
                f.result()

        # All threads should get the same instance
        assert len(instances) == 10
        assert len(set(instances)) == 1, f"Got {len(set(instances))} different instances"
    finally:
        # Restore original settings
        _settings.CACHE_DIR = orig_cache_dir
        _settings.CACHE_DISCOVERY_TTL = orig_disc_ttl
        _settings.CACHE_RESEARCH_TTL = orig_res_ttl
        _settings.CACHE_ENABLED = orig_enabled
        _settings.CACHE_MAX_SIZE_MB = orig_max_size
        reset_cache_instance()
