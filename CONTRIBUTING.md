# Contributing

Thanks for looking. This is a small project with a narrow job, so the bar for changes is mostly about keeping that job narrow.

## What is most useful

**Threshold arguments.** The defaults say things like "flag if there has been no commit in twelve months". That number is a judgment call and the current one is only a starting point. If you think it is wrong, open an issue and say why. This is the most valuable kind of contribution because it is the part of the tool that is genuinely arguable.

**False positives.** If a card said `RISKY` or `YOU ALREADY HAVE THIS` and it was plainly wrong, that is a bug worth reporting. Paste the card and what you expected. These matter more than missing features, because a tool that cries wolf gets uninstalled.

**New sources.** Support for ecosystems that are not covered yet: Go, Rust, Ruby, PHP. The requirement is that the source is free, public and needs no key, so that installing this never involves signing up for anything.

**Plain language.** If a card used jargon, that is a bug. The reader is often not a developer.

## What is out of scope

- **Scores.** No 0 to 100 rating. A score invites arguing with the arithmetic instead of reading the evidence.
- **Recommendations the tool cannot support.** It reports what it measured and which line that crossed. It does not develop taste.
- **Executing anything.** It never runs install scripts or the package under evaluation, and that will not change.
- **Paid or key-gated sources.** Install has to stay a copy and paste with no signup.

## Making a change

1. Fork and branch.
2. Make the change. The whole tool is markdown, so there is no build step.
3. Test it by running `/toolcheck` on at least three real things: one healthy, one abandoned, one that overlaps with something you already have.
4. Paste the three cards in the pull request. Seeing the actual output is how changes get reviewed here.

## The one rule that cannot bend

**No guessing.** Every factual claim in a card must trace to a source that was fetched, with the date it was fetched. If a fact cannot be verified, the correct output is `UNKNOWN`.

A change that makes cards look more complete by filling gaps with plausible estimates will be rejected, however good the estimates are. The entire value of this tool is that its facts can be relied on, and that survives exactly as long as it never invents one.
