from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CpuRow:
    workers: int
    elapsed_ms: int
    files: int
    total_tokens: int
    unique_tokens: int


@dataclass(frozen=True)
class CrawlerRow:
    workers: int
    elapsed_ms: int
    urls: int
    ok: int
    failed: int
    avg_per_url_ms: int


def _run_script(script_path: Path, args: list[str]) -> None:
    raise NotImplementedError("Use _run_script_with_progress")


def _run_script_with_progress(
    script_path: Path,
    args: list[str],
    *,
    label: str,
    progress: bool,
    progress_interval_s: float,
) -> None:
    cmd = [sys.executable, str(script_path), *args]

    if progress:
        print(f"[bench] start: {label}", flush=True)

    started = time.perf_counter()
    proc = subprocess.Popen(cmd)
    interval = max(0.5, float(progress_interval_s))
    next_tick = started + interval

    while True:
        rc = proc.poll()
        if rc is not None:
            break

        now = time.perf_counter()
        if progress and now >= next_tick:
            elapsed_s = int(now - started)
            print(f"[bench] running: {label} ({elapsed_s}s)", flush=True)
            next_tick = now + interval

        time.sleep(0.2)

    if proc.returncode != 0:
        raise SystemExit(f"Błąd uruchomienia ({proc.returncode}): {' '.join(cmd)}")

    if progress:
        elapsed_s = int(time.perf_counter() - started)
        print(f"[bench] done: {label} ({elapsed_s}s)", flush=True)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON output must be an object")
    return data


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(parts: Iterable[str]) -> str:
        return "  ".join(str(p).ljust(widths[i]) for i, p in enumerate(parts))

    sep = "  ".join("-" * w for w in widths)
    out = [fmt_row(headers), sep]
    out.extend(fmt_row(r) for r in rows)
    return "\n".join(out)


def _bench_cpu(
    cpu_main_path: Path,
    input_path: str,
    out_dir: Path,
    top: int,
    workers_min: int,
    workers_max: int,
    progress: bool,
    progress_interval_s: float,
) -> list[CpuRow]:
    rows: list[CpuRow] = []
    total_runs = workers_max - workers_min + 1
    for workers in range(workers_min, workers_max + 1):
        if progress:
            idx = workers - workers_min + 1
            print(f"[{idx}/{total_runs}] workers={workers}: start...", flush=True)
        out_path = out_dir / f"hist_w{workers}.json"
        t0 = time.perf_counter()
        _run_script_with_progress(
            cpu_main_path,
            [
                "--input",
                input_path,
                "--workers",
                str(workers),
                "--top",
                str(max(1, int(top))),
                "--out",
                str(out_path),
            ],
            label=f"cpu workers={workers}",
            progress=progress,
            progress_interval_s=progress_interval_s,
        )
        wall_ms = int((time.perf_counter() - t0) * 1000)

        payload = _load_json(out_path)
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        elapsed_ms = int(meta.get("total_elapsed_ms", wall_ms) or wall_ms)
        files = int(meta.get("files", 0) or 0)
        total_tokens = int(meta.get("total_tokens", 0) or 0)
        unique_tokens = int(meta.get("unique_tokens", 0) or 0)

        if progress:
            tok_s = int(total_tokens / max(0.001, (elapsed_ms / 1000)))
            print(
                f"[{idx}/{total_runs}] workers={workers}: done ({elapsed_ms} ms, tok/s={tok_s})",
                flush=True,
            )

        rows.append(
            CpuRow(
                workers=workers,
                elapsed_ms=elapsed_ms,
                files=files,
                total_tokens=total_tokens,
                unique_tokens=unique_tokens,
            )
        )

    return rows


def _bench_crawler(
    crawler_path: Path,
    input_path: str,
    timeout_s: float,
    out_dir: Path,
    workers_min: int,
    workers_max: int,
    progress: bool,
    progress_interval_s: float,
) -> list[CrawlerRow]:
    rows: list[CrawlerRow] = []
    total_runs = workers_max - workers_min + 1
    for workers in range(workers_min, workers_max + 1):
        if progress:
            idx = workers - workers_min + 1
            print(f"[{idx}/{total_runs}] workers={workers}: start...", flush=True)
        out_path = out_dir / f"crawl_w{workers}.json"
        t0 = time.perf_counter()
        _run_script_with_progress(
            crawler_path,
            [
                "--input",
                input_path,
                "--workers",
                str(workers),
                "--timeout",
                str(float(timeout_s)),
                "--out",
                str(out_path),
            ],
            label=f"crawler workers={workers}",
            progress=progress,
            progress_interval_s=progress_interval_s,
        )
        wall_ms = int((time.perf_counter() - t0) * 1000)

        payload = _load_json(out_path)
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        elapsed_ms = int(meta.get("total_elapsed_ms", wall_ms) or wall_ms)
        urls = int(meta.get("total_urls", 0) or 0)
        ok = int(meta.get("ok", 0) or 0)
        failed = int(meta.get("failed", 0) or 0)
        avg = int(meta.get("avg_elapsed_ms", 0) or 0)

        if progress:
            rate = 0
            if elapsed_ms > 0:
                rate = int(urls / max(0.001, (elapsed_ms / 1000)))
            print(
                f"[{idx}/{total_runs}] workers={workers}: done ({elapsed_ms} ms, ok={ok}, failed={failed}, urls/s={rate})",
                flush=True,
            )

        rows.append(
            CrawlerRow(
                workers=workers,
                elapsed_ms=elapsed_ms,
                urls=urls,
                ok=ok,
                failed=failed,
                avg_per_url_ms=avg,
            )
        )

    return rows


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Benchmark 1..8 workerów (threads/processes) i czytelna tabelka z wynikami."
        )
    )
    ap.add_argument(
        "--mode",
        choices=["cpu", "crawler"],
        default="cpu",
        help="Który program benchmarkować (cpu = histogram, crawler = pobieranie URL).",
    )
    ap.add_argument(
        "--input",
        required=True,
        help="Wejście: katalog/plik .txt (cpu) lub plik z URL-ami (crawler)",
    )
    ap.add_argument("--min", type=int, default=1, help="Minimalna liczba workerów")
    ap.add_argument("--max", type=int, default=8, help="Maksymalna liczba workerów")
    ap.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout (sekundy) – tylko dla mode=crawler",
    )
    ap.add_argument(
        "--out-dir",
        default="output/bench",
        help="Katalog na pliki JSON powstające podczas benchmarku",
    )
    ap.add_argument(
        "--summary-out",
        default="",
        help="Ścieżka zbiorczego podsumowania JSON (domyślnie: <out-dir>/summary_<mode>.json)",
    )
    ap.add_argument(
        "--top",
        type=int,
        default=30,
        help="Ile najczęstszych słów liczyć (tylko mode=cpu)",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Bez komunikatów postępu (zostaje tylko tabelka na końcu)",
    )
    ap.add_argument(
        "--progress-interval",
        type=float,
        default=5.0,
        help="Co ile sekund wypisywać komunikat, że nadal działa (domyślnie: 5s)",
    )
    args = ap.parse_args()

    workers_min = max(1, int(args.min))
    workers_max = max(workers_min, int(args.max))

    here = Path(__file__).resolve().parent
    out_dir = Path(str(args.out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_out = Path(str(args.summary_out)) if str(args.summary_out).strip() else out_dir / f"summary_{args.mode}.json"
    progress = not bool(args.quiet)

    if args.mode == "cpu":
        cpu_main_path = here / "cpu_main.py"
        rows = _bench_cpu(
            cpu_main_path=cpu_main_path,
            input_path=str(args.input),
            out_dir=out_dir,
            top=int(args.top),
            workers_min=workers_min,
            workers_max=workers_max,
            progress=progress,
            progress_interval_s=float(args.progress_interval),
        )

        table_rows: list[list[str]] = []
        for r in rows:
            tok_s = int(r.total_tokens / max(0.001, (r.elapsed_ms / 1000)))
            table_rows.append(
                [
                    str(r.workers),
                    str(r.elapsed_ms),
                    str(r.files),
                    str(r.total_tokens),
                    str(r.unique_tokens),
                    str(tok_s),
                ]
            )

        base_ms = rows[0].elapsed_ms if rows else 0
        summary = {
            "meta": {
                "mode": "cpu",
                "input": str(args.input),
                "workers_min": workers_min,
                "workers_max": workers_max,
                "top": int(args.top),
                "out_dir": str(out_dir),
            },
            "rows": [
                {
                    "workers": r.workers,
                    "elapsed_ms": r.elapsed_ms,
                    "files": r.files,
                    "total_tokens": r.total_tokens,
                    "unique_tokens": r.unique_tokens,
                    "tok_per_s": int(r.total_tokens / max(0.001, (r.elapsed_ms / 1000))),
                    "speedup_vs_1": (float(base_ms) / r.elapsed_ms) if (base_ms and r.elapsed_ms) else None,
                }
                for r in rows
            ],
        }
        _write_summary(summary_out, summary)
        if progress:
            print(f"Podsumowanie JSON: {summary_out}")

        print(
            _format_table(
                headers=["workers", "elapsed_ms", "files", "tokens", "unique", "tok/s"],
                rows=table_rows,
            )
        )
        return 0

    crawler_path = here / "main.py"
    rows = _bench_crawler(
        crawler_path=crawler_path,
        input_path=str(args.input),
        timeout_s=float(args.timeout),
        out_dir=out_dir,
        workers_min=workers_min,
        workers_max=workers_max,
        progress=progress,
        progress_interval_s=float(args.progress_interval),
    )

    table_rows = [
        [
            str(r.workers),
            str(r.elapsed_ms),
            str(r.urls),
            str(r.ok),
            str(r.failed),
            str(r.avg_per_url_ms),
        ]
        for r in rows
    ]

    base_ms = rows[0].elapsed_ms if rows else 0
    summary = {
        "meta": {
            "mode": "crawler",
            "input": str(args.input),
            "timeout_s": float(args.timeout),
            "workers_min": workers_min,
            "workers_max": workers_max,
            "out_dir": str(out_dir),
        },
        "rows": [
            {
                "workers": r.workers,
                "elapsed_ms": r.elapsed_ms,
                "urls": r.urls,
                "ok": r.ok,
                "failed": r.failed,
                "avg_per_url_ms": r.avg_per_url_ms,
                "urls_per_s": int(r.urls / max(0.001, (r.elapsed_ms / 1000))) if r.elapsed_ms else None,
                "speedup_vs_1": (float(base_ms) / r.elapsed_ms) if (base_ms and r.elapsed_ms) else None,
            }
            for r in rows
        ],
    }
    _write_summary(summary_out, summary)
    if progress:
        print(f"Podsumowanie JSON: {summary_out}")

    print(
        _format_table(
            headers=[
                "workers",
                "elapsed_ms",
                "urls",
                "ok",
                "failed",
                "avg_per_url_ms",
            ],
            rows=table_rows,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
