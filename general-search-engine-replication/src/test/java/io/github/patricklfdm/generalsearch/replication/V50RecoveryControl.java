package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;

/** Test-only semantic control, launched with the checksum-pinned published V4.4 core JAR. */
public final class V50RecoveryControl {
    private V50RecoveryControl() { }
    public static void main(String[] args) throws Exception {
        System.err.println("controlSource=" + io.github.patricklfdm.generalsearch.engine.SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI().getPath());
        try (var engine = io.github.patricklfdm.generalsearch.engine.SearchEngine.builder(SCHEMA).indexes(INDEXES).build()) {
            for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.US_ASCII)) {
                var request = ReplicaWire.object(ReplicaJson.decode(line.getBytes(StandardCharsets.US_ASCII), 1024 * 1024));
                switch (ReplicaWire.string(request, "command")) {
                    case "add" -> engine.add(V50RecoveryWorker.document(request)).join();
                    case "update" -> engine.update(V50RecoveryWorker.document(request)).join();
                    case "remove" -> engine.remove(Math.toIntExact(ReplicaWire.number(request, "id"))).join();
                    case "drop" -> engine.dropIndex("value").join();
                    case "index" -> engine.createIndex(INDEXES.getFirst()).join();
                    default -> throw new IllegalArgumentException("unknown control operation");
                }
            }
            System.out.println(V50RecoveryWorker.json(V50RecoveryWorker.state(engine)));
        }
    }
}
