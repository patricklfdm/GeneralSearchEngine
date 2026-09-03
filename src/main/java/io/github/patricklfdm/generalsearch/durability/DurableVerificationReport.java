package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.OptionalLong;

/** Immutable codec-free structural-verification result for one directory snapshot. */
public record DurableVerificationReport(
        Path directory,
        DurableVerificationStatus status,
        List<DurableVerificationFinding> findings,
        OptionalLong sequence,
        long authoritativeBytes
) {
    /** Normalizes paths and freezes a deterministic, duplicate-free finding list. */
    public DurableVerificationReport {
        directory = Objects.requireNonNull(directory, "directory")
                .toAbsolutePath().normalize();
        status = Objects.requireNonNull(status, "status");
        findings = List.copyOf(Objects.requireNonNull(findings, "findings"));
        sequence = Objects.requireNonNull(sequence, "sequence");
        if (sequence.isPresent() && sequence.getAsLong() < 0) {
            throw new IllegalArgumentException("sequence must not be negative");
        }
        if (authoritativeBytes < 0) {
            throw new IllegalArgumentException(
                    "authoritativeBytes must not be negative");
        }
        if (new HashSet<>(findings).size() != findings.size()) {
            throw new IllegalArgumentException("findings must not contain duplicates");
        }
        for (int index = 1; index < findings.size(); index++) {
            if (DurableVerificationFinding.CANONICAL_ORDER.compare(
                    findings.get(index - 1), findings.get(index)) > 0) {
                throw new IllegalArgumentException(
                        "findings must use canonical code/member/detail order");
            }
        }
    }
}
