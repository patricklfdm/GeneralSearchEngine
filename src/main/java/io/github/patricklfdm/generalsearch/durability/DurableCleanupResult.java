package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;

/** Immutable proof of one successfully applied, post-verified cleanup plan. */
public record DurableCleanupResult(
        Path directory,
        String planDigest,
        List<Path> deletedMembers,
        long deletedBytes
) {
    private static final Pattern SHA256 = Pattern.compile("[0-9a-f]{64}");

    /** Normalizes paths and validates the bounded successful result. */
    public DurableCleanupResult {
        directory = Objects.requireNonNull(directory, "directory")
                .toAbsolutePath().normalize();
        planDigest = Objects.requireNonNull(planDigest, "planDigest");
        deletedMembers = List.copyOf(Objects.requireNonNull(
                deletedMembers, "deletedMembers").stream()
                .map(path -> Objects.requireNonNull(path, "deleted member")
                        .toAbsolutePath().normalize())
                .toList());
        if (!SHA256.matcher(planDigest).matches()) {
            throw new IllegalArgumentException("planDigest must be lowercase SHA-256");
        }
        if (deletedBytes < 0) {
            throw new IllegalArgumentException("deletedBytes must not be negative");
        }
        if (new HashSet<>(deletedMembers).size() != deletedMembers.size()) {
            throw new IllegalArgumentException(
                    "deletedMembers must not contain duplicates");
        }
    }
}
