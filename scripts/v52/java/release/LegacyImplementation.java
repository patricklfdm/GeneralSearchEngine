package fixture.v52;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.durability.DurabilityMetrics;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

/** Compiled ONLY against published 5.1; contains no V5.2 types or read override. */
public final class LegacyImplementation implements AutomaticReplicatedSearchEngine<Object, Object> {
    private AssertionError unexpected() { return new AssertionError("legacy implementation must not be called"); }
    public CompletableFuture<AutomaticReplicationStatus> start() { throw unexpected(); }
    public AutomaticReplicationStatus leadershipStatus() { throw unexpected(); }
    public long currentSequence() { throw unexpected(); }
    public CompletableFuture<Void> checkpoint() { throw unexpected(); }
    public DurabilityMetrics durabilityMetrics() { throw unexpected(); }
    public CompletableFuture<Void> add(Object document) { throw unexpected(); }
    public CompletableFuture<Void> update(Object document) { throw unexpected(); }
    public CompletableFuture<Void> remove(Object id) { throw unexpected(); }
    public CompletableFuture<Void> createIndex(IndexDefinition<Object> definition) { throw unexpected(); }
    public CompletableFuture<Void> dropIndex(String fieldName) { throw unexpected(); }
    public Object get(Object id) { throw unexpected(); }
    public List<Object> search(Query<Object> query) { throw unexpected(); }
    public SearchSchema<Object, Object> schema() { throw unexpected(); }
    public SearchEngineMetrics metrics() { throw unexpected(); }
    public void close() { throw unexpected(); }
}
