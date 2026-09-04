package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.regex.Pattern;

/** Stable caller-supplied identity for migration transform semantics. */
public record DurableMigrationTransformDescriptor(String identifier, int version) {
    private static final Pattern IDENTIFIER =
            Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    public DurableMigrationTransformDescriptor {
        Objects.requireNonNull(identifier, "identifier");
        if (!IDENTIFIER.matcher(identifier).matches()) {
            throw new IllegalArgumentException(
                    "identifier must match [a-z0-9][a-z0-9-]{0,127}");
        }
        if (version < 0) {
            throw new IllegalArgumentException("version must not be negative");
        }
    }
}
