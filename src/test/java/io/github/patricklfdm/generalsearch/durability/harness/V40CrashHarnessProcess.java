package io.github.patricklfdm.generalsearch.durability.harness;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.regex.Pattern;

/** Separate-JVM Phase 1 process used by the local crash-harness scaffold. */
public final class V40CrashHarnessProcess {
    private static final Pattern ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    private V40CrashHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3) {
            throw new IllegalArgumentException("expected mode, workspace and barrier ID");
        }
        String mode = arguments[0];
        Path workspace = Path.of(arguments[1]).toAbsolutePath().normalize();
        String barrier = arguments[2];
        if (!ID.matcher(barrier).matches()) {
            throw new IllegalArgumentException("invalid barrier ID");
        }
        Files.createDirectories(workspace);
        if (mode.equals("child-halt") || mode.equals("child-wait")) {
            runChild(workspace, barrier, mode.equals("child-halt"));
            return;
        }
        if (mode.equals("recover")) {
            recover(workspace, barrier);
            return;
        }
        throw new IllegalArgumentException("unknown mode: " + mode);
    }

    private static void runChild(Path workspace, String barrier, boolean halt)
            throws Exception {
        Path gracefulMarker = workspace.resolve("graceful-close.marker");
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(
                        gracefulMarker,
                        "shutdown-hook-ran\n",
                        StandardCharsets.UTF_8,
                        StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // The parent treats any marker presence as an invalid abrupt-crash case.
            }
        }, "v40-harness-shutdown-marker"));
        Files.writeString(
                workspace.resolve("phase1-scaffold.properties"),
                "schemaVersion=1\nbarrierId=" + barrier
                        + "\nproductionStorage=false\n",
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_BARRIER_READY={\"schemaVersion\":1,\"barrierId\":\""
                + barrier + "\",\"pid\":" + ProcessHandle.current().pid() + "}");
        System.out.flush();
        if (halt) {
            Runtime.getRuntime().halt(86);
        }
        while (true) {
            Thread.sleep(1_000L);
        }
    }

    private static void recover(Path workspace, String barrier) throws Exception {
        String state = Files.readString(
                workspace.resolve("phase1-scaffold.properties"),
                StandardCharsets.UTF_8);
        if (!state.contains("barrierId=" + barrier + "\n")
                || !state.contains("productionStorage=false\n")) {
            throw new IllegalStateException("scaffold state mismatch");
        }
        if (Files.exists(workspace.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("graceful shutdown path ran");
        }
        System.out.println("GSE_RECOVERY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"productionStorage\":false,"
                + "\"barrierId\":\"" + barrier + "\"}");
    }
}
