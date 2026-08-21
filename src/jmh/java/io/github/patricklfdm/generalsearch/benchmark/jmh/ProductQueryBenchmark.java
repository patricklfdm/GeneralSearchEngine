package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.engine.SnapshotUpdateEngine;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
import io.github.patricklfdm.generalsearch.query.Query;
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

@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class ProductQueryBenchmark {
    @Param("10000")
    public int productCount;

    private SnapshotUpdateEngine engine;
    private Query<Product> categoryQuery;
    private Query<Product> priceQuery;
    private Query<Product> prefixQuery;
    private Query<Product> compositeQuery;
    private Query<Product> unindexedRatingQuery;

    @Setup(Level.Trial)
    public void setUp() {
        engine = new SnapshotUpdateEngine();
        ProductBenchmarkData.load(engine, productCount);
        categoryQuery = Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS);
        priceQuery = Query.between(ProductFields.PRICE, 250.0, 500.0);
        prefixQuery = Query.prefix(ProductFields.NAME, "Product 12");
        compositeQuery = Query.and(
                Query.eq(ProductFields.CATEGORY, Category.BOOKS),
                Query.eq(ProductFields.PRIME, true),
                Query.between(ProductFields.PRICE, 100.0, 700.0));
        unindexedRatingQuery =
                Query.between(ProductFields.RATING, 3.0, 4.5);
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public int equalityIndex() {
        return engine.search(categoryQuery).size();
    }

    @Benchmark
    public int rangeIndex() {
        return engine.search(priceQuery).size();
    }

    @Benchmark
    public int prefixIndex() {
        return engine.search(prefixQuery).size();
    }

    @Benchmark
    public int indexedComposite() {
        return engine.search(compositeQuery).size();
    }

    @Benchmark
    public int unindexedRangeScan() {
        return engine.search(unindexedRatingQuery).size();
    }
}
