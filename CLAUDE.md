# Cockpit

Local browser page showing every vault node, its kind and its tasks from whichever sources they live in: vault files, Notion, local git repos.

Tracked by the vault node `CKP – Cockpit` at `C:\Users\Alex\Documents\Vault\Vault_OS\CKP - Cockpit\`. Pointer node: this repo is master and holds the thinking and state. The vault STATE only names this repo (`repo:`), nothing is copied back. Design reasoning: `Vault_OS/_node/sessions/2026-10-02 cockpit.md` in the vault.

- Stack: FastAPI + htmx, local only. Notion via `_node/notion.json` snapshots and a pull button, never live on page load. Read-only first.
- Tasks live in `STATE.md` at the repo root, the vault's STATE shape: Blocked on, Waiting on, numbered rows with a short title on the line and detail on indented lines beneath, Notes for next time. The cockpit reads it as this node's task source. Decisions go to `prototype/FINDINGS.md`, not here.
- `prototype/` is throwaway. Run `python prototype/front_page.py`, open http://localhost:8765, flip variants with the arrows.
