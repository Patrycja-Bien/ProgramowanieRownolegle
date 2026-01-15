from __future__ import annotations

import argparse
import os
import random
import string
from typing import Iterable


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _make_vocab(rng: random.Random, size: int, min_len: int, max_len: int) -> list[str]:
    letters = string.ascii_lowercase
    vocab: list[str] = []
    for _ in range(size):
        n = rng.randint(min_len, max_len)
        vocab.append("".join(rng.choice(letters) for _ in range(n)))
    return vocab


def _iter_words(rng: random.Random, vocab: list[str], total_words: int) -> Iterable[str]:
    hot = vocab[: max(1, len(vocab) // 20)]
    for _ in range(total_words):
        if rng.random() < 0.35:
            yield rng.choice(hot)
        else:
            yield rng.choice(vocab)


def generate(out_dir: str, files: int, words_per_file: int, vocab: int, seed: int) -> None:
    rng = random.Random(seed)
    _ensure_dir(out_dir)

    v = _make_vocab(rng, size=vocab, min_len=3, max_len=10)

    for i in range(1, files + 1):
        path = os.path.join(out_dir, f"gen_{i:04d}.txt")
        chunk: list[str] = []
        chunk_size = 2000

        with open(path, "w", encoding="utf-8") as f:
            for w in _iter_words(rng, v, total_words=words_per_file):
                chunk.append(w)
                if len(chunk) >= chunk_size:
                    f.write(" ".join(chunk))
                    f.write("\n")
                    chunk.clear()

            if chunk:
                f.write(" ".join(chunk))
                f.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generator plików .txt do benchmarku CPU")
    ap.add_argument("--out-dir", default="data/texts_big", help="Katalog docelowy na pliki .txt")
    ap.add_argument("--files", type=int, default=80, help="Ile plików wygenerować")
    ap.add_argument("--words-per-file", type=int, default=300_000, help="Ile słów na plik")
    ap.add_argument("--vocab", type=int, default=8000, help="Rozmiar słownika (unikalne słowa)")
    ap.add_argument("--seed", type=int, default=123, help="Seed losowania (powtarzalność)")
    args = ap.parse_args()

    files = max(1, int(args.files))
    words_per_file = max(1, int(args.words_per_file))
    vocab = max(10, int(args.vocab))

    generate(
        out_dir=str(args.out_dir),
        files=files,
        words_per_file=words_per_file,
        vocab=vocab,
        seed=int(args.seed),
    )

    print(f"Wygenerowano {files} plików w: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
