const WORD_RE = /[\p{L}\p{N}]+/gu;

function mulberry32(seed) {
    let t = seed >>> 0;
    return function () {
        t += 0x6d2b79f5;
        let x = t;
        x = Math.imul(x ^ (x >>> 15), x | 1);
        x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
        return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
    };
}

function makeWord(rng, minLen, maxLen) {
    const letters = 'abcdefghijklmnopqrstuvwxyz';
    const n = Math.floor(rng() * (maxLen - minLen + 1)) + minLen;
    let s = '';
    for (let i = 0; i < n; i++) {
        s += letters[Math.floor(rng() * letters.length)];
    }
    return s;
}

function makeVocab(seed, size, minLen, maxLen) {
    const rng = mulberry32(seed);
    const vocab = new Array(size);
    for (let i = 0; i < size; i++) {
        vocab[i] = makeWord(rng, minLen, maxLen);
    }
    return vocab;
}

function countWordsFromText(text) {
    const counts = Object.create(null);
    let tokens = 0;

    WORD_RE.lastIndex = 0;
    let m;
    while ((m = WORD_RE.exec(text)) !== null) {
        const w = String(m[0]).toLowerCase();
        tokens++;
        counts[w] = (counts[w] || 0) + 1;
    }

    return { counts, tokens };
}

function countWordsGenerated(demo, sharedVocab) {
    const counts = Object.create(null);
    const rng = mulberry32((demo.seed ?? 1) >>> 0);
    const wordsTotal = Math.max(0, Number(demo.words || 0));

    const hotSize = Math.max(1, Math.floor(sharedVocab.length / 20));

    for (let i = 0; i < wordsTotal; i++) {
        const useHot = rng() < 0.35;
        const idx = useHot
            ? Math.floor(rng() * hotSize)
            : Math.floor(rng() * sharedVocab.length);
        const w = sharedVocab[idx];
        counts[w] = (counts[w] || 0) + 1;
    }

    return { counts, tokens: wordsTotal };
}

self.onmessage = (evt) => {
    const { id, files } = evt.data;

    const demoConfig = evt.data.demoConfig;
    const isDemo = !!demoConfig;

    const sharedVocab = isDemo
        ? makeVocab(
              (demoConfig.vocabSeed ?? 123) >>> 0,
              Math.max(100, Number(demoConfig.vocabSize || 8000)),
              Math.max(1, Number(demoConfig.minLen || 3)),
              Math.max(2, Number(demoConfig.maxLen || 10))
          )
        : null;

    const merged = Object.create(null);
    let tokens = 0;
    const fileStats = [];

    for (const f of files) {
        const t0 = performance.now();
        const r = isDemo
            ? countWordsGenerated(f.demo || {}, sharedVocab)
            : countWordsFromText(f.text || '');
        const elapsedMs = Math.round(performance.now() - t0);
        tokens += r.tokens;
        for (const [w, c] of Object.entries(r.counts)) {
            merged[w] = (merged[w] || 0) + c;
        }

        fileStats.push({
            name: f.name || 'unknown',
            tokens: r.tokens,
            elapsed_ms: elapsedMs,
        });
    }

    self.postMessage({ id, counts: merged, tokens, fileStats });
};
