#!/usr/bin/env python3
"""
Generate polished charts for the fio benchmark report.

- Chart 1: block size impact (line charts)
- Chart 2: iodepth effect (line charts)
- Chart 3: numjobs effect (line charts)
- Chart 4: I/O engine comparison (grouped bar charts)

The figures are saved both in the lab root and in the LaTeX `images/`
directory so the report can be recompiled directly after regeneration.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D


# ============================================================
# DATA
# ============================================================
bs_labels = ["4k", "8k", "16k", "32k", "64k", "128k"]

seq_read_bs = {
    "4k": {"iops": 454000, "bw": 1859, "lat": 1.51},
    "8k": {"iops": 278900, "bw": 2231, "lat": 3.57},
    "16k": {"iops": 172900, "bw": 2767, "lat": 5.68},
    "32k": {"iops": 108000, "bw": 3457, "lat": 9.13},
    "64k": {"iops": 60.7e3, "bw": 3888, "lat": 16.22},
    "128k": {"iops": 32.7e3, "bw": 4189, "lat": 30.26},
}
seq_write_bs = {
    "4k": {"iops": 467000, "bw": 1915, "lat": 1.72},
    "8k": {"iops": 283100, "bw": 2265, "lat": 3.50},
    "16k": {"iops": 178200, "bw": 2852, "lat": 5.56},
    "32k": {"iops": 110800, "bw": 3545, "lat": 8.91},
    "64k": {"iops": 62.6e3, "bw": 4006, "lat": 15.75},
    "128k": {"iops": 33.8e3, "bw": 4330, "lat": 30.04},
}
rnd_read_bs = {
    "4k": {"iops": 13.0e3, "bw": 57.2, "lat": 0.069},
    "8k": {"iops": 12.8e3, "bw": 111.3, "lat": 0.14},
    "16k": {"iops": 10.6e3, "bw": 181.7, "lat": 0.26},
    "32k": {"iops": 8.1e3, "bw": 269, "lat": 0.40},
    "64k": {"iops": 5.8e3, "bw": 387, "lat": 0.80},
    "128k": {"iops": 3.8e3, "bw": 492, "lat": 1.67},
}
rnd_write_bs = {
    "4k": {"iops": 386e3, "bw": 1582, "lat": 2.04},
    "8k": {"iops": 215e3, "bw": 1761, "lat": 3.58},
    "16k": {"iops": 118e3, "bw": 1905, "lat": 6.50},
    "32k": {"iops": 62.6e3, "bw": 2018, "lat": 15.75},
    "64k": {"iops": 32.7e3, "bw": 2100, "lat": 30.44},
    "128k": {"iops": 17.6e3, "bw": 2264, "lat": 57.74},
}

concurrency_data = {
    (1, 1): {
        "seq_read": {"iops": 454000, "bw": 1859, "lat": 1.51},
        "seq_write": {"iops": 467000, "bw": 1915, "lat": 1.72},
        "rnd_read": {"iops": 13.0e3, "bw": 57.2, "lat": 0.069},
        "rnd_write": {"iops": 386e3, "bw": 1582, "lat": 2.04},
    },
    (1, 16): {
        "seq_read": {"iops": 459000, "bw": 1881, "lat": 1.51},
        "seq_write": {"iops": 459000, "bw": 1885, "lat": 1.73},
        "rnd_read": {"iops": 16.4e3, "bw": 71.7, "lat": 0.062},
        "rnd_write": {"iops": 392e3, "bw": 1608, "lat": 1.87},
    },
    (1, 64): {
        "seq_read": {"iops": 461000, "bw": 1891, "lat": 1.51},
        "seq_write": {"iops": 459000, "bw": 1885, "lat": 1.74},
        "rnd_read": {"iops": 15.7e3, "bw": 68.5, "lat": 0.066},
        "rnd_write": {"iops": 386e3, "bw": 1585, "lat": 1.93},
    },
    (4, 1): {
        "seq_read": {"iops": 2.28e6, "bw": 2342, "lat": 0.59},
        "seq_write": {"iops": 1.93e6, "bw": 2402, "lat": 5.17},
        "rnd_read": {"iops": 209.6e3, "bw": 858, "lat": 14.6},
        "rnd_write": {"iops": 133e3, "bw": 546, "lat": 5.98},
    },
    (4, 16): {
        "seq_read": {"iops": 2.28e6, "bw": 2400, "lat": 0.60},
        "seq_write": {"iops": 1.92e6, "bw": 2394, "lat": 5.21},
        "rnd_read": {"iops": 214e3, "bw": 900, "lat": 13.99},
        "rnd_write": {"iops": 544e3, "bw": 2124, "lat": 6.04},
    },
    (4, 64): {
        "seq_read": {"iops": 2.42e6, "bw": 2418, "lat": 2.08},
        "seq_write": {"iops": 2.41e6, "bw": 2408, "lat": 5.22},
        "rnd_read": {"iops": 214e3, "bw": 836, "lat": 13.99},
        "rnd_write": {"iops": 538e3, "bw": 2108, "lat": 6.11},
    },
    (8, 1): {
        "seq_read": {"iops": 4.49e6, "bw": 4527, "lat": 0.30},
        "seq_write": {"iops": 3.03e6, "bw": 2466, "lat": 10.34},
        "rnd_read": {"iops": 339.7e3, "bw": 2717, "lat": 7.47},
        "rnd_write": {"iops": 263e3, "bw": 1028, "lat": 12.79},
    },
    (8, 16): {
        "seq_read": {"iops": 4.49e6, "bw": 3698, "lat": 3.18},
        "seq_write": {"iops": 3.10e6, "bw": 2488, "lat": 10.24},
        "rnd_read": {"iops": 294.7e3, "bw": 2287, "lat": 7.39},
        "rnd_write": {"iops": 555e3, "bw": 2168, "lat": 11.94},
    },
    (8, 64): {
        "seq_read": {"iops": 4.23e6, "bw": 3368, "lat": 3.21},
        "seq_write": {"iops": 3.10e6, "bw": 2475, "lat": 10.30},
        "rnd_read": {"iops": 288e3, "bw": 2279, "lat": 7.50},
        "rnd_write": {"iops": 551e3, "bw": 2150, "lat": 12.03},
    },
}

io_engine_data = {
    "pvsync": {
        "seq_read": {"iops": 279e3, "bw": 1090, "lat": 1.46},
        "seq_write": {"iops": 450e3, "bw": 1758, "lat": 1.82},
        "rnd_read": {"iops": 14.1e3, "bw": 55.2, "lat": 0.0678},
        "rnd_write": {"iops": 371e3, "bw": 1449, "lat": 2.14},
    },
    "libaio": {
        "seq_read": {"iops": 261e3, "bw": 1020, "lat": 1.55},
        "seq_write": {"iops": 478e3, "bw": 1868, "lat": 1.72},
        "rnd_read": {"iops": 15.7e3, "bw": 61.2, "lat": 0.0608},
        "rnd_write": {"iops": 393e3, "bw": 1534, "lat": 2.03},
    },
    "mmap": {
        "seq_read": {"iops": 257e3, "bw": 1005, "lat": 1.49},
        "seq_write": {"iops": 422e3, "bw": 1647, "lat": 1.80},
        "rnd_read": {"iops": 13.1e3, "bw": 51.2, "lat": 0.0733},
        "rnd_write": {"iops": 12.5e3, "bw": 48.8, "lat": 0.0784},
    },
}

platform_compare_data = {
    "Linux": {
        "seq_read": {"iops": 454e3, "bw": 1859, "lat": 1.51},
        "seq_write": {"iops": 467e3, "bw": 1915, "lat": 1.72},
        "rnd_read": {"iops": 13.0e3, "bw": 57.2, "lat": 0.069},
        "rnd_write": {"iops": 379e3, "bw": 1553, "lat": 2.04},
    },
    "Mac": {
        "seq_read": {"iops": 166.504e3, "bw": 682.001, "lat": 0.005496},
        "seq_write": {"iops": 100.647e3, "bw": 412.248, "lat": 0.009339},
        "rnd_read": {"iops": 28.599e3, "bw": 117.141, "lat": 0.033979},
        "rnd_write": {"iops": 2.704e3, "bw": 11.077, "lat": 0.367756},
    },
}


# ============================================================
# STYLE
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIRS = [
    BASE_DIR,
    BASE_DIR / "计算机系统前沿第一次实验报告" / "images",
]

OPS = ["seq_read", "seq_write", "rnd_read", "rnd_write"]
LABELS = {
    "seq_read": "Seq Read",
    "seq_write": "Seq Write",
    "rnd_read": "Rnd Read",
    "rnd_write": "Rnd Write",
}
COLORS = {
    "seq_read": "#2563A6",
    "seq_write": "#D97745",
    "rnd_read": "#3E8B63",
    "rnd_write": "#9A4E5F",
}
MARKERS = {
    "seq_read": "o",
    "seq_write": "s",
    "rnd_read": "^",
    "rnd_write": "D",
}
METRICS = {
    "bw": {"title": "Bandwidth", "label": "MB/s", "log": False},
    "iops": {"title": "IOPS", "label": "k", "log": True},
    "lat": {"title": "Latency", "label": "ms", "log": True},
}
PLATFORM_COLORS = {
    "Linux": "#3E6FB6",
    "Mac": "#D18952",
}
LEGEND_ELEMENTS = [
    Line2D(
        [0],
        [0],
        color=COLORS[op],
        marker=MARKERS[op],
        markersize=7,
        linewidth=2.6,
        markeredgecolor="white",
        markeredgewidth=1.0,
        label=LABELS[op],
    )
    for op in OPS
]


def set_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11.5,
            "axes.titlesize": 13,
            "axes.labelsize": 11.5,
            "xtick.labelsize": 10.5,
            "ytick.labelsize": 10.5,
            "legend.fontsize": 10.5,
            "figure.facecolor": "#FBFAF7",
            "axes.facecolor": "#FFFFFF",
            "axes.edgecolor": "#CFC9BE",
            "axes.linewidth": 1.0,
            "grid.color": "#C9C2B6",
            "grid.linestyle": "--",
            "grid.linewidth": 0.7,
            "grid.alpha": 0.45,
            "axes.grid": True,
            "axes.axisbelow": True,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.08,
        }
    )


def convert_value(metric: str, value: float) -> float:
    if metric == "iops":
        return value / 1000.0
    return value


def create_figure():
    fig = plt.figure(figsize=(8.8, 7.4))
    grid = GridSpec(2, 2, figure=fig, height_ratios=[1.0, 1.05], hspace=0.34, wspace=0.24)
    axes = {
        "bw": fig.add_subplot(grid[0, 0]),
        "iops": fig.add_subplot(grid[0, 1]),
        "lat": fig.add_subplot(grid[1, :]),
    }
    return fig, axes


def style_axis(ax, metric: str) -> None:
    meta = METRICS[metric]
    ax.set_title(meta["title"], loc="left", fontweight="bold", color="#3B372F", pad=10)
    ax.set_ylabel(meta["label"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(True, axis="y")
    if meta["log"]:
        ax.set_yscale("log")


def finalize_axis_limits(ax, metric: str, plotted_values) -> None:
    positive = [value for value in plotted_values if value > 0]
    if not positive:
        return
    low = min(positive)
    high = max(positive)
    if METRICS[metric]["log"]:
        ax.set_ylim(low * 0.72, high * 1.42)
    else:
        ax.set_ylim(0, high * 1.15)


def add_legend(fig) -> None:
    legend = fig.legend(
        handles=LEGEND_ELEMENTS,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=4,
        frameon=True,
        columnspacing=1.6,
        handletextpad=0.7,
        borderpad=0.6,
    )
    legend.get_frame().set_facecolor("#F6F1E7")
    legend.get_frame().set_edgecolor("#D8D0C2")
    legend.get_frame().set_linewidth(0.9)


def save_figure(fig, filename: str) -> None:
    for output_dir in OUTPUT_DIRS:
        output_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_dir / filename)


def plot_line_chart(ax, x, labels, series_map, metric: str, xlabel: str) -> None:
    values_for_limits = []
    for op in OPS:
        y = [convert_value(metric, series_map[op][item][metric]) for item in labels]
        values_for_limits.extend(y)
        ax.plot(
            x,
            y,
            color=COLORS[op],
            marker=MARKERS[op],
            linewidth=2.5,
            markersize=7,
            markeredgewidth=1.0,
            markeredgecolor="white",
            solid_capstyle="round",
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_xlabel(xlabel)
    style_axis(ax, metric)
    finalize_axis_limits(ax, metric, values_for_limits)


def plot_grouped_bar(ax, x, labels, series_map, metric: str, xlabel: str) -> None:
    bar_width = 0.18
    offsets = np.linspace(-1.5 * bar_width, 1.5 * bar_width, len(OPS))
    values_for_limits = []
    for op, offset in zip(OPS, offsets):
        y = [convert_value(metric, series_map[label][op][metric]) for label in labels]
        values_for_limits.extend(y)
        ax.bar(
            x + offset,
            y,
            width=bar_width,
            color=COLORS[op],
            edgecolor="white",
            linewidth=0.9,
            alpha=0.96,
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_xlabel(xlabel)
    style_axis(ax, metric)
    finalize_axis_limits(ax, metric, values_for_limits)


def plot_platform_bar(ax, metric: str) -> None:
    ops = ["seq_read", "seq_write", "rnd_read", "rnd_write"]
    op_labels = ["Seq Read", "Seq Write", "Rnd Read", "Rnd Write"]
    platforms = ["Linux", "Mac"]
    x = np.arange(len(ops))
    width = 0.34
    values_for_limits = []

    for idx, platform in enumerate(platforms):
        offset = (-0.5 + idx) * width
        vals = [convert_value(metric, platform_compare_data[platform][op][metric]) for op in ops]
        values_for_limits.extend(vals)
        ax.bar(
            x + offset,
            vals,
            width=width,
            color=PLATFORM_COLORS[platform],
            edgecolor="white",
            linewidth=0.9,
            label=platform,
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(op_labels)
    style_axis(ax, metric)
    finalize_axis_limits(ax, metric, values_for_limits)


def add_platform_legend(fig) -> None:
    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=PLATFORM_COLORS[name], edgecolor="white", label=name)
        for name in ["Linux", "Mac"]
    ]
    legend = fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=2,
        frameon=True,
        columnspacing=1.8,
        handletextpad=0.7,
        borderpad=0.6,
    )
    legend.get_frame().set_facecolor("#F6F1E7")
    legend.get_frame().set_edgecolor("#D8D0C2")
    legend.get_frame().set_linewidth(0.9)


# ============================================================
# CHARTS
# ============================================================
def chart1_block_size():
    fig, axes = create_figure()
    x = np.arange(len(bs_labels))
    series_map = {
        "seq_read": seq_read_bs,
        "seq_write": seq_write_bs,
        "rnd_read": rnd_read_bs,
        "rnd_write": rnd_write_bs,
    }

    plot_line_chart(axes["bw"], x, bs_labels, series_map, "bw", "Block Size")
    plot_line_chart(axes["iops"], x, bs_labels, series_map, "iops", "Block Size")
    plot_line_chart(axes["lat"], x, bs_labels, series_map, "lat", "Block Size")

    add_legend(fig)
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.09, right=0.98)
    return fig


def chart2_iodepth():
    fig, axes = create_figure()
    iodepths = [1, 16, 64]
    x = np.arange(len(iodepths))

    series_map = {
        op: {depth: concurrency_data[(1, depth)][op] for depth in iodepths}
        for op in OPS
    }

    plot_line_chart(axes["bw"], x, iodepths, series_map, "bw", "iodepth (numjobs=1)")
    plot_line_chart(axes["iops"], x, iodepths, series_map, "iops", "iodepth (numjobs=1)")
    plot_line_chart(axes["lat"], x, iodepths, series_map, "lat", "iodepth (numjobs=1)")

    add_legend(fig)
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.09, right=0.98)
    return fig


def chart3_numjobs():
    fig, axes = create_figure()
    numjobs_list = [1, 4, 8]
    x = np.arange(len(numjobs_list))

    series_map = {
        op: {numjobs: concurrency_data[(numjobs, 1)][op] for numjobs in numjobs_list}
        for op in OPS
    }

    plot_line_chart(axes["bw"], x, numjobs_list, series_map, "bw", "numjobs (iodepth=1)")
    plot_line_chart(axes["iops"], x, numjobs_list, series_map, "iops", "numjobs (iodepth=1)")
    plot_line_chart(axes["lat"], x, numjobs_list, series_map, "lat", "numjobs (iodepth=1)")

    add_legend(fig)
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.09, right=0.98)
    return fig


def chart4_ioengine():
    fig, axes = create_figure()
    engines = ["pvsync", "libaio", "mmap"]
    x = np.arange(len(engines))

    plot_grouped_bar(axes["bw"], x, engines, io_engine_data, "bw", "I/O Engine")
    plot_grouped_bar(axes["iops"], x, engines, io_engine_data, "iops", "I/O Engine")
    plot_grouped_bar(axes["lat"], x, engines, io_engine_data, "lat", "I/O Engine")

    add_legend(fig)
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.09, right=0.98)
    return fig


def chart5_platform_compare():
    fig, axes = create_figure()
    plot_platform_bar(axes["bw"], "bw")
    plot_platform_bar(axes["iops"], "iops")
    plot_platform_bar(axes["lat"], "lat")
    add_platform_legend(fig)
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.09, right=0.98)
    return fig


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    set_style()

    figures = {
        "chart_1.pdf": chart1_block_size(),
        "chart_2.pdf": chart2_iodepth(),
        "chart_3.pdf": chart3_numjobs(),
        "chart_4.pdf": chart4_ioengine(),
        "chart_7.pdf": chart5_platform_compare(),
    }

    for filename, fig in figures.items():
        save_figure(fig, filename)
        plt.close(fig)
        print(f"saved {filename}")


if __name__ == "__main__":
    main()
