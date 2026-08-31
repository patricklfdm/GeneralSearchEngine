package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Invocation-local query evidence normalization and fragment construction. */
final class HighlightAssembler {
    private HighlightAssembler() {
    }

    static <T> HighlightedSearchResult<T> assemble(
            List<ExecutedSearchHit<T>> hits,
            List<TextField<T>> fields,
            ScoringPlanNode<T> root,
            int contextCharacters,
            int maxFragmentsPerField
    ) {
        List<HighlightedSearchHit<T>> highlighted = new ArrayList<>(hits.size());
        for (ExecutedSearchHit<T> executed : hits) {
            SearchHit<T> hit = executed.hit();
            List<FieldHighlight> fieldHighlights = new ArrayList<>();
            for (TextField<T> field : fields) {
                String source = field.field().valueOf(hit.document());
                if (source == null || source.isEmpty()) {
                    continue;
                }
                OffsetAnalyzer analyzer = requireOffsetAnalyzer(field);
                List<OffsetAnalyzedToken> tokens =
                        OffsetTokenSequenceValidator.validate(
                                field.name(),
                                source,
                                analyzer.analyzeWithOffsets(source)
                        );
                List<HighlightSpan> spans = normalizeSpans(
                        HighlightEvidenceCollector.collect(
                                root,
                                executed.documentId(),
                                field.name(),
                                tokens
                        )
                );
                List<HighlightFragment> fragments = fragments(
                        source,
                        spans,
                        contextCharacters,
                        maxFragmentsPerField
                );
                if (!fragments.isEmpty()) {
                    fieldHighlights.add(new FieldHighlight(
                            field.name(),
                            fragments
                    ));
                }
            }
            highlighted.add(new HighlightedSearchHit<>(hit, fieldHighlights));
        }
        return new HighlightedSearchResult<>(highlighted);
    }

    private static OffsetAnalyzer requireOffsetAnalyzer(TextField<?> field) {
        if (field.analyzer() instanceof OffsetAnalyzer offsetAnalyzer) {
            return offsetAnalyzer;
        }
        throw new UnsupportedOperationException(
                "text field '" + field.name()
                        + "' does not use an OffsetAnalyzer");
    }

    static List<HighlightSpan> normalizeSpans(List<HighlightSpan> rawSpans) {
        List<HighlightSpan> raw = new ArrayList<>(List.copyOf(rawSpans));
        raw.sort(Comparator
                .comparingInt(HighlightSpan::startOffset)
                .thenComparingInt(HighlightSpan::endOffset));
        List<HighlightSpan> normalized = new ArrayList<>();
        for (HighlightSpan span : raw) {
            if (normalized.isEmpty()) {
                normalized.add(span);
                continue;
            }
            HighlightSpan previous = normalized.getLast();
            if (span.startOffset() < previous.endOffset()) {
                normalized.set(
                        normalized.size() - 1,
                        new HighlightSpan(
                                previous.startOffset(),
                                Math.max(previous.endOffset(), span.endOffset())
                        )
                );
            } else {
                normalized.add(span);
            }
        }
        return List.copyOf(normalized);
    }

    static List<HighlightFragment> fragments(
            String source,
            List<HighlightSpan> spans,
            int contextCharacters,
            int maxFragmentsPerField
    ) {
        if (spans.isEmpty()) {
            return List.of();
        }
        List<Window> windows = new ArrayList<>();
        for (HighlightSpan span : spans) {
            int start = (int) Math.max(
                    0L,
                    (long) span.startOffset() - contextCharacters
            );
            int end = (int) Math.min(
                    source.length(),
                    (long) span.endOffset() + contextCharacters
            );
            start = adjustStart(source, start);
            end = adjustEnd(source, end);
            if (!windows.isEmpty() && start < windows.getLast().endOffset()) {
                Window previous = windows.removeLast();
                windows.add(new Window(
                        previous.startOffset(),
                        Math.max(previous.endOffset(), end)
                ));
            } else {
                windows.add(new Window(start, end));
            }
        }

        List<HighlightFragment> fragments = new ArrayList<>();
        for (Window window : windows) {
            if (fragments.size() == maxFragmentsPerField) {
                break;
            }
            List<HighlightSpan> contained = spans.stream()
                    .filter(span -> span.startOffset() >= window.startOffset()
                            && span.endOffset() <= window.endOffset())
                    .toList();
            fragments.add(new HighlightFragment(
                    window.startOffset(),
                    window.endOffset(),
                    source.substring(window.startOffset(), window.endOffset()),
                    contained
            ));
        }
        return List.copyOf(fragments);
    }

    private static int adjustStart(String source, int boundary) {
        return splitsSurrogatePair(source, boundary) ? boundary - 1 : boundary;
    }

    private static int adjustEnd(String source, int boundary) {
        return splitsSurrogatePair(source, boundary) ? boundary + 1 : boundary;
    }

    private static boolean splitsSurrogatePair(String source, int boundary) {
        return boundary > 0
                && boundary < source.length()
                && Character.isHighSurrogate(source.charAt(boundary - 1))
                && Character.isLowSurrogate(source.charAt(boundary));
    }

    private record Window(int startOffset, int endOffset) {
    }
}
