package io.github.patricklfdm.generalsearch.index.text;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class PersistentCodePointTrieTest {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void changesMembershipOnlyAtEmptyNonEmptyPostingTransitions() {
        TextIndexSnapshot<Document> initial = indexOf(
                new Document("alpha"),
                new Document("beta")
        );
        assertEquals(2, initial.fuzzyDictionary().size());

        TextIndexBuilder<Document> postingUpdate = builder(initial);
        postingUpdate.update(
                0,
                new Document("alpha"),
                new Document("alpha alpha")
        );
        TextIndexSnapshot<Document> updatedPosting = build(postingUpdate);
        assertNotSame(initial, updatedPosting);
        assertSame(initial.fuzzyDictionary(), updatedPosting.fuzzyDictionary());

        TextIndexBuilder<Document> insertion = builder(updatedPosting);
        insertion.add(2, new Document("gamma"));
        TextIndexSnapshot<Document> withGamma = build(insertion);
        assertEquals(3, withGamma.fuzzyDictionary().size());
        assertSame(
                updatedPosting.fuzzyDictionary().nodeForPrefix("alpha"),
                withGamma.fuzzyDictionary().nodeForPrefix("alpha")
        );

        TextIndexBuilder<Document> removal = builder(withGamma);
        removal.remove(1, new Document("beta"));
        TextIndexSnapshot<Document> withoutBeta = build(removal);
        assertEquals(2, withoutBeta.fuzzyDictionary().size());
        assertSame(
                withGamma.fuzzyDictionary().nodeForPrefix("gamma"),
                withoutBeta.fuzzyDictionary().nodeForPrefix("gamma")
        );
    }

    @Test
    void removeThenReaddInOnePublicationKeepsDictionaryMembership() {
        TextIndexSnapshot<Document> initial = indexOf(new Document("alpha"));
        TextIndexBuilder<Document> builder = builder(initial);

        builder.remove(0, new Document("alpha"));
        builder.add(0, new Document("alpha"));

        TextIndexSnapshot<Document> rebuilt = build(builder);
        assertSame(initial.fuzzyDictionary(), rebuilt.fuzzyDictionary());
        assertEquals(1, rebuilt.posting("alpha").documentFrequency());
    }

    @SafeVarargs
    private static TextIndexSnapshot<Document> indexOf(Document... documents) {
        TextIndexSnapshot<Document> empty = TextIndexSnapshot.empty(TEXT);
        TextIndexBuilder<Document> builder = builder(empty);
        for (int docId = 0; docId < documents.length; docId++) {
            builder.add(docId, documents[docId]);
        }
        return build(builder);
    }

    private static TextIndexBuilder<Document> builder(
            TextIndexSnapshot<Document> snapshot
    ) {
        IndexBuilder<Document> builder = snapshot.toBuilder();
        return (TextIndexBuilder<Document>) builder;
    }

    private static TextIndexSnapshot<Document> build(
            TextIndexBuilder<Document> builder
    ) {
        return (TextIndexSnapshot<Document>) builder.build();
    }

    private record Document(String body) {
    }
}
