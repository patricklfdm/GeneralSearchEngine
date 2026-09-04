package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.regex.Pattern;

/** Versioned immutable backup-bundle format identity. */
public record DurableBackupFormat(String family, int major, int minor) {
    private static final Pattern FAMILY = Pattern.compile(
            "[a-z0-9][a-z0-9._-]{0,127}");

    /** Exact V4.1 full-backup format. */
    public static final DurableBackupFormat V1_0 =
            new DurableBackupFormat("gse-backup", 1, 0);

    /** Exact V4.2 full-backup format for a {@code gse-durable (1,1)} source. */
    public static final DurableBackupFormat V1_1 =
            new DurableBackupFormat("gse-backup", 1, 1);

    /** Validates the stable family and non-negative version components. */
    public DurableBackupFormat {
        Objects.requireNonNull(family, "family");
        if (!FAMILY.matcher(family).matches()) {
            throw new IllegalArgumentException("family is not a stable identifier");
        }
        if (major < 0 || minor < 0) {
            throw new IllegalArgumentException("format versions must not be negative");
        }
    }
}
