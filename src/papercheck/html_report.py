"""HTML report generator for papercheck results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from papercheck.models import CheckResult, Issue

# --- CSS ---

_CSS = """\
:root {
    --bg: #1a1b26;
    --surface: #24283b;
    --surface2: #2f3349;
    --text: #c0caf5;
    --text-muted: #565f89;
    --border: #3b4261;
    --error: #f7768e;
    --warning: #e0af68;
    --info: #7aa2f7;
    --success: #9ece6a;
    --score-green: #9ece6a;
    --score-yellow: #e0af68;
    --score-red: #f7768e;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
                 Ubuntu, Cantarell, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
    max-width: 960px;
    margin: 0 auto;
}
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
/* Score gauge */
.score-section { display: flex; align-items: center; gap: 2rem; margin-bottom: 2rem; }
.score-ring {
    position: relative; width: 100px; height: 100px;
}
.score-ring svg { transform: rotate(-90deg); }
.score-ring circle {
    fill: none; stroke-width: 8; cx: 50; cy: 50; r: 42;
}
.score-ring .track { stroke: var(--surface2); }
.score-ring .fill { stroke-linecap: round; transition: stroke-dashoffset 0.5s; }
.score-value {
    position: absolute; inset: 0; display: flex; align-items: center;
    justify-content: center; font-size: 1.6rem; font-weight: 700;
}
/* Stats */
.stats { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.stat { text-align: center; }
.stat-num { font-size: 1.4rem; font-weight: 700; }
.stat-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; }
.stat-error .stat-num { color: var(--error); }
.stat-warning .stat-num { color: var(--warning); }
.stat-info .stat-num { color: var(--info); }
/* Category groups */
details {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; margin-bottom: 0.75rem;
}
summary {
    padding: 0.75rem 1rem; cursor: pointer; font-weight: 600;
    list-style: none; display: flex; align-items: center; gap: 0.5rem;
}
summary::before { content: "\25b6"; font-size: 0.7rem; transition: transform 0.2s; }
details[open] summary::before { transform: rotate(90deg); }
summary .badge {
    margin-left: auto; background: var(--surface2); border-radius: 12px;
    padding: 0.15rem 0.6rem; font-size: 0.75rem; color: var(--text-muted);
}
/* Issue rows */
.issue {
    padding: 0.6rem 1rem; border-top: 1px solid var(--border);
    display: grid; grid-template-columns: auto 1fr auto; gap: 0.5rem;
    align-items: start;
}
.severity-dot {
    width: 8px; height: 8px; border-radius: 50%; margin-top: 0.45rem;
}
.severity-dot.error { background: var(--error); }
.severity-dot.warning { background: var(--warning); }
.severity-dot.info { background: var(--info); }
.issue-body { min-width: 0; }
.issue-code { font-size: 0.75rem; color: var(--text-muted); font-family: monospace; }
.issue-msg { font-size: 0.875rem; }
.issue-suggestion {
    font-size: 0.8rem; color: var(--info); margin-top: 0.2rem; font-style: italic;
}
.issue-loc {
    font-size: 0.75rem; color: var(--text-muted); font-family: monospace;
    white-space: nowrap;
}
.no-issues { padding: 2rem; text-align: center; color: var(--text-muted); }
"""


def _score_color(score: int) -> str:
    if score >= 80:
        return "var(--score-green)"
    if score >= 50:
        return "var(--score-yellow)"
    return "var(--score-red)"


def _circumference() -> float:
    return 2 * 3.14159265 * 42


def _dash_offset(score: int) -> float:
    circ = _circumference()
    return circ - (circ * score / 100)


def _escape(text: str) -> str:
    out = text.replace("&", "&amp;").replace("<", "&lt;")
    return out.replace(">", "&gt;").replace('"', "&quot;")


def _render_issue(issue: Issue) -> str:
    sev = issue.severity.value
    loc = ""
    if issue.location:
        loc_text = f"{issue.location.file}:{issue.location.line}"
        if issue.location.col:
            loc_text += f":{issue.location.col}"
        loc = f'<span class="issue-loc">{_escape(loc_text)}</span>'

    suggestion = ""
    if issue.suggestion:
        suggestion = f'<div class="issue-suggestion">{_escape(issue.suggestion)}</div>'

    return (
        f'<div class="issue">'
        f'<span class="severity-dot {sev}"></span>'
        f'<div class="issue-body">'
        f'<span class="issue-code">{_escape(issue.code)}</span> '
        f'<span class="issue-msg">{_escape(issue.message)}</span>'
        f"{suggestion}"
        f"</div>"
        f"{loc}"
        f"</div>"
    )


def generate_html_report(result: CheckResult, output_path: Path | None = None) -> str:
    """Generate standalone HTML report. Returns HTML string, optionally writes to file."""
    score = result.score
    color = _score_color(score)
    circ = _circumference()
    offset = _dash_offset(score)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    by_cat = result.by_category()

    # Build category sections
    category_html = ""
    for cat, issues in sorted(by_cat.items(), key=lambda x: len(x[1]), reverse=True):
        rows = "\n".join(_render_issue(i) for i in issues)
        category_html += (
            f"<details>\n"
            f'<summary>{_escape(cat.value)}<span class="badge">{len(issues)}</span></summary>\n'
            f"{rows}\n"
            f"</details>\n"
        )

    if not by_cat:
        category_html = '<div class="no-issues">No issues found. Nice work!</div>'

    html = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>papercheck report</title>\n"
        f"<style>\n{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>papercheck report</h1>\n"
        f'<p class="subtitle">Generated {_escape(timestamp)}</p>\n'
        '<div class="score-section">\n'
        '  <div class="score-ring">\n'
        '    <svg viewBox="0 0 100 100">\n'
        f'      <circle class="track"></circle>\n'
        f'      <circle class="fill" stroke="{color}" '
        f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"></circle>\n'
        "    </svg>\n"
        f'    <span class="score-value" style="color:{color}">{score}</span>\n'
        "  </div>\n"
        '  <div class="stats">\n'
        f'    <div class="stat stat-error">'
        f'<div class="stat-num">{result.error_count}</div>'
        f'<div class="stat-label">Errors</div></div>\n'
        f'    <div class="stat stat-warning">'
        f'<div class="stat-num">{result.warning_count}</div>'
        f'<div class="stat-label">Warnings</div></div>\n'
        f'    <div class="stat stat-info">'
        f'<div class="stat-num">{result.info_count}</div>'
        f'<div class="stat-label">Info</div></div>\n'
        f'    <div class="stat">'
        f'<div class="stat-num">{len(result.files_checked)}</div>'
        f'<div class="stat-label">Files</div></div>\n'
        f'    <div class="stat">'
        f'<div class="stat-num">{result.total_lines}</div>'
        f'<div class="stat-label">Lines</div></div>\n'
        "  </div>\n"
        "</div>\n"
        f"{category_html}"
        "</body>\n"
        "</html>\n"
    )

    if output_path is not None:
        Path(output_path).write_text(html, encoding="utf-8")

    return html
