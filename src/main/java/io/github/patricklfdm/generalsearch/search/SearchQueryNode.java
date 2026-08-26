package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Package-private immutable representation retained for later planning. */
sealed interface SearchQueryNode<T>
        permits LeafSearchQueryNode, BoolSearchQueryNode, BoostSearchQueryNode {
}

enum SearchLeafKind {
    TEXT,
    PHRASE,
    FUZZY
}

record LeafSearchQueryNode<T>(SearchLeafKind kind, TextField<T> field, String text)
        implements SearchQueryNode<T> {
}

record BoolSearchQueryNode<T>(List<SearchQuery<T>> must, List<SearchQuery<T>> should)
        implements SearchQueryNode<T> {
    BoolSearchQueryNode {
        must = List.copyOf(must);
        should = List.copyOf(should);
    }
}

record BoostSearchQueryNode<T>(SearchQuery<T> query, double multiplier)
        implements SearchQueryNode<T> {
}
