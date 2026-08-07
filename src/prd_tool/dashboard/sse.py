"""File-watch driven Server-Sent Events stream for the dashboard."""

from __future__ import annotations

import asyncio
import json
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from pathlib import Path

from watchfiles import Change, awatch


def classify_event(
    prd_dir: Path, change_type: Change, path: Path, status_dir: Path | None = None
) -> dict[str, str] | None:
    """Convert a watchfiles event into the SSE payload we emit (or None to skip)."""
    rel = None
    is_status = False

    if status_dir:
        try:
            rel = path.relative_to(status_dir)
            is_status = True
        except ValueError:
            pass

    if rel is None:
        try:
            rel = path.relative_to(prd_dir)
        except ValueError:
            return None

    if is_status:
        if path.suffix != ".toml":
            return None
        # We classify status changes as feature changes (prd_changed) so the frontend refreshes
        return {"type": "prd_changed", "path": str(rel.with_suffix(".xml"))}

    if path.suffix != ".xml":
        return None

    if rel.name == "index.xml":
        return {"type": "index_changed", "path": str(rel)}

    if change_type == Change.deleted:
        return {"type": "index_changed", "path": str(rel)}

    if path.is_file():
        try:
            ET.parse(path)
        except (ET.ParseError, OSError):
            return {"type": "invalid", "path": str(rel)}

    return {"type": "prd_changed", "path": str(rel)}


async def watch_events(
    prd_dir: Path,
    *,
    status_dir: Path | None = None,
    stop_event: asyncio.Event | None = None,
    debounce_ms: int = 100,
) -> AsyncIterator[dict[str, str]]:
    """Yield classified events as files under prd_dir (and optionally status_dir) change."""
    kwargs = {"step": 50, "debounce": debounce_ms}
    if stop_event is not None:
        kwargs["stop_event"] = stop_event  # type: ignore[assignment]
    
    paths_to_watch = [prd_dir]
    if status_dir is not None:
        paths_to_watch.append(status_dir)
        
    async for changes in awatch(*paths_to_watch, **kwargs):  # type: ignore[arg-type]
        for change_type, path_str in changes:
            event = classify_event(prd_dir, change_type, Path(path_str), status_dir)
            if event is not None:
                yield event


async def sse_stream(prd_dir: Path, status_dir: Path | None = None) -> AsyncIterator[bytes]:
    """SSE-format generator suitable for StreamingResponse."""
    # Initial hello so the client knows the stream is alive.
    yield b": connected\n\n"
    async for event in watch_events(prd_dir, status_dir=status_dir):
        data = json.dumps(event)
        yield f"event: {event['type']}\ndata: {data}\n\n".encode()
