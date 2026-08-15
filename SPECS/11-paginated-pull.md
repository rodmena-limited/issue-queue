# 11 — `sync` reads only the first page of a paginated pull

Ticket: issuedb #11

## Why

The server paginates `/v1/sync/pull` and says so in `has_more`. The client never
asked. That was correct for as long as every feed fit in one page, and it broke
silently the moment one did not:

- `issuedb-cli sync` printed *"Pulled 200 change(s)"* — a real number, and not
  the answer to the question the user asked. Nothing errored.
- The dry run therefore described a fraction of what `--apply` would do, which
  is the specific failure the dry run exists to prevent.
- The first-contact probe reported **"DIVERGENCE: the entry created by THIS RUN
  did not come back from pull"** — a false accusation against a correct server.
  The push was fine; the newest change was on the **last** page, which is
  exactly the page a single read never sees.

Nothing changed in either codebase. Only the data grew past 200 changes. A check
that had been passing for hours became wrong on its own.

## EARS SPEC

- When the server reports `has_more` on a pull, the sync command shall request
  further pages until the server reports no more.
- The sync command shall report the number of pages read whenever more than one
  page was needed.
- If the page bound is reached while the server still reports more, then the
  sync command shall warn on stderr that the run covers only part of the feed,
  and shall not present the run as complete.
- When applying, the sync command shall apply the changes from every page read,
  and shall advance the cursor only to the last durably committed change.
- The first-contact probe shall walk the whole feed before concluding that an
  entry is absent, and if it stops early it shall report `PROBE BROKEN` rather
  than a server defect.

## Verification

`tests/test_sync_pagination.py`, four tests, **proven able to go red**: reverting
the loop to single-page behaviour fails three of them, including the one that
matters —

    assert "issue 450" in titles, "PAGE 3 DID NOT LAND — the feed was truncated"

The fourth (a single-page feed must not print "over 1 pages") correctly stays
green, because it is the control against over-correcting.

Asserting only the printed count would pass against a client that reads every
page and applies the first, so the apply test asserts **rows in the database**
from pages 1, 2 and 3, and the final cursor.

Through the product's own interface against the live server at `49b64ab`:

    Pulled 264 change(s) over 2 pages from cursor c:0.
    264 change(s): 203 create, 61 skip

Previously the same command reported 181, then 200 — the page cap, mistaken for
the feed.

Probe, same build, after the fix: `pull -> 240 change(s) over 2 page(s)`, *the
entry written by THIS RUN came back (page 2)*. Control run separately: a uid
that was never pushed is still correctly **not** found after a full walk, so the
fix did not turn a false negative into a check that cannot go red.
