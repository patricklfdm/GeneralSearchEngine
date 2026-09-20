package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51AutomaticStoreTest {
    @TempDir Path root;
    byte[] manifest;
    Path node;
    @BeforeEach void initialize() throws Exception { manifest = setup(root); node = root.resolve("node-1"); }
    AutomaticStore open() { return AutomaticStore.open(node, manifest, "node-1", ReplicationBounds.defaults(), AutomaticStore.Faults.NONE); }

    @Test void forcePrecedesReceiptsAndExactRetriesDoNotAppend() throws Exception {
        var events = new ArrayList<String>();
        byte[] entry = entry(manifest, 1, null, 9, new byte[0]); byte[] accept = accept(manifest, entry, 2), proof = proof(manifest, entry, 2);
        try (var store = AutomaticStore.open(node, manifest, "node-1", ReplicationBounds.defaults(), new AutomaticStore.Faults() {
            @Override public void at(String cut) { events.add(cut); }
        })) {
            store.promise(promise(manifest, 2)); String accepted = store.accept(accept); events.add("ACCEPT_ACK");
            String proven = store.prove(proof); events.add("PROOF_ACK");
            assertEquals(receipt("ACCEPT_ACK", digest(manifest), "node-1", decode(accept, "ACCEPT").value(), 1, digest(entry)), accepted);
            assertEquals(receipt("PROOF_ACK", digest(manifest), "node-1", decode(proof, "PROOF").value(), 1, sha(proof)), proven);
            var before = inventory(); store.promise(promise(manifest, 2)); store.accept(accept); store.prove(proof);
            assertEquals(before, inventory());
            for (String kind : List.of("ACCEPT", "PROOF")) assertTrue(events.indexOf(kind + "_AFTER_FORCE") < events.indexOf(kind + "_ACK"));
            assertEquals(1, store.status().get("provenThrough")); assertEquals(0L, store.status().get("applicationSequence"));
        }
        try (var reopened = open()) { assertEquals(1, reopened.status().get("provenThrough")); assertArrayEquals(entry, reopened.acceptedEntry(1)); }
    }
    @Test void retainedHigherPromiseCarriesImmutableOriginAndRejectsConflictingTail() {
        byte[] first = entry(manifest, 1, null, 1, new byte[]{7});
        try (var store = open()) { store.promise(promise(manifest, 2)); store.accept(accept(manifest, first, 2)); store.promise(promise(manifest, 5)); }
        try (var store = open()) {
            assertEquals(5L, store.status().get("promisedEpoch"));
            assertThrows(AutomaticReplicationException.class, () -> store.accept(accept(manifest, first, 2)));
            byte[] conflict = entry(manifest, 1, null, 1, new byte[]{8});
            assertThrows(AutomaticReplicationException.class, () -> store.accept(accept(manifest, conflict, 5)));
            store.accept(accept(manifest, first, 5)); store.prove(proof(manifest, first, 5));
            assertArrayEquals(first, store.acceptedEntry(1)); assertEquals(1L, store.status().get("applicationSequence"));
        }
        try (var store = open()) { assertEquals(1L, store.status().get("applicationSequence")); }
    }
    @Test void enforcesOneUnresolvedSlotAndContiguousProofs() {
        byte[] first = entry(manifest, 1, null, 1, new byte[]{1}), second = entry(manifest, 2, first, 9, new byte[0]);
        try (var store = open()) {
            assertThrows(AutomaticReplicationException.class, () -> store.accept(accept(manifest, first, 2)));
            store.promise(promise(manifest, 2)); store.accept(accept(manifest, first, 2));
            assertThrows(AutomaticReplicationException.class, () -> store.accept(accept(manifest, second, 2)));
            assertThrows(AutomaticReplicationException.class, () -> store.prove(proof(manifest, second, 2)));
            store.prove(proof(manifest, first, 2)); store.accept(accept(manifest, second, 2)); store.prove(proof(manifest, second, 2));
            assertEquals(2, store.status().get("provenThrough")); assertEquals(1L, store.status().get("applicationSequence"));
        }
    }
    @Test void rejectsDuplicateBallotWithDifferentIncarnationAndWrongRank() throws Exception {
        try (var store = open()) {
            store.promise(promise(manifest, 2)); var changed = copy(decode(promise(manifest, 2), "PROMISE").value());
            changed.put("incarnation", "22222222-2222-2222-2222-222222222222"); var before = inventory();
            assertThrows(AutomaticReplicationException.class, () -> store.promise(encode("PROMISE", changed)));
            changed.put("epoch", 5L); changed.put("proposer", "node-3");
            assertThrows(AutomaticReplicationException.class, () -> store.promise(encode("PROMISE", changed))); assertEquals(before, inventory());
        }
    }
    @Test void exclusiveLockAndCloseAreIdempotent() {
        var first = open(); assertThrows(AutomaticReplicationException.class, this::open); first.close(); first.close();
        assertThrows(AutomaticReplicationException.class, first::status);
        try (var next = open()) { assertEquals(1L, next.status().get("promisedEpoch")); }
    }
    @Test void missingAuthorityNeverCreatesOrRepairsFiles() throws Exception {
        for (String file : AutomaticAdmission.ROOT_FILES) {
            byte[] original = Files.readAllBytes(node.resolve(file)); Files.delete(node.resolve(file)); var before = inventory();
            assertThrows(AutomaticReplicationException.class, this::open, file); assertEquals(before, inventory()); Files.write(node.resolve(file), original);
        }
        Path absent = root.resolve("missing");
        assertThrows(AutomaticReplicationException.class, () -> AutomaticStore.open(absent, manifest, "node-1", ReplicationBounds.defaults(), AutomaticStore.Faults.NONE));
        assertFalse(Files.exists(absent));
    }
    @Test void partialPromiseAcceptanceAndProofStayQuarantinedOnReopen() throws Exception {
        byte[] first = entry(manifest, 1, null, 1, new byte[]{1});
        try (var store = open()) { store.promise(promise(manifest, 2)); store.accept(accept(manifest, first, 2)); store.prove(proof(manifest, first, 2)); }
        for (String name : List.of("promises.gsr", "accepted.gsr", "proofs.gsr")) {
            byte[] original = Files.readAllBytes(node.resolve(name)); Files.write(node.resolve(name), Arrays.copyOf(original, original.length - 1));
            var before = inventory(); assertThrows(AutomaticReplicationException.class, this::open, name); assertEquals(before, inventory());
            Files.write(node.resolve(name), original);
        }
        try (var store = open()) { assertEquals(1, store.status().get("provenThrough")); }
    }
    @Test void copyingSealedDirectoryCannotEnrollAnotherPath() throws Exception {
        Path clone = root.resolve("copied"); Files.createDirectory(clone);
        for (String file : AutomaticAdmission.ROOT_FILES) Files.copy(node.resolve(file), clone.resolve(file));
        assertThrows(AutomaticReplicationException.class, () -> AutomaticStore.open(clone, manifest, "node-1", ReplicationBounds.defaults(), AutomaticStore.Faults.NONE));
        try (var store = open()) { assertEquals("node-1", store.status().get("node")); }
    }
    @Test void unknownFilesAndLinksRejectWithoutMutation() throws Exception {
        Files.writeString(node.resolve("foreign"), "keep"); var before = inventory();
        assertThrows(AutomaticReplicationException.class, this::open); assertEquals(before, inventory()); Files.delete(node.resolve("foreign"));
        Path data = root.resolve("saved-manifest"); Files.move(node.resolve("manifest.gsr"), data); Files.createSymbolicLink(node.resolve("manifest.gsr"), data);
        assertThrows(AutomaticReplicationException.class, this::open); assertArrayEquals(manifest, Files.readAllBytes(data));
    }
    @Test void rejectedCapacityLeavesAuthorityUsableAndRetriesFitWithoutAdditionalBytes() throws Exception {
        long initial = 0; for (String file : AutomaticAdmission.ROOT_FILES) initial += Files.size(node.resolve(file));
        byte[] grant = promise(manifest, 2); var d = ReplicationBounds.defaults();
        var bounds = new ReplicationBounds(d.maxFrameBytes(), d.maxEntriesPerAppend(), d.maxInFlightPerPeer(), d.maxPendingClientOperations(),
                d.maxRetryAttempts(), d.requestTimeoutMillis(), d.retryBackoffMillis(), d.snapshotChunkBytes(), initial + grant.length, d.maxSnapshotStagingBytes());
        try (var store = AutomaticStore.open(node, manifest, "node-1", bounds, AutomaticStore.Faults.NONE)) {
            store.promise(grant); store.promise(grant); var before = inventory();
            var error = assertThrows(AutomaticReplicationException.class, () -> store.promise(promise(manifest, 5)));
            assertEquals(AutomaticReplicationException.Reason.CAPACITY_EXCEEDED, error.reason()); assertEquals(before, inventory());
            assertEquals(2L, store.status().get("promisedEpoch"));
        }
    }
    @Test void openingCannotExpandSealedByteLimits() throws Exception {
        var d = ReplicationBounds.defaults(); var before = inventory();
        var expanded = new ReplicationBounds(d.maxFrameBytes(), d.maxEntriesPerAppend(), d.maxInFlightPerPeer(), d.maxPendingClientOperations(),
                d.maxRetryAttempts(), d.requestTimeoutMillis(), d.retryBackoffMillis(), d.snapshotChunkBytes(), d.maxRetainedLogBytes() + 1, d.maxSnapshotStagingBytes());
        assertThrows(AutomaticReplicationException.class, () -> AutomaticStore.open(node, manifest, "node-1", expanded, AutomaticStore.Faults.NONE));
        assertEquals(before, inventory());
    }
    @Test void promiseHistoryExhaustionAllowsExactRetryButNeverResetsAuthority() throws Exception {
        var bytes = new java.io.ByteArrayOutputStream(); bytes.write(Files.readAllBytes(node.resolve("promises.gsr")));
        for (int i = 0; i < 9999; i++) bytes.write(promise(manifest, 2L + 3L * i));
        Files.write(node.resolve("promises.gsr"), bytes.toByteArray());
        try (var store = open()) {
            assertEquals(10000, store.status().get("promiseCount")); var before = inventory();
            store.promise(promise(manifest, 29996));
            var error = assertThrows(AutomaticReplicationException.class, () -> store.promise(promise(manifest, 29999)));
            assertEquals(AutomaticReplicationException.Reason.CAPACITY_EXCEEDED, error.reason());
            assertEquals(before, inventory()); assertEquals(29996L, store.status().get("promisedEpoch"));
        }
        Files.write(node.resolve("promises.gsr"), promise(manifest, 29999), StandardOpenOption.APPEND);
        var before = inventory(); assertThrows(AutomaticReplicationException.class, this::open); assertEquals(before, inventory());
    }
    @Test void maximumEpochRemainsExactAcrossRestart() {
        try (var store = open()) { store.promise(promise(manifest, Long.MAX_VALUE)); }
        try (var store = open()) {
            assertEquals(Long.MAX_VALUE, store.status().get("promisedEpoch"));
            assertThrows(AutomaticReplicationException.class, () -> store.promise(promise(manifest, 2)));
        }
    }
    @Test void ambiguousWriteOrForceFailureStopsAllFurtherAuthorityUse() throws Exception {
        for (String cut : List.of("PROMISE_BEFORE_WRITE", "PROMISE_WRITE_CHUNK", "PROMISE_AFTER_WRITE", "PROMISE_AFTER_FORCE", "PROMISE_BEFORE_ACK")) {
            byte[] original = Files.readAllBytes(node.resolve("promises.gsr"));
            try (var store = AutomaticStore.open(node, manifest, "node-1", ReplicationBounds.defaults(), new AutomaticStore.Faults() {
                @Override public void at(String stage) throws IOException { if (stage.equals(cut)) throw new IOException("injected " + stage); }
                @Override public int maximumWriteBytes() { return 7; }
            })) {
                assertThrows(AutomaticReplicationException.class, () -> store.promise(promise(manifest, 2)));
                assertThrows(AutomaticReplicationException.class, store::status);
                assertThrows(AutomaticReplicationException.class, () -> store.promise(promise(manifest, 5)));
            }
            if (cut.equals("PROMISE_WRITE_CHUNK")) assertThrows(AutomaticReplicationException.class, this::open);
            else try (var store = open()) { assertEquals(cut.equals("PROMISE_BEFORE_WRITE") ? 1L : 2L, store.status().get("promisedEpoch")); }
            Files.write(node.resolve("promises.gsr"), original);
        }
    }
    @Test void recomputedValidRecordsCannotForgeAReplayedPrefix() throws Exception {
        byte[] first = entry(manifest, 1, null, 9, new byte[0]), second = entry(manifest, 2, first, 9, new byte[0]);
        try (var store = open()) { store.promise(promise(manifest, 2)); store.accept(accept(manifest, first, 2)); }
        // Both records are valid in isolation, but no local proof permits the second slot.
        Files.write(node.resolve("accepted.gsr"), accept(manifest, second, 2), StandardOpenOption.APPEND);
        var before = inventory(); assertThrows(AutomaticReplicationException.class, this::open); assertEquals(before, inventory());
    }
    private java.util.Map<String, String> inventory() throws Exception {
        var result = new java.util.TreeMap<String, String>();
        try (var files = Files.list(node)) { for (Path p : files.toList()) result.put(p.getFileName().toString(), sha(Files.readAllBytes(p))); }
        return result;
    }
}
