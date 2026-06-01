from __future__ import annotations

import argparse
import collections
import math
import os
from typing import Dict, Iterable, Optional, Tuple
from xml.sax.saxutils import escape

import requests


LANGUAGE_RULES = [
    (("*.tsx", "*.ts"), "TypeScript"),
    (("*.jsx", "*.js", "*.mjs", "*.cjs"), "JavaScript"),
    (("*.go",), "Go"),
    (("*.py",), "Python"),
    (("*.java",), "Java"),
    (("*.cs",), "C#"),
    (("*.rb",), "Ruby"),
    (("*.php",), "PHP"),
    (("*.rs",), "Rust"),
    (("*.kt", "*.kts"), "Kotlin"),
    (("*.swift",), "Swift"),
    (("*.dart",), "Dart"),
    (("*.lua",), "Lua"),
    (("*.sh", "*.bash"), "Shell"),
    (("*.sql",), "SQL"),
    (("*.scala",), "Scala"),
    (("*.c",), "C"),
    (("*.cc", "*.cpp", "*.cxx", "*.hh", "*.hpp", "*.hxx"), "C++"),
    (("*.html", "*.htm"), "HTML"),
    (("*.css",), "CSS"),
    (("*.yml", "*.yaml"), "YAML"),
    (("*.json",), "JSON"),
]

SPECIAL_FILES = {
    "Dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "Makefile": "Makefile",
    "Gemfile": "Ruby",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "go.sum": "Go",
    "package.json": "JavaScript",
    "tsconfig.json": "TypeScript",
    "Pipfile": "Python",
    "requirements.txt": "Python",
}

PALETTE = [
    "#f7df1e",
    "#3178c6",
    "#00add8",
    "#3776ab",
    "#b07219",
    "#178600",
    "#c6538c",
    "#4f5d95",
    "#dea584",
    "#dea584",
    "#a97bff",
    "#ff6b6b",
    "#22c55e",
    "#06b6d4",
    "#8b5cf6",
    "#f97316",
]


def repo_parts() -> Tuple[str, str]:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        return "", ""
    return repo.split("/", 1)


def infer_language(path: str) -> Optional[str]:
    base = path.rsplit("/", 1)[-1]
    if base in SPECIAL_FILES:
        return SPECIAL_FILES[base]

    lower = base.lower()
    for patterns, language in LANGUAGE_RULES:
        for pattern in patterns:
            suffix = pattern[1:].lower()
            if lower.endswith(suffix):
                return language
    return None


def github_get(session: requests.Session, url: str, params: Optional[dict] = None) -> requests.Response:
    resp = session.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp


def list_commits(
    session: requests.Session,
    owner: str,
    repo: str,
    author: str,
    max_commits: int,
) -> Iterable[dict]:
    page = 1
    seen = 0

    while seen < max_commits:
        resp = github_get(
            session,
            f"https://api.github.com/repos/{owner}/{repo}/commits",
            params={
                "author": author,
                "per_page": min(100, max_commits - seen),
                "page": page,
            },
        )
        commits = resp.json()
        if not commits:
            break

        for commit in commits:
            yield commit
            seen += 1
            if seen >= max_commits:
                return

        page += 1


def get_commit(session: requests.Session, owner: str, repo: str, sha: str) -> dict:
    resp = github_get(session, f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}")
    return resp.json()


def polar_to_cartesian(cx: float, cy: float, r: float, angle_deg: float) -> Tuple[float, float]:
    rad = math.radians(angle_deg - 90.0)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def arc_path(cx: float, cy: float, r: float, start_deg: float, end_deg: float) -> str:
    start_x, start_y = polar_to_cartesian(cx, cy, r, end_deg)
    end_x, end_y = polar_to_cartesian(cx, cy, r, start_deg)
    large_arc = 1 if (end_deg - start_deg) > 180 else 0
    return f"M {start_x:.2f} {start_y:.2f} A {r:.2f} {r:.2f} 0 {large_arc} 0 {end_x:.2f} {end_y:.2f}"


def color_for_index(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def build_svg(counts: Dict[str, int], output: str, title: str) -> None:
    filtered = {k: v for k, v in counts.items() if v > 0}
    if not filtered:
        filtered = {"No code files found": 1}

    items = sorted(filtered.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(v for _, v in items)

    width = 1200
    height = 800
    cx = 320
    cy = 400
    radius = 180
    stroke_width = 56

    # Larger gap so rounded caps do not overlap
    gap_deg = max(18.0, math.degrees((stroke_width / radius) * 1.25))

    left_x = 620
    top_y = 180
    row_h = 56

    svg: list[str] = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(title)}">'
    )
    svg.append(
        """
  <defs>
    <style><![CDATA[
      .title {
        font: 700 34px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        fill: #111827;
      }
      .subtitle {
        font: 500 16px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        fill: #6b7280;
      }
      .label {
        font: 600 22px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        fill: #111827;
      }
      .value {
        font: 500 18px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        fill: #374151;
      }
      .legend-row {
        opacity: 0;
      }
    ]]></style>
  </defs>
        """.strip()
    )

    svg.append(f'<text x="{left_x}" y="90" class="title">{escape(title)}</text>')
    svg.append(
        f'<text x="{left_x}" y="122" class="subtitle">'
        f'Language mix inferred from changed files in commits by the selected author'
        f'</text>'
    )

    start_angle = -90.0
    for idx, (language, value) in enumerate(items):
        color = color_for_index(idx)

        available = max(1.0, 360.0 - gap_deg * len(items))
        raw_span = max(1.0, available * (value / total))

        seg_start = start_angle + gap_deg / 2.0
        seg_end = seg_start + raw_span

        path_d = arc_path(cx, cy, radius, seg_start, seg_end)
        arc_len = math.radians(seg_end - seg_start) * radius
        delay = 0.12 + idx * 0.08

        svg.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-dasharray="{arc_len:.2f} {arc_len:.2f}" stroke-dashoffset="{arc_len:.2f}">'
        )
        svg.append(
            f'  <animate attributeName="stroke-dashoffset" from="{arc_len:.2f}" to="0" '
            f'dur="0.9s" begin="{delay:.2f}s" fill="freeze" />'
        )
        svg.append("</path>")

        start_angle = seg_end + gap_deg / 2.0

    for idx, (language, value) in enumerate(items):
        pct = (value / total) * 100.0
        y = top_y + idx * row_h
        color = color_for_index(idx)
        begin = 0.18 + idx * 0.07

        svg.append(
            f'<g class="legend-row" transform="translate({left_x},{y})">'
        )
        svg.append(
            f'  <animate attributeName="opacity" from="0" to="1" '
            f'dur="0.25s" begin="{begin:.2f}s" fill="freeze" />'
        )
        svg.append(
            f'  <rect x="0" y="0" width="18" height="18" rx="6" ry="6" fill="{color}" />'
        )
        svg.append(
            f'  <text x="30" y="16" class="label">{escape(language)}</text>'
        )
        svg.append(
            f'  <text x="250" y="16" class="value">{pct:.1f}%</text>'
        )
        svg.append("</g>")

    svg.append("</svg>")

    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
        

def main() -> None:
    default_owner, default_repo = repo_parts()

    parser = argparse.ArgumentParser(
        description="Generate a transparent animated SVG doughnut chart from GitHub commit languages."
    )
    parser.add_argument("--owner", default=os.environ.get("OWNER") or default_owner)
    parser.add_argument("--repo", default=os.environ.get("REPO") or default_repo)
    parser.add_argument("--author", default=os.environ.get("AUTHOR") or os.environ.get("GITHUB_ACTOR"))
    parser.add_argument("--max-commits", type=int, default=int(os.environ.get("MAX_COMMITS", "200")))
    parser.add_argument("--output", default=os.environ.get("OUTPUT", "language-donut.svg"))
    parser.add_argument("--title", default=os.environ.get("TITLE", "Commit language mix"))
    args = parser.parse_args()

    if not args.owner or not args.repo:
        raise SystemExit("OWNER/REPO or GITHUB_REPOSITORY must be set.")
    if not args.author:
        raise SystemExit("AUTHOR or GITHUB_ACTOR must be set.")

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required.")

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "commit-language-chart",
        }
    )

    counts = collections.Counter()

    for commit in list_commits(session, args.owner, args.repo, args.author, args.max_commits):
        detail = get_commit(session, args.owner, args.repo, commit["sha"])
        for file in detail.get("files", []):
            language = infer_language(file.get("filename", ""))
            if language:
                counts[language] += int(file.get("changes", 0))

    build_svg(dict(counts), args.output, args.title)


if __name__ == "__main__":
    main()
