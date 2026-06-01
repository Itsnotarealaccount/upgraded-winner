from __future__ import annotations

import argparse
import collections
import os
from typing import Dict, Iterable, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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


def build_chart(counts: Dict[str, int], output: str, title: str) -> None:
    filtered = {k: v for k, v in counts.items() if v > 0}
    if not filtered:
        filtered = {"No code files found": 1}

    labels = list(filtered.keys())
    values = list(filtered.values())

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"aspect": "equal"})
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")

    wedges, _ = ax.pie(
        values,
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.38, "edgecolor": "none"},
    )
    ax.set_title(title, pad=16)

    legend_labels = [f"{label} — {value}" for label, value in zip(labels, values)]
    ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
    )

    plt.tight_layout()
    plt.savefig(output, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    default_owner, default_repo = repo_parts()

    parser = argparse.ArgumentParser(
        description="Generate a transparent SVG doughnut chart from GitHub commit languages."
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

    build_chart(dict(counts), args.output, args.title)


if __name__ == "__main__":
    main()
