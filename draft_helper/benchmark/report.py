"""Render a BenchmarkReport as markdown (for reading) or JSON (for storage)."""
from __future__ import annotations

import json

from .models import BenchmarkReport


def render_markdown(report: BenchmarkReport) -> str:
    lines: list[str] = []
    lines.append(f"# Draft benchmark — {report.set_code}")
    lines.append(f"Source: `{report.source}`")
    lines.append("")
    lines.append(f"- **Agreement rate:** {report.agreement_rate:.0%}")
    lines.append(f"- **Mean rank of human's pick:** {report.mean_human_rank:.2f}")
    lines.append(f"- **Coverage:** scored {report.scored_count}/"
                 f"{len(report.results)} picks "
                 f"({report.skipped_count} skipped as unrecognized)")
    lines.append("")

    lines.append("| Pack | Pick | Tool pick | Human pick | Agree | Human rank |")
    lines.append("|-----:|-----:|-----------|------------|:-----:|-----------:|")
    for r in report.results:
        agree = "—" if not r.scored else ("✓" if r.agree else "✗")
        rank = "—" if not r.scored else str(r.human_rank)
        lines.append(f"| {r.pack_number} | {r.pick_number} | {r.tool_pick} | "
                     f"{r.human_pick} | {agree} | {rank} |")
    lines.append("")

    disagreements = [r for r in report.results if r.scored and not r.agree]
    disagreements.sort(key=lambda r: r.human_rank, reverse=True)
    if disagreements:
        lines.append("## Biggest disagreements")
        for r in disagreements:
            lines.append(f"- P{r.pack_number}P{r.pick_number}: tool took "
                         f"`{r.tool_pick}`, human took `{r.human_pick}` "
                         f"(human's pick ranked #{r.human_rank})")
    return "\n".join(lines)


def render_json(report: BenchmarkReport) -> str:
    payload = {
        "set_code": report.set_code,
        "source": report.source,
        "agreement_rate": report.agreement_rate,
        "mean_human_rank": report.mean_human_rank,
        "scored_count": report.scored_count,
        "skipped_count": report.skipped_count,
        "results": [
            {
                "pack_number": r.pack_number,
                "pick_number": r.pick_number,
                "tool_pick": r.tool_pick,
                "human_pick": r.human_pick,
                "agree": r.agree,
                "human_rank": r.human_rank,
                "pack_size": r.pack_size,
                "scored": r.scored,
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, indent=2)
