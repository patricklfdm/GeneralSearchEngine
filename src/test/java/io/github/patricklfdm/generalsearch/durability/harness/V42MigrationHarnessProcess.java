package io.github.patricklfdm.generalsearch.durability.harness;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.regex.Pattern;

/** Separate JVM scaffold for V4.2 migration barriers before migration exists. */
public final class V42MigrationHarnessProcess {
    private static final Pattern ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    private V42MigrationHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 4 || !ID.matcher(arguments[3]).matches()) {
            throw new IllegalArgumentException(
                    "expected mode, source, target and barrier ID");
        }
        String mode = arguments[0];
        Path source = Path.of(arguments[1]).toAbsolutePath().normalize();
        Path target = Path.of(arguments[2]).toAbsolutePath().normalize();
        String barrier = arguments[3];
        if (mode.equals("child-halt") || mode.equals("child-wait")) {
            child(source, target, barrier, mode.equals("child-halt"));
        } else if (mode.equals("verify")) {
            verify(source, target, barrier);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void child(Path source, Path target, String barrier, boolean halt)
            throws Exception {
        Files.createDirectories(source);
        if (Files.exists(target)) {
            throw new IllegalStateException("Phase 1 target must be absent");
        }
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(source.resolve("graceful-close.marker"),
                        "shutdown-hook-ran\n", StandardCharsets.UTF_8,
                        StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // Presence is the only signal consumed by the parent.
            }
        }, "v42-migration-shutdown-marker"));
        Files.writeString(source.resolve("v42-phase1-source.properties"),
                "schemaVersion=1\nbarrierId=" + barrier
                        + "\nsourceFormat=gse-durable-1.0"
                        + "\nproductionMigration=false\ntargetCreated=false\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_V42_BARRIER_READY={\"schemaVersion\":1,"
                + "\"barrierId\":\"" + barrier + "\",\"pid\":"
                + ProcessHandle.current().pid() + ",\"targetCreated\":false}");
        System.out.flush();
        if (halt) {
            Runtime.getRuntime().halt(88);
        }
        while (true) {
            Thread.sleep(1_000L);
        }
    }

    private static void verify(Path source, Path target, String barrier)
            throws Exception {
        String value = Files.readString(
                source.resolve("v42-phase1-source.properties"),
                StandardCharsets.UTF_8);
        if (!value.contains("barrierId=" + barrier + "\n")
                || !value.contains("sourceFormat=gse-durable-1.0\n")
                || !value.contains("productionMigration=false\n")
                || !value.contains("targetCreated=false\n")
                || Files.exists(source.resolve("graceful-close.marker"))
                || Files.exists(target)) {
            throw new IllegalStateException("V4.2 migration scaffold state mismatch");
        }
        System.out.println("GSE_V42_VERIFY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"sourceUnchanged\":true,"
                + "\"targetAbsent\":true,\"productionMigration\":false,"
                + "\"barrierId\":\"" + barrier + "\"}");
    }
}
