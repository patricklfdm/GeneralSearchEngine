package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/** Builds one public explanation from an already prepared snapshot-bound plan. */
final class ExplainExecutor<T> {
    SearchExplanation<T> explain(
            SearchPlan<T> plan,
            int docId,
            T document
    ) {
        Objects.requireNonNull(plan, "plan");
        Objects.requireNonNull(document, "document");
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }

        ExplanationNode rankedDetail = plan.root().explain(docId);
        ExplanationNode ranked = new ExplanationNode(
                rankedDetail.matched(),
                rankedDetail.score(),
                "ranked query",
                List.of(rankedDetail)
        );
        List<ExplanationNode> children = new ArrayList<>(2);
        children.add(ranked);

        boolean filterMatched = true;
        if (plan.filter() != null) {
            filterMatched = plan.filter().matches(document);
            children.add(new ExplanationNode(
                    filterMatched,
                    0.0,
                    "structured filter "
                            + (filterMatched ? "matched" : "did not match"),
                    List.of()
            ));
        }

        boolean matched = ranked.matched() && filterMatched;
        double score = matched ? ranked.score() : 0.0;
        ExplanationNode root = new ExplanationNode(
                matched,
                score,
                "SEARCH REQUEST",
                children
        );
        return new SearchExplanation<>(document, matched, score, root);
    }
}
