# Programowanie równoległe — crawler + histogram + demo WWW

## Cel projektu

Projekt demonstruje programowanie **równoległe** na 3 sposoby:

1. **Python (I/O-bound)**: równoległe pobieranie wielu stron WWW (wątki).
2. **Python (CPU-bound)**: równoległe liczenie histogramu słów w wielu plikach `.txt` (procesy).
3. **WWW (GitHub Pages)**: worker przez stronę — równoległe obliczenia CPU w przeglądarce (Web Workers) + wykres.

## Zastosowane mechanizmy

- `concurrent.futures.ThreadPoolExecutor` – równoległe zadania I/O (crawler).
- `concurrent.futures.ProcessPoolExecutor` – równoległe zadania CPU (histogram).
- **Web Workers** (JS) – równoległość w przeglądarce + wizualizacja (Chart.js).

## Technologie

- **Python 3.10+**: standardowa biblioteka (`concurrent.futures`, `urllib`, `html.parser`, regex, JSON).
- **Matplotlib**: generowanie wykresów PNG z wyników CLI.
- **JavaScript (przeglądarka)**: Web Workers do równoległych obliczeń + Chart.js do wizualizacji.

## Działanie

1) Crawler (I/O-bound, wątki)

- wejście: plik z URL-ami (1 URL/linia)
- każdy URL = jedno zadanie w `ThreadPoolExecutor`
- pobranie HTML, wyciągnięcie tekstu i `<title>`, policzenie słów
- wyjście: JSON z metadanymi i wynikami per URL

2) Histogram (CPU-bound, procesy)

- wejście: plik `.txt` lub katalog z `.txt` (rekurencyjnie)
- każdy plik = jedno zadanie w `ProcessPoolExecutor` (liczenie słów)
- proces główny scala histogramy cząstkowe
- wyjście: JSON z `meta` oraz `top_words`

3) Demo WWW (Web Workers)

- wejście: wgrane pliki `.txt` albo tryb demo (deterministyczny workload)
- podział plików na paczki i analiza w wielu workerach
- scalanie wyników w wątku głównym + wykres TOP słów

## Struktura projektu

- `index.html` – wejście do demo WWW (GitHub Pages)
- `docs/app.js`, `docs/worker.js`, `docs/store.js` – logika demo WWW (Web Workers)
- `src/main.py` – CLI: crawler (wątki)
- `src/cpu_main.py` – CLI: histogram (procesy)
- `src/generate_texts.py` – generator dużego datasetu `.txt` do testów CPU
- `src/plot_results.py` – generowanie wykresów PNG z JSON
- `src/bench_workers.py` – benchmark workerów 1..8 + tabelka wyników (CLI)
- `data/urls.txt` – przykładowe URL-e
- `data/texts/` – przykładowe małe pliki `.txt`
- `data/texts/texts_big` – przykładowe duże pliki `.txt`

## Wymagania

- Python 3.10+ (zalecane 3.12)
- `matplotlib` jest potrzebny tylko do `src/plot_results.py` (wykresy PNG). Pozostałe skrypty działają na standardowej bibliotece.

## Instalacja (CLI)

Jeśli chcesz uruchamiać wykresy (`src/plot_results.py`), zainstaluj zależności:

```bash
python -m pip install -e .
```

---

## Uruchomienie przez stronę (GitHub Pages) — „test workera”

### Jak uruchomić demo w przeglądarce

1. Otwórz stronę (link z GitHub Pages).
2. Ustaw **Liczba workerów**.
3. Masz 2 opcje uruchomienia:

**A) Demo bez plików (duże pliki, zawsze te same)**

- Kliknij **„Uruchom demo (bez plików)”**.
- Demo generuje deterministyczny workload: **200 bardzo dużych „plików”** (te same seedy za każdym razem).
- Obliczenia są wykonywane w wielu Web Workerach, a na ekranie dostajesz:
  - czas całkowity,
  - tokeny i unikalne słowa,
  - „czas per plik” (lista) + wykres TOP słów.

**B) Wgranie własnych plików `.txt`**

- Wybierz pliki `.txt` w polu „Pliki tekstowe” i kliknij **„Uruchom analizę”**.

Dodatkowo:

- przycisk **„Pobierz wynik JSON”** zapisuje wynik lokalnie.

### Jak uruchomić stronę lokalnie (opcjonalnie)

GitHub Pages = statyczne pliki, więc lokalnie uruchamiasz to jako „static server”:

```bash
python -m http.server 5175 --bind 127.0.0.1
```

Następnie wejdź: `http://127.0.0.1:5175/`

---

## Uruchomienie przez komendy (CLI) — Python

Poniżej są 2 niezależne programy CLI. Każdy zapisuje wynik do JSON, który można potem zwizualizować.

### 1) Crawler WWW (wątki) — `src/main.py`

**Działanie:**

- każdy URL to osobne zadanie,
- zadania są wykonywane równolegle w wątkach (`ThreadPoolExecutor`),
- wynik zawiera m.in. status HTTP, czas odpowiedzi, tytuł strony, liczbę słów.

**Przykłady uruchomienia:**

```bash
python src/main.py --input data/urls.txt --workers 1 --out output/results_seq.json
python src/main.py --input data/urls.txt --workers 8 --out output/results_par.json
```

### 2) Histogram słów (procesy) — `src/cpu_main.py`

**Działanie:**

- każdy plik `.txt` to osobne zadanie,
- zadania są wykonywane równolegle w procesach (`ProcessPoolExecutor`),
- proces główny scala wyniki cząstkowe w jeden histogram (reduce),
- wynik zawiera metadane oraz `top_words`.

**Przykłady uruchomienia na małych danych:**

```bash
python src/cpu_main.py --input data/texts --workers 1 --out output/hist_1.json
python src/cpu_main.py --input data/texts --workers 8 --out output/hist_8.json
```

**Większe dane (benchmark CPU):**

```bash
python src/generate_texts.py --out-dir data/texts/texts_big --files 80 --words-per-file 300000 --vocab 8000
python src/cpu_main.py --input data/texts/texts_big --workers 1 --out output/hist_big_1.json
python src/cpu_main.py --input data/texts/texts_big --workers 8 --out output/hist_big_8.json
```

### Benchmark workerów 1..8 (tabelka) — `src/bench_workers.py`

Histogram CPU (procesy) na danych tekstowych:

```bash
python src/bench_workers.py --mode cpu --input data/texts --min 1 --max 8
```

Histogram CPU (procesy) na dużych danych tekstowych:

```bash
python src/bench_workers.py --mode cpu --input data/texts/texts_big --min 1 --max 8
```

Crawler WWW (wątki) na URL-ach:

```bash
python src/bench_workers.py --mode crawler --input data/urls.txt --min 1 --max 8 --timeout 10
```

Uwagi:

- Skrypt zapisuje zbiorcze podsumowanie do `output/bench/summary_<mode>.json` (możesz ustawić własną ścieżkę przez `--summary-out`).
- Dla długich przebiegów wypisuje komunikaty postępu; można je wyłączyć przez `--quiet` albo zmienić częstotliwość przez `--progress-interval`.

### Wizualizacja wyników z CLI (PNG) — `src/plot_results.py`

**Działanie:**

- skrypt wczytuje JSON i generuje wykres PNG:
  - dla crawlera: czasy pobrania per URL,
  - dla histogramu: TOP słowa.

**Przykłady:**

```bash
python src/plot_results.py --input output/results_par.json --out output/crawler_plot.png
python src/plot_results.py --input output/hist_big_8.json --out output/hist_plot.png
```

---

## Format wyników (JSON) 

**Crawler (`src/main.py`)**

- `meta`: liczba workerów, czasy, liczba URL-i, OK/błędy
- `results[]`: `{ url, ok, status, elapsed_ms, title, word_count, error }`

**Histogram (`src/cpu_main.py`)**

- `meta`: liczba procesów, liczba plików, tokeny, czas
- `top_words[]`: lista `{ word, count }`

**Demo WWW (Web Workers)**

- `meta`: liczba workerów, liczba plików, tokeny, czas
- `top_words[]`
- `per_file[]`: `{ name, tokens, elapsed_ms }`
