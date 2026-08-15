"""IssueDB - A command-line issue tracking system for software development projects."""

__version__ = "2.19.0"
__author__ = "Farshid Ashouri"
__email__ = "farsheed.ashouri@gmail.com"

from issuedb.models import Issue, Priority, Status

__all__ = ["Issue", "Priority", "Status"]
