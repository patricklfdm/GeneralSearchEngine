package io.github.patricklfdm.generalsearch.admission;

import java.util.List;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;

/** Compiled separately against published V4.4 and the candidate. */
public final class PublicRuntimeWorkload {
    private PublicRuntimeWorkload() { }
    public static void apply(SearchEngine<Integer, Doc> engine) {
        engine.addAll(List.of(new Doc(12, "Java Twelve", "guide", 12, "java search"), new Doc(13, "Java Thirteen", "guide", 13, "java query search"))).join();
        engine.updateAll(List.of(new Doc(3, "Java Updated", "guide", 33, "java search search tuned"), new Doc(12, "Java Twelve", "guide", 15, "java search"))).join();
        engine.removeAll(List.of(7, 13)).join();
        engine.dropIndex("category").join(); engine.createIndex(IndexDefinition.equality(CATEGORY)).join();
    }
}
