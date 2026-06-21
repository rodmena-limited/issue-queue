"""Time tracking CLI methods."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from issuedb.cli import CLI


def timer_start(self: CLI, issue_id: int, note: str | None = None, as_json: bool = False) -> str:
    """Start a timer for an issue.

    Args:
        issue_id: Issue ID to start timer for.
        note: Optional note for this time entry.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    entry = self.repo.start_timer(issue_id, note)
    result = {
        "message": f"Timer started for issue #{issue_id}",
        "entry_id": entry.get("id"),
        "issue_id": issue_id,
    }
    if note:
        result["note"] = note
    return self.format_output(result, as_json)


def timer_stop(self: CLI, issue_id: int | None = None, as_json: bool = False) -> str:
    """Stop a timer for an issue.

    Args:
        issue_id: Issue ID (stops all running timers for this issue if None).
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    try:
        entry = self.repo.stop_timer(issue_id)
        duration = entry.get("duration_seconds", 0)
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        result = {
            "message": "Timer stopped",
            "entry_id": entry.get("id"),
            "issue_id": entry.get("issue_id"),
            "duration_seconds": duration,
            "duration_formatted": f"{hours}h {minutes}m {seconds}s",
        }
        return self.format_output(result, as_json)
    except ValueError:
        result = {"message": "No running timer found"}
        return self.format_output(result, as_json)


def timer_status(self: CLI, as_json: bool = False) -> str:
    """Show running timers.

    Args:
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    running = self.repo.get_running_timers()
    if not running:
        result = {"message": "No running timers", "timers": []}
        return self.format_output(result, as_json)

    timers = []
    for entry in running:
        # Repo already calculates elapsed_seconds
        elapsed = entry.get("elapsed_seconds", 0)
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        timers.append(
            {
                "entry_id": entry["id"],
                "issue_id": entry["issue_id"],
                "issue_title": entry.get("issue_title", ""),
                "started_at": entry["started_at"],
                "elapsed": f"{hours}h {minutes}m",
                "elapsed_seconds": elapsed,
                "note": entry.get("note"),
            }
        )

    if as_json:
        return json.dumps({"timers": timers}, indent=2)
    else:
        lines = ["Running Timers:"]
        for t in timers:
            note_str = f" - {t['note']}" if t.get("note") else ""
            lines.append(f"  #{t['issue_id']} {t['issue_title']}: {t['elapsed']}{note_str}")
        return "\n".join(lines)


def set_estimate(self: CLI, issue_id: int, hours: float, as_json: bool = False) -> str:
    """Set time estimate for an issue.

    Args:
        issue_id: Issue ID.
        hours: Estimated hours.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    self.repo.set_estimate(issue_id, hours)
    result = {
        "message": f"Estimate set for issue {issue_id}",
        "issue_id": issue_id,
        "estimated_hours": hours,
    }
    return self.format_output(result, as_json)


def time_log(self: CLI, issue_id: int, as_json: bool = False) -> str:
    """Show time entries for an issue.

    Args:
        issue_id: Issue ID.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    entries = self.repo.get_time_entries(issue_id)

    if not entries:
        result = {"message": f"No time entries for issue {issue_id}", "entries": []}
        return self.format_output(result, as_json)

    formatted = []
    total_seconds = 0
    for entry in entries:
        duration = entry.get("duration_seconds", 0) or 0
        total_seconds += duration
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        formatted.append(
            {
                "id": entry["id"],
                "started_at": entry.get("started_at"),  # Already a string from SQLite
                "ended_at": entry.get("ended_at"),
                "duration": f"{hours}h {minutes}m",
                "duration_seconds": duration,
                "note": entry.get("note"),
                "running": entry.get("ended_at") is None,
            }
        )

    total_hours = total_seconds // 3600
    total_minutes = (total_seconds % 3600) // 60

    if as_json:
        return json.dumps(
            {
                "issue_id": issue_id,
                "entries": formatted,
                "total_seconds": total_seconds,
                "total_formatted": f"{total_hours}h {total_minutes}m",
            },
            indent=2,
        )
    else:
        lines = [f"Time Log for Issue #{issue_id}:", ""]
        for e in formatted:
            status = "[RUNNING]" if e["running"] else ""
            note_str = f" - {e['note']}" if e.get("note") else ""
            lines.append(f"  {e['started_at']}: {e['duration']}{note_str} {status}")
        lines.append("")
        lines.append(f"Total: {total_hours}h {total_minutes}m")
        return "\n".join(lines)


def time_report(
    self: CLI, period: str = "all", issue_id: int | None = None, as_json: bool = False
) -> str:
    """Generate time report.

    Args:
        period: Time period (all, week, month).
        issue_id: Optional issue ID to filter by.
        as_json: Output as JSON.

    Returns:
        Formatted output.
    """
    report = self.repo.get_time_report(period, issue_id)

    if as_json:
        return json.dumps(report, indent=2)
    else:
        period_labels = {"all": "All Time", "week": "This Week", "month": "This Month"}
        period_label = period_labels.get(period, period)
        lines = [f"Time Report ({period_label})", "=" * 30]

        total_hours = report["total_seconds"] // 3600
        total_minutes = (report["total_seconds"] % 3600) // 60
        lines.append(f"Total: {total_hours}h {total_minutes}m")
        lines.append("")

        if report.get("issues"):
            lines.append("By Issue:")
            for item in report["issues"]:
                seconds = item.get("total_seconds", 0)
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                estimate_str = ""
                if item.get("estimated_hours"):
                    est_h = item["estimated_hours"]
                    if item.get("over_estimate"):
                        estimate_str = f" (est: {est_h}h) [OVER]"
                    else:
                        estimate_str = f" (est: {est_h}h)"
                issue_id = item["issue_id"]
                title = item["title"]
                lines.append(f"  #{issue_id} {title}: {hours}h {minutes}m{estimate_str}")

        return "\n".join(lines)
