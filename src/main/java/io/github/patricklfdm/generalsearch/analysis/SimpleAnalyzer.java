package io.github.patricklfdm.generalsearch.analysis;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Locale-independent NFKC/lowercase analyzer using non-letter/digit boundaries.
 */
public enum SimpleAnalyzer implements OffsetAnalyzer {
    /** Shared stateless analyzer instance. */
    INSTANCE;

    @Override
    public List<Token> analyze(String text) {
        if (text == null || text.isEmpty()) {
            return List.of();
        }
        String normalized = Normalizer.normalize(text, Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT);
        List<Token> tokens = new ArrayList<>();
        StringBuilder term = new StringBuilder();
        normalized.codePoints().forEach(codePoint -> {
            if (Character.isLetterOrDigit(codePoint)) {
                term.appendCodePoint(codePoint);
            } else if (!term.isEmpty()) {
                tokens.add(new Token(term.toString()));
                term.setLength(0);
            }
        });
        if (!term.isEmpty()) {
            tokens.add(new Token(term.toString()));
        }
        return List.copyOf(tokens);
    }

    /**
     * Retains the published direct ordinary path without constructing offset tokens.
     */
    @Override
    public List<AnalyzedToken> analyzeWithPositions(String text) {
        return analyze(text).stream()
                .map(token -> new AnalyzedToken(token.term(), 1))
                .toList();
    }

    /**
     * Analyzes text with exact original-string UTF-16 ranges. NFKC and lowercase
     * output is identical to {@link #analyze(String)}, including compatibility
     * characters that expand to multiple delimiter-separated terms.
     */
    @Override
    public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
        if (text == null || text.isEmpty()) {
            return List.of();
        }
        List<MappedCodePoint> normalized = mapNormalizedCodePoints(text);
        List<OffsetAnalyzedToken> tokens = new ArrayList<>();
        StringBuilder term = new StringBuilder();
        int tokenStart = Integer.MAX_VALUE;
        int tokenEnd = -1;
        for (MappedCodePoint mapped : normalized) {
            if (Character.isLetterOrDigit(mapped.codePoint())) {
                term.appendCodePoint(mapped.codePoint());
                tokenStart = Math.min(tokenStart, mapped.startOffset());
                tokenEnd = Math.max(tokenEnd, mapped.endOffset());
            } else if (!term.isEmpty()) {
                tokens.add(new OffsetAnalyzedToken(
                        term.toString(),
                        1,
                        tokenStart,
                        tokenEnd
                ));
                term.setLength(0);
                tokenStart = Integer.MAX_VALUE;
                tokenEnd = -1;
            }
        }
        if (!term.isEmpty()) {
            tokens.add(new OffsetAnalyzedToken(
                    term.toString(),
                    1,
                    tokenStart,
                    tokenEnd
            ));
        }
        return List.copyOf(tokens);
    }

    private static List<MappedCodePoint> mapNormalizedCodePoints(String source) {
        List<MappedCodePoint> mapped = new ArrayList<>();
        Map<Integer, String> normalizedCodePoints = new HashMap<>();
        int chunkStart = 0;
        while (chunkStart < source.length()) {
            int codePoint = source.codePointAt(chunkStart);
            int chunkEnd = chunkStart + Character.charCount(codePoint);
            if (isNormalizationClusterCodePoint(codePoint)) {
                while (chunkEnd < source.length()) {
                    int next = source.codePointAt(chunkEnd);
                    if (!isNormalizationClusterCodePoint(next)) {
                        break;
                    }
                    chunkEnd += Character.charCount(next);
                }
            }
            appendMappedChunk(
                    source,
                    chunkStart,
                    chunkEnd,
                    mapped,
                    normalizedCodePoints
            );
            chunkStart = chunkEnd;
        }

        String expected = normalize(source);
        if (!mappedText(mapped).equals(expected)) {
            return mapIncrementally(source, 0, source.length());
        }
        return List.copyOf(mapped);
    }

    private static void appendMappedChunk(
            String source,
            int chunkStart,
            int chunkEnd,
            List<MappedCodePoint> destination,
            Map<Integer, String> normalizedCodePoints
    ) {
        List<MappedCodePoint> independent = new ArrayList<>();
        int sourceIndex = chunkStart;
        while (sourceIndex < chunkEnd) {
            int sourceCodePoint = source.codePointAt(sourceIndex);
            int sourceEnd = sourceIndex + Character.charCount(sourceCodePoint);
            int mappedStart = sourceIndex;
            int mappedEnd = sourceEnd;
            String normalizedCodePoint = normalizedCodePoints.computeIfAbsent(
                    sourceCodePoint,
                    SimpleAnalyzer::normalizeCodePoint
            );
            normalizedCodePoint.codePoints().forEach(codePoint ->
                    independent.add(new MappedCodePoint(
                            codePoint,
                            mappedStart,
                            mappedEnd
                    ))
            );
            sourceIndex = sourceEnd;
        }
        String normalizedChunk = normalize(source.substring(chunkStart, chunkEnd));
        if (mappedText(independent).equals(normalizedChunk)) {
            destination.addAll(independent);
        } else {
            destination.addAll(mapIncrementally(source, chunkStart, chunkEnd));
        }
    }

    private static List<MappedCodePoint> mapIncrementally(
            String source,
            int sourceStart,
            int sourceEnd
    ) {
        List<MappedCodePoint> mapped = new ArrayList<>();
        int sourceIndex = sourceStart;
        while (sourceIndex < sourceEnd) {
            int sourceCodePoint = source.codePointAt(sourceIndex);
            int nextSourceIndex = sourceIndex + Character.charCount(sourceCodePoint);
            int[] nextCodePoints = normalize(source.substring(
                    sourceStart,
                    nextSourceIndex
            )).codePoints().toArray();
            int common = 0;
            while (common < mapped.size()
                    && common < nextCodePoints.length
                    && mapped.get(common).codePoint() == nextCodePoints[common]) {
                common++;
            }

            int replacementStart = sourceIndex;
            int replacementEnd = nextSourceIndex;
            for (int index = common; index < mapped.size(); index++) {
                MappedCodePoint replaced = mapped.get(index);
                replacementStart = Math.min(
                        replacementStart,
                        replaced.startOffset()
                );
                replacementEnd = Math.max(replacementEnd, replaced.endOffset());
            }
            while (mapped.size() > common) {
                mapped.removeLast();
            }
            for (int index = common; index < nextCodePoints.length; index++) {
                mapped.add(new MappedCodePoint(
                        nextCodePoints[index],
                        replacementStart,
                        replacementEnd
                ));
            }
            sourceIndex = nextSourceIndex;
        }
        return List.copyOf(mapped);
    }

    private static boolean isNormalizationClusterCodePoint(int codePoint) {
        if (Character.isLetterOrDigit(codePoint)) {
            return true;
        }
        int type = Character.getType(codePoint);
        return type == Character.NON_SPACING_MARK
                || type == Character.COMBINING_SPACING_MARK
                || type == Character.ENCLOSING_MARK;
    }

    private static String normalize(String text) {
        return Normalizer.normalize(text, Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT);
    }

    private static String normalizeCodePoint(int codePoint) {
        return normalize(new String(Character.toChars(codePoint)));
    }

    private static String mappedText(List<MappedCodePoint> mapped) {
        StringBuilder text = new StringBuilder();
        mapped.forEach(value -> text.appendCodePoint(value.codePoint()));
        return text.toString();
    }

    private record MappedCodePoint(
            int codePoint,
            int startOffset,
            int endOffset
    ) {
    }
}
