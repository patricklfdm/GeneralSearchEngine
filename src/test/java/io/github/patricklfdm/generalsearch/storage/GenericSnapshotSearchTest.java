package io.github.patricklfdm.generalsearch.storage;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.SnapshotSearcher;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;

class GenericSnapshotSearchTest {
    private static final Field<InventoryItem, String> WAREHOUSE =
            Field.of("warehouse", String.class, InventoryItem::warehouse);
    private static final Field<InventoryItem, Integer> QUANTITY =
            Field.of("quantity", Integer.class, InventoryItem::quantity);
    private static final Field<InventoryItem, String> NAME =
            Field.of("name", String.class, InventoryItem::name);

    @Test
    void nonProductDocumentsUseTheGenericStorageIndexAndQueryChain() {
        Random random = new Random(87);
        InventoryItem[] oracle = new InventoryItem[300];
        SearchSnapshot<InventoryItem> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.equality(WAREHOUSE),
                IndexDefinition.range(QUANTITY),
                IndexDefinition.prefix(NAME)
        ));
        SnapshotSearcher<InventoryItem> searcher = new SnapshotSearcher<>();

        for (int docId = 0; docId < oracle.length; docId++) {
            InventoryItem item = randomItem(docId, random);
            oracle[docId] = item;
            snapshot = snapshot.add(docId, item);
        }

        for (int operation = 0; operation < 600; operation++) {
            int docId = random.nextInt(oracle.length);
            if (oracle[docId] == null) {
                InventoryItem item = randomItem(docId, random);
                oracle[docId] = item;
                snapshot = snapshot.add(docId, item);
            } else if (random.nextInt(5) == 0) {
                oracle[docId] = null;
                snapshot = snapshot.remove(docId);
            } else {
                InventoryItem item = randomItem(docId, random);
                oracle[docId] = item;
                snapshot = snapshot.update(docId, item);
            }

            if (operation % 20 == 0) {
                for (int queryNumber = 0; queryNumber < 12; queryNumber++) {
                    Query<InventoryItem> query = randomQuery(random);
                    assertEquals(fullScan(oracle, query), skus(searcher.search(snapshot, query)));
                }
            }
        }
    }

    private static InventoryItem randomItem(int docId, Random random) {
        String warehouse = switch (random.nextInt(3)) {
            case 0 -> "north";
            case 1 -> "south";
            default -> "west";
        };
        String name = (random.nextBoolean() ? "Cable " : "Adapter ") + docId;
        return new InventoryItem("sku-" + docId, name, warehouse, random.nextInt(500));
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

    private static Set<String> fullScan(
            InventoryItem[] documents,
            Query<InventoryItem> query
    ) {
        Set<String> result = new HashSet<>();
        for (InventoryItem document : documents) {
            if (document != null && query.matches(document)) {
                result.add(document.sku());
            }
        }
        return result;
    }

    private static Set<String> skus(List<InventoryItem> documents) {
        Set<String> result = new HashSet<>();
        documents.forEach(document -> result.add(document.sku()));
        return result;
    }

    private record InventoryItem(
            String sku,
            String name,
            String warehouse,
            int quantity
    ) {}
}
