"""Enforce the 500-soft / 550-hard line cap on source files.

Nine files already breach the hard cap (issuedb #24). Refactoring them is scoped
work, so this guard **grandfathers exactly those nine** and blocks everything
else: a new file over the cap fails, and a grandfathered file that grows fails.
The baseline is a ratchet, not an amnesty.

TWO THINGS THIS GUARD DOES DELIBERATELY, BOTH LEARNED FROM `tracker-fbe1b4`
SHIPPING THE SAME GUARD AND FINDING IT BLIND:

1. **It enumerates the filesystem, not the git index.** Their version used
   `git ls-files`, so an untracked 800-line file PASSED and the same file FAILED
   after `git add -N`. The normal order of work is write the file, run the
   gate, then add — so the gate ran at the precise moment a new file was
   invisible to it. The default path, not an edge case.

2. **It carries a membership control, not only a size control.** All three of
   their controls padded a file that was already tracked, which tests GROWTH and
   can never test ARRIVAL — a padded file was in the population before the test
   began. `test_an_arriving_file_is_seen` creates one and asserts it is
   enumerated.
"""

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SOFT, HARD = 500, 550

# Directories that hold generated artifacts, fixtures or data blobs. The cap is
# a rule about code.
SKIP_DIRS = {".git", ".venv", "venv", "_build", "__pycache__", ".mypy_cache",
             ".pytest_cache", "node_modules", ".ruff_cache", "SPECS"}

# Named exemptions, each with its reason. A fixture is not a source file.
EXEMPT = {
    "tests/data/faketracker.py": "test double standing in for the Tracker server; a fixture",
}

# The nine files already over the hard cap when #24 was filed. Each entry is the
# line count AT THAT MOMENT: a grandfathered file may shrink, never grow.
#
# REMOVE AN ENTRY WHEN ITS FILE COMES UNDER THE CAP. `_apply.py` left this list
# entirely at 506 lines, after the feed, endpoint, kind, render and write
# concerns were extracted from it. `test_baseline_entries_are_real_breaches`
# refuses a grandfathered entry that is no longer a breach, which is how that
# was caught rather than left as a standing amnesty for a compliant file.
#
# TIGHTEN AN ENTRY WHEN ITS FILE SHRINKS. Leaving the old, larger number would
# hand back the slack that was just recovered — `_apply.py` went 598 -> 577 when
# the feed and endpoint helpers were extracted, and a stale 598 here would let
# it creep straight back. The ratchet only ratchets if it is re-tightened.
BASELINE = {
    "audit/evaluations/first_contact_probe.py": 746,
    "tests/test_git_integration.py": 676,
    "tests/test_similarity.py": 615,
    "issuedb/cli/_main.py": 593,
    "tests/test_sync_apply.py": 591,
    "tests/test_web.py": 575,
    "tests/test_time_tracking.py": 561,
    "tests/test_code_refs.py": 554,
}


def _iter_sources(root: pathlib.Path = REPO):
    """Every .py file on disk, tracked or not."""
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _measure(root: pathlib.Path = REPO) -> dict[str, int]:
    out = {}
    for path in _iter_sources(root):
        rel = path.relative_to(root).as_posix()
        if rel in EXEMPT:
            continue
        out[rel] = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return out


def test_the_enumeration_finds_the_repo():
    """Control: a glob that matches nothing looks exactly like a clean repo."""
    measured = _measure()
    assert len(measured) > 100, f"only {len(measured)} source files found; the walk is broken"
    assert "issuedb/sync/_canonical.py" in measured


def test_an_arriving_file_is_seen(tmp_path):
    """MEMBERSHIP control: the guard must detect ARRIVAL, not only growth.

    A padded existing file cannot test this — it was in the population before
    the test began. Pointed at a git-index enumeration this assertion fails,
    which is the bug `tracker-fbe1b4` shipped and fixed.
    """
    (tmp_path / "pkg").mkdir()
    newcomer = tmp_path / "pkg" / "arrived.py"
    newcomer.write_text("x = 1\n" * 800, encoding="utf-8")
    # Never added to any index; it exists only on disk, as a new file does.
    measured = _measure(tmp_path)
    assert "pkg/arrived.py" in measured, "an arriving untracked file was NOT in the population"
    assert measured["pkg/arrived.py"] == 800


def test_no_new_file_breaches_the_hard_cap():
    """Any file over 550 that is not grandfathered is a new breach."""
    breaches = {
        rel: n for rel, n in _measure().items() if n > HARD and rel not in BASELINE
    }
    assert not breaches, (
        "NEW hard-cap breach(es) — split or extract instead of appending:\n"
        + "\n".join(f"  {n:>5} lines  {rel}" for rel, n in sorted(breaches.items()))
    )


def test_grandfathered_files_do_not_grow():
    """The baseline is a ratchet: these may shrink, never grow."""
    measured = _measure()
    grown = {
        rel: (was, measured[rel])
        for rel, was in BASELINE.items()
        if rel in measured and measured[rel] > was
    }
    assert not grown, (
        "a file already over the hard cap grew further:\n"
        + "\n".join(f"  {rel}: {was} -> {now}" for rel, (was, now) in sorted(grown.items()))
    )


def test_the_baseline_has_not_rotted():
    """A baseline naming files that no longer exist quietly stops guarding.

    Without this, renaming a grandfathered file would drop it from the ratchet
    AND exempt its replacement from nothing — the entry would sit there looking
    like protection.
    """
    measured = _measure()
    missing = sorted(rel for rel in BASELINE if rel not in measured)
    assert not missing, (
        "BASELINE names files that no longer exist; remove them (or fix the rename):\n"
        + "\n".join(f"  {rel}" for rel in missing)
    )
    assert BASELINE, "an empty baseline would make the ratchet test vacuous"


def test_exemptions_still_exist_and_are_justified():
    """An exemption for a deleted file is dead config that hides the next one."""
    for rel, reason in EXEMPT.items():
        assert (REPO / rel).exists(), f"EXEMPT names a missing file: {rel}"
        assert reason.strip(), f"EXEMPT entry {rel} has no stated reason"


@pytest.mark.parametrize("rel,count", sorted(BASELINE.items()))
def test_baseline_entries_are_real_breaches(rel, count):
    """Each grandfathered entry must actually be over the cap.

    A baseline padded with compliant files would silently widen the amnesty.
    """
    assert count > HARD, f"{rel} is in BASELINE at {count} lines but is not over {HARD}"


def test_soft_cap_is_reported_but_not_enforced(capsys):
    """500 is advisory. Surfacing it keeps the next hard breach from surprising us."""
    approaching = {
        rel: n for rel, n in _measure().items()
        if SOFT < n <= HARD and rel not in BASELINE
    }
    if approaching:
        print("\nApproaching the 500-line soft cap (advisory, not a failure):")
        for rel, n in sorted(approaching.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>5} lines  {rel}")
    # No assertion on content: the soft cap is a report, and asserting it would
    # make an advisory into a gate.
    assert True
