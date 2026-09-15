package io.github.patricklfdm.generalsearch.replication;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Separate-process fixture worker; it is not a production replica. */
public final class V50ReplicaFixtureWorker {
    private V50ReplicaFixtureWorker() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("usage: node-id workspace generation");
        }
        String nodeId = args[0];
        Path workspace = Path.of(args[1]);
        int generation = Integer.parseInt(args[2]);
        Files.createDirectories(workspace);
        long pid = ProcessHandle.current().pid();
        String receipt = "nodeId=" + nodeId + "\n"
                + "generation=" + generation + "\n"
                + "pid=" + pid + "\n";
        Files.writeString(workspace.resolve("ready.properties"), receipt,
                StandardCharsets.UTF_8, StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING);
        Files.writeString(workspace.resolve("events.log"),
                "READY node=" + nodeId + " generation=" + generation
                        + " pid=" + pid + "\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE,
                StandardOpenOption.APPEND);
        Path storageFault = workspace.resolve("commands").resolve("storage-fault");
        while (true) {
            if (Files.exists(storageFault)) {
                Files.writeString(workspace.resolve("events.log"),
                        "STORAGE_FAULT node=" + nodeId + " generation=" + generation
                                + " pid=" + pid + "\n",
                        StandardCharsets.UTF_8, StandardOpenOption.CREATE,
                        StandardOpenOption.APPEND);
                Files.writeString(workspace.resolve("storage-fault.properties"),
                        receipt + "exitCode=20\n", StandardCharsets.UTF_8,
                        StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
                System.exit(20);
            }
            Thread.sleep(50);
        }
    }
}
