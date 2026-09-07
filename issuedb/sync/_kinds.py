"""The action kinds a plan can contain.

Their own module so the writer (`_apply`) and the renderer (`_render`) can
share them without either importing the other — extracted under the 550-line
cap (issuedb #24).

The distinctions are load-bearing and were each paid for:

* ``SKIP`` — we could not apply this row yet (a missing endpoint). It may
  succeed on a later sync.
* ``UNSUPPORTED`` — the SERVER sent an entity this client does not implement.
  Fixed by upgrading issuedb.
* ``MALFORMED`` — the row cannot be written as sent. A defect to report, not a
  wait. A client that called everything "unsupported" would satisfy the
  unsupported test alone, which is why both directions are asserted.
"""

from __future__ import annotations

CREATE = "create"
UPDATE = "update"
DELETE = "delete"
SKIP = "skip"
AMBIGUOUS = "ambiguous"
UNSUPPORTED = "unsupported"
MALFORMED = "malformed"
