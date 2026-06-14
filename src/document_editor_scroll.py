"""Document editor scroll synchronization utilities.

Python port of the browser-side scroll-sync logic used by the document
editor (see ``static/js/document.js``). Useful for server-side rendering,
snapshot tests, and verifying the editor's expected behaviour from
Python (issues #1496, #1501).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class LineMetrics:
    """Geometric information for a single logical line."""

    index: int
    text: str
    row_count: int
    top: int
    height: int

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class ScrollState:
    """Computed scroll state for the document editor."""

    scroll_top: int
    total_height: int
    viewport_height: int
    line_height: int
    metrics: Tuple[LineMetrics, ...]
    visible_line_indices: Tuple[int, ...]

    @property
    def max_scroll_top(self) -> int:
        return max(0, self.total_height - self.viewport_height)

    @property
    def is_at_top(self) -> bool:
        return self.scroll_top <= 0

    @property
    def is_at_bottom(self) -> bool:
        return self.scroll_top >= self.max_scroll_top

    @property
    def line_count(self) -> int:
        return len(self.metrics)


def _wrap_row_count(text: str, max_width: int) -> int:
    """Return the number of visual rows a line occupies when wrapped.

    An empty line still occupies one row (the editor must show a cursor
    and a line-number gutter entry for it). A line longer than
    ``max_width`` wraps onto additional rows.
    """
    if max_width <= 0:
        return 1
    effective = max(len(text), 1)
    # Ceiling division without floating point.
    return (effective + max_width - 1) // max_width


def _normalize_lines(
    lines: Optional[Iterable[str]],
    text: Optional[str],
) -> Tuple[str, ...]:
    if lines is None and text is None:
        return ()
    if lines is not None and text is not None:
        raise ValueError("Provide either 'lines' or 'text', not both.")
    if text is not None:
        return tuple(text.split("\n"))
    return tuple(lines)  # type: ignore[arg-type]


def document_editor_scroll(
    lines: Optional[Iterable[str]] = None,
    *,
    text: Optional[str] = None,
    scroll_top: int = 0,
    line_height: int = 20,
    max_width: int = 80,
    viewport_height: int = 400,
) -> ScrollState:
    """Compute the scroll state of the document editor.

    Parameters
    ----------
    lines:
        The logical lines of text. Mutually exclusive with ``text``.
    text:
        The full document text; will be split on ``\\n``. Mutually
        exclusive with ``lines``.
    scroll_top:
        Current vertical scroll offset in pixels. Out-of-range values
        are clamped to ``[0, max_scroll_top]``.
    line_height:
        Pixel height of a single visual row. Non-positive values are
        coerced to 1 to avoid division by zero.
    max_width:
        Maximum number of characters per visual row (for wrapping).
        Non-positive values are coerced to 1.
    viewport_height:
        Pixel height of the visible editor area. Non-positive values
        fall back to ``line_height``.

    Returns
    -------
    ScrollState
        A dataclass containing the clamped scroll position, total
        document height, per-line metrics, and the indices of the lines
        currently visible in the viewport.

    Notes
    -----
    Edge cases handled:

    * Empty document — returns an empty ``metrics`` tuple and visible list.
    * Empty lines — each still occupies one visual row.
    * Lines longer than ``max_width`` — wrap onto multiple rows.
    * ``scroll_top`` beyond content — clamped to the last valid position.
    * Negative ``scroll_top`` — clamped to 0.
    * Non-positive geometry parameters — coerced to safe positive values.
    * Passing both ``lines`` and ``text`` — raises ``ValueError``.
    """
    normalized = _normalize_lines(lines, text)

    safe_line_height = line_height if line_height > 0 else 1
    safe_max_width = max_width if max_width > 0 else 1
    safe_viewport = viewport_height if viewport_height > 0 else safe_line_height

    metrics_list: List[LineMetrics] = []
    cursor = 0
    for idx, line in enumerate(normalized):
        rows = _wrap_row_count(line, safe_max_width)
        height = rows * safe_line_height
        metrics_list.append(
            LineMetrics(
                index=idx,
                text=line,
                row_count=rows,
                top=cursor,
                height=height,
            )
        )
        cursor += height
    metrics = tuple(metrics_list)
    total_height = cursor

    max_scroll = max(0, total_height - safe_viewport)
    if scroll_top < 0:
        clamped = 0
    elif scroll_top > max_scroll:
        clamped = max_scroll
    else:
        clamped = scroll_top

    visible_end = clamped + safe_viewport
    visible_indices = tuple(
        m.index for m in metrics if m.bottom > clamped and m.top < visible_end
    )

    return ScrollState(
        scroll_top=clamped,
        total_height=total_height,
        viewport_height=safe_viewport,
        line_height=safe_line_height,
        metrics=metrics,
        visible_line_indices=visible_indices,
    )


def scroll_to_line(
    state: ScrollState,
    line_index: int,
    *,
    align: str = "top",
) -> int:
    """Return the scroll offset needed to bring ``line_index`` into view.

    ``align`` may be ``"top"`` (default), ``"center"``, or ``"bottom"``.
    Returns ``state.scroll_top`` unchanged if the line is already visible
    and ``align`` is ``"keep"`` (no-op sentinel).
    """
    if align == "keep":
        return state.scroll_top
    if not state.metrics:
        return 0
    # Clamp the requested index into the valid range.
    if line_index < 0:
        line_index = 0
    elif line_index >= len(state.metrics):
        line_index = len(state.metrics) - 1

    metric = state.metrics[line_index]
    if align == "top":
        return metric.top
    if align == "bottom":
        target = metric.bottom - state.viewport_height
        return max(0, min(target, state.max_scroll_top))
    if align == "center":
        midpoint = metric.top + metric.height // 2
        target = midpoint - state.viewport_height // 2
        return max(0, min(target, state.max_scroll_top))
    raise ValueError(f"Unknown align value: {align!r}")


def line_at_scroll(
    state: ScrollState,
    offset: Optional[int] = None,
) -> Optional[int]:
    """Return the index of the line under the given scroll offset.

    ``offset`` defaults to ``state.scroll_top``. Returns ``None`` if the
    document is empty.
    """
    if not state.metrics:
        return None
    if offset is None:
        offset = state.scroll_top
    # Clamp into the document range.
    if offset <= 0:
        return state.metrics[0].index
    if offset >= state.total_height:
        return state.metrics[-1].index
    for metric in state.metrics:
        if offset < metric.bottom:
            return metric.index
    return state.metrics[-1].index


__all__ = [
    "LineMetrics",
    "ScrollState",
    "document_editor_scroll",
    "line_at_scroll",
    "scroll_to_line",
]