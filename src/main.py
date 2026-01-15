from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from concurrent.futures import ThreadPoolExecutor, as_completed


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._in_title = False
        self.title: Optional[str] = None

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and self.title is None:
            cleaned = data.strip()
            if cleaned:
                self.title = cleaned
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks)


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: Optional[int]
    elapsed_ms: int
    title: Optional[str]
    word_count: Optional[int]
    error: Optional[str]


_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def fetch_and_analyze(url: str, timeout_s: float) -> FetchResult:
    start = time.perf_counter()
    try:
        req = Request(
            url,
            headers={
                "User-Agent": "ParallelCrawler/1.0 (course project)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        with urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", None)
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")

        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("latin-1", errors="replace")

        parser = _TextExtractor()
        parser.feed(html)
        text = parser.get_text()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FetchResult(
            url=url,
            ok=True,
            status=status,
            elapsed_ms=elapsed_ms,
            title=parser.title,
            word_count=_count_words(text),
            error=None,
        )

    except HTTPError as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FetchResult(
            url=url,
            ok=False,
            status=e.code,
            elapsed_ms=elapsed_ms,
            title=None,
            word_count=None,
            error=f"HTTPError: {e.code}",
        )
    except URLError as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FetchResult(
            url=url,
            ok=False,
            status=None,
            elapsed_ms=elapsed_ms,
            title=None,
            word_count=None,
            error=f"URLError: {e.reason}",
        )
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FetchResult(
            url=url,
            ok=False,
            status=None,
            elapsed_ms=elapsed_ms,
            title=None,
            word_count=None,
            error=f"Exception: {type(e).__name__}: {e}",
        )


def read_urls(path: str) -> list[str]:
    urls: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            urls.append(s)
    return urls


def run(urls: Iterable[str], workers: int, timeout_s: float) -> list[FetchResult]:
    results: list[FetchResult] = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(fetch_and_analyze, url, timeout_s) for url in urls]
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: r.url)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Równoległy crawler i analizator stron")
    ap.add_argument("--input", required=True, help="Plik z URL-ami (po jednym w linii)")
    ap.add_argument("--workers", type=int, default=8, help="Liczba wątków (1 = sekwencyjnie)")
    ap.add_argument("--timeout", type=float, default=10.0, help="Timeout pobierania w sekundach")
    ap.add_argument("--out", default="output/results.json", help="Ścieżka pliku wynikowego JSON")
    args = ap.parse_args()

    urls = read_urls(args.input)
    if not urls:
        print("Brak URL-i do przetworzenia.")
        return 2

    t0 = time.perf_counter()
    results = run(urls, workers=max(1, args.workers), timeout_s=args.timeout)
    total_ms = int((time.perf_counter() - t0) * 1000)

    ok_count = sum(1 for r in results if r.ok)
    fail_count = len(results) - ok_count
    avg_ms = int(sum(r.elapsed_ms for r in results) / max(1, len(results)))

    payload = {
        "meta": {
            "workers": max(1, args.workers),
            "timeout_s": args.timeout,
            "total_urls": len(results),
            "ok": ok_count,
            "failed": fail_count,
            "total_elapsed_ms": total_ms,
            "avg_elapsed_ms": avg_ms,
        },
        "results": [asdict(r) for r in results],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"URL-i: {len(results)} | OK: {ok_count} | Błędy: {fail_count}")
    print(f"Czas całkowity: {total_ms} ms | Średnio/URL: {avg_ms} ms | workers={max(1, args.workers)}")
    print(f"Wynik: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
