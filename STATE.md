---
updated: 2026-10-03
---

**Blocked on:** nothing.

**Next:** nothing.

**Waiting:**

1. Claude Code CLI login – Alex
   - headless runs fail "OAuth session expired"; Suggest actions untested end to end until then
2. First real Apply ticked – Alex
   - the Notion write path has not run yet; watch the first one

**Backlog:**

1. Decide what counts as last touched
   - Proposed: newest of STATE updated, last LOG line, newest file, last commit. Upwork shows the conflict
2. Promote Notion backlog to Next, due 2026-10-15
   - Discussed 2026-10-02, not decided: first page write, Notion only, confirm click
3. Middle-level Area pages
4. Move all to home
   - Parked: drop paired copies, preview first
5. LLM pair matching at Notion pull
6. Check this node button
   - Read-only LLM run, PC only, result cached
7. Real build: FastAPI, out of prototype/
   - not before CKP ends 2026-11-15; the model is still moving. Decided 2026-10-02
8. Global CLAUDE.md and memory index have no link
   - outside the vault, Obsidian can't open them; Windows has no .md app set
9. Skills, workflows and tools summary
   - serves VOS objective, decided 2026-10-03: each has an entry saying what it is for, where it lives and what uses it; Alex finds five at random in two clicks, by 2026-11-15
   - which skills exist (vault, global, plugin), what each is for from its description, and which a node uses as its runbook
   - grouped by category, e.g. organisational, voice and writing, dev and tooling, domain
   - category written as `category:` in each SKILL.md front matter, not guessed. Decided 2026-10-02
   - "likely out of date" = age against the category's shelf life: tooling dates fastest as models improve, voice slower, organisational slowest. Shelf lives Proposed, e.g. 3, 12 and 18 months
10. CRM in the Notion pull
    - Companies, Contacts, Deals; data source ids in the GTD Notion reference
11. Scripts and MCP wiring list
    - every script that exists (vault `Tools/`, `~/dev` repos, skills), its language and what calls it
    - every MCP server and connector: which account or workspace it is bound to, which scripts and skills use it
    - serves the same VOS objective as row 9
12. Task review: editable date on "Reset due" rows
    - prefilled with Claude's guess, Alex sets it before Apply
13. Task review Apply: full error text and a log line
    - errors cut at 80 chars hid the cause of the 2026-10-03 failure (likely a task already trashed, cache stale)
    - log the skill's step 5 line to `Vault_OS/_node/LOG.md`; the 13 applied on 2026-10-03 are unlogged
14. Task review skill: How to propose
    - suggestions were not on point, 2026-10-03. Rules per section in SKILL.md from Alex's real misses; page prompt keeps only the reply format
    - note in the skill that the page mirrors steps 1, 3 and 5 in code
15. Circle-and-tick as a status cue
    - decoration added 2026-10-03, the same icon on every task row; next is meaning: empty circle open, ticked done

**Notes for next time:** decisions live in `prototype/FINDINGS.md`, tasks here. Vault-side items (session-close tidy step, refresh misreading Areas with STATE) sit in VOS STATE.
