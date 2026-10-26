// SPDX-License-Identifier: Apache-2.0
package io.github.pysourceafis;

import com.machinezoo.sourceafis.FingerprintMatcher;
import com.machinezoo.sourceafis.FingerprintTemplate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * In-memory collection of templates with parallel 1:N search.
 *
 * Entries are identified by a long id chosen by the Python side. A search
 * builds one FingerprintMatcher for the probe (documented as thread-safe for
 * match()) and scans the gallery in chunks on a fixed thread pool, keeping a
 * bounded top-K per worker. Searches take the read lock; mutations take the
 * write lock, so add/remove are safe while searching.
 */
public final class Gallery implements AutoCloseable {
    private static final int CHUNK = 256;

    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private final ExecutorService pool;
    private final int threads;

    private FingerprintTemplate[] templates = new FingerprintTemplate[256];
    private long[] ids = new long[256];
    private int nextSlot = 0;
    private int live = 0;
    private final HashMap<Long, Integer> slots = new HashMap<>();

    public Gallery(int threads) {
        this.threads = threads > 0 ? threads : Runtime.getRuntime().availableProcessors();
        AtomicInteger n = new AtomicInteger();
        this.pool = Executors.newFixedThreadPool(this.threads, r -> {
            Thread t = new Thread(r, "pysourceafis-match-" + n.incrementAndGet());
            t.setDaemon(true);
            return t;
        });
    }

    public int threads() { return threads; }

    /** Adds or replaces entries with already deserialized templates. */
    public void putAll(long[] keys, FingerprintTemplate[] values) {
        if (keys.length != values.length)
            throw new IllegalArgumentException("keys and templates differ in length");
        lock.writeLock().lock();
        try {
            for (int i = 0; i < keys.length; i++) {
                if (values[i] == null)
                    throw new IllegalArgumentException("null template");
                removeLocked(keys[i]);
                int slot = allocateLocked();
                templates[slot] = values[i];
                ids[slot] = keys[i];
                slots.put(keys[i], slot);
                live++;
            }
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Deserializes templates in parallel and adds them. Returns the indexes
     * (into the input arrays) of templates that could not be deserialized.
     */
    public int[] putAllSerialized(long[] keys, byte[][] serialized) throws InterruptedException {
        int n = serialized.length;
        FingerprintTemplate[] parsed = new FingerprintTemplate[n];
        AtomicInteger cursor = new AtomicInteger();
        List<Future<?>> futures = new ArrayList<>();
        for (int w = 0; w < Math.min(threads, Math.max(1, n / 32)); w++) {
            futures.add(pool.submit(() -> {
                int i;
                while ((i = cursor.getAndIncrement()) < n) {
                    try {
                        parsed[i] = new FingerprintTemplate(serialized[i]);
                    } catch (RuntimeException ex) {
                        parsed[i] = null;
                    }
                }
            }));
        }
        await(futures);
        int failed = 0;
        for (FingerprintTemplate t : parsed)
            if (t == null)
                failed++;
        int[] failures = new int[failed];
        long[] okKeys = new long[n - failed];
        FingerprintTemplate[] okTemplates = new FingerprintTemplate[n - failed];
        for (int i = 0, f = 0, k = 0; i < n; i++) {
            if (parsed[i] == null) {
                failures[f++] = i;
            } else {
                okKeys[k] = keys[i];
                okTemplates[k++] = parsed[i];
            }
        }
        putAll(okKeys, okTemplates);
        return failures;
    }

    public boolean remove(long key) {
        lock.writeLock().lock();
        try {
            boolean removed = removeLocked(key);
            if (removed && nextSlot - live > Math.max(1024, live))
                compactLocked();
            return removed;
        } finally {
            lock.writeLock().unlock();
        }
    }

    public void clear() {
        lock.writeLock().lock();
        try {
            Arrays.fill(templates, 0, nextSlot, null);
            nextSlot = 0;
            live = 0;
            slots.clear();
        } finally {
            lock.writeLock().unlock();
        }
    }

    public int size() {
        lock.readLock().lock();
        try {
            return live;
        } finally {
            lock.readLock().unlock();
        }
    }

    public boolean contains(long key) {
        lock.readLock().lock();
        try {
            return slots.containsKey(key);
        } finally {
            lock.readLock().unlock();
        }
    }

    public FingerprintTemplate get(long key) {
        lock.readLock().lock();
        try {
            Integer slot = slots.get(key);
            return slot == null ? null : templates[slot];
        } finally {
            lock.readLock().unlock();
        }
    }

    /** Deep memory estimate of all templates, as reported by SourceAFIS (bytes). */
    public long memory() {
        lock.readLock().lock();
        try {
            long total = 0;
            for (int i = 0; i < nextSlot; i++)
                if (templates[i] != null)
                    total += templates[i].memory();
            return total;
        } finally {
            lock.readLock().unlock();
        }
    }

    /**
     * Compares the probe with every template and returns the best {@code topK}
     * results with a score of at least {@code minScore}, best first.
     */
    public SearchResult search(FingerprintTemplate probe, int topK, double minScore) throws InterruptedException {
        long t0 = System.nanoTime();
        FingerprintMatcher matcher = new FingerprintMatcher(probe);
        lock.readLock().lock();
        try {
            final int total = nextSlot;
            final FingerprintTemplate[] snapshot = templates;
            int chunks = (total + CHUNK - 1) / CHUNK;
            int workers = Math.max(1, Math.min(threads, chunks));
            AtomicInteger cursor = new AtomicInteger();
            List<Future<TopK>> futures = new ArrayList<>(workers);
            for (int w = 0; w < workers; w++) {
                futures.add(pool.submit(() -> {
                    TopK local = new TopK(topK);
                    int c;
                    while ((c = cursor.getAndIncrement()) < chunks) {
                        int end = Math.min(total, (c + 1) * CHUNK);
                        for (int i = c * CHUNK; i < end; i++) {
                            FingerprintTemplate candidate = snapshot[i];
                            if (candidate == null)
                                continue;
                            double score = matcher.match(candidate);
                            local.comparisons++;
                            if (score >= minScore)
                                local.offer(i, score);
                        }
                    }
                    return local;
                }));
            }
            TopK merged = new TopK(topK);
            for (Future<TopK> f : futures) {
                try {
                    merged.merge(f.get());
                } catch (ExecutionException ex) {
                    throw new IllegalStateException(ex.getCause());
                }
            }
            return merged.toResult(ids, System.nanoTime() - t0);
        } finally {
            lock.readLock().unlock();
        }
    }

    @Override
    public void close() {
        pool.shutdownNow();
    }

    private boolean removeLocked(long key) {
        Integer slot = slots.remove(key);
        if (slot == null)
            return false;
        templates[slot] = null;
        live--;
        return true;
    }

    private int allocateLocked() {
        if (nextSlot == templates.length) {
            if (nextSlot - live > live) {
                compactLocked();
                if (nextSlot < templates.length)
                    return nextSlot++;
            }
            int cap = templates.length * 2;
            templates = Arrays.copyOf(templates, cap);
            ids = Arrays.copyOf(ids, cap);
        }
        return nextSlot++;
    }

    private void compactLocked() {
        int j = 0;
        for (int i = 0; i < nextSlot; i++) {
            if (templates[i] == null)
                continue;
            templates[j] = templates[i];
            ids[j] = ids[i];
            slots.put(ids[j], j);
            j++;
        }
        Arrays.fill(templates, j, nextSlot, null);
        nextSlot = j;
    }

    private static void await(List<Future<?>> futures) throws InterruptedException {
        for (Future<?> f : futures) {
            try {
                f.get();
            } catch (ExecutionException ex) {
                throw new IllegalStateException(ex.getCause());
            }
        }
    }
}
