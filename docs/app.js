import { store } from './store.js';

const filesEl = document.querySelector('#files');
const workersEl = document.querySelector('#workers');
const runBtn = document.querySelector('#run');
const runDemoBtn = document.querySelector('#runDemo');
const resetBtn = document.querySelector('#reset');
const downloadBtn = document.querySelector('#download');

const statusLabelEl = document.querySelector('#statusLabel');
const statusEl = document.querySelector('#status');
const filesCountEl = document.querySelector('#filesCount');
const elapsedEl = document.querySelector('#elapsed');
const tokensEl = document.querySelector('#tokens');
const uniqueEl = document.querySelector('#unique');
const avgPerFileEl = document.querySelector('#avgPerFile');
const fileStatsEl = document.querySelector('#fileStats');

let chart;

function setBusy(busy) {
    runBtn.disabled = busy;
    runDemoBtn.disabled = busy;
    resetBtn.disabled = busy;
    filesEl.disabled = busy;
    workersEl.disabled = busy;
}

function formatMs(ms) {
    if (ms == null) return '-';
    return `${ms} ms`;
}

function formatMaybeInt(x) {
    if (x == null) return '-';
    return String(x);
}

function formatAvgPerFile(ms, files) {
    if (ms == null || !files) return '-';
    return `${Math.round(ms / files)} ms`;
}

function mergeCounts(total, partial) {
    for (const [w, c] of Object.entries(partial)) {
        total[w] = (total[w] || 0) + c;
    }
}

function topN(counts, n) {
    const arr = Object.entries(counts);
    arr.sort((a, b) => b[1] - a[1]);
    return arr.slice(0, n).map(([word, count]) => ({ word, count }));
}

function downloadJson(obj, filename = 'result.json') {
    const blob = new Blob([JSON.stringify(obj, null, 2)], {
        type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

function renderChart(topWords) {
    const ctx = document.querySelector('#chart');
    const labels = topWords.map((x) => x.word);
    const data = topWords.map((x) => x.count);

    if (!chart) {
        chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Liczność',
                        data,
                    },
                ],
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: 'TOP słowa (Web Workers)' },
                },
                scales: {
                    x: { beginAtZero: true },
                },
            },
        });
    } else {
        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
        chart.update();
    }
}

async function readFiles(fileList) {
    const files = Array.from(fileList || []);
    const out = [];
    for (const f of files) {
        const text = await f.text();
        out.push({ name: f.name, text });
    }
    return out;
}

function getDemoFilesBig() {
    const filesCount = 200;
    const wordsPerFile = 120_000;

    const files = [];
    for (let i = 1; i <= filesCount; i++) {
        files.push({
            name: `demo_big_${String(i).padStart(2, '0')}.txt`,
            demo: {
                seed: 1000 + i,
                words: wordsPerFile,
            },
        });
    }
    return files;
}

function splitIntoChunks(items, parts) {
    const chunks = Array.from({ length: parts }, () => []);
    for (let i = 0; i < items.length; i++) {
        chunks[i % parts].push(items[i]);
    }
    return chunks.filter((c) => c.length > 0);
}

function runChunkInWorker({ chunk, id, demoConfig, onData }) {
    return new Promise((resolve, reject) => {
        const w = new Worker(new URL('./worker.js', import.meta.url), {
            type: 'module',
        });

        w.onmessage = (evt) => {
            try {
                onData(evt.data || {});
                w.terminate();
                resolve();
            } catch (e) {
                w.terminate();
                reject(e);
            }
        };

        w.onerror = (e) => {
            w.terminate();
            reject(e);
        };

        w.postMessage({ id, files: chunk, demoConfig });
    });
}

async function runAnalysis({ useDemo = false } = {}) {
    const fileList = filesEl.files;
    if (!useDemo && (!fileList || fileList.length === 0)) {
        store.patch({
            status: 'error',
            message: 'Wybierz przynajmniej 1 plik .txt (albo uruchom demo).',
        });
        return;
    }

    const workers = Math.max(
        1,
        Math.min(32, parseInt(workersEl.value || '4', 10))
    );

    setBusy(true);
    downloadBtn.disabled = true;
    store.patch({
        status: 'running',
        message: useDemo
            ? 'Start demo (duże pliki): generowanie i analiza w workerach...'
            : 'Czytanie plików...',
        filesCount: useDemo ? 0 : fileList.length,
        elapsedMs: null,
        topWords: [],
        jsonResult: null,
    });

    const t0 = performance.now();
    const files = useDemo ? getDemoFilesBig() : await readFiles(fileList);

    store.patch({ filesCount: files.length });

    store.patch({
        status: 'running',
        message: `Start: ${workers} workerów...`,
    });

    const chunks = splitIntoChunks(files, workers);

    const total = Object.create(null);
    let tokens = 0;
    const perFile = [];

    const demoConfig = useDemo
        ? {
              vocabSeed: 123,
              vocabSize: 8000,
              minLen: 3,
              maxLen: 10,
          }
        : null;

    const promises = chunks.map((chunk, idx) => {
        return runChunkInWorker({
            chunk,
            id: idx,
            demoConfig,
            onData: ({ counts, tokens: t, fileStats }) => {
                if (counts) mergeCounts(total, counts);
                tokens += Number(t || 0);
                if (Array.isArray(fileStats)) perFile.push(...fileStats);
            },
        });
    });

    try {
        await Promise.all(promises);
    } catch (e) {
        const ms = Math.round(performance.now() - t0);
        store.patch({
            status: 'error',
            message: `Błąd workera: ${e}`,
            elapsedMs: ms,
        });
        setBusy(false);
        return;
    }

    const topWords = topN(total, 30);
    const ms = Math.round(performance.now() - t0);
    perFile.sort((a, b) => (b.elapsed_ms || 0) - (a.elapsed_ms || 0));
    const unique = Object.keys(total).length;
    const avgPerFile = files.length ? Math.round(ms / files.length) : null;

    const result = {
        meta: {
            mode: 'web-workers',
            workers: chunks.length,
            files: files.length,
            total_tokens: tokens,
            unique_tokens: unique,
            total_elapsed_ms: ms,
            avg_elapsed_ms_per_file: avgPerFile,
        },
        top_words: topWords,
        per_file: perFile,
    };

    store.patch({
        status: 'done',
        message: 'Gotowe.',
        elapsedMs: ms,
        topWords,
        jsonResult: result,
        tokens,
        unique,
        avgPerFile,
        perFile,
    });

    downloadBtn.disabled = false;
    setBusy(false);
}

function reset() {
    store.patch({
        status: 'idle',
        message: '',
        filesCount: 0,
        elapsedMs: null,
        topWords: [],
        jsonResult: null,
        tokens: null,
        unique: null,
        avgPerFile: null,
        perFile: [],
    });
    downloadBtn.disabled = true;
    setBusy(false);
    if (chart) {
        chart.destroy();
        chart = null;
    }
}

runBtn.addEventListener('click', () => runAnalysis({ useDemo: false }));
runDemoBtn.addEventListener('click', () => runAnalysis({ useDemo: true }));
resetBtn.addEventListener('click', () => reset());
downloadBtn.addEventListener('click', () => {
    const s = store.getState();
    if (s.jsonResult) downloadJson(s.jsonResult, 'web_workers_histogram.json');
});

filesEl.addEventListener('change', () => {
    store.set('filesCount', filesEl.files?.length || 0);
});

store.subscribe('status', (v) => (statusLabelEl.textContent = v));
store.subscribe(
    'filesCount',
    (v) => (filesCountEl.textContent = String(v || 0))
);
store.subscribe('elapsedMs', (v) => (elapsedEl.textContent = formatMs(v)));
store.subscribe('message', (v) => (statusEl.textContent = v || ''));
store.subscribe('topWords', (v) => {
    if (Array.isArray(v) && v.length) renderChart(v);
});

store.subscribe('tokens', (v) => (tokensEl.textContent = formatMaybeInt(v)));
store.subscribe('unique', (v) => (uniqueEl.textContent = formatMaybeInt(v)));
store.subscribeAll((s) => {
    avgPerFileEl.textContent = formatAvgPerFile(s.elapsedMs, s.filesCount);
});

store.subscribe('perFile', (v) => {
    if (!Array.isArray(v) || v.length === 0) {
        fileStatsEl.textContent = 'Brak danych';
        return;
    }
    const lines = v
        .slice()
        .sort((a, b) => (b.elapsed_ms || 0) - (a.elapsed_ms || 0))
        .map(
            (x) =>
                `${String(x.name).padEnd(24)}  ${String(x.elapsed_ms).padStart(
                    5
                )} ms  ${String(x.tokens).padStart(6)} tok`
        );
    fileStatsEl.textContent = lines.join('\n');
});

reset();
