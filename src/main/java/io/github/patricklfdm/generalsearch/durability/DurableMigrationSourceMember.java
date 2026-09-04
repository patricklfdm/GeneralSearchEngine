package io.github.patricklfdm.generalsearch.durability;

import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.regex.Pattern;

/** Exact authoritative source member bound into a migration plan. */
public record DurableMigrationSourceMember(String name, long size, String sha256) {
    private static final Pattern NAME =
            Pattern.compile("[a-z0-9][a-z0-9._-]{0,254}");
    private static final Pattern SHA256 = Pattern.compile("[a-f0-9]{64}");

    public DurableMigrationSourceMember {
        Objects.requireNonNull(name, "name");
        Objects.requireNonNull(sha256, "sha256");
        if (!NAME.matcher(name).matches()
                || name.getBytes(StandardCharsets.UTF_8).length > 255
                || name.equals(".") || name.equals("..")) {
            throw new IllegalArgumentException("invalid canonical member name");
        }
        if (size < 0) {
            throw new IllegalArgumentException("size must not be negative");
        }
        if (!SHA256.matcher(sha256).matches()) {
            throw new IllegalArgumentException("sha256 must be lowercase hexadecimal");
        }
    }
}
