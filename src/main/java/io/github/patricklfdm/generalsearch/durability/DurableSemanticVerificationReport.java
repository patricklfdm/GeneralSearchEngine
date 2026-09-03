package io.github.patricklfdm.generalsearch.durability;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;

/** Immutable result of one complete typed semantic backup-verification pass. */
public record DurableSemanticVerificationReport(
        DurableVerificationReport structuralReport,
        DurableSemanticVerificationStatus status,
        List<DurableVerificationFinding> findings,
        long documentCount
) {
    /** Freezes a canonical, duplicate-free, payload-free finding list. */
    public DurableSemanticVerificationReport {
        structuralReport = Objects.requireNonNull(
                structuralReport, "structuralReport");
        status = Objects.requireNonNull(status, "status");
        findings = List.copyOf(Objects.requireNonNull(findings, "findings"));
        if (documentCount < 0) {
            throw new IllegalArgumentException("documentCount must not be negative");
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
