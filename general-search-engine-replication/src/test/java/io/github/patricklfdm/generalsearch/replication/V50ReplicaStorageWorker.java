package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaStorageTestSupport.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.concurrent.CountDownLatch;

/** Separate-process driver for the production storage gate; never packaged in a release JAR. */
public final class V50ReplicaStorageWorker {
    private V50ReplicaStorageWorker() { }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        Path directory = Path.of(args[1]);
        try {
            switch (mode) {
                case "create" -> {
                    initialize(directory);
                    try (var store = open(directory)) { populate(store); }
                    report(directory);
                }
                case "inspect" -> report(directory);
                case "hold" -> {
                    try (var ignored = open(directory)) { stopAt(Path.of(args[2]), "OWNED"); }
                }
                case "crash" -> {
                    String barrier = args[2];
                    Path marker = Path.of(args[3]);
                    var faults = new ReplicaStore.Faults() {
                        public int maxWriteBytes() { return barrier.endsWith("WRITE_CHUNK") ? 7 : Integer.MAX_VALUE; }
                        public void at(String current) throws IOException {
                            if (current.equals(barrier)) stopAt(marker, current);
                        }
                    };
                    if (barrier.contains("INIT_")) {
                        ReplicaStore.initialize(directory, MANIFEST, LOCAL, BOUNDS, faults);
                    } else {
                        initialize(directory);
                        try (var setup = open(directory)) {
                            if (!barrier.contains("PROMISE")) setup.promise(LEADER, 2, INCARNATION);
                            if (barrier.contains("PROOF")) setup.append(LEADER, next(setup, "NO_OP", ""));
                        }
                        try (var store = ReplicaStore.open(directory, MANIFEST, LOCAL, BOUNDS, faults)) {
                            if (barrier.contains("PROMISE")) store.promise(LEADER, 2, INCARNATION);
                            else if (barrier.contains("ENTRY")) store.append(LEADER, next(store, "NO_OP", ""));
                            else {
                                var entry = new ReplicaEntry(MANIFEST.digest(), 2, INCARNATION, 1, "NO_OP",
                                        1, 0, MANIFEST.digest(), new byte[0]);
                                store.storeProof(LEADER, proof(entry));
                            }
                        }
                    }
                    throw new AssertionError("target barrier was not reached");
                }
                default -> throw new IllegalArgumentException("unknown worker mode");
            }
        } catch (ReplicationException error) {
            System.out.println("{\"accepted\":false,\"reason\":\"" + error.reason() + "\"}");
            System.exit(3);
        }
    }

    private static void stopAt(Path marker, String barrier) throws IOException {
        Files.writeString(marker, "{\"pid\":" + ProcessHandle.current().pid()
                + ",\"barrier\":\"" + barrier + "\",\"ackReturned\":false}", StandardOpenOption.CREATE_NEW);
        try { new CountDownLatch(1).await(); }
        catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new IOException("barrier interrupted", interrupted);
        }
    }

    private static void report(Path directory) {
        var status = ReplicationStorageOperations.inspect(directory);
        if (!status.structurallyValid()) throw new AssertionError("missing store");
        try (var store = open(directory)) {
            System.out.println("{\"accepted\":true,\"promisedEpoch\":" + store.promisedEpoch()
                    + ",\"lastLogIndex\":" + store.lastLogIndex() + ",\"commitIndex\":" + store.commitIndex() + "}");
        }
    }
}
