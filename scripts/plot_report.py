"""Generate Phase 2 report figures and a LaTeX results table."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_results(path: Path) -> dict[int, dict[str, float]]:
    with path.open(newline="", encoding="utf-8") as file:
        return {
            int(row["request_rate_per_second"]): {
                "average": float(row["average_latency_ms"]),
                "p99": float(row["p99_latency_ms"]),
                "failed": float(row["failed_requests"]),
            }
            for row in csv.DictReader(file)
        }


def write_figure(
    output: Path,
    title: str,
    warm: dict[int, dict[str, float]],
    cold: dict[int, dict[str, float]],
    metric: str,
) -> None:
    rates = sorted(warm)
    figure, axis = plt.subplots(figsize=(3.35, 2.35))
    axis.plot(
        rates,
        [warm[rate][metric] for rate in rates],
        marker="o",
        label="Warm",
    )
    axis.plot(
        rates,
        [cold[rate][metric] for rate in rates],
        marker="s",
        label="Cold",
    )
    axis.set(
        title=title,
        xlabel="Keyword requests per second",
        ylabel="Latency (ms)",
        yscale="log",
    )
    axis.grid(True, which="both", alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output, format="pdf")
    plt.close(figure)


def write_table(output: Path, warm: dict[int, dict[str, float]], cold: dict[int, dict[str, float]]) -> None:
    rates = sorted(warm)
    with output.open("w", encoding="utf-8") as file:
        file.write("\\setlength{\\tabcolsep}{2pt}\n")
        file.write("\\begin{tabular}{r|rrrrr}\n")
        file.write("\\hline\n")
        file.write(
            "Rate & Warm avg. & Warm p99 & Cold avg. & Cold p99 & "
            "Cold failed \\\\\n"
        )
        file.write("(req/s) & (ms) & (ms) & (ms) & (ms) & (requests) \\\\\n")
        file.write("\\hline\n")
        for rate in rates:
            file.write(
                f"{rate} & {warm[rate]['average']:.1f} & "
                f"{warm[rate]['p99']:.1f} & {cold[rate]['average']:.1f} & "
                f"{cold[rate]['p99']:.1f} & {int(cold[rate]['failed'])} \\\\\n"
            )
        file.write("\\hline\n")
        file.write("\\end{tabular}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/tables"),
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("../ADS-Project"),
    )
    args = parser.parse_args()

    warm = read_results(args.results_dir / "phase2_latency_warm.csv")
    cold = read_results(args.results_dir / "phase2_latency_cold.csv")
    figures_dir = args.report_dir / "figures"
    tables_dir = args.report_dir / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_figure(
        figures_dir / "phase2-average-latency.pdf",
        "Average execution latency",
        warm,
        cold,
        "average",
    )
    write_figure(
        figures_dir / "phase2-p99-latency.pdf",
        "99th-percentile execution latency",
        warm,
        cold,
        "p99",
    )
    write_table(tables_dir / "phase2-results.tex", warm, cold)


if __name__ == "__main__":
    main()
