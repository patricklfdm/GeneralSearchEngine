package io.github.patricklfdm.generalsearch.durability;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

/** Immutable codec-free report for one catalog-referenced derived component. */
public record DurableDerivedComponentReport(
        int ordinal,
        String indexName,
        String indexKind,
        DurableDerivedComponentStatus status,
        long bytes,
        Optional<String> sha256,
        List<DurableDerivedFinding> findings
) {
    private static final Pattern KIND = Pattern.compile("[a-z][a-z0-9-]{0,63}");
    private static final Pattern SHA256 = Pattern.compile("[a-f0-9]{64}");

    /** Validates ordering-independent component values and freezes collections. */
    public DurableDerivedComponentReport {
        if (ordinal < 0 || ordinal >= 100_000) {
            throw new IllegalArgumentException("ordinal is outside its bound");
        }
        indexName = bounded(indexName, "indexName", 1024 * 1024);
        indexKind = Objects.requireNonNull(indexKind, "indexKind");
        status = Objects.requireNonNull(status, "status");
        sha256 = Objects.requireNonNull(sha256, "sha256");
        findings = List.copyOf(Objects.requireNonNull(findings, "findings"));
        if (!KIND.matcher(indexKind).matches()) {
            throw new IllegalArgumentException("indexKind is not a stable identifier");
        }
        if (bytes < 0 || bytes > 2L * 1024 * 1024 * 1024) {
            throw new IllegalArgumentException("bytes is outside its bound");
        }
        sha256.ifPresent(value -> {
            if (!SHA256.matcher(value).matches()) {
                throw new IllegalArgumentException("sha256 must be lowercase hexadecimal");
            }
        });
        if (findings.size() > 100_000
                || !findings.stream().sorted(DurableDerivedFinding.CANONICAL_ORDER)
                        .toList().equals(findings)) {
            throw new IllegalArgumentException("findings must be bounded and canonical");
        }
        if ((status == DurableDerivedComponentStatus.ADMISSIBLE
                && (bytes == 0 || sha256.isEmpty() || !findings.isEmpty()))
                || (status == DurableDerivedComponentStatus.MISSING
                        && (bytes != 0 || sha256.isPresent()))
                || (status != DurableDerivedComponentStatus.ADMISSIBLE
                        && findings.isEmpty())) {
            throw new IllegalArgumentException(
                    "component status, evidence and findings are inconsistent");
        }
    }

    private static String bounded(String value, String name, int maximum) {
        Objects.requireNonNull(value, name);
        if (value.isEmpty() || value.length() > maximum
                || value.indexOf('\n') >= 0 || value.indexOf('\r') >= 0) {
            throw new IllegalArgumentException(name + " is outside its bound");
        }
        return value;
    }
}
