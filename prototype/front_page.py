"""PROTOTYPE - throwaway. Cockpit front page, three radically different variants.

Question: what should the cockpit's front page look like?
Three variants of the vault front page, switchable via ?variant=A|B|C, on one route.
  A  Outline - indented tree with a detail pane (htmx)
  B  Board   - every node by status, the "what needs me" view
  C  Map     - nested boxes, the node model drawn as containers

Read-only, stdlib only (FastAPI comes with the real build). Run:
    python prototype/front_page.py      then open http://localhost:8765
"""
import html, json, os, re, subprocess, sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

qp = lambda s: quote(s, safe='')

VAULT = os.environ.get('VAULT', r'C:\Users\Alex\Documents\Vault')
SKIP = {'.obsidian', '.claude', '_retired', '_session-notes', 'Daily Notes', 'Tools', 'Library', '_node', 'sessions', 'retired', '_runbook'}
CADENCE_DAYS = {'daily': 1, 'weekly': 7, 'monthly': 31, 'quarterly': 92}
NOTION_MAP = {'backlog': 'backlog', 'someday': 'backlog', 'not started': 'backlog', 'next': 'next', 'active': 'next', 'in progress': 'next',
              'waiting': 'waiting', 'blocked': 'blocked', 'done': 'done', 'cancelled': 'done'}
esc = html.escape


# ---------- data ----------

def frontmatter(txt):
    m = re.match(r'---\n(.*?)\n---\n?(.*)', txt, re.S)
    if not m: return {}, txt
    fm, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r'\s+-\s', line) and key:
            if not isinstance(fm.get(key), list): fm[key] = []
            fm[key].append(line.split('-', 1)[1].strip()); continue
        k, _, v = line.partition(':')
        key = k.strip(); fm[key] = v.strip()
    return fm, m.group(2)


BUCKETS = {'next': 'next', 'waiting': 'waiting', 'backlog': 'backlog', 'open': 'backlog'}  # old Open reads as Backlog


def parse_state_body(body, source):
    """STATE blocks, vault or repo, as task dicts. Buckets: Next, Waiting, Backlog (old Open).
    Blocked on, and the old inline Waiting on, describe the node: exempt from task homes."""
    tasks, blocked = [], ''
    def node_line(text, status):
        text = text.strip().rstrip('.')
        if text and not text.lower().startswith('nothing'):
            tasks.append({'status': status, 'title': text, 'detail': '', 'due': '', 'source': source, 'exempt': True})
    # a heading is a bold run at the start of a line: **Next:**, **Open**, **Open, on Alex:**
    for sec in re.split(r'(?m)^(?=\*\*[^*\n]+\*\*)', body):
        h = re.match(r'\*\*([^*\n]+?):?\*\*:?(.*)', sec)
        if not h: continue
        name, inline = h.group(1).strip().lower(), h.group(2)
        if not name.startswith('blocked on'): name = name.split(',')[0].strip()
        if name.startswith('blocked on'):
            # old forms: "Blocked on: x. **Waiting on:** y" on one line, or "Blocked on / Waiting on: x"
            first, _, rest = inline.partition('**Waiting on:**')
            node_line(first, 'waiting' if 'waiting on' in name else 'blocked')
            if rest: node_line(rest.split('\n')[0], 'waiting')
            continue
        if name == 'waiting on':
            node_line(inline.split('\n')[0], 'waiting'); continue
        status = BUCKETS.get(name)
        if not status: continue
        # a row is a numbered line; indented lines under it are its detail
        for m in re.finditer(r'^\d+\.\s+(.+)\n((?:[ \t]+\S.*\n?)*)', sec + '\n', re.M):
            detail = ' '.join(l.strip(' -*') for l in m.group(2).splitlines() if l.strip())
            tasks.append(dict(split_title(m.group(1), detail), status=status, source=source))
    return tasks


def read(p):
    try:
        with open(p, encoding='utf-8') as f: return f.read().replace('\r\n', '\n')
    except OSError: return ''


class Node:
    def __init__(self, folder, scaffold):
        self.folder, self.children, self.parent = folder, [], None
        self.rel = os.path.relpath(folder, VAULT)
        node_txt = read(os.path.join(scaffold, 'NODE.md'))
        h = re.search(r'^# (.+)$', node_txt, re.M)
        title = h.group(1).strip() if h else os.path.basename(folder)
        m = re.match(r'([A-Z][A-Z0-9]{2})\s*[–-]\s*(.+)', title)
        self.code, self.name = (m.group(1), m.group(2)) if m else ('', title)
        a = re.search(r'\*\*Aim:\*\*\s*(.+)', node_txt)
        self.aim = a.group(1).strip() if a else ''
        self.state_txt = read(os.path.join(scaffold, 'STATE.md'))
        fm, body = frontmatter(self.state_txt)
        self.fm, self.body = fm, body
        self.status = fm.get('status', '')
        self.next = fm.get('next', '')
        self.updated = fm.get('updated', '')
        self.cadence = fm.get('cadence', '')
        self.vault_tasks = parse_state_body(body, 'vault')
        self.blocked_on = next((t['title'] for t in self.vault_tasks if t['status'] == 'blocked'), '')
        # sources
        notion = fm.get('notion', '')
        snap_p = os.path.join(scaffold, 'notion.json')
        self.notion = json.loads(read(snap_p)) if os.path.exists(snap_p) else None
        self.notion_linked = notion.startswith('http') or self.notion is not None
        repo = fm.get('repo', '')
        if not repo:
            r = re.search(r'~/dev/[\w.-]+', ' '.join(str(v) for v in fm.values()))
            repo = r.group(0) if r else ''
        self.repo = repo
        self.repo_info = git_info(repo) if repo else None
        # a repo keeps its own STATE.md at its root, same three blocks as the vault
        self.repo_tasks = []
        if repo:
            _, rbody = frontmatter(read(os.path.join(os.path.expanduser(repo), 'STATE.md')))
            self.repo_tasks = parse_state_body(rbody, 'repo')

    @property
    def kind(self):
        if self.cadence: return 'workflow'
        if self.children or not self.state_txt: return 'area'
        return 'project'

    @property
    def own_work(self):  # an Area carrying its own STATE, decided 2026-10-02
        return self.kind == 'area' and bool(self.state_txt)

    @property
    def due(self):
        days = CADENCE_DAYS.get(self.cadence)
        if not days or not self.updated: return False
        try: return (date.today() - date.fromisoformat(self.updated)).days > days
        except ValueError: return False

    @property
    def shown_status(self):
        if self.kind == 'area' and not self.own_work: return derived(self)
        return 'due' if self.due and self.status == 'active' else (self.status or 'waiting')

    @property
    def tasks(self):
        out = self.vault_tasks + self.repo_tasks
        # Notion's manual order isn't in the API: dated tasks first, soonest first, then as pulled
        for t in sorted((self.notion or {}).get('tasks', []), key=lambda t: (not t.get('due'), t.get('due') or '')):
            out.append({'status': NOTION_MAP.get(t.get('status', '').lower(), 'backlog'), 'title': t.get('task', ''),
                        'source': 'notion', 'url': t.get('url', ''), 'due': (t.get('due') or '')[:10]})
        return out

    @property
    def task_home(self):
        """Where this node's tasks should live. Written as `tasks:` only to override the guess."""
        home = self.fm.get('tasks', '')
        if home in ('notion', 'vault', 'repo'): return home
        return 'notion' if self.notion_linked else 'repo' if self.repo else 'vault'

    def is_stray(self, t):
        return not t.get('exempt') and t['status'] != 'done' and t['source'] != self.task_home

    @property
    def sources(self):
        return [s for s, on in (('vault', True), ('notion', self.notion_linked), ('repo', bool(self.repo))) if on]


DUE = re.compile(r'[,;–-]?\s*\bdue (\d{4}-\d{2}-\d{2})\b', re.I)


def split_title(row, detail=''):
    """Short title plus detail. Indented detail wins; otherwise the first sentence is the title (stopgap).
    `due YYYY-MM-DD` anywhere in the row is lifted out as the task's date."""
    m = DUE.search(row) or DUE.search(detail)
    due = m.group(1) if m else ''
    row, detail = DUE.sub('', row).strip(), DUE.sub('', detail).strip()
    if detail: return {'title': row, 'detail': detail, 'due': due}
    m = re.match(r'(.+?[.:;])\s+(\S.*)', row)
    if m and len(m.group(1)) >= 12: return {'title': m.group(1).rstrip('.:;'), 'detail': m.group(2), 'due': due}
    return {'title': row, 'detail': '', 'due': due}


def derived(n):
    order = ['blocked', 'due', 'active', 'waiting', 'done']
    seen = [c.shown_status for c in n.children]
    for s in order:
        if s in seen: return s
    return 'waiting'


def git_info(repo):
    path = os.path.expanduser(repo)
    if not os.path.isdir(os.path.join(path, '.git')): return {'exists': os.path.isdir(path), 'last': '', 'dirty': 0}
    try:
        last = subprocess.run(['git', '-C', path, 'log', '-1', '--format=%cs'], capture_output=True, text=True).stdout.strip()
        dirty = len(subprocess.run(['git', '-C', path, 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines())
        return {'exists': True, 'last': last, 'dirty': dirty}
    except OSError: return {'exists': True, 'last': '', 'dirty': 0}


def load():
    nodes = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith('.'))
        if '_node' in os.listdir(root) and os.path.exists(os.path.join(root, '_node', 'NODE.md')):
            nodes.append(Node(root, os.path.join(root, '_node')))
        elif 'NODE.md' in files:
            nodes.append(Node(root, root))
    by_folder = {n.folder: n for n in nodes}
    for n in nodes:
        p = os.path.dirname(n.folder)
        while len(p) >= len(VAULT):
            if p in by_folder:
                n.parent = by_folder[p]; by_folder[p].children.append(n); break
            if p == os.path.dirname(p): break
            p = os.path.dirname(p)
    roots = [n for n in nodes if n.parent is None]
    return nodes, roots


# ---------- shared bits ----------

GLYPH = {'area': '<span class="g g-area" title="Area"></span>', 'project': '<span class="g g-project" title="Project"></span>',
         'workflow': '<span class="g g-workflow" title="Workflow">↻</span>'}


def badges(n):
    out = ''
    for s in n.sources:
        tip = s
        if s == 'notion' and n.notion: tip = f"Notion snapshot pulled {n.notion.get('pulled', '?')}"
        if s == 'repo':
            ri = n.repo_info or {}
            tip = f"{n.repo} · " + ('last commit ' + ri['last'] if ri.get('last') else ('no commits yet' if ri.get('exists') else 'not created yet'))
        out += f'<span class="src src-{s}" title="{esc(tip)}">{s[0].upper()}</span>'
    return f'<span class="srcs">{out}</span>'


def pill(n):
    s = n.shown_status
    derived_mark = ' derived' if n.kind == 'area' and not n.own_work else ''
    return f'<span class="pill p-{s}{derived_mark}" title="{"derived from children" if derived_mark else "authored in STATE"}">{s}</span>'


def label(n):
    code = f'<b>{esc(n.code)}</b> ' if n.code else ''
    return f'{code}<span class="nm">{esc(n.name)}</span>'


def detail(n):
    rows = ''.join(f'<li class="t t-{t["status"]}"><span class="ts">{t["status"]}</span>{esc(t["title"][:140])}'
                   f'<span class="src src-{t["source"]}">{t["source"][0].upper()}</span></li>' for t in n.tasks[:14])
    more = f'<p class="muted">+ {len(n.tasks) - 14} more</p>' if len(n.tasks) > 14 else ''
    kind = n.kind + (' · own work' if n.own_work else '') + (f' · {n.cadence}' if n.cadence else '')
    repo = ''
    if n.repo:
        ri = n.repo_info or {}
        repo = f'<p><span class="k">Repo</span>{esc(n.repo)} · ' + (
            f'last commit {ri["last"]}, {ri["dirty"]} uncommitted' if ri.get('last') else
            ('no commits yet' if ri.get('exists') else 'not created yet')) + '</p>'
        if ri.get('last') and n.updated and ri['last'] > n.updated:
            repo += f'<p class="finding">Finding: repo moved on {ri["last"]}, STATE last updated {n.updated}</p>'
    kids = ''.join(f'<li>{GLYPH[c.kind]} {label(c)} {pill(c)}</li>' for c in n.children)
    return f'''<div class="detail">
<h2>{GLYPH[n.kind]} {label(n)} {pill(n)}</h2>
<p class="muted">{esc(kind)} · {esc(n.rel)} {badges(n)}</p>
{f'<p class="aim">{esc(n.aim)}</p>' if n.aim else ''}
{f'<p><span class="k">Next</span>{esc(n.next)}</p>' if n.next else ''}
{repo}
{f'<h3>Tasks <span class="muted">{len(n.tasks)}</span></h3><ul class="tasks">{rows}</ul>{more}' if n.tasks else ''}
{f'<h3>Children</h3><ul class="kids">{kids}</ul>' if kids else ''}
</div>'''


# ---------- variant A: outline + detail pane ----------

def variant_a(nodes, roots):
    def tree(ns, depth=0):
        out = ''
        for n in ns:
            out += (f'<div class="row d{depth}" hx-get="/node?p={qp(n.rel)}" hx-target="#pane" tabindex="0">'
                    f'{GLYPH[n.kind]} {label(n)} {pill(n)} {badges(n)}'
                    f'<span class="nx">{esc(n.next[:90])}</span></div>')
            out += tree(n.children, depth + 1)
        return out
    first = next((n for n in nodes if n.code == 'VOS'), roots[0])
    return f'<div class="va"><div class="outline">{tree(roots)}</div><aside id="pane">{detail(first)}</aside></div>'


# ---------- variant B: board by status ----------

def variant_b(nodes, roots):
    cols = ['blocked', 'due', 'active', 'waiting', 'done']
    work = [n for n in nodes if n.kind != 'area' or n.own_work]
    out = ''
    for c in cols:
        cards = ''
        for n in [n for n in work if n.shown_status == c]:
            crumb, p = [], n.parent
            while p: crumb.insert(0, p.code or p.name); p = p.parent
            counts = {}
            for t in n.tasks: counts[t['status']] = counts.get(t['status'], 0) + 1
            cnt = ' '.join(f'<span class="cnt t-{k}">{v} {k}</span>' for k, v in counts.items() if k != 'done')
            cards += (f'<div class="card k-{n.kind}" hx-get="/node?p={qp(n.rel)}" hx-target="#modal" tabindex="0">'
                      f'<div class="crumb">{esc(" › ".join(crumb))}</div>'
                      f'<div class="ct">{GLYPH[n.kind]} {label(n)} {badges(n)}</div>'
                      f'<div class="nx">{esc(n.next[:110])}</div><div class="cnts">{cnt}</div></div>')
        out += f'<section class="col"><h3><span class="pill p-{c}">{c}</span> <span class="muted">{cards.count("class=\"card")}</span></h3>{cards}</section>'
    return f'<div class="vb">{out}</div><div id="modal" onclick="if(event.target===this)this.innerHTML=\'\'"></div>'


# ---------- variant C: map of nested boxes ----------

def variant_c(nodes, roots):
    def box(n):
        if n.kind == 'area':
            own = ''
            if n.own_work:
                own = (f'<div class="own"><span class="k">Own work</span>{len(n.tasks)} rows · next: {esc(n.next[:70])}</div>')
            kids = ''.join(box(c) for c in n.children)
            return (f'<div class="abox"><div class="ah" hx-get="/node?p={qp(n.rel)}" hx-target="#modal">{GLYPH["area"]} {label(n)} {pill(n)} {badges(n)}</div>'
                    f'{own}<div class="kids">{kids}</div></div>')
        open_n = sum(1 for t in n.tasks if t['status'] != 'done')
        return (f'<div class="tile k-{n.kind} s-{n.shown_status}" hx-get="/node?p={qp(n.rel)}" hx-target="#modal" title="{esc(n.next)}">'
                f'{GLYPH[n.kind]} {label(n)}<div class="tm">{pill(n)} {badges(n)} <span class="muted">{open_n} open</span></div></div>')
    legend = (f'<div class="legend">{GLYPH["area"]} Area &nbsp; {GLYPH["project"]} Project &nbsp; {GLYPH["workflow"]} Workflow &nbsp;·&nbsp; '
              f'<span class="src src-vault">V</span> vault <span class="src src-notion">N</span> Notion <span class="src src-repo">R</span> repo</div>')
    return f'{legend}<div class="vc">{"".join(box(r) for r in roots)}</div><div id="modal" onclick="if(event.target===this)this.innerHTML=\'\'"></div>'


# ---------- variant D: headline, the three anchor areas ----------

GENERATED = {'overview.html', '_overview.html', 'notion.json'}


def touched(n):
    """Most recent evidence of work: STATE updated, last LOG date, newest file, last commit. Subtree included."""
    if hasattr(n, '_touched'): return n._touched
    dates = []
    if n.updated: dates.append(n.updated[:10])
    scaffold = os.path.join(n.folder, '_node') if os.path.isdir(os.path.join(n.folder, '_node')) else n.folder
    m = re.findall(r'^(\d{4}-\d{2}-\d{2})', read(os.path.join(scaffold, 'LOG.md')), re.M)
    if m: dates.append(max(m))
    child_folders = {c.folder for c in n.children}
    newest = 0
    for root, dirs, files in os.walk(n.folder):
        dirs[:] = [d for d in dirs if os.path.join(root, d) not in child_folders and not d.startswith('.')]
        for f in files:
            if f in GENERATED: continue
            try: newest = max(newest, os.path.getmtime(os.path.join(root, f)))
            except OSError: pass
    if newest: dates.append(datetime.fromtimestamp(newest).strftime('%Y-%m-%d'))
    if n.repo_info and n.repo_info.get('last'): dates.append(n.repo_info['last'])
    dates += [touched(c) for c in n.children if touched(c)]
    n._touched = max(dates) if dates else ''
    return n._touched


def ago(d):
    if not d: return 'never'
    days = (date.today() - date.fromisoformat(d)).days
    if days <= 0: return 'today'
    if days < 14: return f'{days}d'
    if days < 70: return f'{days // 7}w'
    return f'{days // 30}mo'


def variant_d(nodes, roots):
    anchors = sorted(roots, key=lambda n: ['NGT', 'PER', 'VOS'].index(n.code) if n.code in ('NGT', 'PER', 'VOS') else 9)
    cols = ''
    for a in anchors:
        rows = ''.join(f'<li><span class="kp kp-{c.kind}">{c.kind}</span><span class="hn">{esc(c.name)}</span>'
                       f'<span class="ago">{ago(touched(c))}</span></li>'
                       for c in sorted(a.children, key=lambda c: touched(c), reverse=True))
        cols += f'<section class="hcol"><h2>{esc(a.name)}</h2><ul>{rows}</ul></section>'
    return f'<div class="vd">{cols}</div>'


# ---------- variant E: left nav + anchor page ----------

STALE_DAYS = 30


def days_since(d):
    try: return (date.today() - date.fromisoformat(d)).days
    except (ValueError, TypeError): return 9999


def descendants(n):
    for c in n.children:
        yield c
        yield from descendants(c)


def crumb(n, stop):
    parts, p = [], n.parent
    while p and p is not stop: parts.insert(0, p.name); p = p.parent
    return ' › '.join(parts)


def attention(anchor):
    items = []
    for n in descendants(anchor):
        if n.kind == 'area' and not n.own_work: continue
        if n.status == 'done': continue
        if n.status == 'blocked':
            items.append((0, 'blocked', n, n.blocked_on or n.next))
        elif n.due:
            items.append((1, 'due', n, f'{n.cadence}, last run {ago(n.updated)} ago'))
        elif days_since(touched(n)) > STALE_DAYS:
            items.append((2, f'untouched {ago(touched(n))}', n, n.next))
    return sorted(items, key=lambda i: (i[0], -days_since(touched(i[2]))))


def anchor_page(a):
    items = attention(a)
    rows = ''.join(f'<li hx-get="/view?p={qp(n.rel)}" hx-target="#main"><span class="why why-{k.split()[0]}">{esc(k)}</span>'
                   f'<div><div class="an">{esc(n.name)}<span class="acr">{esc(crumb(n, a))}</span></div>'
                   f'<div class="aline">{esc(line[:120])}</div></div></li>' for _, k, n, line in items)
    body = f'<ul class="att">{rows}</ul>' if items else '<p class="quiet">All quiet.</p>'
    return (f'<div class="anchor"><h1>{esc(a.name)}</h1>{f"<p class=aim>{esc(a.aim)}</p>" if a.aim else ""}'
            f'<h3>Needs attention</h3>{body}</div>')


def mid_page(n):
    return f'<div class="anchor"><h1>{esc(n.name)}</h1><p class="quiet">Middle-level area. Page not designed yet.</p></div>'


def section(txt, label):
    """Body of a NODE section, either **Label:** inline-or-list, or a ## Label heading."""
    m = re.search(rf'^\*\*{label}:\*\*(.*?)(?=^\*\*[^*\n]+:\*\*|^#|\Z)', txt, re.S | re.M) or \
        re.search(rf'^#+ {label}\s*\n(.*?)(?=^#|\Z)', txt, re.S | re.M)
    return m.group(1).strip() if m else None


def items(body):
    rows = re.findall(r'^\s*(?:[-*]|\d+\.)\s+(.+)$', body, re.M)
    lead = re.split(r'^\s*(?:[-*]|\d+\.)\s', body, maxsplit=1, flags=re.M)[0].strip()
    return lead, rows


def norm(s):
    return ' '.join(re.findall(r'[a-z0-9]+', s.lower().replace("'s", '')))


def pair_up(rows):
    """Reorder rows so a vault task and its near-identical copy from another source sit together.
    Plain text similarity for now; LLM matching, cached at pull time, if this misses pairs."""
    from difflib import SequenceMatcher
    cands = []
    for i, a in enumerate(rows):
        for j, b in enumerate(rows):
            if j <= i or a['source'] == b['source']: continue
            na, nb = norm(a['title'] + ' ' + a.get('detail', '')), norm(b['title'] + ' ' + b.get('detail', ''))
            r = SequenceMatcher(None, na, nb).ratio()
            wa, wb = set(na.split()), set(nb.split())
            short = min((wa, wb), key=len)
            cover = len(wa & wb) / len(short) if len(short) >= 4 else 0  # the shorter one's words all appear in the longer
            score = max(r, cover)
            if score >= 0.8: cands.append((score, i, j))
    used, partner = set(), {}
    for r, i, j in sorted(cands, reverse=True):
        if i in used or j in used: continue
        used |= {i, j}; partner[i] = j
    out, placed = [], set()
    for i, t in enumerate(rows):
        if i in placed: continue
        if i in partner:
            out += [(t, 'pa'), (rows[partner[i]], 'pb')]; placed |= {i, partner[i]}
        elif i not in used:
            out.append((t, '')); placed.add(i)
    return out


def state_box(n):
    def task_li(t, cls=''):
        title = esc(t['title'][:200])
        if t.get('url'): title = f'<a href="{esc(t["url"])}" target="_blank" rel="noopener">{title}</a>'
        stray = (f'<span class="stray" title="Out of place: this node keeps its tasks in {n.task_home.title()}">→ {n.task_home.title()}</span>'
                 if n.is_stray(t) else '')
        det = t.get('detail', '')
        if det:
            title = f'<span class="tt has-det" onclick="this.parentNode.classList.toggle(\'open\')" title="Show detail">{title}<span class="more">…</span></span>'
            det = f'<div class="det">{esc(det)}</div>'
        due = ''
        if t.get('due'):
            late = ' late' if t['due'] < date.today().isoformat() and t['status'] != 'done' else ''
            try: label = date.fromisoformat(t['due']).strftime('%d %b').lstrip('0')
            except ValueError: label = t['due']
            due = f'<span class="due{late}" title="{"Overdue, " if late else ""}due {t["due"]}">{label}</span>'
        inner = f'{title}{stray}{due}<span class="sm sm-{t["source"]}" title="{t["source"]}">{t["source"][0].upper()}</span>{det}'
        return f'<div class="pr">{inner}</div>' if cls == 'pr' else f'<li>{inner}</li>'
    def ul(rows):
        out, items = '', pair_up(rows)
        for i, (t, c) in enumerate(items):
            if c == 'pa':  # one card, one line per source
                out += f'<li class="pair" title="Same task in more than one place">{task_li(t, "pr")}{task_li(items[i + 1][0], "pr")}</li>'
            elif c != 'pb':
                out += task_li(t)
        return f'<ul class="tl">{out}</ul>'
    ts = n.tasks
    by = lambda s: [t for t in ts if t['status'] == s]
    out = ''
    nxt = by('next')
    if n.next or nxt:
        head = f'<p class="nextline">{esc(n.next)}<span class="sm sm-vault" title="vault">V</span></p>' if n.next else ''
        more = ul(nxt) if nxt else ''
        out += f'<h4>Next</h4>{head}{more}'
    for s in ('blocked', 'waiting'):
        rows = by(s)
        if rows: out += f'<h4 class="h-{s}">{s.title()}</h4>{ul(rows)}'
    back = by('backlog')
    if back:
        out += (f'<details class="bl"><summary><h4>Backlog <span class="muted">{len(back)}</span></h4></summary>'
                f'{ul(back)}</details>')
    if not out: out = '<p class="quiet">Nothing recorded.</p>'
    status = n.shown_status
    strays = sum(1 for t in ts if n.is_stray(t))
    sc = f'<span class="strays" title="Tasks outside this node\'s home ({n.task_home.title()}). Tidied at session close.">{strays} out of place</span>' if strays else ''
    return f'<section class="box"><h3>State <span class="st st-{status}">{status}</span>{sc}</h3>{out}</section>'


def sys_pills(n):
    tips = {'vault': f'STATE updated {n.updated or "?"}'}
    if n.notion_linked:
        tips['notion'] = f'snapshot pulled {n.notion.get("pulled", "?")}' if n.notion else 'linked, never pulled'
    if n.repo:
        ri = n.repo_info or {}
        tips['repo'] = f'{n.repo} · ' + (f'last commit {ri["last"]}' if ri.get('last') else 'no commits yet' if ri.get('exists') else 'not created')
    return ''.join(f'<span class="sp sp-{s}" title="{esc(tips[s])}">{s.title()}</span>' for s in n.sources)


def purpose(path):
    """A file says what it is for in its own first line: first sentence of the body, headings skipped."""
    if not path.endswith('.md'): return ''
    _, body = frontmatter(read(path))
    for line in body.splitlines():
        t = line.strip().strip('*_>').strip()
        if t and not t.startswith('#') and not t.startswith('---'):
            m = re.match(r'(.+?[.!?])(\s|$)', t)
            t = re.sub(r'\[\[([^]|]+\|)?([^]]+)\]\]', r'\2', (m.group(1) if m else t))
            return t[:110] + ('…' if len(t) > 110 else '')
    return ''


def mtime_date(path):
    try: return datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d')
    except OSError: return ''


def context_box(n):
    scaffold = os.path.join(n.folder, '_node') if os.path.isdir(os.path.join(n.folder, '_node')) else n.folder
    def row(label, path, note=''):
        age = ago(mtime_date(path)) if os.path.exists(path) else ''
        desc = note or purpose(path)
        return (f'<li><span class="fn">{esc(label)}</span><span class="fp">{esc(desc)}</span>'
                f'<span class="ago">{age}</span></li>')
    # always loaded: global, then every CLAUDE.md from the vault root down to this node
    rules = [('Global CLAUDE.md', os.path.expanduser(r'~\.claude\CLAUDE.md'), 'Your global rules')]
    d, chain = n.folder, []
    while len(d) >= len(VAULT):
        if os.path.exists(os.path.join(d, 'CLAUDE.md')): chain.append(d)
        if d == VAULT: break
        d = os.path.dirname(d)
    rules += [(('Vault' if c == VAULT else os.path.basename(c)) + '/CLAUDE.md', os.path.join(c, 'CLAUDE.md'), 'Rules for this folder and below')
              for c in reversed(chain)]
    # loaded on open: NODE, STATE and every context: path, which may be relative to the node or its _node/
    on_open = [('NODE.md', os.path.join(scaffold, 'NODE.md'), 'What this is'), ('STATE.md', os.path.join(scaffold, 'STATE.md'), 'Where it is')]
    loaded = {os.path.normcase(p) for _, p, _ in on_open}
    ctx = n.fm.get('context', [])
    for c in ctx if isinstance(ctx, list) else []:
        cands = [os.path.normpath(os.path.join(base, c)) for base in (n.folder, scaffold)]
        hit = next((p for p in cands if os.path.exists(p)), None)
        on_open.append((c, hit or cands[0], '' if hit else 'Missing: listed in context: but not found'))
        if hit: loaded.add(os.path.normcase(hit))
    # not loaded: the rest of the node's own files, newest first; child nodes are in the nav
    kids = {c.folder for c in n.children}
    files, folders = [], []
    for e in os.scandir(n.folder):
        if e.name.startswith(('_', '.')) or e.path in kids: continue
        if e.is_dir():
            cnt = sum(len(fs) for _, _, fs in os.walk(e.path))
            folders.append((e.name, cnt, max((mtime_date(os.path.join(r, f)) for r, _, fs in os.walk(e.path) for f in fs), default='')))
        elif os.path.normcase(e.path) not in loaded and e.name not in ('CLAUDE.md',) and not e.name.endswith('overview.html'):
            files.append((mtime_date(e.path), e.name, e.path))
    files.sort(reverse=True)
    not_loaded = ''.join(row(name, p) for _, name, p in files)
    not_loaded += ''.join(f'<li class="fold"><span class="fn">{esc(name)}/</span><span class="fp">{cnt} files</span><span class="ago">{ago(last)}</span></li>'
                          for name, cnt, last in sorted(folders, key=lambda f: f[2], reverse=True))
    link = 'obsidian://open?vault=Vault&file=' + qp(os.path.relpath(os.path.join(scaffold, 'NODE.md'), VAULT).replace(os.sep, '/'))
    return (f'<section class="box"><h3>Context <a class="olink" href="{link}">Open in Obsidian ↗</a></h3>'
            f'<h4>Always loaded</h4><ul class="fl">{"".join(row(*r) for r in rules)}</ul>'
            f'<h4>Loaded on open</h4><ul class="fl">{"".join(row(*r) for r in on_open)}</ul>'
            + (f'<h4>Not loaded</h4><ul class="fl">{not_loaded}</ul>' if not_loaded else '') + '</section>')


def node_page(n):
    scaffold = os.path.join(n.folder, '_node') if os.path.isdir(os.path.join(n.folder, '_node')) else n.folder
    txt = read(os.path.join(scaffold, 'NODE.md'))
    aim = n.aim or (section(txt, 'Aim') or '').split('\n')[0]
    obj, old = section(txt, 'Objectives'), None
    if obj is None:
        old = section(txt, 'Done when') or section(txt, 'Healthy when')
    def render(body):
        lead, rows = items(body)
        lis = ''.join(f'<li>{esc(r)}</li>' for r in rows)
        return (f'<p class="olead">{esc(lead)}</p>' if lead else '') + (f'<ol class="objs">{lis}</ol>' if lis else '')
    objs = render(obj) if obj else '<p class="quiet">None yet.</p>'
    legacy = f'<h3>Done when <span class="old">old shape</span></h3>{render(old)}' if old else ''
    return (f'<div class="anchor"><h1>{esc(n.name)}</h1>'
            f'<p class="meta"><span class="kp kp-{n.kind}">{n.kind}</span>{sys_pills(n)}<span class="muted">touched {ago(touched(n))}{" ago" if ago(touched(n)) not in ("today", "never") else ""}</span></p>'
            f'{f"<p class=aim>{esc(aim)}</p>" if aim else ""}'
            f'<section class="box"><h3>Objectives</h3>{objs}</section>{legacy}{state_box(n)}{context_box(n)}</div>')


def view(n):
    if n.parent is None: return anchor_page(n)
    if n.kind == 'area' and not n.own_work: return mid_page(n)
    return node_page(n)


def variant_e(nodes, roots):
    anchors = sorted(roots, key=lambda n: ['NGT', 'PER', 'VOS'].index(n.code) if n.code in ('NGT', 'PER', 'VOS') else 9)
    def tree(ns):
        out = ''
        for c in sorted(ns, key=lambda c: touched(c), reverse=True):
            done = ' done' if c.status == 'done' else ''
            tw = '<span class="tw">▸</span>' if c.children else '<span class="tw blank"></span>'
            sub = f'<ul class="sub">{tree(c.children)}</ul>' if c.children else ''
            out += (f'<li class="it{done}" data-k="{esc(c.rel)}"><div class="nv{done}" hx-get="/view?p={qp(c.rel)}" hx-target="#main">'
                    f'{tw}<span class="kp kp-{c.kind}">{c.kind[0].upper()}</span><span class="hn">{esc(c.name)}</span>'
                    f'<span class="ago">{ago(touched(c))}</span></div>{sub}</li>')
        return out
    nav = ''.join(f'<div class="it anc-it open" data-k="{esc(a.rel)}"><div class="anc" hx-get="/view?p={qp(a.rel)}" hx-target="#main">'
                  f'<span class="tw">▸</span>{esc(a.name)}</div><ul class="sub">{tree(a.children)}</ul></div>' for a in anchors)
    tools = ('<div class="navtools"><button data-all="1">Expand all</button><button data-all="0">Collapse all</button>'
             '<button id="donebtn">Show done</button></div>')
    js = '''<script>(function(){
const KEY='cockpit.open';let open;try{open=JSON.parse(localStorage.getItem(KEY)||'null')}catch(e){open=null}
const items=()=>document.querySelectorAll('nav .it');
function save(){try{localStorage.setItem(KEY,JSON.stringify([...items()].filter(i=>i.classList.contains('open')).map(i=>i.dataset.k)))}catch(e){}}
if(open)items().forEach(i=>i.classList.toggle('open',open.includes(i.dataset.k)));
document.addEventListener('click',e=>{const t=e.target.closest('nav .tw');if(t&&!t.classList.contains('blank')){e.stopPropagation();e.preventDefault();
t.closest('.it').classList.toggle('open');save();return}
const b=e.target.closest('nav [data-all]');if(b){items().forEach(i=>i.classList.toggle('open',b.dataset.all==='1'));save()}
if(e.target.id==='donebtn'){setDone(!document.body.classList.contains('show-done'))}},true);
function setDone(on){document.body.classList.toggle('show-done',on);const d=document.getElementById('donebtn');if(d)d.textContent=on?'Hide done':'Show done';
try{localStorage.setItem('cockpit.done',on?'1':'0')}catch(e){}}
let sd=false;try{sd=localStorage.getItem('cockpit.done')==='1'}catch(e){}setDone(sd);
})();</script>'''
    return f'<div class="ve"><nav>{tools}{nav}</nav><section id="main">{anchor_page(anchors[0])}</section></div>{js}'


VARIANTS = {'E': ('Nav + anchor', variant_e), 'D': ('Headline', variant_d), 'A': ('Outline', variant_a), 'B': ('Board', variant_b), 'C': ('Map', variant_c)}

CSS = '''
:root{--bg:#f6f5f2;--surface:#fff;--ink:#1d1d1b;--muted:#77756f;--line:#e2dfd8;--accent:#2f5d8a;
--blocked:#c2412d;--due:#b7791f;--active:#2f7d4f;--waiting:#6b7280;--done:#a8a29e;--backlog:#8b8b8b;--next:#2f5d8a;
--vault:#5b4b8a;--notion:#1d1d1b;--repo:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--surface:#1f1f1d;--ink:#ecebe7;--muted:#9a978f;--line:#33322f;--accent:#7fa8d1;--notion:#d6d3cc}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 Inter,system-ui,sans-serif}
header{display:flex;align-items:baseline;gap:16px;padding:14px 24px;border-bottom:1px solid var(--line);background:var(--surface)}
header h1{font-size:16px;margin:0;letter-spacing:.02em}header .muted{font-size:12px}
main{padding:20px 24px 90px}.muted{color:var(--muted)}b{font-weight:600}
.g{display:inline-block;width:11px;height:11px;margin-right:4px;vertical-align:-1px}
.g-area{border:2px solid var(--ink);border-radius:2px}.g-project{background:var(--ink);border-radius:50%}
.g-workflow{width:auto;height:auto;font-size:13px;line-height:1;color:var(--accent);font-weight:700}
.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:10px;color:#fff;background:var(--waiting);margin-left:6px;text-transform:uppercase;letter-spacing:.04em}
.p-blocked{background:var(--blocked)}.p-due{background:var(--due)}.p-active{background:var(--active)}.p-done{background:var(--done)}
.pill.derived{background:transparent!important;color:var(--muted);border:1px dashed var(--muted)}
.srcs{margin-left:6px}.src{display:inline-block;width:17px;height:17px;line-height:17px;text-align:center;font-size:10px;font-weight:700;border-radius:3px;color:#fff;margin-left:2px}
.src-vault{background:var(--vault)}.src-notion{background:var(--notion);color:var(--bg)}.src-repo{background:var(--repo)}
.k{display:inline-block;min-width:56px;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-right:8px}
.finding{background:#fdf2e3;color:#8a4b0f;padding:6px 10px;border-radius:4px}
.nx{color:var(--muted);font-size:12px}
/* A */
.va{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:20px;align-items:start}
.outline{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:6px 0}
.row{padding:6px 14px;cursor:pointer;display:flex;flex-wrap:wrap;align-items:center;gap:2px 4px;border-left:3px solid transparent}
.row:hover,.row:focus{background:var(--bg);border-left-color:var(--accent);outline:none}
.row .nx{flex-basis:100%;padding-left:16px}
.d1{padding-left:34px}.d2{padding-left:54px}.d3{padding-left:74px}.d4{padding-left:94px}
aside#pane{position:sticky;top:16px;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:16px 20px;max-height:calc(100vh - 120px);overflow:auto}
.detail h2{font-size:17px;margin:0 0 4px}.detail h3{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:18px 0 6px}
.aim{font-style:italic}.tasks,.kids{list-style:none;padding:0;margin:0}
.t{display:flex;gap:8px;align-items:baseline;padding:4px 0;border-bottom:1px solid var(--line);font-size:13px}.t .src{margin-left:auto;flex:none}
.ts{flex:none;width:58px;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.t-blocked .ts{color:var(--blocked)}.t-waiting .ts{color:var(--waiting)}.t-next .ts{color:var(--next)}
.kids li{padding:3px 0}
/* B */
.vb{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;align-items:start}
.col h3{font-size:13px;margin:0 0 10px}.col .pill{margin-left:0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:10px 12px;margin-bottom:10px;cursor:pointer}
.card:hover{border-color:var(--accent)}.card.k-workflow{border-left:3px solid var(--accent)}
.crumb{font-size:11px;color:var(--muted);margin-bottom:2px}.ct{font-size:14px}.card .nx{margin-top:4px}
.cnts{margin-top:6px}.cnt{font-size:11px;margin-right:6px;color:var(--muted)}.cnt.t-blocked{color:var(--blocked)}.cnt.t-waiting{color:var(--waiting)}
/* C */
.legend{font-size:12px;color:var(--muted);margin-bottom:14px}
.vc{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start}
.abox{border:2px solid var(--line);border-radius:8px;padding:10px;background:color-mix(in srgb,var(--surface) 60%,transparent);flex:1 1 300px}
.abox .abox{flex:1 1 220px;border-style:dashed}
.ah{font-size:14px;margin-bottom:8px;cursor:pointer}
.own{font-size:12px;background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--vault);border-radius:4px;padding:6px 8px;margin-bottom:8px}
.abox .kids{display:flex;flex-wrap:wrap;gap:8px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:8px 10px;min-width:170px;flex:1 1 170px;cursor:pointer}
.tile.k-workflow{border-radius:18px;border-color:var(--accent)}.tile.s-blocked{border-color:var(--blocked);border-width:2px}.tile.s-due{border-color:var(--due);border-width:2px}.tile.s-done{opacity:.55}
.tile .tm{margin-top:4px}.tile .pill{margin-left:0}
#modal:not(:empty){position:fixed;inset:0;background:rgba(0,0,0,.35);display:flex;justify-content:center;align-items:flex-start;padding-top:8vh;z-index:5}
#modal .detail{background:var(--surface);border-radius:8px;padding:18px 22px;width:min(640px,92vw);max-height:80vh;overflow:auto}
/* D */
.vd{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:48px;max-width:1100px;margin:24px auto}
.hcol h2{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.hcol ul{list-style:none;margin:0;padding:0}.hcol li{display:flex;align-items:center;gap:10px;padding:9px 0}
.hn{flex:1;font-size:15px}.ago{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.kp{font-size:10px;text-transform:uppercase;letter-spacing:.06em;padding:2px 0;width:68px;text-align:center;border-radius:10px;border:1px solid var(--line);color:var(--muted)}
.kp-project{border-color:var(--ink);color:var(--ink)}.kp-workflow{border-color:var(--accent);color:var(--accent)}
/* E */
.ve{display:grid;grid-template-columns:300px minmax(0,1fr);gap:40px;align-items:start}
.ve nav{position:sticky;top:16px;max-height:calc(100vh - 110px);overflow:auto;padding-right:8px}
.ve nav ul{list-style:none;margin:0 0 18px;padding:0}
.anc{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:6px 8px;cursor:pointer;border-radius:4px}
.anc:hover,.nv:hover{background:var(--surface)}
.nv{display:flex;align-items:center;gap:8px;padding:5px 8px;cursor:pointer;border-radius:4px;font-size:14px}
.nv.done{opacity:.45}nav li.it.done{display:none}body.show-done nav li.it.done{display:block}
.ve nav ul.sub{margin:0;padding-left:16px;display:none}.ve nav .it.open>ul.sub{display:block}.anc-it>ul.sub{padding-left:0;margin-bottom:14px}
.tw{flex:none;width:14px;display:inline-block;text-align:center;color:var(--muted);font-size:11px;cursor:pointer;transition:transform .12s;user-select:none}
.tw:hover{color:var(--ink)}.it.open>.nv>.tw,.it.open>.anc>.tw{transform:rotate(90deg)}.tw.blank{cursor:default}
.anc{display:flex;align-items:center;gap:6px}
.navtools{display:flex;gap:6px;margin:0 0 12px 8px}
.navtools button{font:inherit;font-size:11px;color:var(--muted);background:none;border:1px solid var(--line);border-radius:4px;padding:2px 8px;cursor:pointer}
.navtools button:hover{color:var(--ink);border-color:var(--muted)}
.nv .kp{width:20px;padding:1px 0;font-size:9px}.nv .hn{font-size:14px}.nv .ago{font-size:12px}
.htmx-request{opacity:.6}
.anchor{max-width:720px}.anchor h1{font-size:24px;font-weight:600;margin:4px 0 6px}
.anchor h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:28px 0 8px}
.quiet{color:var(--muted)}
.att{list-style:none;margin:0;padding:0}
.att li{display:flex;gap:14px;align-items:flex-start;padding:12px 0;border-bottom:1px solid var(--line);cursor:pointer}
.att li:hover .an{color:var(--accent)}
.why{flex:none;width:118px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);padding-top:2px}
.why-blocked{color:var(--blocked)}.why-due{color:var(--due)}
.an{font-size:15px}.acr{font-size:12px;color:var(--muted);margin-left:10px}.aline{font-size:13px;color:var(--muted);margin-top:2px}
#main .detail{max-width:720px}
.box{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:4px 22px 16px;margin:24px 0 32px}
.box h3{margin-top:16px}
.olink{float:right;font-size:11px;font-weight:400;text-transform:none;letter-spacing:0;color:var(--accent);text-decoration:none}
.fl{list-style:none;margin:0 0 4px;padding:0}.fl li{display:flex;gap:12px;align-items:baseline;padding:5px 0;border-bottom:1px solid var(--line);font-size:13px}
.fl li:last-child{border-bottom:0}.fn{flex:none;width:210px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fp{flex:1;color:var(--muted)}.fl .ago{flex:none}.fl li.fold .fn{color:var(--muted)}
.box h4{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:16px 0 4px;display:inline-block}
.h-blocked{color:var(--blocked)!important}.h-waiting{color:var(--waiting)}
.nextline{font-size:16px;margin:2px 0 4px;line-height:1.5}
.tl{list-style:none;margin:0;padding:0}.tl li{padding:6px 0;border-bottom:1px solid var(--line);font-size:14px;display:flex;gap:10px;align-items:baseline}
.tl li:last-child{border-bottom:0}
.tl li,.tl li:last-child{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:8px 0}
.tl li::before{content:'';flex:none;width:5px;height:5px;border-radius:50%;background:var(--muted);align-self:center;margin-right:2px}
.tl li{flex-wrap:wrap}.tt.has-det{cursor:pointer}.more{color:var(--muted);margin-left:4px}.li-open .more{display:none}
.det{display:none;flex-basis:100%;font-size:13px;color:var(--muted);padding:6px 0 2px 15px;line-height:1.5}
.tl li.open .det{display:block}.tl li.open .more{display:none}
.tl li.pair{display:block;padding:4px 12px}.tl li.pair::before{display:none}
.pr{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;padding:4px 0}
.pr::before{content:'';flex:none;width:5px;height:5px;border-radius:50%;background:var(--muted);align-self:center;margin-right:2px}
.pr.open .det{display:block}.pr.open .more{display:none}.tl a{color:inherit;text-decoration:none}.tl a:hover{color:var(--accent)}
.sm{margin-left:auto;flex:none;font-size:9px;font-weight:700;color:var(--muted);border:1px solid var(--line);border-radius:3px;padding:0 4px}
.nextline .sm{margin-left:8px;vertical-align:2px}
.due{flex:none;margin-left:auto;font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:8px;padding:0 7px;white-space:nowrap}
.due.late{color:var(--due);border-color:var(--due)}.stray+.due{margin-left:8px}.due+.sm{margin-left:6px}
.stray{flex:none;margin-left:auto;font-size:11px;color:var(--due);white-space:nowrap}.stray+.sm{margin-left:6px}
.strays{font-size:11px;font-weight:400;text-transform:none;letter-spacing:0;color:var(--due);margin-left:10px}
.bl summary{list-style:none;cursor:pointer;display:block}.bl summary::-webkit-details-marker{display:none}
.bl summary h4::before{content:'▸ ';}.bl[open] summary h4::before{content:'▾ '}
.st{font-size:10px;letter-spacing:.06em;border-radius:8px;padding:1px 7px;margin-left:6px;border:1px solid var(--line);vertical-align:1px}
.st-blocked{color:var(--blocked);border-color:var(--blocked)}.st-due{color:var(--due);border-color:var(--due)}.st-active{color:var(--active);border-color:var(--active)}
.sp{font-size:10px;text-transform:uppercase;letter-spacing:.06em;padding:2px 9px;border-radius:10px;color:#fff}
.sp-vault{background:var(--vault)}.sp-notion{background:var(--notion);color:var(--bg)}.sp-repo{background:var(--repo)}
.meta{display:flex;align-items:center;gap:12px;margin:0 0 14px;font-size:13px}
.objs{margin:0;padding-left:20px}.objs li{padding:6px 0;font-size:15px;line-height:1.5}.olead{font-size:15px;margin:0 0 6px}
.old{font-size:10px;letter-spacing:.06em;color:var(--due);border:1px solid var(--due);border-radius:8px;padding:1px 6px;margin-left:6px;vertical-align:1px}
/* switcher */
.switch{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#111;color:#fff;border-radius:22px;padding:6px 8px;display:flex;align-items:center;gap:8px;box-shadow:0 6px 24px rgba(0,0,0,.3);font-size:13px;z-index:9}
.switch a{color:#fff;text-decoration:none;padding:4px 10px;border-radius:14px}.switch a:hover{background:#333}.switch span{min-width:130px;text-align:center}
@media (max-width:900px){.va,.vb{grid-template-columns:1fr}}
'''


def page(variant):
    nodes, roots = load()
    name, fn = VARIANTS[variant]
    keys = list(VARIANTS)
    i = keys.index(variant)
    prev, nxt = keys[i - 1], keys[(i + 1) % len(keys)]
    counts = {}
    for n in nodes:
        if n.kind != 'area' or n.own_work: counts[n.shown_status] = counts.get(n.shown_status, 0) + 1
    summary = ' · '.join(f'{v} {k}' for k, v in sorted(counts.items()))
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cockpit</title><script src="https://unpkg.com/htmx.org@2.0.3"></script><style>{CSS}</style></head><body>
<header><h1>COCKPIT</h1>{'' if variant in 'DE' else f'<span class="muted">PROTOTYPE · {len(nodes)} nodes · {summary} · read {datetime.now():%H:%M}</span>'}</header>
<main>{fn(nodes, roots)}</main>
<div class="switch"><a href="?variant={prev}">←</a><span>{variant} ({name})</span><a href="?variant={nxt}">→</a></div>
<script>document.addEventListener('keydown',e=>{{if(e.target.closest('input,textarea,[contenteditable]'))return;
if(e.key==='ArrowLeft')location.search='?variant={prev}';if(e.key==='ArrowRight')location.search='?variant={nxt}';
if(e.key==='Escape'){{const m=document.getElementById('modal');if(m)m.innerHTML=''}}}});</script>
</body></html>'''


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == '/view':
            nodes, _ = load()
            n = next((n for n in nodes if n.rel == q.get('p', [''])[0]), None)
            body = view(n) if n else '<p>not found</p>'
        elif u.path == '/node':
            nodes, _ = load()
            n = next((n for n in nodes if n.rel == q.get('p', [''])[0]), None)
            body = detail(n) if n else '<p>not found</p>'
        elif u.path == '/':
            v = q.get('variant', ['E'])[0].upper()
            body = page(v if v in VARIANTS else 'E')
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def log_message(self, *a): pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    host = os.environ.get('HOST', '127.0.0.1')  # HOST=0.0.0.0 to serve on the LAN
    print(f'Cockpit prototype on http://{host}:{port}  (vault: {VAULT})')
    ThreadingHTTPServer((host, port), H).serve_forever()
