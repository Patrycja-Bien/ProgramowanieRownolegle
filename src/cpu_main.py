from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from concurrent.futures import ProcessPoolExecutor, as_completed


_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


@dataclass(frozen=True)
class FileCount:
    path: str
    tokens: int
    counts: dict[str, int]


def _iter_text_files(input_path: str) -> list[str]:
    p = Path(input_path)
    if p.is_file():
        return [str(p)]

    if not p.exists():
        return []

    paths = sorted(str(x) for x in p.rglob("*.txt") if x.is_file())
    return paths


def count_words_in_file(path: str) -> FileCount:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    tokens = _WORD_RE.findall(text.lower())
    c = Counter(tokens)

    return FileCount(path=path, tokens=len(tokens), counts=dict(c))


def run(paths: Iterable[str], workers: int) -> tuple[list[FileCount], Counter[str]]:
    per_file: list[FileCount] = []
    total = Counter()

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(count_words_in_file, p) for p in paths]
        for fut in as_completed(futures):
            fc = fut.result()
            per_file.append(fc)
            total.update(fc.counts)

    per_file.sort(key=lambda x: x.path)
    return per_file, total


def main() -> int:
    ap = argparse.ArgumentParser(description="CPU-bound: równoległe liczenie histogramu słów")
    ap.add_argument(
        "--input",
        required=True,
        help="Plik .txt lub katalog z plikami .txt (rekurencyjnie)",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 2,
        help="Liczba procesów (domyślnie: liczba rdzeni)",
    )
    ap.add_argument("--top", type=int, default=30, help="Ile najczęstszych słów zapisać w podsumowaniu")
    ap.add_argument("--out", default="output/histogram.json", help="Ścieżka pliku wynikowego JSON")
    args = ap.parse_args()

    paths = _iter_text_files(args.input)
    if not paths:
        print("Nie znaleziono plików .txt do analizy.")
        return 2

    workers = max(1, int(args.workers))

    t0 = time.perf_counter()
    per_file, total = run(paths, workers=workers)
    total_ms = int((time.perf_counter() - t0) * 1000)

    total_tokens = sum(fc.tokens for fc in per_file)
    unique = len(total)
    top = total.most_common(max(1, int(args.top)))

    payload = {
        "meta": {
            "mode": "cpu-process-pool",
            "workers": workers,
            "files": len(per_file),
            "total_tokens": total_tokens,
            "unique_tokens": unique,
            "total_elapsed_ms": total_ms,
        },
        "top_words": [{"word": w, "count": n} for (w, n) in top],
        "per_file": [
            {
                "path": fc.path,
                "tokens": fc.tokens,
            }
            for fc in per_file
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Pliki: {len(per_file)} | Tokeny: {total_tokens} | Unikalne: {unique}")
    print(f"Czas całkowity: {total_ms} ms | workers={workers}")
    print(f"Wynik: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
