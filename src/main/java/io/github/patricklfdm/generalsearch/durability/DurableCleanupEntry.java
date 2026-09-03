package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * One exact member proven non-authoritative by an offline cleanup plan.
 *
 * @param member normalized absolute member path
 * @param reason stable bounded reason for deletion eligibility
 * @param size observed bytes, or zero for an operation-owned directory
 * @param fingerprint lowercase SHA-256 fingerprint of the observed member
 */
public record DurableCleanupEntry(
        Path member,
        String reason,
        long size,
        String fingerprint
) {
    private static final Pattern REASON = Pattern.compile("[a-z][a-z0-9-]{0,63}");
    private static final Pattern SHA256 = Pattern.compile("[0-9a-f]{64}");

    /** Normalizes and validates one deterministic delete-set entry. */
    public DurableCleanupEntry {
        member = Objects.requireNonNull(member, "member")
                .toAbsolutePath().normalize();
        reason = Objects.requireNonNull(reason, "reason");
        fingerprint = Objects.requireNonNull(fingerprint, "fingerprint");
        if (!REASON.matcher(reason).matches()) {
            throw new IllegalArgumentException("reason must be a lowercase identifier");
        }
        if (size < 0) {
            throw new IllegalArgumentException("size must not be negative");
        }
        if (!SHA256.matcher(fingerprint).matches()) {
            throw new IllegalArgumentException("fingerprint must be lowercase SHA-256");
        }
    }
}
