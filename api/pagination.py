from rest_framework.pagination import CursorPagination


class TimestampCursorPagination(CursorPagination):
    """Cursor pagination ordered newest first.

    Stable across concurrent writes, so it is safe for live time-series feeds.
    The id tiebreaker keeps pages consistent when points share a timestamp.
    """

    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000
    ordering = ('-timestamp', '-id')
    cursor_query_param = 'cursor'
