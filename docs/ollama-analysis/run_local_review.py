#!/usr/bin/env python3
"""Drive a local Ollama model through a code review of a repository.

Zero-dependency (stdlib only). Point it at a repo and a model tag, and it:
  1. walks the repo's Python sources (largest-first, budget-capped),
  2. asks the model for a structured review of each file,
  3. asks the model for a whole-repo synthesis at the end,
  4. writes everything to a markdown report you can diff/commit.

Interactive mode (--chat) drops you into a REPL with the review context
loaded, so you can argue with the model about its findings.

Examples:
    # one-shot review of commander-builder with the recommended coder model
    python run_local_review.py ~/code/commander-builder --model qwen2.5-coder:7b

    # domain-analyst pass with a reasoning model, then discuss
    python run_local_review.py ~/code/commander-builder \
        --model qwen3:14b --persona analyst --chat

Requires an Ollama daemon (https://ollama.com) on localhost:11434 and the
model already pulled (`ollama pull qwen2.5-coder:7b`).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://localhost:11434"

PERSONAS = {
    "reviewer": (
        "You are a rigorous senior Python code reviewer. Report only defects "
        "you can justify from the code shown: bugs, fragile error handling, "
        "JSON-parsing weaknesses, statistics mistakes, dead code, and API "
        "misuse. For each finding give severity (high/med/low), the line, "
        "why it fails, and a concrete fix. If the code is fine, say so "
        "briefly — do not invent problems."
    ),
    "analyst": (
        "You are a Magic: The Gathering Commander format expert reviewing "
        "deck-building software. Judge the *game logic*: land counts, "
        "ramp/draw/removal quotas, bracket rules, archetype detection, "
        "EDHREC usage, simulation validity for 4-player Commander. Flag "
        "heuristics that diverge from current community consensus and "
        "suggest domain improvements. Ignore code style."
    ),
}

FILE_PROMPT = "Review this file from the repository '{repo}'.\n\nFILE: {path}\n\n```python\n{code}\n```"

SYNTH_PROMPT = (
    "You have now reviewed {n} files from '{repo}'. Here are your per-file "
    "findings:\n\n{findings}\n\nSynthesize: (1) the 5 most important issues "
    "overall, (2) cross-cutting patterns, (3) the top 5 improvements you "
    "would make to this application. Be specific."
)


def ollama_chat(url: str, model: str, messages: list[dict], timeout: int = 600) -> str:
    """POST to /api/chat and return the assistant text (non-streaming)."""
    body = json.dumps(
        {"model": model, "messages": messages, "stream": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("message", {}).get("content", "")


def check_daemon(url: str, model: str) -> None:
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=5) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        sys.exit(
            f"error: no Ollama daemon at {url} ({exc}). Start it with "
            f"`ollama serve` (or install from https://ollama.com)."
        )
    names = {m["name"] for m in tags.get("models", [])}
    if model not in names and model.split(":")[0] not in {n.split(":")[0] for n in names}:
        sys.exit(
            f"error: model '{model}' not found locally. Run: ollama pull {model}\n"
            f"available: {', '.join(sorted(names)) or '(none)'}"
        )


def collect_files(repo: Path, limit_kb: int, max_files: int) -> list[Path]:
    skip_parts = {".git", "vendor", "node_modules", "__pycache__", ".venv", "venv"}
    files = [
        p
        for p in repo.rglob("*.py")
        if not skip_parts.intersection(p.relative_to(repo).parts)
        and p.stat().st_size <= limit_kb * 1024
    ]
    # Largest first: the big orchestrators are where reviews pay off.
    files.sort(key=lambda p: p.stat().st_size, reverse=True)
    return files[:max_files]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo", type=Path, help="path to the repository to review")
    ap.add_argument("--model", default="qwen2.5-coder:7b", help="Ollama model tag")
    ap.add_argument("--url", default=DEFAULT_URL, help="Ollama base URL")
    ap.add_argument("--persona", choices=sorted(PERSONAS), default="reviewer")
    ap.add_argument("--max-files", type=int, default=12, help="files per run")
    ap.add_argument("--limit-kb", type=int, default=64, help="skip files larger than this")
    ap.add_argument("--out", type=Path, default=None, help="markdown report path")
    ap.add_argument("--chat", action="store_true", help="interactive discussion after review")
    args = ap.parse_args()

    repo = args.repo.expanduser().resolve()
    if not repo.is_dir():
        sys.exit(f"error: {repo} is not a directory")
    check_daemon(args.url, args.model)

    files = collect_files(repo, args.limit_kb, args.max_files)
    if not files:
        sys.exit("error: no reviewable .py files found")

    out = args.out or Path(f"ollama-review-{repo.name}-{time.strftime('%Y%m%d-%H%M%S')}.md")
    system = PERSONAS[args.persona]
    report_lines = [
        f"# Ollama {args.persona} review of `{repo.name}`",
        f"- model: `{args.model}`  \n- date: {time.strftime('%Y-%m-%d %H:%M')}  \n- files: {len(files)}",
        "",
    ]
    findings_digest: list[str] = []

    for i, path in enumerate(files, 1):
        rel = path.relative_to(repo)
        code = path.read_text(encoding="utf-8", errors="replace")
        print(f"[{i}/{len(files)}] {rel} ({len(code) // 1024}KB)...", flush=True)
        t0 = time.time()
        try:
            answer = ollama_chat(
                args.url,
                args.model,
                [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": FILE_PROMPT.format(repo=repo.name, path=rel, code=code),
                    },
                ],
            )
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            answer = f"(review failed: {exc})"
        dt = time.time() - t0
        print(f"    done in {dt:.0f}s", flush=True)
        report_lines += [f"## {rel}", "", answer.strip(), ""]
        findings_digest.append(f"### {rel}\n{answer.strip()[:2000]}")

    print("synthesizing...", flush=True)
    synthesis = ollama_chat(
        args.url,
        args.model,
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": SYNTH_PROMPT.format(
                    n=len(files), repo=repo.name, findings="\n\n".join(findings_digest)
                ),
            },
        ],
    )
    report_lines += ["## Synthesis", "", synthesis.strip(), ""]
    out.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nreport written to {out}")

    if args.chat:
        history = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "Here is your review synthesis for context:\n" + synthesis,
            },
            {"role": "assistant", "content": "Understood. Ask me anything about the review."},
        ]
        print("\ninteractive mode — empty line or Ctrl-D to quit")
        while True:
            try:
                q = input("you> ").strip()
            except EOFError:
                break
            if not q:
                break
            history.append({"role": "user", "content": q})
            reply = ollama_chat(args.url, args.model, history)
            history.append({"role": "assistant", "content": reply})
            print(f"\n{args.model}> {reply}\n")


if __name__ == "__main__":
    main()
