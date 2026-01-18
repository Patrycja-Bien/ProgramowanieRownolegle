class Store {
    #state = {
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
    };

    #subscribers = new Map();

    getState() {
        return { ...this.#state };
    }

    set(key, value) {
        if (this.#state[key] !== value) {
            this.#state[key] = value;
            this.#notify(key);
            this.#notify('*');
        }
    }

    patch(partial) {
        for (const [k, v] of Object.entries(partial)) {
            this.#state[k] = v;
            this.#notify(k);
        }
        this.#notify('*');
    }

    subscribe(key, callback) {
        if (!this.#subscribers.has(key)) {
            this.#subscribers.set(key, new Set());
        }
        this.#subscribers.get(key).add(callback);
        callback(this.#state[key]);
        return () => this.#subscribers.get(key).delete(callback);
    }

    subscribeAll(callback) {
        return this.subscribe('*', () => callback(this.getState()));
    }

    #notify(key) {
        const set = this.#subscribers.get(key);
        if (!set) return;
        for (const cb of set) cb(this.#state[key]);
    }
}

export const store = new Store();
