package io.github.patricklfdm.generalsearch.query;

public final class MatchAllQuery<T> implements Query<T> {
    @Override
    public boolean matches(T document) {
        return true;
    }
}
