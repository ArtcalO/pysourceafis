// SPDX-License-Identifier: Apache-2.0
package io.github.pysourceafis;

/** Ranked search output; arrays are parallel and sorted by descending score. */
public final class SearchResult {
    public final long[] ids;
    public final double[] scores;
    /** Number of SourceAFIS comparisons performed. */
    public final long comparisons;
    public final long nanos;

    SearchResult(long[] ids, double[] scores, long comparisons, long nanos) {
        this.ids = ids;
        this.scores = scores;
        this.comparisons = comparisons;
        this.nanos = nanos;
    }
}
