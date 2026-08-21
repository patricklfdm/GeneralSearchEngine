package org.example.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;

final class ProductBenchmarkData {
    private static final int LOAD_BATCH_SIZE = 1_000;

    private ProductBenchmarkData() {}

    static void load(SnapshotUpdateEngine engine, int productCount) {
        List<CompletableFuture<Void>> pending = new ArrayList<>(LOAD_BATCH_SIZE);
        for (int slot = 0; slot < productCount; slot++) {
            pending.add(engine.add(product(slot, 0)));
            if (pending.size() == LOAD_BATCH_SIZE) {
                await(pending);
            }
        }
        await(pending);
    }

    static Product product(int slot, long revision) {
        long mixed = slot * 31L + revision * 17L;
        return new Product(
                "p" + slot,
                (revision % 3 == 0 ? "Product " : "Updated ") + slot,
                Category.values()[(int) Math.floorMod(
                        mixed, Category.values().length)],
                Math.floorMod(mixed * 13L, 100_000L) / 100.0,
                (mixed & 1) == 0,
                1.0 + Math.floorMod(mixed * 7L, 400L) / 100.0
        );
    }

    private static void await(List<CompletableFuture<Void>> pending) {
        CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
        pending.clear();
    }
}
