from __future__ import annotations

import argparse
import json
import os
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object")
    return data


def _ensure_out_dir(path: str) -> None:
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)


def _plot_crawler(data: dict[str, Any], out_path: str, show: bool) -> None:
    import matplotlib

    if not show:
        matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    results = data.get("results", [])
    if not isinstance(results, list) or not results:
        raise ValueError("Crawler JSON must contain non-empty 'results' list")

    rows: list[tuple[str, int, bool]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url", ""))
        elapsed = int(r.get("elapsed_ms", 0) or 0)
        ok = bool(r.get("ok", False))
        if url:
            rows.append((url, elapsed, ok))

    rows.sort(key=lambda x: x[1], reverse=True)

    labels = [u for (u, _ms, _ok) in rows]
    values = [ms for (_u, ms, _ok) in rows]
    colors = ["#2ca02c" if ok else "#d62728" for (_u, _ms, ok) in rows]

    fig = plt.figure(figsize=(12, max(4, 0.35 * len(labels))))
    ax = fig.add_subplot(1, 1, 1)
    ax.barh(labels, values, color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("Czas pobrania [ms]")
    ax.set_title("Crawler: czas pobrania per URL (zielone=OK, czerwone=błąd)")

    fig.tight_layout()
    _ensure_out_dir(out_path)
    fig.savefig(out_path, dpi=150)

    if show:
        plt.show()


def _plot_histogram(data: dict[str, Any], out_path: str, show: bool) -> None:
    import matplotlib

    if not show:
        matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    top_words = data.get("top_words")
    if not isinstance(top_words, list) or not top_words:
        raise ValueError("Histogram JSON must contain non-empty 'top_words' list")

    words: list[str] = []
    counts: list[int] = []
    for item in top_words:
        if not isinstance(item, dict):
            continue
        w = str(item.get("word", ""))
        c = int(item.get("count", 0) or 0)
        if w:
            words.append(w)
            counts.append(c)

    pairs = list(zip(words, counts))
    pairs.sort(key=lambda x: x[1])
    words = [p[0] for p in pairs]
    counts = [p[1] for p in pairs]

    fig = plt.figure(figsize=(10, max(4, 0.35 * len(words))))
    ax = fig.add_subplot(1, 1, 1)
    ax.barh(words, counts)
    ax.set_xlabel("Liczność")
    ax.set_title("Histogram: TOP słowa")

    fig.tight_layout()
    _ensure_out_dir(out_path)
    fig.savefig(out_path, dpi=150)

    if show:
        plt.show()


def main() -> int:
    ap = argparse.ArgumentParser(description="Wizualizacja wyników (wykresy z JSON)")
    ap.add_argument("--input", required=True, help="Ścieżka do pliku JSON (crawler lub histogram)")
    ap.add_argument("--out", default="output/plot.png", help="Ścieżka PNG wyjściowego")
    ap.add_argument(
        "--show",
        action="store_true",
        help="Pokaż okno z wykresem (wymaga środowiska GUI)",
    )
    args = ap.parse_args()

    data = _load_json(args.input)

    if "results" in data:
        _plot_crawler(data, out_path=args.out, show=bool(args.show))
    elif "top_words" in data:
        _plot_histogram(data, out_path=args.out, show=bool(args.show))
    else:
        raise SystemExit("Nieznany format JSON (brak 'results' ani 'top_words').")

    print(f"Wykres zapisany do: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
