import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch


LEVEL_ORDER = ["easy", "mid", "hard"]
DISPLAY_LABELS = {
    "Schema grounding error": "Schema grounding",
    "Query-structure error": "Query structure",
    "Condition error": "Condition",
    "General generation error": "General generation",
    "Execution invalidity": "Execution invalidity",
}
PRIMARY_TYPES = [

    "Schema grounding error",
    "Query-structure error",
    "Condition error",
    "General generation error",
    "Execution invalidity",
]

MULTI_TYPES = [
    "Schema grounding error",
    "Query-structure error",
    "Condition error",
    "General generation error",
    "Execution invalidity",
]

# Soft, paper-friendly palette.
COLOR_MAP = {
    "Correct": "#D9D9D9",                  # light gray, low visual weight
    "Schema grounding error": "#8FBAD9",   # soft blue
    "Query-structure error": "#F2B880",    # soft orange
    "Condition error": "#9FD39B",          # soft green
    "General generation error": "#C8B6E2", # soft purple
    "Execution invalidity": "#E6A0A0",     # soft red
}


def read_count_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)

    df.index = df.index.astype(str).str.strip().str.lower()
    df = df.reindex(LEVEL_ORDER)

    for col in columns:
        if col not in df.columns:
            df[col] = 0

    df = df[columns].fillna(0)
    return df


def pie_values(row: pd.Series):
    values = row.astype(float)
    values = values[values > 0]
    labels = values.index.tolist()
    counts = values.values.tolist()
    colors = [COLOR_MAP[x] for x in labels]
    return labels, counts, colors


def autopct_fn(values):
    total = sum(values)

    def _fmt(pct):
        if total <= 0 or pct < 4:
            return ""
        return f"{pct:.1f}%"

    return _fmt


def draw_one_pie(ax, row: pd.Series, title: str):
    labels, values, colors = pie_values(row)

    if not values:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=10)
        ax.set_title(title, fontsize=12)
        ax.axis("off")
        return

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,                 # no direct labels on pie
        colors=colors,
        autopct=autopct_fn(values),
        startangle=90,
        counterclock=False,
        pctdistance=0.68,
        wedgeprops={
            "linewidth": 0.8,
            "edgecolor": "white",
        },
        textprops={
            "fontsize": 15,
            "color": "#222222",
        },
    )

    for t in autotexts:
        t.set_fontsize(15)

    ax.set_title(title, fontsize=12)
    ax.axis("equal")


def draw_pies(
    primary_df: pd.DataFrame,
    multi_df: pd.DataFrame,
    output: Path,
    output_pdf: Path | None,
):
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 8.2))

    for col_idx, level in enumerate(LEVEL_ORDER):
        draw_one_pie(
            axes[0, col_idx],
            primary_df.loc[level],
            f"{level.capitalize()} - Primary",
        )

        draw_one_pie(
            axes[1, col_idx],
            multi_df.loc[level],
            f"{level.capitalize()} - Multi-label",
        )

    legend_types = PRIMARY_TYPES
    handles = [
        Patch(facecolor=COLOR_MAP[t], edgecolor="white", label=DISPLAY_LABELS.get(t, t))
        for t in legend_types
    ]

    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.02),
        frameon=False,
        fontsize=13,
        ncol=len(handles),
        handlelength=1.4,
        handleheight=1.2,
        columnspacing=1.4,
    )
    #fig.suptitle("GPT Error Type Distribution by Tier", fontsize=16)

    # Leave right margin for legend.
    plt.subplots_adjust(
    left=0.04,
    right=0.96,
    top=0.94,
    bottom=0.14,
    wspace=-0.12,
    hspace=0.22,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, bbox_inches="tight")

    if output_pdf is not None:
        fig.savefig(output_pdf, bbox_inches="tight")

    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--primary",
        default="results_analysis/gpt_primary_diff_type_count.csv",
        help="Primary Diff Type count CSV.",
    )
    parser.add_argument(
        "--multi",
        default="results_analysis/gpt_diff_type_multilabel_count_no_correct.csv",
        help="Multi-label Diff Type count CSV without Correct.",
    )
    parser.add_argument(
        "--output",
        default="results_analysis/gpt_diff_type_pies.png",
        help="Output PNG figure.",
    )
    parser.add_argument(
        "--output-pdf",
        default="results_analysis/gpt_diff_type_pies.pdf",
        help="Optional output PDF figure. Use empty string to disable.",
    )
    args = parser.parse_args()

    primary_path = Path(args.primary)
    multi_path = Path(args.multi)
    output_path = Path(args.output)
    output_pdf = Path(args.output_pdf) if args.output_pdf else None

    primary_df = read_count_csv(primary_path, PRIMARY_TYPES)
    multi_df = read_count_csv(multi_path, MULTI_TYPES)

    draw_pies(primary_df, multi_df, output_path, output_pdf)

    print(f"Saved PNG: {output_path}")
    if output_pdf is not None:
        print(f"Saved PDF: {output_pdf}")


if __name__ == "__main__":
    main()