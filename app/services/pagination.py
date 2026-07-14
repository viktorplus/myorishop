"""Shared pagination helper (D-01/D-02/D-03, Phase 14): the single page-size
constant and page-window/ellipsis algorithm every list service must reuse —
no list may hand-roll its own "1 2 3 … 8" math.
"""

LIST_PAGE_SIZE = 20


def page_window(page: int, total_pages: int, spread: int = 2) -> list[int | str]:
    """0-based page indices to render, with `"…"` gap markers.

    Always includes the first (0) and last (total_pages - 1) page indices,
    plus `spread` pages either side of `page`. Defensive: returns `[]` when
    `total_pages <= 0`.
    """
    if total_pages <= 0:
        return []
    indices = {0, total_pages - 1}
    indices.update(range(max(0, page - spread), min(total_pages, page + spread + 1)))
    ordered = sorted(indices)
    window: list[int | str] = []
    previous: int | None = None
    for index in ordered:
        if previous is not None and index - previous > 1:
            window.append("…")
        window.append(index)
        previous = index
    return window


def paginate(rows: list, page: int) -> tuple[list, int, int]:
    """Python-side slicer: `(page_rows, total, total_pages)`.

    `total_pages` is never 0 (empty list still reports 1). An out-of-range
    `page` is clamped to the last valid page — never raises, never returns
    an empty slice for an out-of-range page.
    """
    total = len(rows)
    total_pages = max(1, -(-total // LIST_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * LIST_PAGE_SIZE
    return rows[start : start + LIST_PAGE_SIZE], total, total_pages
