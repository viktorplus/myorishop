"""Phase 14 (LIST-01) executable contract: the shared pagination helper
module (D-01/D-02/D-03) — LIST_PAGE_SIZE, page_window, paginate.
"""

from app.services.pagination import LIST_PAGE_SIZE, page_window, paginate


def test_page_size_constant():
    assert LIST_PAGE_SIZE == 20


def test_page_window_single_page():
    assert page_window(0, 1) == [0]


def test_page_window_empty():
    assert page_window(0, 0) == []


def test_page_window_with_ellipsis_gaps():
    assert page_window(5, 10) == [0, "…", 3, 4, 5, 6, 7, "…", 9]


def test_paginate_empty_list():
    assert paginate([], 0) == ([], 0, 1)


def test_paginate_first_page():
    rows, total, total_pages = paginate(list(range(45)), 0)
    assert rows == list(range(20))
    assert total == 45
    assert total_pages == 3


def test_paginate_clamps_out_of_range_page():
    rows, total, total_pages = paginate(list(range(45)), 5)
    assert rows == list(range(40, 45))
    assert total == 45
    assert total_pages == 3
