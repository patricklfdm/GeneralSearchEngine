package io.github.patricklfdm.generalsearch.engine;

import java.nio.charset.StandardCharsets;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.equality.EqualityIndexDefinition;
import io.github.patricklfdm.generalsearch.index.prefix.PrefixIndexDefinition;
import io.github.patricklfdm.generalsearch.index.range.RangeIndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexDefinition;

record DurableIndexDescriptor(byte kind, String fieldName, String analyzerId) {
    static final byte EQUALITY = 1;
    static final byte RANGE = 2;
    static final byte PREFIX = 3;
    static final byte TEXT = 4;
    static final String SIMPLE_ANALYZER = "gse-simple-v1";

    DurableIndexDescriptor {
        if (kind < EQUALITY || kind > TEXT) {
            throw new IllegalArgumentException("unknown durable index kind");
        }
        Objects.requireNonNull(fieldName, "fieldName");
        Objects.requireNonNull(analyzerId, "analyzerId");
        int fieldBytes = fieldName.getBytes(StandardCharsets.UTF_8).length;
        if (fieldBytes == 0 || fieldBytes > 1024) {
            throw new IllegalArgumentException("index field name has invalid size");
        }
        if (kind == TEXT && !analyzerId.equals(SIMPLE_ANALYZER)) {
            throw new IllegalArgumentException("unknown durable text analyzer");
        }
        if (kind != TEXT && !analyzerId.isEmpty()) {
            throw new IllegalArgumentException("non-text index has an analyzer");
        }
    }

    static <T> DurableIndexDescriptor from(IndexDefinition<T> definition) {
        Objects.requireNonNull(definition, "definition");
        String fieldName = Objects.requireNonNull(
                definition.field(), "index field").name();
        if (definition instanceof EqualityIndexDefinition<?, ?>) {
            return new DurableIndexDescriptor(EQUALITY, fieldName, "");
        }
        if (definition instanceof RangeIndexDefinition<?, ?>) {
            return new DurableIndexDescriptor(RANGE, fieldName, "");
        }
        if (definition instanceof PrefixIndexDefinition<?>) {
            return new DurableIndexDescriptor(PREFIX, fieldName, "");
        }
        if (definition instanceof TextIndexDefinition<?> text
                && text.textField().analyzer() == SimpleAnalyzer.INSTANCE) {
            return new DurableIndexDescriptor(TEXT, fieldName, SIMPLE_ANALYZER);
        }
        throw new DurabilityException(
                DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                "durable mode supports only built-in indexes and the simple analyzer");
    }
}
