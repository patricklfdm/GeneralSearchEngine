package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.ENTRY;
import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.frame;
import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.sha256;
import static io.github.patricklfdm.generalsearch.replication.ReplicaStorageTestSupport.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;
import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class V50ReplicaStorageTest {
    @TempDir Path temporary;

    @Test
    void absentInspectionDoesNotCreateAnything() {
        Path path = temporary.resolve("absent");
        var status = ReplicationStorageOperations.inspect(path);
        assertFalse(status.present());
        assertFalse(status.structurallyValid());
        assertTrue(status.groupId().isEmpty());
        assertFalse(Files.exists(path));
    }

    @Test
    void independentGoldenBytesMatchJavaWriterAndReopen() throws Exception {
        Path golden = Path.of(getClass().getResource("/replication/v50-storage-v1/node-2").toURI());
        Path copy = temporary.resolve("copy");
        Files.createDirectory(copy);
        for (String name : ReplicaStore.FILES) Files.copy(golden.resolve(name), copy.resolve(name));
        Map<String, String> before = inventory(copy);
        try (var store = open(copy)) {
            assertEquals(2, store.promisedEpoch());
            assertEquals(3, store.lastLogIndex());
            assertEquals(2, store.commitIndex());
            assertEquals("cfb0b47406b809826e9549850703adef153e6e836fe1edcc3ce3d666d2d3f25f", store.lastEntryDigest());
        }
        assertEquals(before, inventory(copy));
        Path java = temporary.resolve("java");
        initialize(java);
        try (var store = open(java)) { populate(store); }
        assertEquals(before, inventory(java));
        var status = ReplicationStorageOperations.inspect(java);
        assertTrue(status.structurallyValid());
        assertEquals(MANIFEST.groupId(), status.groupId().orElseThrow());
        assertEquals(LOCAL, status.nodeId().orElseThrow());
        assertEquals(before, inventory(java));
    }

    @Test
    void immutableGroupLocalIdentityAndExistingTargetsAreRejected() throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        var before = inventory(directory);
        var other = new ReplicaManifest(MANIFEST.groupId(), "config-v2", LEADER, MANIFEST.members(),
                MANIFEST.codecId(), 1, MANIFEST.schemaId(), 1, MANIFEST.indexConfigurationDigest());
        rejected(PROTOCOL_MISMATCH, () -> ReplicaStore.open(directory, other, LOCAL, BOUNDS, ReplicaStore.Faults.NONE));
        rejected(PROTOCOL_MISMATCH, () -> ReplicaStore.open(directory, MANIFEST, LEADER, BOUNDS, ReplicaStore.Faults.NONE));
        rejected(STORAGE_FAILURE, () -> initialize(directory));
        assertEquals(before, inventory(directory));
    }

    @Test
    void liveOwnershipIsExclusiveInspectionReadOnlyAndCloseIdempotent() {
        Path directory = temporary.resolve("store");
        initialize(directory);
        var store = open(directory);
        rejected(STORAGE_FAILURE, () -> open(directory));
        rejected(STORAGE_FAILURE, () -> ReplicationStorageOperations.inspect(directory));
        store.close();
        store.close();
        rejected(CLOSED, () -> store.promise(LEADER, 2, INCARNATION));
        assertTrue(ReplicationStorageOperations.inspect(directory).structurallyValid());
        try (var reopened = open(directory)) { assertEquals(0, reopened.lastLogIndex()); }
    }

    @Test
    void acknowledgementsFollowForceAndExactRetriesDoNotGrowJournals() throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        var barriers = new ArrayList<String>();
        var faults = new ReplicaStore.Faults() {
            public void at(String barrier) { barriers.add(barrier); }
        };
        try (var store = ReplicaStore.open(directory, MANIFEST, LOCAL, BOUNDS, faults)) {
            store.promise(LEADER, 2, INCARNATION);
            var entry = next(store, "ADD_ALL", "opaque batch");
            var ack = store.append(LEADER, entry);
            assertEquals(0, store.commitIndex());
            var proof = proof(entry);
            String proofDigest = store.storeProof(LEADER, proof);
            assertEquals(1, store.commitIndex());
            for (String operation : List.of("PROMISE", "ENTRY", "PROOF")) {
                assertTrue(barriers.indexOf("BEFORE_" + operation + "_FORCE")
                        < barriers.indexOf("AFTER_" + operation + "_FORCE"));
                assertTrue(barriers.indexOf("AFTER_" + operation + "_FORCE")
                        < barriers.indexOf("BEFORE_" + operation + "_ACK"));
            }
            var before = inventory(directory);
            store.promise(LEADER, 2, INCARNATION);
            assertEquals(ack, store.append(LEADER, entry));
            assertEquals(proofDigest, store.storeProof(LEADER, proof));
            assertEquals(before, inventory(directory));
            assertEquals(2, barriers.stream().filter("BEFORE_ENTRY_ACK"::equals).count());
        }
    }

    @Test
    void rejectsStaleIncarnationWrongLeaderGapsAndConflictingRetriesBeforeWriting() throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        try (var store = open(directory)) {
            var entry = next(store, "ADD", "value");
            rejected(STALE_EPOCH, () -> store.append(LEADER, entry));
            store.promise(LEADER, 2, INCARNATION);
            store.append(LEADER, entry);
            var before = inventory(directory);
            rejected(NOT_CONFIGURED_LEADER, () -> store.promise(LOCAL, 3, UUID.randomUUID()));
            rejected(NOT_CONFIGURED_LEADER, () -> store.append(LOCAL, entry));
            rejected(STALE_EPOCH, () -> store.promise(LEADER, 1, INCARNATION));
            rejected(STALE_EPOCH, () -> store.promise(LEADER, 2, UUID.randomUUID()));
            var conflict = new ReplicaEntry(MANIFEST.digest(), 2, INCARNATION, 1, "ADD", 1, 0,
                    MANIFEST.digest(), new byte[] {1});
            rejected(CONFLICTING_HISTORY, () -> store.append(LEADER, conflict));
            var gap = new ReplicaEntry(MANIFEST.digest(), 2, INCARNATION, 3, "ADD", 2, 2,
                    store.lastEntryDigest(), new byte[0]);
            rejected(CONFLICTING_HISTORY, () -> store.append(LEADER, gap));
            assertEquals(before, inventory(directory));
        }
    }

    @Test
    void higherPromiseSurvivesReopenAndFencesOldEpochWithoutLosingCommittedPrefix() {
        Path directory = temporary.resolve("store");
        UUID newer = UUID.randomUUID();
        initialize(directory);
        try (var store = open(directory)) {
            populate(store);
            store.promise(LEADER, 3, newer);
        }
        try (var store = open(directory)) {
            assertEquals(3, store.promisedEpoch());
            assertEquals(2, store.commitIndex());
            rejected(STALE_EPOCH, () -> store.append(LEADER, next(store, "ADD", "stale")));
            var entry = new ReplicaEntry(MANIFEST.digest(), 3, newer, 4, "NO_OP", 2, 3,
                    store.lastEntryDigest(), new byte[0]);
            store.append(LEADER, entry);
            store.storeProof(LEADER, proof(entry));
        }
        try (var store = open(directory)) { assertEquals(4, store.commitIndex()); }
    }

    @Test
    void proofRequiresExactAvailableEntryAndDistinctConfiguredReceipts() throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        try (var store = open(directory)) {
            store.promise(LEADER, 2, INCARNATION);
            var entry = next(store, "ADD", "value");
            var proof = proof(entry);
            rejected(CONFLICTING_HISTORY, () -> store.storeProof(LEADER, proof));
            store.append(LEADER, entry);
            var before = inventory(directory);
            var invalid = new ReplicaProof(MANIFEST.digest(), 2, INCARNATION, 1, proof.entryDigest(),
                    proof.previousDigest(), List.of(new ReplicaProof.Receipt(LEADER, "0".repeat(64)), proof.receipts().get(1)));
            rejected(INTEGRITY_FAILURE, () -> store.storeProof(LEADER, invalid));
            var alien = new ReplicationNodeId("node-9");
            var foreign = new ReplicaProof(MANIFEST.digest(), 2, INCARNATION, 1, proof.entryDigest(),
                    proof.previousDigest(), List.of(proof.receipts().get(0),
                    ReplicaProof.acknowledgement(alien, entry, proof.entryDigest())));
            rejected(PROTOCOL_MISMATCH, () -> store.storeProof(LEADER, foreign));
            assertThrows(IllegalArgumentException.class, () -> new ReplicaProof(MANIFEST.digest(), 2,
                    INCARNATION, 1, proof.entryDigest(), proof.previousDigest(),
                    List.of(proof.receipts().get(0), proof.receipts().get(0))));
            var wrong = new ReplicaProof(MANIFEST.digest(), 2, INCARNATION, 1, "0".repeat(64),
                    proof.previousDigest(), proof.receipts());
            rejected(CONFLICTING_HISTORY, () -> store.storeProof(LEADER, wrong));
            assertEquals(before, inventory(directory));
            assertEquals(0, store.commitIndex());
            store.storeProof(LEADER, proof);
            var expanded = new ReplicaProof(MANIFEST.digest(), 2, INCARNATION, 1, proof.entryDigest(),
                    proof.previousDigest(), List.of(proof.receipts().get(0), proof.receipts().get(1),
                    ReplicaProof.acknowledgement(new ReplicationNodeId("node-3"), entry, proof.entryDigest())));
            rejected(CONFLICTING_HISTORY, () -> store.storeProof(LEADER, expanded));
        }
    }

    @Test
    void frameAndRetainedByteLimitsRejectBeforeWriting() throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        long initial;
        try (var paths = Files.list(directory)) {
            initial = paths.mapToLong(p -> { try { return Files.size(p); }
                catch (IOException e) { throw new java.io.UncheckedIOException(e); } }).sum();
        }
        try (var store = ReplicaStore.open(directory, MANIFEST, LOCAL, bounds(200, initial + 200), ReplicaStore.Faults.NONE)) {
            store.promise(LEADER, 2, INCARNATION);
            var before = inventory(directory);
            rejected(CAPACITY_EXCEEDED, () -> store.append(LEADER, next(store, "ADD", "too-large")));
            rejected(CAPACITY_EXCEEDED, () -> store.append(LEADER, next(store, "NO_OP", "")));
            assertEquals(before, inventory(directory));
        }
        Path absent = temporary.resolve("too-small");
        rejected(CAPACITY_EXCEEDED, () -> ReplicaStore.initialize(absent, MANIFEST, LOCAL, bounds(200, 1), ReplicaStore.Faults.NONE));
        assertFalse(Files.exists(absent));
        rejected(CAPACITY_EXCEEDED, () -> ReplicaStore.open(directory, MANIFEST, LOCAL, bounds(200, initial), ReplicaStore.Faults.NONE));
    }

    @Test
    void shortWritesCompleteAndPayloadOwnershipIsDefensive() {
        Path directory = temporary.resolve("store");
        var faults = new ReplicaStore.Faults() { public int maxWriteBytes() { return 7; } };
        ReplicaStore.initialize(directory, MANIFEST, LOCAL, BOUNDS, faults);
        try (var store = ReplicaStore.open(directory, MANIFEST, LOCAL, BOUNDS, faults)) { populate(store); }
        try (var store = open(directory)) { assertEquals(2, store.commitIndex()); }
        byte[] payload = {1, 2};
        var entry = new ReplicaEntry(MANIFEST.digest(), 2, INCARNATION, 1, "ADD", 1, 0, MANIFEST.digest(), payload);
        payload[0] = 9;
        entry.payload()[1] = 9;
        assertArrayEquals(new byte[] {1, 2}, entry.payload());
    }

    @ParameterizedTest
    @ValueSource(strings = {"BEFORE_PROMISE_FORCE", "AFTER_PROMISE_FORCE", "BEFORE_PROMISE_ACK",
            "AFTER_ENTRY_WRITE_CHUNK", "BEFORE_ENTRY_FORCE", "AFTER_ENTRY_FORCE", "BEFORE_ENTRY_ACK",
            "BEFORE_PROOF_FORCE", "AFTER_PROOF_FORCE", "BEFORE_PROOF_ACK"})
    void ioFailureNeverAcknowledgesAndPoisonsWriter(String barrier) throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        var faults = new ReplicaStore.Faults() {
            public void at(String current) throws IOException {
                if (current.equals(barrier)) throw new IOException("injected " + current);
            }
        };
        try (var store = ReplicaStore.open(directory, MANIFEST, LOCAL, BOUNDS, faults)) {
            rejected(STORAGE_FAILURE, () -> {
                store.promise(LEADER, 2, INCARNATION);
                var entry = next(store, "ADD", "value");
                store.append(LEADER, entry);
                store.storeProof(LEADER, proof(entry));
                fail("all acknowledgements returned despite injected I/O failure");
            });
            var before = inventory(directory);
            rejected(STORAGE_FAILURE, () -> store.promise(LEADER, 3, UUID.randomUUID()));
            assertEquals(before, inventory(directory));
        }
        // Complete bytes without an ACK are indeterminate; reopening may retain them.
        try (var store = open(directory)) {
            assertEquals(2, store.promisedEpoch());
            assertEquals(barrier.contains("PROMISE") ? 0 : 1, store.lastLogIndex());
            assertEquals(barrier.contains("PROOF") ? 1 : 0, store.commitIndex());
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"manifest.gsr", "node.gsr", "promises.gsr", "entries.gsr", "proofs.gsr", "storage-ready.gsr"})
    void everyCorruptOrTornAuthoritativeFileFailsClosedWithoutRepair(String filename) throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        try (var store = open(directory)) { populate(store); }
        byte[] original = Files.readAllBytes(directory.resolve(filename));
        for (int length : new int[] {0, 7, 47, original.length - 1}) {
            Files.write(directory.resolve(filename), Arrays.copyOf(original, length));
            unchangedOnRejection(directory);
        }
        byte[] corrupt = original.clone();
        corrupt[corrupt.length - 1] ^= 1;
        Files.write(directory.resolve(filename), corrupt);
        unchangedOnRejection(directory);
    }

    @ParameterizedTest
    @ValueSource(strings = {"major", "length", "operation", "payload", "predecessor", "epoch", "incarnation", "trailing"})
    void malformedEntriesAreRejectedEvenWithRecomputedOuterChecksum(String mutation) throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        try (var store = open(directory)) { populate(store); }
        Path entries = directory.resolve(ReplicaStore.ENTRY_FILE);
        byte[] bytes = Files.readAllBytes(entries);
        int start = 48 + ByteBuffer.wrap(bytes).getInt(12);
        int bodyLength = ByteBuffer.wrap(bytes).getInt(start + 12);
        byte[] body = Arrays.copyOfRange(bytes, start + 48, start + 48 + bodyLength);
        switch (mutation) {
            case "operation" -> body[64] = 11;
            case "payload" -> body[117] ^= 1;
            case "predecessor" -> body[81] ^= 1;
            case "epoch" -> ByteBuffer.wrap(body).putLong(32, 3);
            case "incarnation" -> body[40] ^= 1;
            case "trailing" -> body = Arrays.copyOf(body, body.length + 1);
            default -> { }
        }
        byte[] edited = frame(ENTRY, body, BOUNDS.maxFrameBytes());
        if (mutation.equals("major")) edited[5] = 2;
        if (mutation.equals("length")) ByteBuffer.wrap(edited).putInt(12, Integer.MAX_VALUE);
        byte[] result = new byte[bytes.length - bodyLength - 48 + edited.length];
        System.arraycopy(bytes, 0, result, 0, start);
        System.arraycopy(edited, 0, result, start, edited.length);
        System.arraycopy(bytes, start + 48 + bodyLength, result, start + edited.length, bytes.length - start - 48 - bodyLength);
        Files.write(entries, result);
        unchangedOnRejection(directory);
    }

    @Test
    void incompleteInitializationUnknownMembersAndAliasedPathsAreRejected() throws Exception {
        Path directory = temporary.resolve("store");
        var failure = new ReplicaStore.Faults() {
            public void at(String barrier) throws IOException {
                if (barrier.equals("BEFORE_INIT_storage-ready.gsr_WRITE")) throw new IOException("init crash");
            }
        };
        rejected(STORAGE_FAILURE, () -> ReplicaStore.initialize(directory, MANIFEST, LOCAL, BOUNDS, failure));
        unchangedOnRejection(directory);
        Path valid = temporary.resolve("valid");
        initialize(valid);
        Files.writeString(valid.resolve("unknown"), "untouched");
        unchangedOnRejection(valid);
        Files.delete(valid.resolve("unknown"));
        Path alias = temporary.resolve("alias");
        Files.createSymbolicLink(alias, valid);
        rejected(STORAGE_FAILURE, () -> ReplicationStorageOperations.inspect(alias));
        Files.createLink(temporary.resolve("manifest-link"), valid.resolve(ReplicaStore.MANIFEST_FILE));
        unchangedOnRejection(valid);
    }

    @Test
    void missingOwnedEntryPoisonsStoreWithoutNullPointerFailure() throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        try (var store = open(directory)) {
            store.promise(LEADER, 2, INCARNATION);
            var entry = next(store, "NO_OP", "");
            long headerSize = Files.size(directory.resolve(ReplicaStore.ENTRY_FILE));
            store.append(LEADER, entry);
            try (var channel = FileChannel.open(directory.resolve(ReplicaStore.ENTRY_FILE), StandardOpenOption.WRITE)) {
                channel.truncate(headerSize);
            }
            rejected(INTEGRITY_FAILURE, () -> store.append(LEADER, entry));
            rejected(STORAGE_FAILURE, () -> store.promise(LEADER, 3, UUID.randomUUID()));
        }
    }

    @Test
    void invalidOwnedEntryFieldsPoisonWriterEvenWithValidFrameChecksum() throws Exception {
        Path directory = temporary.resolve("store");
        initialize(directory);
        try (var store = open(directory)) {
            store.promise(LEADER, 2, INCARNATION);
            var entry = next(store, "NO_OP", "");
            store.append(LEADER, entry);
            Path path = directory.resolve(ReplicaStore.ENTRY_FILE);
            byte[] bytes = Files.readAllBytes(path);
            int offset = 48 + ByteBuffer.wrap(bytes).getInt(12);
            byte[] body = Arrays.copyOfRange(bytes, offset + 48, bytes.length);
            ByteBuffer.wrap(body).putLong(32, 0); // structurally invalid epoch
            byte[] replacement = frame(ENTRY, body, BOUNDS.maxFrameBytes());
            System.arraycopy(replacement, 0, bytes, offset, replacement.length);
            Files.write(path, bytes);
            rejected(INTEGRITY_FAILURE, () -> store.storeProof(LEADER, proof(entry)));
            rejected(STORAGE_FAILURE, () -> store.promise(LEADER, 3, UUID.randomUUID()));
        }
    }

    private static void rejected(ReplicationException.Reason reason, Runnable action) {
        assertEquals(reason, assertThrows(ReplicationException.class, action::run).reason());
    }

    private static Map<String, String> inventory(Path directory) throws IOException {
        Map<String, String> result = new HashMap<>();
        try (var paths = Files.list(directory)) {
            for (Path path : paths.toList()) result.put(path.getFileName().toString(), sha256(Files.readAllBytes(path)));
        }
        return result;
    }

    private static void unchangedOnRejection(Path directory) throws IOException {
        var before = inventory(directory);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.inspect(directory));
        assertThrows(ReplicationException.class, () -> open(directory));
        assertEquals(before, inventory(directory));
    }
}
