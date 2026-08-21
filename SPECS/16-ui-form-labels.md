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
