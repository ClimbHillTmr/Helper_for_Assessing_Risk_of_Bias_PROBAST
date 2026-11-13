#!/usr/bin/env python3
"""Generate standalone 300-DPI workflow diagram for the JOSS software paper.

Outputs:
  - Paper/joss/figures/fig1_harness_workflow.png (2400 x 1050 px @ 300 DPI)
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

    # Exact 2400 x 1050 px at 300 DPI
    fig = plt.figure(figsize=(8.0, 3.5), dpi=300, facecolor="white")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], facecolor="white")
    ax.set_xlim(0.0, 8.0)
    ax.set_ylim(0.0, 3.5)
    ax.axis("off")

    # Main Title & Subtitle
    ax.text(
        4.0,
        3.29,
        "Medical Research Harness: Zero-Dependency Python 3.10+ Standard-Library Workflow",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color=TEXT_DARK,
    )
    ax.text(
        4.0,
        3.07,
        "Deterministic local provenance locking, planned-vs.-executed manifest auditing, and read-only code/XML verification",
        ha="center",
        va="center",
        fontsize=7.0,
        color=TEXT_MUTED,
    )

    stages = [
        {
            "num": "STAGE 1",
            "subtag": "PROTOCOL LOCK",
            "title": "Governance &\nProtocol Lock",
            "color": SLATE_BLUE,
            "tint": BLUE_TINT,
            "cli": "check_bundle.py\nstudy.py plan",
            "bullets": [
                "• Verifies phase role locators\n  & SHA-256 document locks",
                "• Computes design_sha256 over\n  study.json, rows.csv, folds.csv",
                "• Emits immutable task specs\n  initialized in DRAFT state",
            ],
        },
        {
            "num": "STAGE 2",
            "subtag": "COHORT & FITS",
            "title": "14-Invariant\nManifest Audit",
            "color": SLATE_BLUE,
            "tint": BLUE_TINT,
            "cli": "study.py audit\n--mode planned | executed",
            "bullets": [
                "• Cohort partition disjointness\n  (patient_overlap, fold roles)",
                "• Clinical temporal ordering\n  (feature_max_time <= index_time)",
                "• Separates planned vs. runtime\n  executed fold-fit scopes",
            ],
        },
        {
            "num": "STAGE 3",
            "subtag": "STATIC & XML",
            "title": "Read-Only Code &\nJATS XML Audit",
            "color": TEAL,
            "tint": TEAL_TINT,
            "cli": "project_audit.py\nliterature.py",
            "bullets": [
                "• Python AST + R/SAS static scan\n  under tree SHA-256 snapshot",
                "• Expat XXE/DTD guard & equal-\n  length coordinate masking",
                "• S001..S008 span offset lock:\n  $T[a_k : a_k + L_k] \\equiv q_k$",
            ],
        },
        {
            "num": "STAGE 4",
            "subtag": "SAFETY GATE",
            "title": "Registry Reconciliation\n& Safety Gate",
            "color": TEAL,
            "tint": TEAL_TINT,
            "cli": "study.py summarize\nworkflow.py",
            "bullets": [
                "• Recomputes executed audits\n  freshly from source manifests",
                "• Preserves FAILED, ABORTED,\n  RUNNING, and NOT_RUN runs",
                "• Enforces execution_authorized:\n  false, scientific_acceptance: false",
            ],
        },
    ]

    margin_x = 0.18
    gap_x = 0.22
    card_w = (8.0 - 2 * margin_x - 3 * gap_x) / 4.0  # 1.745 in
    card_y = 0.59
    card_h = 2.31
    header_h = 0.62

    for idx, st in enumerate(stages):
        x0 = margin_x + idx * (card_w + gap_x)
        top_y = card_y + card_h

        # Card body container
        card_box = FancyBboxPatch(
            (x0, card_y),
            card_w,
            card_h,
            boxstyle="round,pad=0.0,rounding_size=0.07",
            linewidth=1.25,
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
            linewidth=0.9,
            zorder=4,
        )

        # Stage badge pill at top-left inside header + subtle right-aligned subtag
        badge_w = 0.49
        badge_h = 0.145
        badge = FancyBboxPatch(
            (x0 + 0.09, top_y - 0.205),
            badge_w,
            badge_h,
            boxstyle="round,pad=0.0,rounding_size=0.04",
            linewidth=0.0,
            facecolor=st["color"],
            zorder=5,
        )
        ax.add_patch(badge)
        ax.text(
            x0 + 0.09 + badge_w / 2.0,
            top_y - 0.132,
            st["num"],
            ha="center",
            va="center",
            fontsize=5.6,
            fontweight="bold",
            color="white",
            zorder=6,
        )
        ax.text(
            x0 + card_w - 0.09,
            top_y - 0.132,
            st["subtag"],
            ha="right",
            va="center",
            fontsize=5.2,
            fontweight="bold",
            color=st["color"],
            zorder=6,
        )

        # Full-width stage title inside header below badge
        ax.text(
            x0 + 0.09,
            top_y - 0.415,
            st["title"],
            ha="left",
            va="center",
            fontsize=7.1,
            fontweight="bold",
            color=TEXT_DARK,
            linespacing=1.16,
            zorder=6,
        )

        # Two-line CLI pill below header
        cli_h = 0.28
        cli_y = top_y - header_h - 0.34
        cli_box = FancyBboxPatch(
            (x0 + 0.08, cli_y),
            card_w - 0.16,
            cli_h,
            boxstyle="round,pad=0.0,rounding_size=0.04",
            linewidth=0.75,
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
            fontsize=5.75,
            family="monospace",
            fontweight="bold",
            color=st["color"],
            linespacing=1.22,
            zorder=5,
        )

        # Three concise bullet blocks with generous vertical spacing
        bullet_tops = [cli_y - 0.09, cli_y - 0.50, cli_y - 0.91]
        for b_y, b_txt in zip(bullet_tops, st["bullets"]):
            ax.text(
                x0 + 0.09,
                b_y,
                b_txt,
                ha="left",
                va="top",
                fontsize=6.05,
                color=TEXT_DARK,
                linespacing=1.22,
                zorder=5,
            )

        # Horizontal connector arrow to next stage
        if idx < len(stages) - 1:
            arr_x0 = x0 + card_w + 0.025
            arr_x1 = x0 + card_w + gap_x - 0.025
            arr_y = card_y + card_h * 0.48
            arrow_color = SLATE_BLUE if idx == 0 else TEAL
            arrow = FancyArrowPatch(
                (arr_x0, arr_y),
                (arr_x1, arr_y),
                arrowstyle="-|>,head_length=5.5,head_width=3.6",
                linewidth=1.6,
                color=arrow_color,
                zorder=6,
            )
            ax.add_patch(arrow)

    # Bottom provenance & privacy guarantee bar (two balanced lines, zero clipping)
    footer = FancyBboxPatch(
        (margin_x, 0.09),
        8.0 - 2 * margin_x,
        0.39,
        boxstyle="round,pad=0.0,rounding_size=0.06",
        linewidth=0.9,
        edgecolor=BORDER_GRAY,
        facecolor=FOOTER_BG,
        zorder=2,
    )
    ax.add_patch(footer)
    ax.text(
        4.0,
        0.285,
        "Pure Python 3.10+ Standard Library Only (ast, csv, hashlib, json, re, xml.parsers.expat, zipfile)\n"
        "Local Aggregate Manifests Only (no raw patient rows, embeddings, or credentials)   •   "
        "Atomic completion.json SHA-256 Artifact Binding",
        ha="center",
        va="center",
        fontsize=6.15,
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
