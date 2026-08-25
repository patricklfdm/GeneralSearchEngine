package io.github.patricklfdm.generalsearch.schema;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;

/** Canonical schema-owned pairing of a String field and its Analyzer semantics. */
public final class TextField<T> {
    private final Field<T, String> field;
    private final Analyzer analyzer;

    private TextField(Field<T, String> field, Analyzer analyzer) {
        this.field = Objects.requireNonNull(field, "field");
        this.analyzer = Objects.requireNonNull(analyzer, "analyzer");
    }

    public static <T> TextField<T> of(
            Field<T, String> field,
            Analyzer analyzer
    ) {
        return new TextField<>(field, analyzer);
    }

    public String name() {
        return field.name();
    }

    public Field<T, String> field() {
        return field;
    }

    public Analyzer analyzer() {
        return analyzer;
    }

    /** Analyzes the configured field value of one document. */
    public List<Token> analyzeDocument(T document) {
        return analyzer.analyze(field.valueOf(document));
    }
}
