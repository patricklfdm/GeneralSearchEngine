package io.github.patricklfdm.generalsearch.search;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.Set;

/** Representation-free reference logic reserved for V3.3 pagination tests. */
final class V33TestReference {
    private static final Comparator<Candidate> CANONICAL_ORDER = (left, right) -> {
        int scoreComparison = Double.compare(right.score(), left.score());
        return scoreComparison != 0
                ? scoreComparison
                : Integer.compare(left.documentId(), right.documentId());
    };

    private V33TestReference() {
    }

    static Page page(
            List<Candidate> candidates,
            int limit,
            Anchor after,
            boolean exactTotalHits
    ) {
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
        List<Candidate> input = List.copyOf(candidates);
        Set<Integer> documentIds = new java.util.HashSet<>();
        for (Candidate candidate : input) {
            if (!documentIds.add(candidate.documentId())) {
                throw new IllegalArgumentException(
                        "document IDs must be unique");
            }
        }

        List<Candidate> matches = input.stream()
                .filter(Candidate::fullMatch)
                .sorted(CANONICAL_ORDER)
                .toList();
        List<Candidate> eligible = matches.stream()
                .filter(candidate -> after == null || isAfter(candidate, after))
                .toList();
        List<Candidate> hits = List.copyOf(eligible.subList(
                0,
                Math.min(limit, eligible.size())
        ));
        Optional<Anchor> nextCursor = eligible.size() > hits.size()
                ? Optional.of(Anchor.from(hits.getLast()))
                : Optional.empty();
        OptionalLong totalHits = exactTotalHits
                ? OptionalLong.of(matches.size())
                : OptionalLong.empty();
        return new Page(hits, nextCursor, totalHits);
    }

    static List<Candidate> walk(
            List<Candidate> candidates,
            int limit,
            boolean exactTotalHits
    ) {
        List<Candidate> collected = new ArrayList<>();
        Anchor after = null;
        while (true) {
            Page page = page(candidates, limit, after, exactTotalHits);
            collected.addAll(page.hits());
            if (page.nextCursor().isEmpty()) {
                return List.copyOf(collected);
            }
            after = page.nextCursor().orElseThrow();
        }
    }

    static Set<Object> directReferenceValues(Object value) {
        Objects.requireNonNull(value, "value");
        Set<Object> references = Collections.newSetFromMap(
                new IdentityHashMap<>());
        for (Field field : value.getClass().getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers())
                    || field.getType().isPrimitive()) {
                continue;
            }
            try {
                field.setAccessible(true);
                references.add(field.get(value));
            } catch (IllegalAccessException inaccessible) {
                throw new AssertionError(inaccessible);
            }
        }
        references.remove(null);
        return references;
    }

    private static boolean isAfter(Candidate candidate, Anchor after) {
        int scoreComparison = Double.compare(candidate.score(), after.score());
        return scoreComparison < 0
                || (scoreComparison == 0
                && candidate.documentId() > after.documentId());
    }

    record Candidate(
            int documentId,
            double score,
            boolean queryMatched,
            boolean filterMatched
    ) {
        Candidate {
            if (documentId < 0) {
                throw new IllegalArgumentException(
                        "document ID must not be negative");
            }
            if (!Double.isFinite(score) || score < 0.0) {
                throw new IllegalArgumentException(
                        "score must be finite and non-negative");
            }
        }

        boolean fullMatch() {
            return queryMatched && filterMatched;
        }
    }

    record Anchor(double score, int documentId) {
        Anchor {
            if (!Double.isFinite(score) || score < 0.0) {
                throw new IllegalArgumentException(
                        "score must be finite and non-negative");
            }
            if (documentId < 0) {
                throw new IllegalArgumentException(
                        "document ID must not be negative");
            }
        }

        static Anchor from(Candidate candidate) {
            return new Anchor(candidate.score(), candidate.documentId());
        }
    }

    record Page(
            List<Candidate> hits,
            Optional<Anchor> nextCursor,
            OptionalLong totalHits
    ) {
        Page {
            hits = List.copyOf(hits);
            nextCursor = Objects.requireNonNull(nextCursor, "nextCursor");
            totalHits = Objects.requireNonNull(totalHits, "totalHits");
        }
    }

    enum CursorReason {
        UNSUPPORTED_CURSOR,
        DIFFERENT_ENGINE,
        DIFFERENT_REQUEST,
        STALE_SNAPSHOT
    }

    static final class ReferenceEngine {
        private final Object ownerToken = new Object();
        private long snapshotVersion;

        ReferenceCursor cursor(Object request, Anchor anchor) {
            Objects.requireNonNull(request, "request");
            Objects.requireNonNull(anchor, "anchor");
            return new ReferenceCursor(
                    ownerToken,
                    request,
                    snapshotVersion,
                    Double.doubleToRawLongBits(anchor.score()),
                    anchor.documentId()
            );
        }

        Optional<CursorReason> rejectionReason(Object cursor, Object request) {
            if (!(cursor instanceof ReferenceCursor referenceCursor)) {
                return Optional.of(CursorReason.UNSUPPORTED_CURSOR);
            }
            if (referenceCursor.ownerToken != ownerToken) {
                return Optional.of(CursorReason.DIFFERENT_ENGINE);
            }
            if (referenceCursor.request != request) {
                return Optional.of(CursorReason.DIFFERENT_REQUEST);
            }
            if (referenceCursor.snapshotVersion != snapshotVersion) {
                return Optional.of(CursorReason.STALE_SNAPSHOT);
            }
            return Optional.empty();
        }

        void publish() {
            snapshotVersion = Math.incrementExact(snapshotVersion);
        }

        void failedPublication() {
            // A failed or cancelled operation publishes no snapshot.
        }
    }

    static final class ReferenceCursor {
        private final Object ownerToken;
        private final Object request;
        private final long snapshotVersion;
        private final long scoreBits;
        private final int documentId;

        private ReferenceCursor(
                Object ownerToken,
                Object request,
                long snapshotVersion,
                long scoreBits,
                int documentId
        ) {
            this.ownerToken = ownerToken;
            this.request = request;
            this.snapshotVersion = snapshotVersion;
            this.scoreBits = scoreBits;
            this.documentId = documentId;
        }

        Anchor anchor() {
            return new Anchor(Double.longBitsToDouble(scoreBits), documentId);
        }
    }
}
