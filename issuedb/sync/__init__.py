"""Sync support for issuedb.

The client half of the issuedb <-> Tracker sync protocol. Nothing here talks
to a network yet; this package holds the identity model that sync is built on
— the canonical uid derivation, the row ledger, and the change feed.

Standard library only, per the project's zero-dependency rule.
"""

from issuedb.sync._canonical import (
    UID_PREFIX,
    canonical_bytes,
    derived_uid,
    mint_uid,
    relation_content_hash,
    relation_uid,
)
from issuedb.sync._project import (
    ProjectIdentityError,
    get_project_uid,
    record_project_uid,
    require_project_uid,
)

__all__ = [
    "ProjectIdentityError",
    "UID_PREFIX",
    "canonical_bytes",
    "derived_uid",
    "mint_uid",
    "relation_content_hash",
    "get_project_uid",
    "record_project_uid",
    "relation_uid",
    "require_project_uid",
]
