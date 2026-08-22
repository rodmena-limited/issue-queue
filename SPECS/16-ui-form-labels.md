# 16 — The issue detail page has no form labels

Ticket: issuedb #16 — **OPEN, NOT STARTED.**

## Why

`_detail.py` and `_detail_part2.py` contain **zero `<label>` elements**. Their
controls are described only by placeholders, which vanish on input and are not
reliably announced by screen readers.

The house pattern already exists and is good — the create and memory forms use
labels that carry the format:

```
Title *            Due Date (YYYY-MM-DD)     Tags (comma separated)
Description        Related Issues (IDs)      Key *  /  Value *  /  Category
```

Putting the format **in the label** is the part that matters: it survives
typing. The detail page simply does not follow the pattern the rest of the UI
already sets.

The code-references, git-links and time-tracking sections additionally have no
line saying what the feature is for, and their empty state renders nothing —
quieter than a bare form, but no more explanatory.

## EARS SPEC

- Every form control on the issue detail page shall have an associated
  `<label>` element.
- The web UI shall not rely on a placeholder as the only description of a
  control.
- Where a control expects a specific format or unit, the label shall state it.
- Each of the code-references, git-links and time-tracking sections shall carry
  one line stating what the feature is for.
- Each of those sections shall show an empty state describing the feature
  rather than rendering nothing or a bare form.

## How to verify

Count controls versus associated labels in the **served** HTML. A placeholder
does not count.

## Added: form rows must share a baseline (from `tracker-manager-0e2462`, 2026-08-22)

The operator found four elements in one `/setup` row sitting at four different
vertical positions — labels 19px apart, controls 20px apart and 2px different
in height, the button on a fourth baseline. The cause was helper text inside
one column making it taller, with nothing aligning the row.

**The criterion, which is mechanical and discriminating:** for controls that are
siblings in a row, the top of each label must be equal and the top of each
control must be equal, within 1px, **measured from the rendered page**.

### Why this belongs on #16 rather than being someone else's problem

Every check in this repo's audit tooling reads the DOM or the CSS *text*. **Not
one of them could catch this**, because the markup for a broken row and a
correct row is identical. The manager had a screenshot of the defect hours
earlier and reported a word count from it — extracting text from an image
instead of looking at it.

### Status here: UNMEASURED, not PASS

`_pages2.py` uses `.form-row` with sibling labelled controls — the same
structure that failed. The CSS is a two-equal-column grid with no per-column
helper text, so their *specific* cause is absent:

```css
.form-row   { display: grid; grid-template-columns: 1fr 1fr; gap: 20px }
.form-group { margin-bottom: 24px }
.form-label { display: block; margin-bottom: 8px }
```

**But that is reasoning from CSS, which is the instrument this finding
disqualifies.** A grid with equal columns still lets each cell stack from its
own top: if one label *wraps* to two lines at a narrow width, its control drops
~19px and the row breaks — identical markup, identical CSS, broken render. The
pair `Due Date (YYYY-MM-DD)` / `Tags (comma separated)` is long enough to wrap.

There is no browser instrument in this repo, so the honest report is
**UNMEASURED**. Not a finding, and not a clean bill.
