"""
Checkpoint manager for pipeline crash recovery.

Saves pipeline state after discovery and periodically during research,
enabling interrupted runs to resume from the last valid checkpoint.
"""
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

from research.cache import atomic_write_json

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoints for pipeline crash recovery.

    Saves state at key milestones (discovery completion, every 5 suburbs during research)
    with atomic writes and SHA-256 checksums. Corrupted checkpoints trigger automatic
    rollback to previous valid checkpoint.
    """

    def __init__(self, run_id: str, checkpoint_dir: Path, max_checkpoints: int = 3):
        """
        Initialize checkpoint manager.

        Args:
            run_id: Unique identifier for this run
            checkpoint_dir: Base directory for checkpoints
            max_checkpoints: Maximum number of research checkpoints to retain (default: 3)
        """
        self.run_id = run_id
        self.checkpoint_dir = checkpoint_dir / run_id
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints

    def save_checkpoint(self, phase: str, state: dict, sequence: int = 0):
        """
        Save a checkpoint for the given phase.

        Args:
            phase: "discovery" or "research"
            state: State dictionary to checkpoint
            sequence: Sequence number for research checkpoints (0 for discovery)
        """
        # Determine checkpoint filename
        if sequence > 0:
            checkpoint_name = f"{phase}_{sequence:04d}"
        else:
            checkpoint_name = phase

        # Build checkpoint data
        checkpoint_data = {
            "run_id": self.run_id,
            "phase": phase,
            "sequence": sequence,
            "timestamp": time.time(),
            "state": state
        }

        # Serialize to JSON string for checksum calculation
        json_str = json.dumps(checkpoint_data, indent=2)

        # Calculate SHA-256 checksum
        checksum = hashlib.sha256(json_str.encode('utf-8')).hexdigest()

        # Write checkpoint file atomically
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.json"
        atomic_write_json(checkpoint_path, checkpoint_data)

        # Write checksum file
        checksum_path = self.checkpoint_dir / f"{checkpoint_name}.json.sha256"
        checksum_path.write_text(checksum)

        logger.info(f"Checkpoint saved: {checkpoint_name}")

        # Cleanup old checkpoints (only for research phase)
        if phase == "research":
            self._cleanup_old_checkpoints(phase)

    def load_latest_checkpoint(self, phase: str) -> Optional[dict]:
        """
        Load the latest valid checkpoint for the given phase.

        Attempts to load checkpoints in order (latest first), verifying
        checksums. Falls back to previous checkpoint if current is corrupted.

        Args:
            phase: "discovery" or "research"

        Returns:
            State dict from checkpoint, or None if no valid checkpoint found
        """
        candidates = self._get_checkpoint_candidates(phase)

        for checkpoint_path in candidates:
            checkpoint_name = checkpoint_path.stem  # Remove .json extension
            checksum_path = self.checkpoint_dir / f"{checkpoint_name}.json.sha256"

            # Skip if checksum file doesn't exist
            if not checksum_path.exists():
                logger.warning(f"Checksum file missing for {checkpoint_name}, skipping")
                continue

            try:
                # Read checkpoint file
                with open(checkpoint_path, 'r') as f:
                    checkpoint_data = json.load(f)

                # Read expected checksum
                expected_checksum = checksum_path.read_text().strip()

                # Calculate actual checksum
                json_str = json.dumps(checkpoint_data, indent=2)
                actual_checksum = hashlib.sha256(json_str.encode('utf-8')).hexdigest()

                # Verify checksum
                if actual_checksum != expected_checksum:
                    logger.warning(
                        f"Checksum mismatch for {checkpoint_name} "
                        f"(expected {expected_checksum[:8]}..., got {actual_checksum[:8]}...), "
                        f"trying previous checkpoint"
                    )
                    continue

                # Verify run_id matches
                if checkpoint_data.get("run_id") != self.run_id:
                    logger.warning(
                        f"Run ID mismatch in {checkpoint_name} "
                        f"(expected {self.run_id}, got {checkpoint_data.get('run_id')})"
                    )
                    continue

                # Valid checkpoint found
                logger.info(f"Loaded checkpoint: {checkpoint_name}")
                return checkpoint_data["state"]

            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Failed to load checkpoint {checkpoint_name}: {e}")
                continue

        # No valid checkpoint found
        logger.warning(f"No valid {phase} checkpoint found for run {self.run_id}")
        return None

    def has_checkpoint(self, phase: str) -> bool:
        """
        Check if any valid checkpoint exists for the given phase.

        Args:
            phase: "discovery" or "research"

        Returns:
            True if at least one valid checkpoint file exists
        """
        candidates = self._get_checkpoint_candidates(phase)
        return len(candidates) > 0

    def _get_checkpoint_candidates(self, phase: str) -> list[Path]:
        """
        Get list of checkpoint file candidates for the given phase.

        For discovery: returns [discovery.json] if exists
        For research: returns all research_*.json files sorted by name descending (latest first),
                      plus discovery.json as final fallback

        Args:
            phase: "discovery" or "research"

        Returns:
            List of checkpoint paths, sorted latest-first
        """
        candidates = []

        if phase == "discovery":
            discovery_path = self.checkpoint_dir / "discovery.json"
            if discovery_path.exists():
                candidates.append(discovery_path)
        elif phase == "research":
            # Get all research checkpoints, sort by name descending (latest first)
            research_files = list(self.checkpoint_dir.glob("research_*.json"))
            research_files.sort(reverse=True)
            candidates.extend(research_files)

            # Also include discovery as final fallback
            discovery_path = self.checkpoint_dir / "discovery.json"
            if discovery_path.exists():
                candidates.append(discovery_path)

        return candidates

    def _cleanup_old_checkpoints(self, phase: str):
        """
        Clean up old checkpoints, retaining only the most recent max_checkpoints.

        Only applies to research phase checkpoints (discovery checkpoint is never deleted).

        Args:
            phase: "research" (cleanup only happens for this phase)
        """
        if phase != "research":
            return

        # Get all research checkpoint files
        research_files = list(self.checkpoint_dir.glob("research_*.json"))

        # Sort by modification time, newest first
        research_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Delete files beyond max_checkpoints
        for old_checkpoint in research_files[self.max_checkpoints:]:
            try:
                # Delete checkpoint file
                old_checkpoint.unlink()

                # Delete checksum file if it exists
                checksum_path = Path(str(old_checkpoint) + ".sha256")
                if checksum_path.exists():
                    checksum_path.unlink()

                logger.info(f"Deleted old checkpoint: {old_checkpoint.name}")
            except OSError as e:
                logger.warning(f"Failed to delete old checkpoint {old_checkpoint.name}: {e}")
