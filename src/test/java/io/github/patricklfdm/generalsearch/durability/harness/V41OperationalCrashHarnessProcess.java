package io.github.patricklfdm.generalsearch.durability.harness;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.regex.Pattern;

/** Separate JVM used to establish V4.1 barriers before operations exist. */
public final class V41OperationalCrashHarnessProcess {
    private static final Pattern ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    private V41OperationalCrashHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3 || !ID.matcher(arguments[2]).matches()) {
            throw new IllegalArgumentException("expected mode, workspace and barrier ID");
        }
        String mode = arguments[0];
        Path workspace = Path.of(arguments[1]).toAbsolutePath().normalize();
        String barrier = arguments[2];
        Files.createDirectories(workspace);
        if (mode.equals("child-halt") || mode.equals("child-wait")) {
            child(workspace, barrier, mode.equals("child-halt"));
        } else if (mode.equals("verify")) {
            verify(workspace, barrier);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void child(Path workspace, String barrier, boolean halt)
            throws Exception {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(workspace.resolve("graceful-close.marker"),
                        "shutdown-hook-ran\n", StandardCharsets.UTF_8,
                        StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // Presence is the only signal consumed by the parent.
            }
        }, "v41-operational-shutdown-marker"));
        Files.writeString(workspace.resolve("v41-phase1-scaffold.properties"),
                "schemaVersion=1\nbarrierId=" + barrier
                        + "\nproductionOperations=false\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_V41_BARRIER_READY={\"schemaVersion\":1,"
                + "\"barrierId\":\"" + barrier + "\",\"pid\":"
                + ProcessHandle.current().pid() + "}");
        System.out.flush();
        if (halt) {
            Runtime.getRuntime().halt(87);
        }
        while (true) {
            Thread.sleep(1_000L);
        }
    }

    private static void verify(Path workspace, String barrier) throws Exception {
        String value = Files.readString(
                workspace.resolve("v41-phase1-scaffold.properties"),
                StandardCharsets.UTF_8);
        if (!value.contains("barrierId=" + barrier + "\n")
                || !value.contains("productionOperations=false\n")
                || Files.exists(workspace.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("V4.1 scaffold state mismatch");
        }
        System.out.println("GSE_V41_VERIFY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"productionOperations\":false,"
                + "\"barrierId\":\"" + barrier + "\"}");
    }
}
