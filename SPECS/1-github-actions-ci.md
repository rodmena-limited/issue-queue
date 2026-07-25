# SPEC 1 — GitHub Actions CI/CD pipeline

- **Ticket:** issuedb #1 (`issuedb-cli context 1`)
- **Status:** in-progress → closed on merge
- **Priority:** high
- **Tag:** ci

## EARS specification

- When a commit is pushed to any branch or a pull request targets `main`, the
  CI pipeline shall run the full pytest suite on Python 3.9, 3.10, 3.11, 3.12,
  3.13 and 3.14 and fail if any test fails.
- When the CI pipeline runs, it shall install the package with its `[web]`
  optional extra so Flask-dependent tests are exercised.
- When the CI pipeline runs, it shall run `ruff check .` and `mypy issuedb` and
  fail if either reports an error.
- When the CI pipeline runs, it shall build the sdist and wheel and validate
  metadata with `twine check`.
- Where a GitHub Release is published, the release pipeline shall build the
  distribution and publish it to PyPI via OIDC Trusted Publishing, after
  verifying the built version matches the release tag.
- If any quality gate (tests, lint, type-check, build) fails, then the pipeline
  shall report failure so the merge is blocked.

## Implementation

- `.github/workflows/ci.yml` — jobs `test` (3.9–3.14 matrix), `lint & type-check`
  (pinned `ruff==0.14.6`, `mypy==1.18.2`), `build & verify dist`.
- `.github/workflows/release.yml` — jobs `verify` (3.9/3.14), `build`
  (with tag/version match check), `publish` (PyPI Trusted Publishing, `pypi`
  environment, `id-token: write`).

## One-time setup required for automated PyPI publishing

1. PyPI → project `issuedb` → Publishing → add a Trusted Publisher:
   owner `rodmena-limited`, repo `issue-queue`, workflow `release.yml`,
   environment `pypi`.
2. GitHub → repo Settings → Environments → create environment `pypi`.

## Verification

Each EARS line verified locally before commit:

- Full suite green on Python 3.9 (641 passed), 3.13 (641 passed) and 3.14
  (641 passed), package installed with `.[web]`.
- `ruff check .` → all checks passed; `mypy issuedb` → no issues in 63 files.
- `python -m build` → sdist + wheel built; `twine check` → PASSED for both.
- Tag/version-match logic exercised against tag `v2.12.0` → match.
- Live pipeline status confirmed after push via the Actions run for the branch.
