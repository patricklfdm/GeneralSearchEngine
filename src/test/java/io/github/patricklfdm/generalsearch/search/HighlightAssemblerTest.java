package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import org.junit.jupiter.api.Test;

class HighlightAssemblerTest {
    @Test
    void normalizesDuplicatesContainmentAndOverlapButKeepsAdjacency() {
        List<HighlightSpan> actual = HighlightAssembler.normalizeSpans(List.of(
                span(8, 10),
                span(2, 4),
                span(2, 4),
                span(3, 7),
                span(7, 8),
                span(9, 12)
        ));

        assertSpans(List.of(range(2, 7), range(7, 8), range(8, 12)), actual);
    }

    @Test
    void fragmentWindowsMergeOnlyOnOverlapAndExpandSurrogateBoundaries() {
        List<HighlightFragment> adjacent = HighlightAssembler.fragments(
                "0123456789",
                List.of(span(2, 4), span(4, 6)),
                0,
                3
        );
        assertEquals(2, adjacent.size());

        List<HighlightFragment> overlapping = HighlightAssembler.fragments(
                "0123456789",
                List.of(span(2, 4), span(6, 8)),
                2,
                3
        );
        assertEquals(1, overlapping.size());
        assertEquals("0123456789", overlapping.getFirst().text());

        List<HighlightFragment> surrogate = HighlightAssembler.fragments(
                "a😀b",
                List.of(span(3, 4)),
                1,
                3
        );
        assertEquals(1, surrogate.size());
        assertEquals(1, surrogate.getFirst().startOffset());
        assertEquals(4, surrogate.getFirst().endOffset());
        assertEquals("😀b", surrogate.getFirst().text());
    }

    @Test
    void randomizedFragmentsEqualIndependentReference() {
        long seed = 0x32F6A63L;
        Random random = new Random(seed);
        String source = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop";
        for (int trial = 0; trial < 2_000; trial++) {
            List<V32TestReference.Range> raw = new ArrayList<>();
            int count = random.nextInt(16);
            for (int index = 0; index < count; index++) {
                int start = random.nextInt(source.length());
                int end = start + 1 + random.nextInt(source.length() - start);
                raw.add(range(start, end));
            }
            int context = random.nextInt(12);
            int cap = 1 + random.nextInt(6);
            List<V32TestReference.Fragment> expected =
                    V32TestReference.fragments(source, raw, context, cap);
            List<HighlightFragment> actual = HighlightAssembler.fragments(
                    source,
                    HighlightAssembler.normalizeSpans(raw.stream()
                            .map(value -> span(value.start(), value.end()))
                            .toList()),
                    context,
                    cap
            );
            assertFragments(
                    expected,
                    actual,
                    "seed=" + seed + " trial=" + trial + " raw=" + raw
            );
        }
    }

    private static void assertFragments(
            List<V32TestReference.Fragment> expected,
            List<HighlightFragment> actual,
            String message
    ) {
        assertEquals(expected.size(), actual.size(), message);
        for (int index = 0; index < expected.size(); index++) {
            V32TestReference.Fragment left = expected.get(index);
            HighlightFragment right = actual.get(index);
            assertEquals(left.window().start(), right.startOffset(), message);
            assertEquals(left.window().end(), right.endOffset(), message);
            assertEquals(left.text(), right.text(), message);
            assertSpans(left.spans(), right.spans());
        }
    }

    private static void assertSpans(
            List<V32TestReference.Range> expected,
            List<HighlightSpan> actual
    ) {
        assertEquals(
                expected,
                actual.stream()
                        .map(value -> range(
                                value.startOffset(),
                                value.endOffset()
                        ))
                        .toList()
        );
    }

    private static HighlightSpan span(int start, int end) {
        return new HighlightSpan(start, end);
    }

    private static V32TestReference.Range range(int start, int end) {
        return new V32TestReference.Range(start, end);
    }
}
