package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;

class V51PublicApiInventoryTest {
    private static String fixture(String name) throws Exception {
        try (var in = V51PublicApiInventoryTest.class.getResourceAsStream("/compatibility/" + name)) {
            if (in == null) throw new IllegalStateException("missing " + name);
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
    private static Set<String> types(String name) throws Exception {
        var names = new TreeSet<String>();
        for (String line : fixture(name).lines().filter(v -> !v.isBlank() && !v.startsWith("#")).toList()) {
            names.add(line.split(" ", 2)[1]);
        }
        return names;
    }
    @Test void allPublicTypesAreExactlyPublishedTypesPlusReviewedAutomaticDeclarations() throws Exception {
        var expected = types("v50-replication-public-api-v2.txt");
        var additions = types("v51-automatic-public-api-v1.txt");
        assertEquals(10, additions.size());
        assertTrue(java.util.Collections.disjoint(expected, additions));
        expected.addAll(additions);
        assertEquals(expected, new V50PublicApiInventoryTest().compiledTopLevelTypes());
        assertEquals("gse-replication/1.1", ReplicatedSearchEngines.PROTOCOL);
        assertEquals("gse-replication/1.2", AutomaticReplicatedSearchEngines.PROTOCOL);
    }
    @Test void everyAdditiveDescriptorAndConstantMatchesReviewedFixture() throws Exception {
        assertEquals(fixture("v51-automatic-public-signatures-v1.txt"), signatures());
    }
    private static String signatures() throws Exception {
        var lines = new TreeSet<String>();var helper = new V50PublicApiInventoryTest();
        for (String name : types("v51-automatic-public-api-v1.txt")) helper.collectSignatures(Class.forName(name), lines);
        return String.join("\n", lines) + "\n";
    }
    /** Explicit generation for review only; test execution never updates fixtures. */
    public static void main(String[] args) throws Exception { System.out.print(signatures()); }
}
