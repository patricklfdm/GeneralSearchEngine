package io.github.patricklfdm.generalsearch.durability.harness;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.stream.Stream;
import java.util.regex.Pattern;

/** Separate-JVM scaffold for V4.3 barriers before production images exist. */
public final class V43FastReopenHarnessProcess {
    private static final Pattern ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    private V43FastReopenHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3 || !ID.matcher(arguments[2]).matches()) {
            throw new IllegalArgumentException("expected mode, store and barrier ID");
        }
        String mode = arguments[0];
        Path store = Path.of(arguments[1]).toAbsolutePath().normalize();
        String barrier = arguments[2];
        switch (mode) {
            case "child-halt" -> child(store, barrier, true);
            case "child-wait" -> child(store, barrier, false);
            case "verify" -> verify(store, barrier);
            default -> throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void child(Path store, String barrier, boolean halt) throws Exception {
        Files.createDirectories(store);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(store.resolve("graceful-close.marker"), "ran\n",
                        StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // Presence is the only parent-visible signal.
            }
        }, "v43-fast-reopen-shutdown-marker"));
        Files.writeString(store.resolve("v43-phase1-canonical.properties"),
                "schemaVersion=1\nbarrierId=" + barrier
                        + "\ncanonicalAuthority=VALID\nformat=PHASE2_PENDING"
                        + "\nproductionDerivedState=false\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_V43_BARRIER_READY={\"schemaVersion\":1,"
                + "\"barrierId\":\"" + barrier + "\",\"pid\":"
                + ProcessHandle.current().pid()
                + ",\"canonicalAuthority\":\"VALID\","
                + "\"derivedMembersCreated\":false}");
        System.out.flush();
        if (halt) {
            Runtime.getRuntime().halt(89);
        }
        while (true) {
            Thread.sleep(1_000L);
        }
    }

    private static void verify(Path store, String barrier) throws Exception {
        String value = Files.readString(store.resolve("v43-phase1-canonical.properties"),
                StandardCharsets.UTF_8);
        boolean derived;
        try (Stream<Path> members = Files.list(store)) {
            derived = members.anyMatch(path -> {
                String name = path.getFileName().toString();
                return name.startsWith("gse-derived-")
                        || name.equals("gse-derived-catalog");
            });
        }
        if (!value.contains("barrierId=" + barrier + "\n")
                || !value.contains("canonicalAuthority=VALID\n")
                || !value.contains("format=PHASE2_PENDING\n")
                || !value.contains("productionDerivedState=false\n")
                || Files.exists(store.resolve("graceful-close.marker")) || derived) {
            throw new IllegalStateException("V4.3 Phase 1 scaffold state mismatch");
        }
        System.out.println("GSE_V43_VERIFY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"canonicalAuthority\":\"VALID\","
                + "\"derivedState\":\"ABSENT\",\"productionDerivedState\":false,"
                + "\"barrierId\":\"" + barrier + "\"}");
    }
}
