package org.example.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.schema.Field;
import org.example.generalsearch.schema.SearchSchema;
import org.junit.jupiter.api.Test;

class GenericSnapshotEngineDifferentialTest {
    private static final Field<InventoryItem, Long> ID =
            Field.of("id", Long.class, InventoryItem::id);
    private static final Field<InventoryItem, String> WAREHOUSE =
            Field.of("warehouse", String.class, InventoryItem::warehouse);
    private static final Field<InventoryItem, Integer> QUANTITY =
            Field.of("quantity", Integer.class, InventoryItem::quantity);
    private static final Field<InventoryItem, String> NAME =
            Field.of("name", String.class, InventoryItem::name);
    private static final SearchSchema<InventoryItem, Long> SCHEMA =
            SearchSchema.builder(InventoryItem.class, ID)
                    .field(WAREHOUSE)
                    .field(QUANTITY)
                    .field(NAME)
                    .build();

    @Test
    void longIdsAndNonProductDocumentsUseTheSameAsyncEngine() {
        Random random = new Random(93);
        InventoryItem[] oracle = new InventoryItem[300];
        try (SnapshotSearchEngine<Long, InventoryItem> engine =
                     new SnapshotSearchEngine<>(
                             new SnapshotEngineConfig(
                                     10_000, 500, Duration.ZERO),
                             SCHEMA,
                             List.of(
                                     IndexDefinition.equality(WAREHOUSE),
                                     IndexDefinition.range(QUANTITY)
                             ))) {
            SearchEngine<Long, InventoryItem> publicApi = engine;
            for (int slot = 0; slot < oracle.length; slot++) {
                InventoryItem item = randomItem(slot, random);
                oracle[slot] = item;
                publicApi.add(item).join();
                assertEquals(item, publicApi.get(item.id()));
            }

            for (int operation = 0; operation < 600; operation++) {
                int slot = random.nextInt(oracle.length);
                if (oracle[slot] == null) {
                    InventoryItem item = randomItem(slot, random);
                    oracle[slot] = item;
                    publicApi.add(item).join();
                } else if (random.nextInt(5) == 0) {
                    long id = idFor(slot);
                    oracle[slot] = null;
                    publicApi.remove(id).join();
                    assertNull(publicApi.get(id));
                } else {
                    InventoryItem item = randomItem(slot, random);
                    oracle[slot] = item;
                    publicApi.update(item).join();
                    assertEquals(item, publicApi.get(item.id()));
                }

                if (operation % 20 == 0) {
                    for (int queryNumber = 0; queryNumber < 12; queryNumber++) {
                        Query<InventoryItem> query = randomQuery(random);
                        assertEquals(
                                fullScan(oracle, query),
                                ids(publicApi.search(query))
                        );
                    }
                }
            }
        }
    }

    private static InventoryItem randomItem(int slot, Random random) {
        String warehouse = switch (random.nextInt(3)) {
            case 0 -> "north";
            case 1 -> "south";
            default -> "west";
        };
        String name = (random.nextBoolean() ? "Cable " : "Adapter ") + slot;
        return new InventoryItem(idFor(slot), name, warehouse, random.nextInt(500));
    }

    private static long idFor(int slot) {
        return 10_000L + slot;
    }

    private static Query<InventoryItem> randomQuery(Random random) {
        String warehouse = switch (random.nextInt(3)) {
            case 0 -> "north";
            case 1 -> "south";
            default -> "west";
        };
        return switch (random.nextInt(8)) {
            case 0 -> Query.eq(WAREHOUSE, warehouse);
            case 1 -> Query.between(QUANTITY, 50, 200);
            case 2 -> Query.prefix(NAME, "Cable");
            case 3 -> Query.and(
                    Query.eq(WAREHOUSE, warehouse),
                    Query.between(QUANTITY, 100, 400));
            case 4 -> Query.or(
                    Query.eq(WAREHOUSE, warehouse),
                    Query.between(QUANTITY, 0, 25));
            case 5 -> Query.not(Query.eq(WAREHOUSE, warehouse));
            case 6 -> Query.not(Query.prefix(NAME, "Adapter"));
            default -> Query.matchAll();
        };
    }

    private static Set<Long> fullScan(
            InventoryItem[] documents,
            Query<InventoryItem> query
    ) {
        Set<Long> result = new HashSet<>();
        for (InventoryItem document : documents) {
            if (document != null && query.matches(document)) {
                result.add(document.id());
            }
        }
        return result;
    }

    private static Set<Long> ids(List<InventoryItem> documents) {
        Set<Long> result = new HashSet<>();
        documents.forEach(document -> result.add(document.id()));
        return result;
    }

    private record InventoryItem(
            long id,
            String name,
            String warehouse,
            int quantity
    ) {}
}
