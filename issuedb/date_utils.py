"""Date parsing utilities for enhanced search functionality."""

import re
from datetime import datetime, timedelta
from typing import Optional


def parse_date(date_str: str) -> datetime:
    """Parse a date string into a datetime object.

    Supports the following formats:
    - YYYY-MM-DD (e.g., "2025-11-26")
    - "today" - current date at 00:00:00
    - "yesterday" - previous day at 00:00:00
    - "Nd" - N days ago (e.g., "7d" = 7 days ago)
    - "Nw" - N weeks ago (e.g., "2w" = 2 weeks ago)
    - "Nm" - N months ago (e.g., "1m" = 1 month ago)

    Args:
        date_str: Date string to parse.

    Returns:
        datetime: Parsed datetime object.

    Raises:
        ValueError: If date string format is invalid.
    """
    date_str = date_str.strip().lower()
    now = datetime.now()

    # Handle "today"
    if date_str == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Handle "yesterday"
    if date_str == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Handle relative dates (Nd, Nw, Nm)
    relative_pattern = re.match(r"^(\d+)([dwm])$", date_str)
    if relative_pattern:
        amount = int(relative_pattern.group(1))
        unit = relative_pattern.group(2)

        if unit == "d":
            # Days ago
            return now - timedelta(days=amount)
        elif unit == "w":
            # Weeks ago
            return now - timedelta(weeks=amount)
        elif unit == "m":
            # Months ago (approximate as 30 days)
            return now - timedelta(days=amount * 30)

    # Handle YYYY-MM-DD format
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass

    # If nothing matched, raise error
    raise ValueError(
        f"Invalid date format: '{date_str}'. "
        "Supported formats: YYYY-MM-DD, 'today', 'yesterday', 'Nd', 'Nw', 'Nm'"
    )


def format_date_for_display(dt: datetime) -> str:
    """Format a datetime object for human-readable display.

    Args:
        dt: datetime object to format.

    Returns:
        str: Formatted date string (YYYY-MM-DD HH:MM:SS).
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> None:
    """Validate that a date range is logical.

    Args:
        start_date: Start of date range.
        end_date: End of date range.

    Raises:
        ValueError: If end_date is before start_date.
    """
    if start_date and end_date and end_date < start_date:
        raise ValueError(
            f"End date ({format_date_for_display(end_date)}) "
            f"cannot be before start date ({format_date_for_display(start_date)})"
        )
