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
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def atomic_write_json(target_path: Path, data: dict):
    """
    Atomically write JSON data to a file using temp file + rename pattern.

    Ensures that writes are durable (fsync) and atomic (os.replace).
    If process crashes during write, the target file is either complete
    or unchanged (never corrupted).

    Args:
        target_path: Destination file path
        data: Dictionary to serialize as JSON

    Raises:
        CacheError: If write operation fails
    """
    from security.exceptions import CacheError

    parent_dir = target_path.parent
    tmp_file = None
    tmp_path = None

    try:
        # Create temp file in same directory as target (ensures same filesystem)
        tmp_file = tempfile.NamedTemporaryFile(
            mode='w',
            dir=parent_dir,
            delete=False,
            prefix='.tmp_',
            suffix='.tmp'
        )
        tmp_path = Path(tmp_file.name)

        # Write JSON content
        json.dump(data, tmp_file, indent=2)
        tmp_file.flush()

        # Force write to disk (durability)
        os.fsync(tmp_file.fileno())
        tmp_file.close()

        # Atomic rename (POSIX guarantees atomicity)
        os.replace(tmp_path, target_path)

        # On POSIX, fsync the parent directory to ensure rename is durable
        if os.name != 'nt':  # Not Windows
            try:
                parent_fd = os.open(parent_dir, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            except (OSError, AttributeError):
                # If directory fsync fails (e.g., not supported), continue
                # The file write itself was still atomic
                pass

    except (OSError, IOError) as e:
        # Clean up temp file on failure
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise CacheError(
            message=f"Failed to write cache file {target_path}: {e}",
            operation="write",
            is_transient=True
        )


@dataclass
class CacheConfig:
    """Configuration for the research cache."""
    cache_dir: Path
    discovery_ttl: int = 86400      # 24 hours
    research_ttl: int = 604800      # 7 days
    enabled: bool = True
    max_size_bytes: int = 500 * 1024 * 1024  # 500 MB default


@dataclass
class CacheEntry:
    """Metadata for a single cached item."""
    key_hash: str
    filepath: str
    created_at: float
    ttl_seconds: int
    cache_type: str  # "discovery" or "research"
    key_parts: dict = field(default_factory=dict)
    size_bytes: int = 0
    last_accessed: float = 0.0


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
        self._last_orphan_cleanup_count = 0
        self._ensure_dir()
        self._cleanup_orphans()

    def _ensure_dir(self):
        """Create cache directory if it doesn't exist."""
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self.config.cache_dir / self.INDEX_FILE

    def _load_index(self) -> dict:
        """Load the cache index from disk, with backup recovery."""
        path = self._index_path()
        backup_path = Path(str(path) + '.backup')

        # Try loading main index
        if path.exists():
            try:
                with open(path, "r") as f:
                    raw = json.load(f)
                # Convert raw dicts back to CacheEntry objects
                index = {}
                for key, entry_data in raw.items():
                    index[key] = CacheEntry(**entry_data)
                return index
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"Cache index corrupted: {e}")
                # Fall through to backup recovery

        # Try loading backup index
        if backup_path.exists():
            try:
                with open(backup_path, "r") as f:
                    raw = json.load(f)
                index = {}
                for key, entry_data in raw.items():
                    index[key] = CacheEntry(**entry_data)

                logger.info(f"Restoring from backup index... ({len(index)} entries recovered)")
                # Copy backup over main
                shutil.copy2(backup_path, path)
                return index
            except (json.JSONDecodeError, TypeError, KeyError, OSError) as e:
                logger.warning(f"Backup index also corrupted: {e}")

        # Both failed, start fresh
        logger.info("Starting with empty cache index")
        return {}

    def _save_index(self, index: dict):
        """Save the cache index to disk with backup."""
        raw = {}
        for key, entry in index.items():
            raw[key] = asdict(entry)

        # Atomic write of main index
        atomic_write_json(self._index_path(), raw)

        # Create backup after successful write
        backup_path = Path(str(self._index_path()) + '.backup')
        try:
            shutil.copy2(self._index_path(), backup_path)
        except OSError as e:
            logger.warning(f"Failed to create backup index: {e}")

    def _cleanup_orphans(self):
        """Remove cache files not referenced in the index."""
        with self._lock:
            index = self._load_index()
            indexed_files = {entry.filepath for entry in index.values()}

            # Protected files that should never be deleted
            protected = {
                self.INDEX_FILE,
                self.INDEX_FILE + '.backup',
            }

            orphan_count = 0
            cache_dir = self.config.cache_dir

            # Find all cache data files
            for pattern in ['discovery_*.json', 'research_*.json']:
                for file_path in cache_dir.glob(pattern):
                    filename = file_path.name

                    # Skip if protected or indexed
                    if filename in protected or filename in indexed_files:
                        continue

                    # Delete orphan
                    try:
                        file_path.unlink()
                        logger.info(f"Deleted orphan cache file: {filename}")
                        orphan_count += 1
                    except OSError as e:
                        logger.warning(f"Failed to delete orphan {filename}: {e}")

            # Also clean up any .tmp_ files from failed writes
            for tmp_file in cache_dir.glob('.tmp_*'):
                try:
                    tmp_file.unlink()
                    logger.debug(f"Deleted temp file: {tmp_file.name}")
                except OSError:
                    pass

            self._last_orphan_cleanup_count = orphan_count
            if orphan_count > 0:
                logger.info(f"Cleaned up {orphan_count} orphaned cache files")

    def _enforce_size_limit(self, new_entry_size: int):
        """
        Enforce cache size limit by evicting LRU entries.

        Args:
            new_entry_size: Size of entry about to be added
        """
        from config import settings

        max_size_bytes = settings.CACHE_MAX_SIZE_MB * 1024 * 1024

        # No limit if configured to 0 or negative
        if max_size_bytes <= 0:
            return

        with self._lock:
            index = self._load_index()

            # Calculate current total size
            total_size = sum(entry.size_bytes for entry in index.values())

            # If we're under limit, done
            if total_size + new_entry_size <= max_size_bytes:
                return

            # Need to evict - sort by last_accessed (LRU first)
            entries_by_lru = sorted(
                index.items(),
                key=lambda item: item[1].last_accessed
            )

            # Evict until under limit
            for key_hash, entry in entries_by_lru:
                # Delete file
                data_path = self.config.cache_dir / entry.filepath
                if data_path.exists():
                    try:
                        data_path.unlink()
                        logger.info(
                            f"Evicted cache entry: {entry.filepath} "
                            f"({entry.size_bytes} bytes, LRU age: "
                            f"{time.time() - entry.last_accessed:.0f}s)"
                        )
                    except OSError as e:
                        logger.warning(f"Failed to delete {entry.filepath}: {e}")

                # Remove from index
                del index[key_hash]
                total_size -= entry.size_bytes

                # Check if we're under limit now
                if total_size + new_entry_size <= max_size_bytes:
                    break

            # Save updated index
            self._save_index(index)

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
                    data = json.load(f)

                # Update last accessed time
                entry.last_accessed = time.time()
                index[key_hash] = entry
                self._save_index(index)

                return data
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

            # Write data file atomically
            atomic_write_json(data_path, data)

            # Get file size
            file_size = data_path.stat().st_size

            # Enforce size limit BEFORE adding to index
            self._enforce_size_limit(file_size)

            # Update index
            entry = CacheEntry(
                key_hash=key_hash,
                filepath=filename,
                created_at=time.time(),
                ttl_seconds=self._get_ttl(cache_type),
                cache_type=cache_type,
                key_parts=key_parts,
                size_bytes=file_size,
                last_accessed=time.time(),
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
            expired_count, oldest_timestamp, newest_timestamp, max_size_bytes,
            orphans_cleaned_last_startup
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

                # Use entry.size_bytes if available, else stat the file
                if entry.size_bytes > 0:
                    total_size += entry.size_bytes
                else:
                    # Backward compat for old entries without size_bytes
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
                "max_size_bytes": self.config.max_size_bytes,
                "orphans_cleaned_last_startup": self._last_orphan_cleanup_count,
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
_cache_lock = threading.Lock()


def get_cache() -> ResearchCache:
    """Get or create the singleton ResearchCache instance."""
    global _cache_instance
    # Fast path: check without lock first
    if _cache_instance is not None:
        return _cache_instance
    # Slow path: acquire lock and check again (double-checked locking)
    with _cache_lock:
        if _cache_instance is None:
            from config import settings
            config = CacheConfig(
                cache_dir=settings.CACHE_DIR,
                discovery_ttl=settings.CACHE_DISCOVERY_TTL,
                research_ttl=settings.CACHE_RESEARCH_TTL,
                enabled=settings.CACHE_ENABLED,
                max_size_bytes=settings.CACHE_MAX_SIZE_MB * 1024 * 1024,
            )
            _cache_instance = ResearchCache(config)
    return _cache_instance


def reset_cache_instance():
    """Reset the singleton (for testing)."""
    global _cache_instance
    with _cache_lock:
        _cache_instance = None
