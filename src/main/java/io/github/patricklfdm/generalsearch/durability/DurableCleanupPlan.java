package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;

/** Immutable dry-run result bound to one exact authority and inventory snapshot. */
public record DurableCleanupPlan(
        Path directory,
        DurableCleanupScope scope,
        String authorityIdentity,
        List<DurableCleanupEntry> deleteSet,
        String planDigest
) {
    private static final Pattern SHA256 = Pattern.compile("[0-9a-f]{64}");

    /** Normalizes paths and freezes the ordered, duplicate-free delete set. */
    public DurableCleanupPlan {
        directory = Objects.requireNonNull(directory, "directory")
                .toAbsolutePath().normalize();
        scope = Objects.requireNonNull(scope, "scope");
        authorityIdentity = Objects.requireNonNull(
                authorityIdentity, "authorityIdentity");
        deleteSet = List.copyOf(Objects.requireNonNull(deleteSet, "deleteSet"));
        planDigest = Objects.requireNonNull(planDigest, "planDigest");
        if (!SHA256.matcher(authorityIdentity).matches()
                || !SHA256.matcher(planDigest).matches()) {
            throw new IllegalArgumentException(
                    "authority identity and plan digest must be lowercase SHA-256");
        }
        if (new HashSet<>(deleteSet).size() != deleteSet.size()) {
            throw new IllegalArgumentException("deleteSet must not contain duplicates");
        }
    }
}
