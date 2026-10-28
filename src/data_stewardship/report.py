"""Self-contained HTML dashboard generator.

``ds-steward dashboard`` renders the current stewardship state (check
results, dataset inventory, rights register, figure manifest, repository
file tree and usage instructions) into a single HTML file with no
external dependencies: all CSS and JavaScript is embedded, so the file
works offline, can be committed to ``docs/dashboard.html`` and published
via GitHub Pages.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from . import __version__
from .checks import (
    CheckResult,
    IGNORED_DIRS,
    IGNORED_FILES,
    StewardshipReport,
    run_all_checks,
)

# --------------------------------------------------------------------------- #
# Embedded assets                                                             #
# --------------------------------------------------------------------------- #

_CSS = """
:root{
  --bg:#f4f6fa; --panel:#ffffff; --ink:#1c2434; --muted:#5b6474;
  --line:#e3e7ef; --accent:#2563eb; --accent-soft:#eaf1fe;
  --good:#158a4c; --good-bg:#e5f6ec; --bad:#c62838; --bad-bg:#fdecee;
  --code:#0f1b2d; --code-ink:#dce7f7; --chip:#eef2f8;
}
[data-theme="dark"]{
  --bg:#0d1220; --panel:#151c2e; --ink:#e8edf6; --muted:#9aa5b8;
  --line:#25304a; --accent:#6ea8ff; --accent-soft:#182641;
  --good:#4ade80; --good-bg:#10321f; --bad:#f87171; --bad-bg:#3a1418;
  --code:#0a0f1c; --code-ink:#d7e3f4; --chip:#1b2438;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 64px}
header.top{background:linear-gradient(135deg,#1d3b8b 0%,#2563eb 55%,#0f766e 100%);color:#fff;padding:34px 0 26px}
header.top .wrap{padding-bottom:0}
.top h1{margin:0;font-size:26px;letter-spacing:.2px}
.top p.sub{margin:6px 0 14px;opacity:.88;font-size:15px}
.badges{display:flex;gap:8px;flex-wrap:wrap}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;
  font-weight:600;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35);color:#fff}
.badge a{color:#fff;text-decoration:none}
.banner{margin:-18px 0 22px;border-radius:12px;padding:14px 18px;font-weight:600;
  display:flex;align-items:center;gap:10px;box-shadow:0 8px 24px rgba(13,30,66,.12)}
.banner.ok{background:var(--good-bg);color:var(--good);border:1px solid var(--good)}
.banner.bad{background:var(--bad-bg);color:var(--bad);border:1px solid var(--bad)}
.dot{width:10px;height:10px;border-radius:50%;background:currentColor;flex:0 0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:26px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card .kpi{font-size:30px;font-weight:700;line-height:1.1}
.card .lbl{color:var(--muted);font-size:13px;margin-top:4px}
section{margin:34px 0}
h2{font-size:19px;margin:0 0 12px;display:flex;align-items:center;gap:10px}
h2 .n{color:var(--accent);font-size:13px;font-weight:700;letter-spacing:.08em}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:14px}
th{ text-align:left;padding:10px 14px;background:var(--chip);color:var(--muted);
  font-size:12px;letter-spacing:.06em;text-transform:uppercase;border-bottom:1px solid var(--line)}
td{padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--accent-soft)}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700}
.pill.pass{background:var(--good-bg);color:var(--good);border:1px solid var(--good)}
.pill.fail{background:var(--bad-bg);color:var(--bad);border:1px solid var(--bad)}
.pill.neutral{background:var(--chip);color:var(--muted);border:1px solid var(--line)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
.muted{color:var(--muted)}
.toolbar{display:flex;gap:10px;align-items:center;margin:0 0 10px;flex-wrap:wrap}
input.filter{flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--line);
  border-radius:9px;background:var(--panel);color:var(--ink);font-size:14px}
button.btn{padding:8px 14px;border-radius:9px;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer}
button.btn:hover{border-color:var(--accent);color:var(--accent)}
details.dir{margin:2px 0}
details.dir summary{cursor:pointer;padding:5px 8px;border-radius:7px;list-style:none;
  font-weight:600;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}
details.dir summary:hover{background:var(--accent-soft)}
details.dir summary::before{content:"+ ";color:var(--accent);font-weight:700}
details.dir[open]>summary::before{content:"- "}
.tree-files{padding-left:22px}
.tree-file{padding:2px 8px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;color:var(--muted)}
.tree-file .size{color:var(--muted);opacity:.75;font-size:11px;margin-left:8px}
.tree-file a{color:inherit;text-decoration:none}
.tree-file a:hover{color:var(--accent)}
.block{position:relative;background:var(--code);border-radius:10px;margin:10px 0}
.block pre{margin:0;padding:14px 90px 14px 16px;overflow-x:auto;color:var(--code-ink);
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;line-height:1.6}
.copy{position:absolute;top:9px;right:9px;padding:5px 12px;border-radius:7px;border:none;
  background:rgba(255,255,255,.14);color:#fff;font-size:12px;font-weight:600;cursor:pointer}
.copy:hover{background:rgba(255,255,255,.28)}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;counter-reset:step}
.step{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;position:relative}
.step::before{counter-increment:step;content:counter(step);position:absolute;top:-10px;left:14px;
  width:24px;height:24px;border-radius:50%;background:var(--accent);color:#fff;font-size:12px;
  font-weight:700;display:flex;align-items:center;justify-content:center}
.step h4{margin:8px 0 4px;font-size:14px}
.step p{margin:0;color:var(--muted);font-size:13px}
.tpl{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.tpl a.card{ text-decoration:none;color:inherit;transition:border-color .15s}
.tpl a.card:hover{border-color:var(--accent)}
.tpl .card b{display:block;font-size:14px;margin-bottom:4px}
.tpl .card span{color:var(--muted);font-size:12.5px}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
  color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
a.link{color:var(--accent);text-decoration:none}
a.link:hover{text-decoration:underline}
"""

_JS = """
(function(){
  var root=document.documentElement;
  var stored=null;
  try{stored=localStorage.getItem('dst-theme')}catch(e){}
  if(stored==='dark'||stored==='light'){root.dataset.theme=stored}
  var btn=document.getElementById('theme-toggle');
  if(btn){btn.addEventListener('click',function(){
    var next=root.dataset.theme==='dark'?'light':'dark';
    root.dataset.theme=next;
    try{localStorage.setItem('dst-theme',next)}catch(e){}
    btn.textContent=next==='dark'?'Light mode':'Dark mode';
  });}
  function fallbackCopy(text){
    var ta=document.createElement('textarea');
    ta.value=text;ta.style.position='fixed';ta.style.opacity='0';
    document.body.appendChild(ta);ta.select();
    try{document.execCommand('copy')}catch(e){}
    document.body.removeChild(ta);
  }
  window.dsCopy=function(btn){
    var code=btn.parentNode.querySelector('pre').innerText;
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(code).then(function(){flash(btn)},function(){fallbackCopy(code);flash(btn)});
    }else{fallbackCopy(code);flash(btn)}
  };
  function flash(btn){
    var old=btn.textContent;btn.textContent='Copied';
    setTimeout(function(){btn.textContent=old},1400);
  }
  var filter=document.getElementById('check-filter');
  if(filter){filter.addEventListener('input',function(){
    var q=filter.value.toLowerCase();
    document.querySelectorAll('#check-table tbody tr').forEach(function(tr){
      tr.style.display=tr.innerText.toLowerCase().indexOf(q)>-1?'':'none';
    });
  });}
})();
"""


# --------------------------------------------------------------------------- #
# Small rendering helpers                                                     #
# --------------------------------------------------------------------------- #

def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _pill(passed: bool) -> str:
    cls = "pass" if passed else "fail"
    label = "PASS" if passed else "FAIL"
    return f'<span class="pill {cls}">{label}</span>'


def _check_detail(check: CheckResult) -> str:
    text = _esc(check.detail) if check.detail else "&mdash;"
    return f'<span class="muted" style="font-size:12.5px">{text}</span>'


def _code_block(code: str) -> str:
    return (
        '<div class="block"><button class="copy" onclick="dsCopy(this)">Copy</button>'
        f"<pre><code>{_esc(code)}</code></pre></div>"
    )


def _file_size(path: Path) -> str:
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _render_tree(root: Path, base: Path = None, depth: int = 0) -> str:
    """Render a collapsible file tree rooted at *base* (defaults to repo root)."""
    base = base or root
    parts: List[str] = ['<div class="tree-files">']
    try:
        entries = sorted(
            base.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower()),
        )
    except OSError:
        entries = []
    for entry in entries:
        if entry.name in IGNORED_DIRS or entry.name in IGNORED_FILES:
            continue
        if entry.is_dir():
            if entry.name.endswith(".egg-info") or depth > 4:
                continue
            rel = entry.resolve().relative_to(root.resolve()).as_posix()
            parts.append(
                f'<details class="dir"><summary>{_esc(entry.name)}/</summary>'
                f'{_render_tree(root, entry, depth + 1)}</details>'
            )
        else:
            rel = entry.resolve().relative_to(root.resolve()).as_posix()
            parts.append(
                f'<div class="tree-file"><a href="{_esc(rel)}">{_esc(entry.name)}</a>'
                f'<span class="size">{_file_size(entry)}</span></div>'
            )
    parts.append("</div>")
    return "".join(parts)


def _count_files(root: Path) -> Tuple[int, int]:
    files = dirs = 0
    for path in root.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and ".git" not in path.parts:
            files += 1
        elif path.is_dir() and not any(
            part in IGNORED_DIRS or part.endswith(".egg-info") for part in path.parts
        ):
            dirs += 1
    return files, dirs


# --------------------------------------------------------------------------- #
# Main generator                                                              #
# --------------------------------------------------------------------------- #

def generate_dashboard(root: Path, output_path: Path) -> StewardshipReport:
    """Run all checks and render the dashboard HTML to *output_path*."""
    root = Path(root)
    report = run_all_checks(root)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # -- imports kept local to avoid a circular dependency at module load ---- #
    from .checks import read_inventory, read_rights_register, FIGURE_MANIFEST

    inventory = read_inventory(root)
    register = read_rights_register(root)

    n_figures = 0
    manifest_path = root / FIGURE_MANIFEST
    if manifest_path.exists():
        n_figures = sum(
            1 for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    n_files, n_dirs = _count_files(root)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # -- status banner -------------------------------------------------------- #
    if report.ok:
        banner = (
            '<div class="banner ok"><span class="dot"></span>'
            f"All stewardship checks passed &mdash; {report.passed_checks}/"
            f"{report.total_checks} checks green. Every dataset has a licence, "
            "metadata and a verified checksum; every figure traces to a versioned input.</div>"
        )
    else:
        banner = (
            '<div class="banner bad"><span class="dot"></span>'
            f"Stewardship failures detected &mdash; {report.passed_checks}/{report.total_checks} "
            "checks green. Fix the FAIL rows below; CI will block merges until these pass.</div>"
        )

    # -- KPI cards ------------------------------------------------------------ #
    kpis = "".join(
        f'<div class="card"><div class="kpi">{value}</div><div class="lbl">{_esc(label)}</div></div>'
        for value, label in (
            (len(inventory), "Datasets in inventory"),
            (f"{report.passed_checks}/{report.total_checks}", "Automated checks passed"),
            (len(register), "Registered licences"),
            (n_figures, "Figures traced to inputs"),
            (n_files, "Files under stewardship"),
        )
    )

    # -- check results table -------------------------------------------------- #
    check_rows: List[str] = []
    for ds in report.dataset_reports:
        for i, check in enumerate(ds.checks):
            ds_cell = _esc(ds.dataset_id) if i == 0 else ""
            check_rows.append(
                "<tr>"
                f"<td class='mono'>{ds_cell}</td>"
                f"<td><b>{_esc(check.name)}</b><br>{_check_detail(check)}</td>"
                f"<td>{_pill(check.passed)}</td>"
                "</tr>"
            )
    for check in report.repo_checks:
        check_rows.append(
            "<tr>"
            "<td class='mono muted'>repository</td>"
            f"<td><b>{_esc(check.name)}</b><br>{_check_detail(check)}</td>"
            f"<td>{_pill(check.passed)}</td>"
            "</tr>"
        )
    check_table = "\n".join(check_rows) or "<tr><td colspan='3' class='muted'>No checks recorded.</td></tr>"

    # -- inventory table ------------------------------------------------------- #
    inv_rows = "".join(
        "<tr>"
        f"<td class='mono'>{_esc(row.get('dataset_id', ''))}</td>"
        f"<td>{_esc(row.get('title', ''))}</td>"
        f"<td class='mono'>{_esc(row.get('version', ''))} <span class='pill neutral'>{_esc(row.get('status', ''))}</span></td>"
        f"<td class='mono'>{_esc(row.get('licence_id', ''))}</td>"
        f"<td class='mono'>{_esc(row.get('steward', ''))}</td>"
        f"<td class='mono muted'>{_esc(row.get('updated', ''))}</td>"
        "</tr>"
        for row in inventory
    ) or "<tr><td colspan='6' class='muted'>Inventory is empty.</td></tr>"

    # -- rights register table -------------------------------------------------- #
    reg_rows = "".join(
        "<tr>"
        f"<td class='mono'>{_esc(row.get('licence_id', ''))}</td>"
        f"<td class='mono'>{_esc(row.get('spdx', ''))}</td>"
        f"<td>{_esc(row.get('name', ''))}</td>"
        f"<td class='mono muted'>{_esc(row.get('applies_to', ''))}</td>"
        f"<td>{_esc(row.get('rights_holder', ''))}</td>"
        "</tr>"
        for row in register.values()
    ) or "<tr><td colspan='5' class='muted'>Rights register is empty.</td></tr>"

    # -- usage blocks ------------------------------------------------------------ #
    usage = "".join(
        _code_block(code)
        for code in (
            "git clone https://github.com/YOUR-USERNAME/data-stewardship-toolkit.git\n"
            "cd data-stewardship-toolkit\npip install -e \".[dev]\"",
            "ds-steward check              # every licence / metadata / checksum rule\n"
            "pytest -v                     # the same rules as a test suite\n"
            "ds-steward check --json       # machine-readable report",
            "# Ingest a file as a new version (checksum + provenance + inventory sync)\n"
            "ds-steward ingest --dataset sample_air_quality \\\n"
            "    --file data/raw/air_quality_feb_2024.csv \\\n"
            "    --actor your.name@example.org --bump minor \\\n"
            "    --note \"February 2024 batch\"",
            "# Register a published figure against a versioned input\n"
            "ds-steward figure --figure-id fig02_pm25_trend \\\n"
            "    --dataset sample_air_quality --output figures/fig02.png \\\n"
            "    --script scripts/make_fig02.py --actor your.name@example.org",
            "# Publish the repo to GitHub\n"
            "git init && git add . && git commit -m \"Data stewardship toolkit\"\n"
            "git remote add origin https://github.com/YOUR-USERNAME/data-stewardship-toolkit.git\n"
            "git push -u origin main",
        )
    )

    # -- templates gallery -------------------------------------------------------- #
    templates = "".join(
        f'<a class="card" href="{_esc(rel)}"><b>{_esc(name)}</b><span>{_esc(desc)}</span></a>'
        for rel, name, desc in (
            ("templates/data-management-plan.md", "Data Management Plan",
             "Science Europe style DMP with fill-in sections"),
            ("templates/sop-data-ingestion.md", "SOP: Data ingestion",
             "From raw file to versioned, checksummed dataset"),
            ("templates/sop-checksum-and-versioning.md", "SOP: Checksums & versioning",
             "SHA-256 policy and semver bump rules"),
            ("templates/sop-publication-release.md", "SOP: Publication release",
             "Pre-release checklist and archiving"),
            ("templates/data-request-form.md", "Data request form",
             "Intake form for incoming data requests"),
            ("templates/intake-review-checklist.md", "Intake review checklist",
             "Reviewer gate before a dataset is accepted"),
            ("templates/README-dataset-template.md", "Dataset README",
             "Per-dataset documentation skeleton"),
        )
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Stewardship Toolkit &mdash; Stewardship Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<header class="top">
  <div class="wrap">
    <h1>Data Stewardship Toolkit &mdash; Stewardship Dashboard</h1>
    <p class="sub">Dataset inventory &middot; licence and rights register &middot; metadata &middot;
    checksums &middot; versioned ingestion &middot; figure provenance. Generated by
    <span class="mono">ds-steward {__version__}</span> on {generated_at}.</p>
    <div class="badges">
      <span class="badge">code: MIT</span>
      <span class="badge">demo data: CC0-1.0</span>
      <span class="badge">Python &ge; 3.9</span>
      <span class="badge">pytest + GitHub Actions CI</span>
    </div>
  </div>
</header>
<div class="wrap">
  {banner}

  <div class="grid">{kpis}</div>

  <section id="checks">
    <h2><span class="n">01</span> Automated check results</h2>
    <div class="toolbar">
      <input id="check-filter" class="filter" type="search"
             placeholder="Filter checks (e.g. licence, checksum, a dataset id)&hellip;">
      <button id="theme-toggle" class="btn" type="button">Dark mode</button>
    </div>
    <div class="panel">
      <table id="check-table">
        <thead><tr><th>Dataset</th><th>Check &amp; detail</th><th>Result</th></tr></thead>
        <tbody>{check_table}</tbody>
      </table>
    </div>
  </section>

  <section id="registries">
    <h2><span class="n">02</span> Dataset inventory</h2>
    <div class="panel">
      <table>
        <thead><tr><th>dataset_id</th><th>Title</th><th>Version / status</th>
        <th>Licence</th><th>Steward</th><th>Updated</th></tr></thead>
        <tbody>{inv_rows}</tbody>
      </table>
    </div>
    <h2 style="margin-top:28px"><span class="n">03</span> Licence &amp; rights register</h2>
    <div class="panel">
      <table>
        <thead><tr><th>licence_id</th><th>SPDX</th><th>Name</th>
        <th>Applies to</th><th>Rights holder</th></tr></thead>
        <tbody>{reg_rows}</tbody>
      </table>
    </div>
  </section>

  <section id="usage">
    <h2><span class="n">04</span> Usage (copy &amp; paste)</h2>
    {usage}
  </section>

  <section id="ci">
    <h2><span class="n">05</span> What CI enforces on every push</h2>
    <div class="steps">
      <div class="step"><h4>Install toolkit</h4><p>Python 3.11, <span class="mono">pip install -e ".[dev]"</span></p></div>
      <div class="step"><h4>ds-steward check</h4><p>Licence, metadata, checksum and provenance gates &mdash; fails the build on any gap.</p></div>
      <div class="step"><h4>pytest</h4><p>Unit + repository-level tests, including tamper detection (broken checksum, missing licence).</p></div>
      <div class="step"><h4>Dashboard artifact</h4><p><span class="mono">docs/dashboard.html</span> regenerated and uploaded on every run.</p></div>
    </div>
  </section>

  <section id="tree">
    <h2><span class="n">06</span> Repository file tree</h2>
    <div class="panel" style="padding:10px">
      {_render_tree(root)}
    </div>
  </section>

  <section id="templates">
    <h2><span class="n">07</span> Governance templates</h2>
    <div class="tpl">{templates}</div>
  </section>

  <footer>
    <div>Data Stewardship Toolkit &middot; code licensed MIT &middot; demo datasets CC0-1.0.</div>
    <div>Links resolve when this file is opened from <span class="mono">docs/dashboard.html</span> inside the repository.</div>
  </footer>
</div>
<script>{_JS}</script>
</body>
</html>
"""
    output_path.write_text(html_doc, encoding="utf-8")
    return report
