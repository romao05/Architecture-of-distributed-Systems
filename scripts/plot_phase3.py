"""Generate Phase 3 report figures and LaTeX results tables."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

Results = dict[int, dict[str, float]]
Distribution = dict[int, dict[str, int]]

N1_BOUND_MS = 4000
SERVERS = ("server1", "server2", "server3")
SERVER_COLOURS = {"server1": "#1f77b4", "server2": "#ff7f0e", "server3": "#2ca02c"}
CONFIGS = (
    ("phase3_single", "1 server", "#555555", "o"),
    ("phase3_lc", "LC (3 servers)", "#1f77b4", "s"),
    ("phase3_lrt", "LRT (3 servers)", "#d62728", "^"),
)
DISTRIBUTION_PANELS = (
    ("phase3_lc", "LC, equal servers"),
    ("phase3_lrt", "LRT, equal servers"),
    ("phase3_slow_lc", "LC, server3 at 0.5 CPU"),
    ("phase3_slow_lrt", "LRT, server3 at 0.5 CPU"),
)

plt.rcParams.update(
    {
        "font.size": 12,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
        "lines.linewidth": 2.2,
        "lines.markersize": 7,
    }
)


def read_results(path: Path) -> Results:
    with path.open(newline="", encoding="utf-8") as file:
        return {
            int(row["request_rate_per_second"]): {
                "average": float(row["average_latency_ms"]),
                "p99": float(row["p99_latency_ms"]),
                "failed": float(row["failed_requests"]),
            }
            for row in csv.DictReader(file)
        }


def read_distribution(path: Path) -> Distribution:
    """Return requests handled per server for each request rate."""
    distribution: Distribution = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            rate = int(row["request_rate_per_second"])
            distribution.setdefault(rate, dict.fromkeys(SERVERS, 0))
            distribution[rate][row["server"]] = int(row["requests"])
    return distribution


def save_figure(figure: plt.Figure, output: Path) -> None:
    figure.savefig(output.with_suffix(".pdf"), format="pdf")
    figure.savefig(output.with_suffix(".png"), format="png", dpi=200)
    plt.close(figure)


def plot_metric(axis: plt.Axes, results: dict[str, Results], metric: str) -> None:
    for label, name, colour, marker in CONFIGS:
        data = results[label]
        rates = sorted(data)
        axis.plot(
            rates,
            [data[rate][metric] for rate in rates],
            color=colour,
            marker=marker,
            label=name,
        )
    axis.set(xlabel="Request rate (requests/s)", yscale="log")
    axis.set_xticks(sorted(results["phase3_single"]))
    axis.grid(True, which="both", alpha=0.3)


def write_latency_figure(output: Path, cold: dict[str, Results]) -> None:
    figure, (average_axis, p99_axis) = plt.subplots(
        1, 2, figsize=(7, 4.2), sharey=True
    )
    plot_metric(average_axis, cold, "average")
    plot_metric(p99_axis, cold, "p99")
    average_axis.set(title="Average latency", ylabel="Latency (ms)")
    p99_axis.set(title="99th-percentile latency")
    p99_axis.axhline(N1_BOUND_MS, color="black", linestyle="--", linewidth=1.3)
    p99_axis.text(
        33,
        N1_BOUND_MS / 1.12,
        f"N1 bound ({N1_BOUND_MS} ms)",
        fontsize=10,
        ha="center",
        va="top",
    )
    highest = max(
        data[rate][metric]
        for data in cold.values()
        for rate in data
        for metric in ("average", "p99")
    )
    p99_axis.set_ylim(top=max(highest, N1_BOUND_MS) * 2)
    handles, labels = average_axis.get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    figure.tight_layout(rect=(0, 0.08, 1, 1))
    save_figure(figure, output)


def write_warm_figure(output: Path, warm: dict[str, Results]) -> None:
    figure, axis = plt.subplots(figsize=(7, 3.3))
    plot_metric(axis, warm, "average")
    axis.set(ylabel="Average latency (ms)", title="Warm requests (cache hits)")
    plain = FuncFormatter(lambda value, _: f"{value:g}")
    axis.yaxis.set_major_formatter(plain)
    axis.yaxis.set_minor_formatter(plain)
    axis.tick_params(axis="y", which="minor", labelsize=9)
    handles, labels = axis.get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    figure.tight_layout(rect=(0, 0.1, 1, 1))
    save_figure(figure, output)


def write_distribution_figure(
    output: Path, distributions: dict[str, Distribution]
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(7, 4.6), sharey=True)
    width = 0.27
    for axis, (label, title) in zip(axes.flat, DISTRIBUTION_PANELS):
        distribution = distributions[label]
        rates = sorted(distribution)
        for index, server in enumerate(SERVERS):
            axis.bar(
                [position + (index - 1) * width for position in range(len(rates))],
                [distribution[rate][server] for rate in rates],
                width=width,
                color=SERVER_COLOURS[server],
                label=server,
            )
        axis.set_xticks(range(len(rates)), [str(rate) for rate in rates])
        axis.set_title(title, fontsize=12)
        axis.grid(True, axis="y", alpha=0.3)
    for axis in axes[1]:
        axis.set_xlabel("Request rate (requests/s)")
    for axis in axes[:, 0]:
        axis.set_ylabel("Requests")
    handles, labels = axes[0][0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    figure.tight_layout(rect=(0, 0.06, 1, 1))
    save_figure(figure, output)


def write_table(output: Path, cold: dict[str, Results]) -> None:
    single, lc, lrt = (cold[label] for label, *_ in CONFIGS)
    with output.open("w", encoding="utf-8") as file:
        file.write("\\setlength{\\tabcolsep}{4pt}\n")
        file.write("\\begin{tabular}{r|rrr|rr|rr}\n")
        file.write("\\hline\n")
        file.write(
            "Rate & \\multicolumn{3}{c|}{1 server} & \\multicolumn{2}{c|}{LC} & "
            "\\multicolumn{2}{c}{LRT} \\\\\n"
        )
        file.write(
            "(req/s) & avg. & p99 & fail & avg. & p99 & avg. & p99 \\\\\n"
        )
        file.write("\\hline\n")
        for rate in sorted(single):
            file.write(
                f"{rate} & {single[rate]['average']:.0f} & {single[rate]['p99']:.0f} & "
                f"{int(single[rate]['failed'])} & "
                f"{lc[rate]['average']:.0f} & {lc[rate]['p99']:.0f} & "
                f"{lrt[rate]['average']:.0f} & {lrt[rate]['p99']:.0f} \\\\\n"
            )
        file.write("\\hline\n")
        file.write("\\end{tabular}\n")


def server3_share(distribution: Distribution, rate: int) -> float:
    counts = distribution[rate]
    return 100 * counts["server3"] / max(1, sum(counts.values()))


def write_slow_table(
    output: Path,
    slow: dict[str, Results],
    distributions: dict[str, Distribution],
) -> None:
    lc, lrt = slow["phase3_slow_lc"], slow["phase3_slow_lrt"]
    with output.open("w", encoding="utf-8") as file:
        file.write("\\setlength{\\tabcolsep}{4pt}\n")
        file.write("\\begin{tabular}{r|rr|rr|rr}\n")
        file.write("\\hline\n")
        file.write(
            "Rate & \\multicolumn{2}{c|}{LC (ms)} & \\multicolumn{2}{c|}{LRT (ms)} & "
            "\\multicolumn{2}{c}{server3 share (\\%)} \\\\\n"
        )
        file.write("(req/s) & avg. & p99 & avg. & p99 & LC & LRT \\\\\n")
        file.write("\\hline\n")
        for rate in sorted(lc):
            file.write(
                f"{rate} & {lc[rate]['average']:.0f} & {lc[rate]['p99']:.0f} & "
                f"{lrt[rate]['average']:.0f} & {lrt[rate]['p99']:.0f} & "
                f"{server3_share(distributions['phase3_slow_lc'], rate):.0f} & "
                f"{server3_share(distributions['phase3_slow_lrt'], rate):.0f} \\\\\n"
            )
        file.write("\\hline\n")
        file.write("\\end{tabular}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results/tables"))
    parser.add_argument("--figures-dir", type=Path, default=Path("results/figures"))
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Also copy figures and tables here, e.g. ../ADS-Project",
    )
    args = parser.parse_args()

    def load(label: str, mode: str) -> Results:
        return read_results(args.results_dir / f"{label}_latency_{mode}.csv")

    cold = {label: load(label, "cold") for label, *_ in CONFIGS}
    warm = {label: load(label, "warm") for label, *_ in CONFIGS}
    slow = {label: load(label, "cold") for label in ("phase3_slow_lc", "phase3_slow_lrt")}
    distributions = {
        label: read_distribution(args.results_dir / f"{label}_distribution_cold.csv")
        for label, _ in DISTRIBUTION_PANELS
    }

    args.figures_dir.mkdir(parents=True, exist_ok=True)
    write_latency_figure(args.figures_dir / "phase3-latency", cold)
    write_warm_figure(args.figures_dir / "phase3-warm-latency", warm)
    write_distribution_figure(args.figures_dir / "phase3-distribution", distributions)
    tables = [args.results_dir / "phase3-results.tex", args.results_dir / "phase3-slow-results.tex"]
    write_table(tables[0], cold)
    write_slow_table(tables[1], slow, distributions)

    if args.report_dir is not None:
        report_figures = args.report_dir / "figures"
        report_tables = args.report_dir / "tables"
        report_figures.mkdir(parents=True, exist_ok=True)
        report_tables.mkdir(parents=True, exist_ok=True)
        for figure_file in args.figures_dir.glob("phase3-*.*"):
            shutil.copy(figure_file, report_figures)
        for table in tables:
            shutil.copy(table, report_tables)


if __name__ == "__main__":
    main()
