# 15 — The entire web UI is monospace; prose should be proportional

Ticket: issuedb #15 — **OPEN, NOT STARTED.**

## Why

`issuedb/web/_base_part1.py:76` sets `body` to a monospace stack:

```css
body {
    font-family: 'JetBrains Mono', 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code',
                 'Droid Sans Mono', 'Source Code Pro', monospace;
```

Every other `font-family` declaration in the UI is `inherit`. So **all prose —
every heading, issue title and description — is set in a terminal typeface.**
Mono is for code and identifiers; prose set in it reads slower, produces a
wall-of-text texture, and reads as a developer's scratch tool rather than a
product.

The wheel also ships **four unsubsetted JetBrains Mono woff2, ~2,075 KB** of a
1.7 MB wheel.

Found when `rodmena-tracker-manager` escalated the same defect in Tracker's UI
(the operator's words: "an abomination and an insult"). I checked my own UI
rather than accept being called the benchmark, and found the identical bug by
the identical mechanism. `rodmena.co.uk` loads **Inter** (text) + **Poppins**
(display).

## EARS SPEC

- The web UI shall set all prose and UI chrome in a proportional typeface.
- The web UI shall use a monospace typeface only for code contexts: file paths,
  code references, issue keys, and CLI snippets.
- Where a font is self-hosted, the web UI shall ship a subsetted font file.
- The web UI shall not increase first-visit transferred bytes as a result of
  adding a proportional family.

## How to verify

**By computed style, not by grepping declarations.** A proportional family can
be present in the CSS while `body` still resolves to mono through an `inherit`
chain — that is exactly how this defect survives a source review. Assert the
computed family on `body` and on an `h1`, and state the measured first-visit
byte total.

## Verification method (upgraded)

Testing whether a proportional family is **declared** is not sufficient — a
family can be declared while `body` still resolves to mono through an
`inherit`/`var()` chain, and every file greps clean. That is exactly how this
defect survives a source review.

Tracker implemented this correction as `resolve_font.py`: follow `var()`
indirection through the **served** CSS and report what `body` actually
*computes* to. On their build it resolved to the JetBrains Mono stack — the
defect confirmed rather than assumed.

**A check needs three states, not two.** Their first version exited 0 when it
found *no* `font-family` at all — a vacuous pass from an empty search. Absence
must exit `PROBE BROKEN` and refuse to conclude:

| Result | Meaning |
|---|---|
| exit 1 | body resolves to a monospace stack — the defect |
| exit 0 | body resolves to a proportional face — fixed |
| exit 2 | nothing found to inspect — PROBE BROKEN, no verdict |

The matcher must also be shown able to say YES (fed `Inter`, `ui-sans-serif`,
`system-ui`, `sans-serif` it reports proportional) before its NO is trusted.

## Subsetting target

Tracker's measured result, for the same problem:

```
InterVariable-subset.woff2           62,048
JetBrainsMono-Regular-subset.woff2   17,376
JetBrainsMono-Bold-subset.woff2      18,012
total                                97,436   vs 376,440 before  = -74%
```

One variable file for every weight rather than four statics. Mono cut to
Regular + Bold — **italic and medium existed only to set prose**, so they were
serving the bug, not code. Self-hosted rather than Google Fonts: a CDN font is
a third party watching every page load, which for a tool rendering someone's
private issue tracker is not a neutral trade.
