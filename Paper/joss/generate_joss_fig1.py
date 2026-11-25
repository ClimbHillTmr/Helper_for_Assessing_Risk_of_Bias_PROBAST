#!/usr/bin/env python3
"""Generate standalone 300-DPI workflow diagram for the JOSS software paper.

Outputs:
  - Paper/joss/figures/fig1_harness_workflow.png (2400 x 1230 px @ 300 DPI)
  - Paper/joss/figures/fig1_harness_workflow.pdf (vector PDF)
"""

from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# Okabe-Ito colorblind-safe palette + high-contrast neutrals on white
SLATE_BLUE = "#0072B2"
TEAL = "#009E73"
BLUE_TINT = "#EEF6FB"
TEAL_TINT = "#EDF8F5"
CODE_BG = "#F3F5F8"
BORDER_GRAY = "#CBD5E1"
TEXT_DARK = "#0F172A"
TEXT_MUTED = "#334155"
FOOTER_BG = "#F8FAFC"


def build_figure() -> None:
    out_dir = Path(__file__).resolve().parent / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    # 2400 x 1230 px at 300 DPI for crisp >=7pt print-equivalent readability in JOSS column width
    fig = plt.figure(figsize=(8.0, 4.1), dpi=300, facecolor="white")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], facecolor="white")
    ax.set_xlim(0.0, 8.0)
    ax.set_ylim(0.0, 4.1)
    ax.axis("off")

    # Main Title & Subtitle
    ax.text(
        4.0,
        3.86,
        "Medical Research Harness: Python 3.10+ Standard-Library Workflow",
        ha="center",
        va="center",
        fontsize=11.2,
        fontweight="bold",
        color=TEXT_DARK,
    )
    ax.text(
        4.0,
        3.60,
        "Protocol SHA-256 locking, planned-vs.-executed manifest auditing, and read-only code/XML checks",
        ha="center",
        va="center",
        fontsize=8.0,
        color=TEXT_MUTED,
    )

    stages = [
        {
            "num": "STAGE 1",
            "subtag": "LOCK",
            "title": "Governance &\nProtocol Lock",
            "color": SLATE_BLUE,
            "tint": BLUE_TINT,
            "cli": "check-bundle\nstudy plan",
            "bullets": [
                "• Checks phase role locators\n  & document SHA-256 locks",
                "• Binds design_sha256 over\n  protocol, rows, and folds",
                "• Emits DRAFT task specs\n  (requires --lab preflight)",
            ],
        },
        {
            "num": "STAGE 2",
            "subtag": "MANIFESTS",
            "title": "Deterministic\nManifest Audit",
            "color": SLATE_BLUE,
            "tint": BLUE_TINT,
            "cli": "study audit\nplanned | executed",
            "bullets": [
                "• Patient disjointness across\n  outer and internal folds",
                "• Clinical temporal ordering\n  (feature_max <= index)",
                "• Separates planned scopes\n  from executed fit logs",
            ],
        },
        {
            "num": "STAGE 3",
            "subtag": "READ-ONLY",
            "title": "Code & JATS\nXML Inspection",
            "color": TEAL,
            "tint": TEAL_TINT,
            "cli": "project-audit\nliterature",
            "bullets": [
                "• Python AST & R/SAS scan\n  under tree SHA-256 lock",
                "• Expat DTD/entity guard &\n  table/figure masking",
                "• Exact span offset lock:\n  $T[a_k : a_k + L_k] = q_k$",
            ],
        },
        {
            "num": "STAGE 4",
            "subtag": "RECONCILE",
            "title": "Run Reconciliation\n& Safety Gate",
            "color": TEAL,
            "tint": TEAL_TINT,
            "cli": "study summarize\nworkflow",
            "bullets": [
                "• Recomputes executed audits\n  freshly from manifests",
                "• Preserves FAILED, ABORTED,\n  RUNNING & NOT_RUN runs",
                "• Withholds execution &\n  scientific acceptance",
            ],
        },
    ]

    margin_x = 0.14
    gap_x = 0.20
    card_w = (8.0 - 2 * margin_x - 3 * gap_x) / 4.0  # 1.78 in
    card_y = 0.66
    card_h = 2.74
    header_h = 0.72

    for idx, st in enumerate(stages):
        x0 = margin_x + idx * (card_w + gap_x)
        top_y = card_y + card_h

        # Card body container
        card_box = FancyBboxPatch(
            (x0, card_y),
            card_w,
            card_h,
            boxstyle="round,pad=0.0,rounding_size=0.07",
            linewidth=1.35,
            edgecolor=st["color"],
            facecolor="white",
            zorder=2,
        )
        ax.add_patch(card_box)

        # Soft header fill
        header_box = FancyBboxPatch(
            (x0, top_y - header_h),
            card_w,
            header_h,
            boxstyle="round,pad=0.0,rounding_size=0.07",
            linewidth=0.0,
            edgecolor="none",
            facecolor=st["tint"],
            zorder=3,
        )
        ax.add_patch(header_box)

        # Square off bottom corners of header tint and draw divider line
        ax.fill_between(
            [x0 + 0.01, x0 + card_w - 0.01],
            top_y - header_h,
            top_y - header_h + 0.09,
            color=st["tint"],
            zorder=3,
        )
        ax.plot(
            [x0, x0 + card_w],
            [top_y - header_h, top_y - header_h],
            color=st["color"],
            linewidth=1.0,
            zorder=4,
        )

        # Stage badge pill + subtle subtag
        badge_w = 0.60
        badge_h = 0.175
        badge = FancyBboxPatch(
            (x0 + 0.08, top_y - 0.235),
            badge_w,
            badge_h,
            boxstyle="round,pad=0.0,rounding_size=0.04",
            linewidth=0.0,
            facecolor=st["color"],
            zorder=5,
        )
        ax.add_patch(badge)
        ax.text(
            x0 + 0.08 + badge_w / 2.0,
            top_y - 0.148,
            st["num"],
            ha="center",
            va="center",
            fontsize=6.8,
            fontweight="bold",
            color="white",
            zorder=6,
        )
        ax.text(
            x0 + card_w - 0.08,
            top_y - 0.148,
            st["subtag"],
            ha="right",
            va="center",
            fontsize=6.3,
            fontweight="bold",
            color=st["color"],
            zorder=6,
        )

        # Stage title inside header
        ax.text(
            x0 + 0.08,
            top_y - 0.485,
            st["title"],
            ha="left",
            va="center",
            fontsize=8.3,
            fontweight="bold",
            color=TEXT_DARK,
            linespacing=1.15,
            zorder=6,
        )

        # Two-line CLI pill below header
        cli_h = 0.35
        cli_y = top_y - header_h - 0.42
        cli_box = FancyBboxPatch(
            (x0 + 0.07, cli_y),
            card_w - 0.14,
            cli_h,
            boxstyle="round,pad=0.0,rounding_size=0.04",
            linewidth=0.85,
            edgecolor=BORDER_GRAY,
            facecolor=CODE_BG,
            zorder=4,
        )
        ax.add_patch(cli_box)
        ax.text(
            x0 + card_w / 2.0,
            cli_y + cli_h / 2.0,
            st["cli"],
            ha="center",
            va="center",
            fontsize=7.2,
            family="monospace",
            fontweight="bold",
            color=st["color"],
            linespacing=1.22,
            zorder=5,
        )

        # Three concise, larger-font bullet blocks
        bullet_tops = [cli_y - 0.11, cli_y - 0.60, cli_y - 1.09]
        for b_y, b_txt in zip(bullet_tops, st["bullets"]):
            ax.text(
                x0 + 0.08,
                b_y,
                b_txt,
                ha="left",
                va="top",
                fontsize=7.15,
                color=TEXT_DARK,
                linespacing=1.24,
                zorder=5,
            )

        # Horizontal connector arrow to next stage
        if idx < len(stages) - 1:
            arr_x0 = x0 + card_w + 0.02
            arr_x1 = x0 + card_w + gap_x - 0.02
            arr_y = card_y + card_h * 0.48
            arrow_color = SLATE_BLUE if idx == 0 else TEAL
            arrow = FancyArrowPatch(
                (arr_x0, arr_y),
                (arr_x1, arr_y),
                arrowstyle="-|>,head_length=5.5,head_width=3.6",
                linewidth=1.7,
                color=arrow_color,
                zorder=6,
            )
            ax.add_patch(arrow)

    # Bottom provenance & privacy guarantee bar
    footer = FancyBboxPatch(
        (margin_x, 0.10),
        8.0 - 2 * margin_x,
        0.44,
        boxstyle="round,pad=0.0,rounding_size=0.06",
        linewidth=0.95,
        edgecolor=BORDER_GRAY,
        facecolor=FOOTER_BG,
        zorder=2,
    )
    ax.add_patch(footer)
    ax.text(
        4.0,
        0.32,
        "Python 3.10+ Standard Library Core (ast, csv, hashlib, json, re, xml.parsers.expat, zipfile)\n"
        "Local Row-Level Metadata Inputs; Aggregate Diagnostics   •   SHA-256 Artifact Binding (completion.json)",
        ha="center",
        va="center",
        fontsize=7.3,
        color=TEXT_MUTED,
        linespacing=1.35,
        zorder=4,
    )

    png_path = out_dir / "fig1_harness_workflow.png"
    pdf_path = out_dir / "fig1_harness_workflow.pdf"
    fig.savefig(png_path, dpi=300, facecolor="white")
    fig.savefig(pdf_path, facecolor="white")
    plt.close(fig)
    print(f"Saved {png_path} and {pdf_path}")


if __name__ == "__main__":
    build_figure()
