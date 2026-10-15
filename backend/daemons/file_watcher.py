"""Background daemon for monitoring local folders and detecting file additions/modifications."""

import logging
from pathlib import Path

from app.api.sync_hub import sync_hub
from app.config import get_settings
from daemons.manager import BaseDaemon

logger = logging.getLogger("aria.daemons.file_watcher")


class FileWatcherDaemon(BaseDaemon):
    """Monitors whitelisted directories for new, modified, or removed files."""

    name = "file_watcher"
    interval_seconds = 15.0

    def __init__(self, watch_roots: list[Path] | None = None) -> None:
        super().__init__()
        self._watch_roots = watch_roots
        self._file_snapshots: dict[str, tuple[float, int]] = {}  # path -> (mtime, size)
        self._initialized = False

    def _get_roots(self) -> list[Path]:
        if self._watch_roots is not None:
            return self._watch_roots
        settings = get_settings()
        return settings.whitelisted_directories

    async def run_iteration(self) -> None:
        """Poll directories and detect file modifications."""
        roots = self._get_roots()
        current_state: dict[str, tuple[float, int]] = {}

        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for item in root.rglob("*"):
                # Skip hidden files or git objects
                if any(part.startswith(".") for part in item.parts):
                    continue
                if item.is_file():
                    try:
                        st = item.stat()
                        current_state[str(item)] = (st.st_mtime, st.st_size)
                    except OSError:
                        continue

        if not self._initialized:
            self._file_snapshots = current_state
            self._initialized = True
            self._extra_meta = {"total_files_watched": len(current_state)}
            return

        added: list[str] = []
        modified: list[str] = []
        removed: list[str] = []

        # Detect additions & modifications
        for fpath, (mtime, size) in current_state.items():
            if fpath not in self._file_snapshots:
                added.append(fpath)
            else:
                old_mtime, old_size = self._file_snapshots[fpath]
                if mtime > old_mtime or size != old_size:
                    modified.append(fpath)

        # Detect removals
        for fpath in self._file_snapshots:
            if fpath not in current_state:
                removed.append(fpath)

        self._file_snapshots = current_state
        self._extra_meta = {
            "total_files_watched": len(current_state),
            "last_changes": {
                "added": len(added),
                "modified": len(modified),
                "removed": len(removed),
            },
        }

        if added or modified or removed:
            logger.info(
                f"FileWatcher detected changes: +{len(added)} ~{len(modified)} -{len(removed)}"
            )
            try:
                await sync_hub.broadcast_all(
                    {
                        "type": "file_watcher_event",
                        "added": added,
                        "modified": modified,
                        "removed": removed,
                    }
                )
            except Exception as exc:
                logger.debug(f"Broadcast file watcher notice: {exc}")


__all__ = ["FileWatcherDaemon"]
