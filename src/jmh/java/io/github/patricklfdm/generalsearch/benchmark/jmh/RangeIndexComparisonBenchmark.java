package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
import io.github.patricklfdm.generalsearch.model.ProductIndexDefinitions;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.query.RangePlanningMode;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Warmup;

/**
 * Compares indexed and scanned execution for the same field, bounds, and result set.
 */
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class RangeIndexComparisonBenchmark {
    @Param("100000")
    public int productCount;

    @Param({"0.01", "0.1", "1.0", "10.0", "25.0", "50.0", "100.0"})
    public double selectivityPercent;

    private SearchEngine<String, Product> costAwareEngine;
    private SearchEngine<String, Product> forcedIndexEngine;
    private SearchEngine<String, Product> forcedScanEngine;
    private IndexSnapshot<Product> priceIndex;
    private Query<Product> priceQuery;

    @Setup(Level.Trial)
    public void setUp() {
        if (productCount <= 0 || productCount > 100_000) {
            throw new IllegalArgumentException(
                    "productCount must be between 1 and 100000");
        }
        if (selectivityPercent <= 0.0 || selectivityPercent > 100.0) {
            throw new IllegalArgumentException(
                    "selectivityPercent must be in (0, 100]");
        }

        List<Product> products = new ArrayList<>(productCount);
        for (int slot = 0; slot < productCount; slot++) {
            products.add(ProductBenchmarkData.product(slot, 0));
        }

        List<Double> sortedPrices = products.stream()
                .map(Product::price)
                .sorted(Comparator.naturalOrder())
                .toList();
        int expectedMatches = Math.max(
                1,
                (int) Math.round(productCount * selectivityPercent / 100.0));
        double maximumPrice = sortedPrices.get(expectedMatches - 1);
        priceQuery = Query.between(ProductFields.PRICE, 0.0, maximumPrice);

        costAwareEngine = engine(RangePlanningMode.COST_AWARE);
        forcedIndexEngine = engine(RangePlanningMode.FORCE_INDEX);
        forcedScanEngine = engine(RangePlanningMode.FORCE_SCAN);
        load(costAwareEngine, products);
        load(forcedIndexEngine, products);
        load(forcedScanEngine, products);

        IndexBuilder<Product> priceIndexBuilder =
                IndexDefinition.range(ProductFields.PRICE)
                        .createEmpty()
                        .toBuilder();
        for (int docId = 0; docId < products.size(); docId++) {
            priceIndexBuilder.add(docId, products.get(docId));
        }
        priceIndex = priceIndexBuilder.build();

        int costAwareMatches = costAwareEngine.search(priceQuery).size();
        int indexedMatches = forcedIndexEngine.search(priceQuery).size();
        int scannedMatches = forcedScanEngine.search(priceQuery).size();
        int candidateMatches = priceIndex.candidates(priceQuery)
                .orElseThrow()
                .bitmap()
                .cardinality();
        if (costAwareMatches != expectedMatches
                || indexedMatches != expectedMatches
                || scannedMatches != expectedMatches
                || candidateMatches != expectedMatches) {
            throw new IllegalStateException(
                    "range comparison produced unequal result counts: expected="
                            + expectedMatches
                            + ", costAware=" + costAwareMatches
                            + ", indexed=" + indexedMatches
                            + ", scanned=" + scannedMatches
                            + ", candidates=" + candidateMatches);
        }
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        if (costAwareEngine != null) {
            costAwareEngine.close();
        }
        if (forcedIndexEngine != null) {
            forcedIndexEngine.close();
        }
        if (forcedScanEngine != null) {
            forcedScanEngine.close();
        }
    }

    @Benchmark
    public int costAwarePriceRange() {
        return costAwareEngine.search(priceQuery).size();
    }

    @Benchmark
    public int forcedIndexPriceRange() {
        return forcedIndexEngine.search(priceQuery).size();
    }

    @Benchmark
    public int forcedScanPriceRange() {
        return forcedScanEngine.search(priceQuery).size();
    }

    @Benchmark
    public int rangeCandidateOnly() {
        return priceIndex.candidates(priceQuery)
                .orElseThrow()
                .bitmap()
                .cardinality();
    }

    private static SearchEngine<String, Product> engine(RangePlanningMode mode) {
        return SearchEngine.builder(ProductFields.SCHEMA)
                .indexes(ProductIndexDefinitions.defaults())
                .plannerConfig(new PlannerConfig(mode))
                .build();
    }

    private static void load(
            SearchEngine<String, Product> engine,
            List<Product> products
    ) {
        List<CompletableFuture<Void>> pending = new ArrayList<>(1_000);
        for (Product product : products) {
            pending.add(engine.add(product));
            if (pending.size() == 1_000) {
                await(pending);
            }
        }
        await(pending);
    }

    private static void await(List<CompletableFuture<Void>> pending) {
        CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
        pending.clear();
    }
}
