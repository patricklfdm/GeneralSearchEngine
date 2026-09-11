package io.github.patricklfdm.generalsearch.durability.harness;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.Properties;
import java.util.regex.Pattern;
import java.util.zip.CRC32C;

/** Separate-JVM Phase 1 protocol scaffold; it never opens production storage. */
public final class V44FinalHardeningHarnessProcess {
    private static final Pattern ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    private V44FinalHardeningHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length < 2) {
            throw new IllegalArgumentException("expected mode and workspace");
        }
        String mode = arguments[0];
        Path store = Path.of(arguments[1]).toAbsolutePath().normalize();
        switch (mode) {
            case "writer-halt" -> writer(store, argument(arguments, 2),
                    argument(arguments, 3), "halt");
            case "writer-wait" -> writer(store, argument(arguments, 2),
                    argument(arguments, 3), "wait");
            case "writer-graceful" -> writer(store, argument(arguments, 2),
                    argument(arguments, 3), "graceful");
            case "startup-failure" -> startupFailure(store);
            case "injected-io-failure" -> injectedIoFailure(store);
            case "writer-malformed" -> malformed(store, argument(arguments, 2));
            case "interrupt" -> interrupt(Long.parseLong(argument(arguments, 2)));
            case "inspect" -> inspect(store, argument(arguments, 2),
                    Integer.parseInt(argument(arguments, 3)));
            case "recover" -> recover(store, argument(arguments, 2));
            case "continue" -> continueHistory(store, argument(arguments, 2));
            default -> throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static String argument(String[] values, int index) {
        if (values.length <= index) {
            throw new IllegalArgumentException("missing argument " + index);
        }
        return values[index];
    }

    private static void writer(Path store, String barrier, String seed,
                               String termination) throws Exception {
        validateId(barrier);
        Long.parseLong(seed);
        Files.createDirectories(store);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(store.resolve("graceful-close.marker"), "ran\n",
                        StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // Marker presence is the parent-visible signal.
            }
        }, "v44-phase1-graceful-marker"));
        writeCanonical(store, barrier, seed, 1);
        System.out.println("GSE_V44_BARRIER_READY={\"barrierId\":\"" + barrier
                + "\",\"pid\":" + ProcessHandle.current().pid()
                + ",\"seed\":" + seed + ",\"sequence\":1}");
        System.out.flush();
        if (termination.equals("halt")) {
            Runtime.getRuntime().halt(89);
        }
        if (termination.equals("graceful")) {
            return;
        }
        while (true) {
            Thread.sleep(1_000L);
        }
    }

    private static void startupFailure(Path store) {
        if (Files.exists(store)) {
            throw new IllegalStateException("startup-failure store must be absent");
        }
        System.err.println("GSE_V44_INJECTED_STARTUP_FAILURE");
        Runtime.getRuntime().halt(78);
    }

    private static void injectedIoFailure(Path store) throws IOException {
        Files.createDirectories(store);
        Files.writeString(store.resolve("canonical.properties.staging"),
                "incomplete=true\n", StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW);
        System.err.println("GSE_V44_INJECTED_IO_FAILURE");
        Runtime.getRuntime().halt(74);
    }

    private static void malformed(Path store, String barrier) throws IOException {
        validateId(barrier);
        Files.createDirectories(store);
        Files.write(store.resolve("canonical.properties"),
                new byte[] {0, 1, 2, 3, 4}, StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_V44_BARRIER_READY={\"barrierId\":\"" + barrier
                + "\",\"pid\":" + ProcessHandle.current().pid()
                + ",\"seed\":440001,\"sequence\":-1}");
        System.out.flush();
        Runtime.getRuntime().halt(89);
    }

    private static void interrupt(long pid) {
        ProcessHandle process = ProcessHandle.of(pid).orElseThrow();
        if (!process.destroyForcibly()) {
            throw new IllegalStateException("interrupter could not kill writer");
        }
        System.out.println("GSE_V44_INTERRUPTER=PASS pid=" + pid);
    }

    private static void inspect(Path store, String barrier, int sequence)
            throws IOException {
        Properties value = readCanonical(store);
        verify(value, barrier, sequence);
        System.out.println("GSE_V44_INSPECT=PASS sequence=" + sequence);
    }

    private static void recover(Path store, String barrier) throws IOException {
        Properties value = readCanonical(store);
        verify(value, barrier, 1);
        Files.writeString(store.resolve("recovery.receipt"),
                "barrierId=" + barrier + "\nsequence=1\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_V44_RECOVERY=PASS sequence=1");
    }

    private static void continueHistory(Path store, String barrier) throws IOException {
        Properties value = readCanonical(store);
        verify(value, barrier, 1);
        writeCanonical(store, barrier, value.getProperty("seed"), 2);
        System.out.println("GSE_V44_CONTINUATION=PASS sequence=2");
    }

    private static void writeCanonical(Path store, String barrier, String seed,
                                       int sequence) throws IOException {
        String body = "schema=gse-v44-phase1-model-v1\nbarrierId=" + barrier
                + "\nseed=" + seed + "\nsequence=" + sequence
                + "\ncanonicalAuthority=VALID\nproductionStorage=false\n";
        CRC32C checksum = new CRC32C();
        checksum.update(body.getBytes(StandardCharsets.UTF_8));
        String complete = body + "crc32c=" + Long.toUnsignedString(checksum.getValue())
                + "\n";
        Path staging = store.resolve("canonical.properties.staging");
        Files.writeString(staging, complete, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
        Files.move(staging, store.resolve("canonical.properties"),
                StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }

    private static Properties readCanonical(Path store) throws IOException {
        Properties value = new Properties();
        try (var reader = Files.newBufferedReader(store.resolve("canonical.properties"),
                StandardCharsets.UTF_8)) {
            value.load(reader);
        }
        return value;
    }

    private static void verify(Properties value, String barrier, int sequence) {
        String body = "schema=" + value.getProperty("schema")
                + "\nbarrierId=" + value.getProperty("barrierId")
                + "\nseed=" + value.getProperty("seed")
                + "\nsequence=" + value.getProperty("sequence")
                + "\ncanonicalAuthority=" + value.getProperty("canonicalAuthority")
                + "\nproductionStorage=" + value.getProperty("productionStorage")
                + "\n";
        CRC32C checksum = new CRC32C();
        checksum.update(body.getBytes(StandardCharsets.UTF_8));
        if (!"gse-v44-phase1-model-v1".equals(value.getProperty("schema"))
                || !barrier.equals(value.getProperty("barrierId"))
                || Integer.parseInt(value.getProperty("sequence", "-1")) != sequence
                || !"VALID".equals(value.getProperty("canonicalAuthority"))
                || !"false".equals(value.getProperty("productionStorage"))
                || !Long.toUnsignedString(checksum.getValue()).equals(
                        value.getProperty("crc32c"))) {
            throw new IllegalStateException("Phase 1 model authority differs");
        }
    }

    private static void validateId(String value) {
        if (!ID.matcher(value).matches()) {
            throw new IllegalArgumentException("invalid barrier ID");
        }
    }
}
