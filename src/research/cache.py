"""
File-based JSON cache for research API results.

Caches discovery and per-suburb research responses to avoid redundant
expensive API calls. Uses a cache index file for metadata and individual
JSON files for cached data.
"""
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for the research cache."""
    cache_dir: Path
    discovery_ttl: int = 86400      # 24 hours
    research_ttl: int = 604800      # 7 days
    enabled: bool = True


@dataclass
class CacheEntry:
    """Metadata for a single cached item."""
    key_hash: str
    filepath: str
    created_at: float
    ttl_seconds: int
    cache_type: str  # "discovery" or "research"
    key_parts: dict = field(default_factory=dict)


class ResearchCache:
    """
    File-based cache for research API results.

    Stores discovery and per-suburb research results as individual JSON files
    with a centralized index for metadata tracking.
    """

    INDEX_FILE = "cache_index.json"

    def __init__(self, config: CacheConfig):
        self.config = config
        self._lock = threading.RLock()
        self._ensure_dir()

    def _ensure_dir(self):
        """Create cache directory if it doesn't exist."""
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self.config.cache_dir / self.INDEX_FILE

    def _load_index(self) -> dict:
        """Load the cache index from disk."""
        path = self._index_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                raw = json.load(f)
            # Convert raw dicts back to CacheEntry objects
            index = {}
            for key, entry_data in raw.items():
                index[key] = CacheEntry(**entry_data)
            return index
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Corrupt cache index, resetting: %s", e)
            return {}

    def _save_index(self, index: dict):
        """Save the cache index to disk."""
        raw = {}
        for key, entry in index.items():
            raw[key] = asdict(entry)
        with open(self._index_path(), "w") as f:
            json.dump(raw, f, indent=2)

    @staticmethod
    def _make_key(cache_type: str, **parts) -> str:
        """Create a deterministic hash key from cache type and key parts."""
        # Sort parts for deterministic ordering
        sorted_parts = sorted(parts.items())
        key_string = f"{cache_type}:" + "|".join(
            f"{k}={v}" for k, v in sorted_parts
        )
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    @staticmethod
    def bucket_price(price: float, bucket_size: int = 50000) -> int:
        """Round price to nearest bucket for better cache hit rates."""
        return round(price / bucket_size) * bucket_size

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if a cache entry has expired."""
        return (time.time() - entry.created_at) > entry.ttl_seconds

    def _get_ttl(self, cache_type: str) -> int:
        """Get TTL for a cache type."""
        if cache_type == "discovery":
            return self.config.discovery_ttl
        return self.config.research_ttl

    def get(self, cache_type: str, **key_parts) -> Optional[dict]:
        """
        Retrieve cached data if available and not expired.

        Args:
            cache_type: "discovery" or "research"
            **key_parts: Key components (e.g., suburb_name, state, dwelling_type)

        Returns:
            Cached data dict, or None if not found/expired
        """
        if not self.config.enabled:
            return None

        with self._lock:
            key_hash = self._make_key(cache_type, **key_parts)
            index = self._load_index()

            entry = index.get(key_hash)
            if entry is None:
                return None

            if self._is_expired(entry):
                # Clean up expired entry
                self._remove_entry(key_hash, entry, index)
                return None

            # Read cached data file
            data_path = self.config.cache_dir / entry.filepath
            if not data_path.exists():
                # Data file missing, clean up index
                del index[key_hash]
                self._save_index(index)
                return None

            try:
                with open(data_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read cache file %s: %s", data_path, e)
                self._remove_entry(key_hash, entry, index)
                return None

    def put(self, cache_type: str, data: dict, **key_parts):
        """
        Store data in the cache.

        Args:
            cache_type: "discovery" or "research"
            data: Data dict to cache
            **key_parts: Key components
        """
        if not self.config.enabled:
            return

        with self._lock:
            key_hash = self._make_key(cache_type, **key_parts)
            filename = f"{cache_type}_{key_hash}.json"
            data_path = self.config.cache_dir / filename

            # Write data file
            with open(data_path, "w") as f:
                json.dump(data, f, indent=2)

            # Update index
            entry = CacheEntry(
                key_hash=key_hash,
                filepath=filename,
                created_at=time.time(),
                ttl_seconds=self._get_ttl(cache_type),
                cache_type=cache_type,
                key_parts=key_parts,
            )

            index = self._load_index()
            index[key_hash] = entry
            self._save_index(index)

    def invalidate(self, cache_type: str, **key_parts) -> bool:
        """
        Remove a specific cache entry.

        Returns:
            True if entry was found and removed, False otherwise
        """
        with self._lock:
            key_hash = self._make_key(cache_type, **key_parts)
            index = self._load_index()

            entry = index.get(key_hash)
            if entry is None:
                return False

            self._remove_entry(key_hash, entry, index)
            return True

    def clear(self, cache_type: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            cache_type: If provided, only clear entries of this type.
                       If None, clear all entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            index = self._load_index()
            count = 0

            keys_to_remove = []
            for key_hash, entry in index.items():
                if cache_type is None or entry.cache_type == cache_type:
                    keys_to_remove.append((key_hash, entry))

            for key_hash, entry in keys_to_remove:
                data_path = self.config.cache_dir / entry.filepath
                if data_path.exists():
                    data_path.unlink()
                del index[key_hash]
                count += 1

            self._save_index(index)
            return count

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with discovery_count, research_count, total_size_bytes,
            expired_count, oldest_timestamp, newest_timestamp
        """
        with self._lock:
            index = self._load_index()

            discovery_count = 0
            research_count = 0
            expired_count = 0
            total_size = 0
            oldest = None
            newest = None

            for entry in index.values():
                if entry.cache_type == "discovery":
                    discovery_count += 1
                else:
                    research_count += 1

                if self._is_expired(entry):
                    expired_count += 1

                data_path = self.config.cache_dir / entry.filepath
                if data_path.exists():
                    total_size += data_path.stat().st_size

                if oldest is None or entry.created_at < oldest:
                    oldest = entry.created_at
                if newest is None or entry.created_at > newest:
                    newest = entry.created_at

            return {
                "discovery_count": discovery_count,
                "research_count": research_count,
                "total_entries": discovery_count + research_count,
                "expired_count": expired_count,
                "total_size_bytes": total_size,
                "oldest_timestamp": oldest,
                "newest_timestamp": newest,
                "enabled": self.config.enabled,
            }

    def _remove_entry(self, key_hash: str, entry: CacheEntry, index: dict):
        """Remove a cache entry and its data file."""
        data_path = self.config.cache_dir / entry.filepath
        if data_path.exists():
            data_path.unlink()
        if key_hash in index:
            del index[key_hash]
        self._save_index(index)


# Singleton cache instance
_cache_instance: Optional[ResearchCache] = None


def get_cache() -> ResearchCache:
    """Get or create the singleton ResearchCache instance."""
    global _cache_instance
    if _cache_instance is None:
        from config import settings
        config = CacheConfig(
            cache_dir=settings.CACHE_DIR,
            discovery_ttl=settings.CACHE_DISCOVERY_TTL,
            research_ttl=settings.CACHE_RESEARCH_TTL,
            enabled=settings.CACHE_ENABLED,
        )
        _cache_instance = ResearchCache(config)
    return _cache_instance


def reset_cache_instance():
    """Reset the singleton (for testing)."""
    global _cache_instance
    _cache_instance = None
