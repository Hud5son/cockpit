# Prototype findings

What the front-page prototype has settled, and what it hasn't. Tagged Decided (Alex said so), Proposed (Claude's, awaiting a yes) or Unverified.

### Decided, 2026-10-03

- **Claude skills from the page run headless Claude Code** (`claude -p`, subscription, not the API). Claude proposes, Alex ticks, plain Python writes, so "nothing before the yes" is enforced by the page, not trusted to the model. Task review's Suggest actions is the first; the hover names the account. Every suggested row is validated against the pull, invented ids are dropped. Pattern for the "Check this node" row.
- **Areas v1.** Every node says `type:` in STATE front matter, and every Area now has a STATE (vault root CLAUDE.md, 2026-10-03). An Area links to its Notion Area with `notion:` in that STATE, like any node. Its page shows State (its own level, plus its Notion Area tasks) and Child state (the nodes below, rolled up on every read, never stored). Nine linked: NGT-Sales, NGT-Operations, NGT-Clients, Health, Home, Family, Finances, Fun, Friends. Self development and Work & Career left unlinked, Alex.
- **Task review sections fold**, closed by default; a section with suggestions opens. Dead parent ignores Backlog tasks under an On hold project.

- **Notion live, one pull.** Tasks, Projects and Areas in one go, CRM later, split by node locally. Cached a few minutes, Refresh forces it, last good pull kept and shown flagged if Notion fails. A full pull took 2s; cost grows with task count, not node count. Replaces per-node `notion.json` snapshots for the cockpit. Alex chose this over snapshots after asking why not live.

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

- **Task homes.** Tasks may sit in two places to start. Each node has a preferred home and tidies strays into it, any direction. The LLM may flag cross-source disagreement. Vault session note 2026-10-02 has the reasoning.
- **Task home guessed unless written**: Notion if linked, else repo, else vault; `tasks:` overrides. Out-of-place rows marked "→ Home", a count on the State heading. `next:` and Blocked/Waiting exempt. Moving happens at session close, never from the page.
- **STATE buckets**: Blocked on (node line), Next, Waiting, Backlog, Notes. A date is `due YYYY-MM-DD` in any row, shown as a chip, amber when late; Notion's Due date the same. Parser reads old shapes too: Open, `**Open**` without a colon, Blocked on / Waiting on on one line.
- **No priority field.** Priority is the bucket (Next vs Backlog); order within a bucket ranks, numbered rows in vault and repo. Notion has no priority property and its manual order isn't in the API, so Notion rows sort by due date, dated first, then as pulled. Decided 2026-10-02.
- **"?" help pattern.** How-things-work lives on the page, beside the section it explains, closed by default. First two: State (buckets, dates, titles) and On /session-open (adding to `context:`). Add more as Alex hits them; the texts seed the Node Model guide. Decided 2026-10-02.
- **Kind parked.** Nodes are blurring; the kind pill stays but nothing depends on it.

### Proposed


- Last touched = most recent of STATE `updated:`, last LOG line, newest file in the folder, last repo commit. Stale = 30 days. Not confirmed.

- **Tasks as light cards with a bullet.** A matched pair is one card with two bulleted lines, one per source. Plain text similarity, same section only; LLM matching at pull time if it misses pairs. Alex: "looks great", 2026-10-02.
- **Title and detail split.** Short title shown, detail on click. Vault convention: title on the numbered line, detail on indented lines (Claude's call at Alex's request). Older rows: first sentence is the title.
- **"Move all to <home>" button**, one per node on the State heading, instead of per task (per task judged overkill). Must drop paired vault copies rather than move them, and show a preview first ("2 to move, 3 already there"). First page write, so it reopens read-only-first. Parked by Alex 2026-10-02.

### Unverified

- Newest-file dates may give false touches (Obsidian linter, sync). Sales showed "today". Alex to judge whether the ages feel right.
- Nothing is past 30 days, possibly because the 2026-09-06 vault reset touched every file.
- Vault Open rows all land in Backlog because STATE doesn't label them next or backlog. Proposed fix in the vault, not here.
- Home security camera shows the reconciliation case unprompted: the same soak-test task in STATE and Notion, both past their date.
- Upwork disagrees with itself: nav says 1d from a file, Needs attention says last run 11d from STATE.
