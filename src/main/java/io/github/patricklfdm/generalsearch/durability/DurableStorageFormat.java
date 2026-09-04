package io.github.patricklfdm.generalsearch.durability;

import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.regex.Pattern;

/** Immutable live durable-storage format identity retained by codec-free inspection. */
public record DurableStorageFormat(String family, int major, int minor) {
    private static final Pattern FAMILY = Pattern.compile(
            "[a-z0-9][a-z0-9-]{0,127}");

    /** Exact published V4.0/V4.1 live format and the V4.2 default. */
    public static final DurableStorageFormat V1_0 =
            new DurableStorageFormat("gse-durable", 1, 0);

    /** Exact V4.2 evolution-profile live format. */
    public static final DurableStorageFormat V1_1 =
            new DurableStorageFormat("gse-durable", 1, 1);

    /** Validates a bounded lowercase-hyphenated family and non-negative versions. */
    public DurableStorageFormat {
        Objects.requireNonNull(family, "family");
        if (!FAMILY.matcher(family).matches()
                || family.getBytes(StandardCharsets.UTF_8).length > 128) {
            throw new IllegalArgumentException(
                    "family must be a lowercase hyphenated identifier of at most 128 bytes");
        }
        if (major < 0 || minor < 0) {
            throw new IllegalArgumentException("format versions must not be negative");
        }
    }
}
