package io.github.patricklfdm.generalsearch.ranking;

import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.query.Query;

/** Immutable ranked request separating scoring text from optional boolean eligibility. */
public final class RankedSearchRequest<T> {
    private final TextScoringQuery<T> scoringQuery;
    private final Query<T> filter;
    private final int limit;
    private final Bm25Config config;

    private RankedSearchRequest(
            TextScoringQuery<T> scoringQuery,
            Query<T> filter,
            int limit,
            Bm25Config config
    ) {
        this.scoringQuery = Objects.requireNonNull(scoringQuery, "scoringQuery");
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
        this.filter = filter;
        this.limit = limit;
        this.config = Objects.requireNonNull(config, "config");
    }

    /** Creates an unfiltered request using {@link Bm25Config#DEFAULT}. */
    public static <T> RankedSearchRequest<T> of(
            TextScoringQuery<T> scoringQuery,
            int limit
    ) {
        return new RankedSearchRequest<>(scoringQuery, null, limit, Bm25Config.DEFAULT);
    }

    /** Creates an unfiltered request with explicit scoring configuration. */
    public static <T> RankedSearchRequest<T> of(
            TextScoringQuery<T> scoringQuery,
            int limit,
            Bm25Config config
    ) {
        return new RankedSearchRequest<>(scoringQuery, null, limit, config);
    }

    /** Creates a filtered request using {@link Bm25Config#DEFAULT}. */
    public static <T> RankedSearchRequest<T> filtered(
            TextScoringQuery<T> scoringQuery,
            Query<T> filter,
            int limit
    ) {
        return new RankedSearchRequest<>(
                scoringQuery,
                Objects.requireNonNull(filter, "filter"),
                limit,
                Bm25Config.DEFAULT
        );
    }

    /** Creates a filtered request with explicit scoring configuration. */
    public static <T> RankedSearchRequest<T> filtered(
            TextScoringQuery<T> scoringQuery,
            Query<T> filter,
            int limit,
            Bm25Config config
    ) {
        return new RankedSearchRequest<>(
                scoringQuery,
                Objects.requireNonNull(filter, "filter"),
                limit,
                config
        );
    }

    public TextScoringQuery<T> scoringQuery() {
        return scoringQuery;
    }

    public Optional<Query<T>> filter() {
        return Optional.ofNullable(filter);
    }

    public int limit() {
        return limit;
    }

    public Bm25Config config() {
        return config;
    }
}
