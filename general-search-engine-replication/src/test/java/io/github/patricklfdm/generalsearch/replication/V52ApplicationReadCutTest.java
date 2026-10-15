package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V52ApplicationReadCutTest {
    @TempDir Path root;

    @Test void acceptedProvenAndReconstructedBytesNeverBecomeAPublishedRead() throws Exception {
        try (var fixture = new V51RuntimeFixture(root, true, false);
             var store = AutomaticStore.open(root.resolve("node-1"), fixture.manifest, "node-1", BOUNDS, AutomaticStore.Faults.NONE);
             var app = new AutomaticApplication<>(SearchEngine.builder(SCHEMA).indexes(INDEXES).configuration(), fixture.materialization(1), BOUNDS)) {
            var manifest = decode(fixture.manifest, "MANIFEST");
            assertThrows(AutomaticReplicationException.class, app::readCut);
            app.validate(manifest, fixture.materialization(1));
            var genesis = app.readCut();
            assertEquals(0, genesis.index()); assertEquals(0, genesis.sequence());
            assertEquals(manifest.digest(), genesis.token().manifestDigest());
            assertEquals(UUID.fromString(text(manifest.value(), "historyId")), genesis.token().historyId());
            assertNotEquals(sha(fixture.manifest), genesis.token().manifestDigest());
            var payload = app.encoder().documents("ADD", List.of(new Document(1, "visible-only-after-publication")));
            byte[] entry = V51StorageFixture.entry(fixture.manifest, 1, null, 1, payload);
            store.promise(V51StorageFixture.promise(fixture.manifest, 2));
            app.stage(1, payload);
            store.accept(V51StorageFixture.accept(fixture.manifest, entry, 2));
            assertNull(app.readCut(genesis, v -> v.get(1)));
            store.prove(V51StorageFixture.proof(fixture.manifest, entry, 2));
            assertEquals(genesis, app.readCut());
            byte[] image = app.reconstruct(store.replay());
            assertNull(app.readCut(genesis, v -> v.get(1)), "reconstructed private image must remain invisible");
            app.publish(store.provenSnapshot(image));
            var first = app.readCut();
            assertEquals(1, first.index()); assertEquals(1, first.sequence());
            assertTrue(first.generation() > genesis.generation());
            assertEquals("visible-only-after-publication", app.readCut(first, v -> {
                assertEquals(first.sequence(), v.currentSequence());
                assertEquals(List.of(v.get(1)), v.search(d -> true));
                return v.get(1).value();
            }));
            assertThrows(AutomaticReplicationException.class, () -> app.readCut(genesis, v -> v.get(1)));

            byte[] noop = V51StorageFixture.entry(fixture.manifest, 2, entry, 9, new byte[0]);
            store.accept(V51StorageFixture.accept(fixture.manifest, noop, 2));
            store.prove(V51StorageFixture.proof(fixture.manifest, noop, 2));
            app.publish(store.provenSnapshot(app.reconstruct(store.replay())));
            var second = app.readCut();
            assertEquals(2, second.index()); assertEquals(first.sequence(), second.sequence());
            assertEquals(first.generation(), second.generation(), "NO_OP preserves the materialization and cursors");
            assertThrows(AutomaticReplicationException.class, () -> app.readCut(first, v -> v.get(1)));
        }
    }

    @Test void everyMethodRejectsEscapedAndForeignThreadUseBeforeQueryValidation() throws Exception {
        try (var fixture = new V51RuntimeFixture(root, true, false);
             var app = new AutomaticApplication<>(SearchEngine.builder(SCHEMA).indexes(INDEXES).configuration(), fixture.materialization(1), BOUNDS)) {
            app.validate(decode(fixture.manifest, "MANIFEST"), fixture.materialization(1));
            var escaped = app.readCut(app.readCut(), view -> {
                assertEquals(0, view.currentSequence());
                try (var executor = Executors.newSingleThreadExecutor()) {
                    executor.submit(() -> assertInactive(view)).get(5, TimeUnit.SECONDS);
                } catch (Exception e) { throw new AssertionError(e); }
                assertNull(view.get(42)); // foreign-thread attempt cannot invalidate the owner's live view
                return view;
            });
            assertInactive(escaped);
        }
    }

    @Test void callbackThrowableSurvivesAndAllExitPathsReleaseTheView() throws Exception {
        try (var fixture = new V51RuntimeFixture(root, true, false);
             var app = new AutomaticApplication<>(SearchEngine.builder(SCHEMA).indexes(INDEXES).configuration(), fixture.materialization(1), BOUNDS)) {
            app.validate(decode(fixture.manifest, "MANIFEST"), fixture.materialization(1));
            var escaped = new AtomicReference<ReplicaReadView<Integer,Document>>();
            var failure = new AssertionError("business callback");
            assertSame(failure, assertThrows(AssertionError.class, () -> app.readCut(app.readCut(), view -> {
                escaped.set(view); throw failure;
            })));
            assertInactive(escaped.get());
            assertNull(app.readCut(app.readCut(), view -> null));
            var queryFailure = new IllegalArgumentException("query predicate");
            assertSame(queryFailure, assertThrows(IllegalArgumentException.class, () -> app.readCut(app.readCut(), view -> {
                throw queryFailure;
            })));
        }
    }

    @Test void minimumCompatibilityBindsAllIdentityFieldsWithoutNarrowingTheIndex() {
        var cut = new AutomaticReadCut(new ReplicationGroupId(UUID.randomUUID()), UUID.randomUUID(), "ab".repeat(32), 3, 9, 1);
        assertDoesNotThrow(() -> cut.compatible(new ReplicaReadToken(1, cut.group(), cut.history(), cut.manifest(), Long.MAX_VALUE)));
        for (var other : List.of(
                new ReplicaReadToken(1, new ReplicationGroupId(UUID.randomUUID()), cut.history(), cut.manifest(), 0),
                new ReplicaReadToken(1, cut.group(), UUID.randomUUID(), cut.manifest(), 0),
                new ReplicaReadToken(1, cut.group(), cut.history(), "cd".repeat(32), 0)))
            assertEquals(ReplicaReadException.Reason.INCOMPATIBLE_HISTORY,
                    assertThrows(ReplicaReadException.class, () -> cut.compatible(other)).reason());
    }

    private static void assertInactive(ReplicaReadView<Integer,Document> view) {
        for (Runnable call : List.<Runnable>of(() -> view.get(null), () -> view.search((Query<Document>) null),
                () -> view.searchTopK((RankedSearchRequest<Document>) null), () -> view.search((SearchRequest<Document>) null),
                () -> view.search((HighlightedSearchRequest<Document>) null), () -> view.explain(null, null), view::currentSequence))
            assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE, assertThrows(ReplicaReadException.class, call::run).reason());
    }
}
