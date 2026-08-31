package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.lang.ref.Reference;
import java.util.ArrayList;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchAfterCursor;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchRequest;

/** Bounded local retained-heap envelope probe for live opaque cursors. */
public final class V33CursorRetentionProbe {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static volatile List<SearchAfterCursor> retainedCursors;

    private V33CursorRetentionProbe() {
    }

    /** Runs one isolated cursor-count measurement. */
    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                    "usage: V33CursorRetentionProbe <positive-cursor-count>");
        }
        int cursorCount = Integer.parseInt(arguments[0]);
        if (cursorCount <= 0) {
            throw new IllegalArgumentException("cursor count must be positive");
        }

        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .index(IndexDefinition.text(TEXT))
                .build()) {
            engine.addAll(List.of(
                    new Document(1, "retention stable"),
                    new Document(2, "retention stable")
            )).join();
            SearchRequest<Document> request = SearchRequest
                    .<Document>builder()
                    .query(io.github.patricklfdm.generalsearch.search.SearchQueries
                            .text(TEXT, "retention"))
                    .limit(1)
                    .build();
            for (int warmup = 0; warmup < 10_000; warmup++) {
                firstCursor(engine, request);
            }
            long baseline = usedAfterFullGc();

            List<SearchAfterCursor> cursors = new ArrayList<>(cursorCount);
            for (int cursor = 0; cursor < cursorCount; cursor++) {
                cursors.add(firstCursor(engine, request));
            }
            retainedCursors = cursors;
            long retained = usedAfterFullGc();
            Reference.reachabilityFence(cursors);

            retainedCursors = null;
            cursors = null;
            long released = usedAfterFullGc();
            long retainedDelta = Math.max(0L, retained - baseline);
            long releaseResidual = Math.max(0L, released - baseline);
            System.out.printf(
                    "cursorCount=%d baselineBytes=%d retainedBytes=%d "
                            + "retainedDeltaBytes=%d bytesPerCursorEnvelope=%.3f "
                            + "releasedBytes=%d releaseResidualBytes=%d%n",
                    cursorCount,
                    baseline,
                    retained,
                    retainedDelta,
                    (double) retainedDelta / cursorCount,
                    released,
                    releaseResidual
            );
        }
    }

    private static SearchAfterCursor firstCursor(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request
    ) {
        return engine.search(SearchPageRequest.builder(request).build())
                .nextCursor()
                .orElseThrow();
    }

    @SuppressWarnings("removal")
    private static long usedAfterFullGc() throws InterruptedException {
        Runtime runtime = Runtime.getRuntime();
        long minimum = Long.MAX_VALUE;
        for (int cycle = 0; cycle < 6; cycle++) {
            System.gc();
            Thread.sleep(50L);
            minimum = Math.min(
                    minimum,
                    runtime.totalMemory() - runtime.freeMemory()
            );
        }
        return minimum;
    }

    private record Document(int id, String body) {
    }
}
