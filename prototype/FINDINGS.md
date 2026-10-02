# Prototype findings

What the front-page prototype has settled, and what it hasn't. Tagged Decided (Alex said so), Proposed (Claude's, awaiting a yes) or Unverified.

### Decided, 2026-10-02

- **Start simple, add detail until something becomes unworkable.** Less is more, no busy pages. Navigation carries no metadata.
- **Three anchors**, NGT, Personal and VOS, as the high-level anchor points.
- **Left nav is the starting point**: the tree, a kind pill and last touched per node, done nodes faded. Expand and collapse per node, plus Expand all and Collapse all, remembered in the browser.
- **Last touched matters** more than status: "have I not looked at this for a while".
- **Anchor page**: aim, then Needs attention (blocked, due, untouched 30d+), "All quiet" when empty.
- **Node page**: name, kind, last touched, aim, then an Objectives section that is always present, "None yet" when empty. Old-shape nodes show Done when below it, flagged.
- **Objectives numbered**, plain numbers, no O1 labels for now.
- **Objectives in a container**, a card with a section break after it.
- **State section, no AI summary.** Its own container below Objectives: status pill, Next (the STATE `next:` line plus Notion next tasks), Blocked and Waiting only when present, Backlog folded with a count, a source letter per row. An AI pass is for cross-source reconciliation later, on demand and cached, never on page load.
- **System pills** on the node page's top line: Vault, Notion, Repo, only those the node uses, last touch per system on hover.
- **Middle-level Areas** are left until the anchor and node pages are right.

### Proposed

- Last touched = most recent of STATE `updated:`, last LOG line, newest file in the folder, last repo commit. Stale = 30 days. Not confirmed.
- Kind should be written down, not inferred from files: HFM shows as a Project, VOS as an Area only because it has a child.

### Unverified

- Newest-file dates may give false touches (Obsidian linter, sync). Sales showed "today". Alex to judge whether the ages feel right.
- Nothing is past 30 days, possibly because the 2026-09-06 vault reset touched every file.
- Vault Open rows all land in Backlog because STATE doesn't label them next or backlog. Proposed fix in the vault, not here.
- Home security camera shows the reconciliation case unprompted: the same soak-test task in STATE and Notion, both past their date.
- Upwork disagrees with itself: nav says 1d from a file, Needs attention says last run 11d from STATE.
