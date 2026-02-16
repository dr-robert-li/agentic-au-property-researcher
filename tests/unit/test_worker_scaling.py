"""
Unit tests for adaptive worker scaling.

Tests CPU detection, memory-aware scaling, override parameters,
minimum/maximum caps, and cgroup parsing.
"""
import sys
from unittest.mock import patch, mock_open, MagicMock

import pytest

from config.worker_scaling import (
    calculate_worker_counts,
    MAX_DISCOVERY_WORKERS,
    MAX_RESEARCH_WORKERS,
)
from config.cpu_detection import detect_cpu_limit


@pytest.mark.unit
class TestWorkerOverrides:
    """Test that manual overrides are respected."""

    def test_override_discovery_workers(self):
        """calculate_worker_counts with override_discovery=4 returns (4, _)."""
        discovery, _ = calculate_worker_counts(override_discovery=4)
        assert discovery == 4

    def test_override_research_workers(self):
        """calculate_worker_counts with override_research=3 returns (_, 3)."""
        _, research = calculate_worker_counts(override_research=3)
        assert research == 3

    def test_minimum_one_worker(self):
        """Override of 0 gets clamped to minimum 1."""
        discovery, research = calculate_worker_counts(
            override_discovery=0, override_research=0
        )
        assert discovery == 1
        assert research == 1


@pytest.mark.unit
class TestWorkerCaps:
    """Test maximum caps are respected."""

    def test_caps_respected(self):
        """Even with many CPUs, workers don't exceed maximums."""
        with patch("src.config.cpu_detection.detect_cpu_limit", return_value=100):
            # Mock psutil module for the lazy import inside calculate_worker_counts
            mock_psutil = MagicMock()
            mock_mem = MagicMock()
            mock_mem.available = 64 * 1024**3  # 64 GB
            mock_psutil.virtual_memory.return_value = mock_mem

            with patch.dict(sys.modules, {"psutil": mock_psutil}):
                discovery, research = calculate_worker_counts()
                assert discovery <= MAX_DISCOVERY_WORKERS
                assert research <= MAX_RESEARCH_WORKERS


@pytest.mark.unit
class TestCPUDetection:
    """Test CPU detection from cgroup and fallback."""

    def test_cpu_detection_fallback(self):
        """When cgroup files don't exist, falls back to os.cpu_count()."""
        with patch("config.cpu_detection._read_cgroup_v2_cpu", return_value=None):
            with patch("config.cpu_detection._read_cgroup_v1_cpu", return_value=None):
                with patch("os.cpu_count", return_value=8):
                    result = detect_cpu_limit()
                    assert result == 8

    def test_cgroup_v2_parsing(self):
        """Mock /sys/fs/cgroup/cpu.max with '200000 100000', verify returns 2."""
        m = mock_open(read_data="200000 100000\n")
        with patch("builtins.open", m):
            from config.cpu_detection import _read_cgroup_v2_cpu

            result = _read_cgroup_v2_cpu()
            assert result == 2

    def test_cgroup_v2_unlimited(self):
        """Mock cpu.max with 'max 100000', verify returns None (unlimited)."""
        m = mock_open(read_data="max 100000\n")
        with patch("builtins.open", m):
            from config.cpu_detection import _read_cgroup_v2_cpu

            result = _read_cgroup_v2_cpu()
            assert result is None


@pytest.mark.unit
class TestMemoryScaling:
    """Test memory-aware worker scaling."""

    def test_memory_scaling(self):
        """With 4GB available, workers capped by memory formula."""
        with patch("src.config.cpu_detection.detect_cpu_limit", return_value=16):
            mock_psutil = MagicMock()
            mock_mem = MagicMock()
            mock_mem.available = 4 * 1024**3  # 4 GB
            mock_psutil.virtual_memory.return_value = mock_mem

            with patch.dict(sys.modules, {"psutil": mock_psutil}):
                discovery, research = calculate_worker_counts()
                # max(1, int((4-2)/0.5)) = 4
                assert discovery <= 4
                assert research <= 4
