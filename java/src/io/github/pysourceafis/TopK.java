// SPDX-License-Identifier: Apache-2.0
package io.github.pysourceafis;

import java.util.Arrays;

/** Bounded top-K collector (min-heap on score). One instance per worker thread. */
final class TopK {
    private final int k;
    private final int[] slots;
    private final double[] scores;
    private int size;
    long comparisons;

    TopK(int k) {
        this.k = Math.max(1, k);
        this.slots = new int[this.k];
        this.scores = new double[this.k];
    }

    void offer(int slot, double score) {
        if (size < k) {
            slots[size] = slot;
            scores[size] = score;
            siftUp(size++);
        } else if (score > scores[0]) {
            slots[0] = slot;
            scores[0] = score;
            siftDown(0);
        }
    }

    void merge(TopK other) {
        for (int i = 0; i < other.size; i++)
            offer(other.slots[i], other.scores[i]);
        comparisons += other.comparisons;
    }

    SearchResult toResult(long[] ids, long nanos) {
        Integer[] order = new Integer[size];
        for (int i = 0; i < size; i++)
            order[i] = i;
        Arrays.sort(order, (a, b) -> Double.compare(scores[b], scores[a]));
        long[] outIds = new long[size];
        double[] outScores = new double[size];
        for (int i = 0; i < size; i++) {
            outIds[i] = ids[slots[order[i]]];
            outScores[i] = scores[order[i]];
        }
        return new SearchResult(outIds, outScores, comparisons, nanos);
    }

    private void siftUp(int i) {
        while (i > 0) {
            int p = (i - 1) / 2;
            if (scores[p] <= scores[i])
                break;
            swap(i, p);
            i = p;
        }
    }

    private void siftDown(int i) {
        while (true) {
            int l = 2 * i + 1, r = l + 1, m = i;
            if (l < size && scores[l] < scores[m])
                m = l;
            if (r < size && scores[r] < scores[m])
                m = r;
            if (m == i)
                return;
            swap(i, m);
            i = m;
        }
    }

    private void swap(int a, int b) {
        int s = slots[a];
        slots[a] = slots[b];
        slots[b] = s;
        double v = scores[a];
        scores[a] = scores[b];
        scores[b] = v;
    }
}
