package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import org.junit.jupiter.api.Test;

class V43DerivedStateOracleTest {
    private final V43DerivedStateOracle oracle = new V43DerivedStateOracle();

    @Test
    void modelsAllFourBuiltInKindsInCanonicalDescriptorOrder() {
        List<V43DerivedStateOracle.Component> components = oracle.build(documents(), List.of(
                descriptor(3, "body-text", V43DerivedStateOracle.Kind.TEXT, "body",
                        "gse-simple-v1"),
                descriptor(1, "price-range", V43DerivedStateOracle.Kind.RANGE, "price", ""),
                descriptor(0, "category-equality", V43DerivedStateOracle.Kind.EQUALITY,
                        "category", ""),
                descriptor(2, "title-prefix", V43DerivedStateOracle.Kind.PREFIX, "title", "")));

        assertEquals(List.of(
                V43DerivedStateOracle.Kind.EQUALITY,
                V43DerivedStateOracle.Kind.RANGE,
                V43DerivedStateOracle.Kind.PREFIX,
                V43DerivedStateOracle.Kind.TEXT),
                components.stream().map(value -> value.descriptor().kind()).toList());
        assertEquals(new V43DerivedStateOracle.ValueGroup(0, List.of(0L, 2L)),
                components.get(0).valueGroups().get("book"));
        assertEquals(List.of("10", "20", "30"),
                components.get(1).valueGroups().keySet().stream().toList());
        assertEquals(List.of(0L, 2L),
                components.get(2).prefixBitmaps().get("Alpha"));
        assertEquals(List.of(0, 2),
                components.get(3).postings().get("red").get(0).positions());
        assertEquals(4, components.get(3).fieldLengths().get(0L));
    }

    @Test
    void outputIsDeterministicAcrossInputOrder() {
        List<V43DerivedStateOracle.Descriptor> descriptors = descriptors();
        List<V43DerivedStateOracle.Component> first = oracle.build(documents(), descriptors);
        List<V43DerivedStateOracle.Component> second = oracle.build(
                List.of(documents().get(2), documents().get(0), documents().get(1)),
                descriptors);
        assertEquals(first, second);
        assertEquals(first.stream().map(V43DerivedStateOracle.Component::digest).toList(),
                second.stream().map(V43DerivedStateOracle.Component::digest).toList());
    }

    @Test
    void rejectsUnsupportedAnalyzerAndNonCanonicalRepresentatives() {
        assertThrows(IllegalArgumentException.class, () -> descriptor(
                0, "text", V43DerivedStateOracle.Kind.TEXT, "body", "custom"));
        assertThrows(IllegalArgumentException.class,
                () -> new V43DerivedStateOracle.ValueGroup(7, List.of(1L, 2L)));
        assertThrows(IllegalArgumentException.class,
                () -> new V43DerivedStateOracle.ValueGroup(2, List.of(2L, 1L)));
    }

    private static List<V43DerivedStateOracle.Document> documents() {
        return List.of(
                new V43DerivedStateOracle.Document(
                        0, "a", "book", 30, "Alpha", "Red blue red fox"),
                new V43DerivedStateOracle.Document(
                        1, "b", "game", 10, "Beta", "Blue fox"),
                new V43DerivedStateOracle.Document(
                        2, "c", "book", 20, "Alpha", "Green fox"));
    }

    private static List<V43DerivedStateOracle.Descriptor> descriptors() {
        return List.of(
                descriptor(0, "category-equality", V43DerivedStateOracle.Kind.EQUALITY,
                        "category", ""),
                descriptor(1, "price-range", V43DerivedStateOracle.Kind.RANGE, "price", ""),
                descriptor(2, "title-prefix", V43DerivedStateOracle.Kind.PREFIX, "title", ""),
                descriptor(3, "body-text", V43DerivedStateOracle.Kind.TEXT, "body",
                        "gse-simple-v1"));
    }

    private static V43DerivedStateOracle.Descriptor descriptor(
            int ordinal, String name, V43DerivedStateOracle.Kind kind,
            String field, String analyzer
    ) {
        return new V43DerivedStateOracle.Descriptor(
                ordinal, name, kind, field, analyzer);
    }
}
