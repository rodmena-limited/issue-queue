# 21 — No `prefers-reduced-motion` support, and no `:active` / `:focus-visible` / `:disabled`

Ticket: issuedb #21 — **OPEN, NOT STARTED.**

## Measured, control first

```
:active          0
:hover          15      <- CONTROL: the search works, so the zeros are real
:focus-visible   0
:focus           4
:disabled        0

prefers-reduced-motion : ABSENT
  CONTROL: 5 other @media blocks found, so the search can see media queries

transitions declared : 10
animations           : 1
```

## The animation is the serious part

```css
animation: pulse 1.5s ease-in-out infinite;
```

**An indefinitely repeating animation with no way for a user to disable it.**
That is an accessibility defect rather than a polish item — WCAG 2.2 SC 2.3.3
and the vestibular-disorder guidance both target exactly this case.

## The interactive states

| state | ours | consequence |
|---|---|---|
| `:hover` | 15 rules | fine |
| `:active` | **0** | pressing a control gives no feedback — a button that is a picture of a button |
| `:focus-visible` | **0** | we use `:focus` (4), which shows a ring on mouse click too |
| `:disabled` | **0** | a disabled control looks identical to an enabled one |

## EARS SPEC

- Where the web UI declares a transition or animation, it shall suppress it
  under `prefers-reduced-motion: reduce`.
- The web UI shall style the `:active` state of interactive controls, so that
  pressing a control gives feedback.
- The web UI shall style `:focus-visible` rather than relying on `:focus`
  alone.
- The web UI shall style `:disabled` controls distinctly from enabled ones.

## How it was found

`tracker-manager-0e2462`'s motion sweep found `:active` unstyled across all 14
of Tracker's served assets — their fifth defect. **Ours is worse on three
further counts**, and their `prefers-reduced-motion` block *is* present and
global, suppressing all 6 transitions and 3 animations product-wide. We have 11
and no guard.

Their method note is the keeper: they reported reduced-motion **absent twice**
when it was present — once from a regex that stopped at the first closing brace
so a block with nested rules never matched, once from a literal
`@media (prefers-reduced-motion` **with a space** that minified CSS does not
contain. The tell was **two of their own measurements disagreeing**, one of
which was right. Running only the extractor would have shipped a false
accusation against a thorough implementation.
