package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/** Immutable codec-free inventory and classification for optional derived state. */
public record DurableDerivedStateReport(
        Path directory,
        DurableDerivedStateStatus status,
        Optional<DurableStorageFormat> declaredFormat,
        Optional<UUID> history,
        OptionalLong checkpointSequence,
        Optional<String> catalogIdentity,
        int expectedComponentCount,
        int referencedComponentCount,
        int admissibleComponentCount,
        int rejectedComponentCount,
        long referencedBytes,
        long admissibleBytes,
        long rejectedBytes,
        long stagingBytes,
        long unreferencedBytes,
        List<DurableDerivedComponentReport> components,
        List<DurableDerivedFinding> findings
) {
    private static final Pattern IDENTITY = Pattern.compile(
            "gse-derived-catalog-v1-[a-f0-9]{64}");

    /** Normalizes paths, freezes collections and enforces aggregate invariants. */
    public DurableDerivedStateReport {
        directory = Objects.requireNonNull(directory, "directory")
                .toAbsolutePath().normalize();
        status = Objects.requireNonNull(status, "status");
        declaredFormat = Objects.requireNonNull(declaredFormat, "declaredFormat");
        history = Objects.requireNonNull(history, "history");
        checkpointSequence = Objects.requireNonNull(
                checkpointSequence, "checkpointSequence");
        catalogIdentity = Objects.requireNonNull(catalogIdentity, "catalogIdentity");
        components = List.copyOf(Objects.requireNonNull(components, "components"));
        findings = List.copyOf(Objects.requireNonNull(findings, "findings"));
        history.ifPresent(value -> {
            if (value.equals(new UUID(0L, 0L))) {
                throw new IllegalArgumentException("history must not be zero");
            }
        });
        if (checkpointSequence.isPresent() && checkpointSequence.getAsLong() < 0) {
            throw new IllegalArgumentException("checkpointSequence must not be negative");
        }
        catalogIdentity.ifPresent(value -> {
            if (!IDENTITY.matcher(value).matches()) {
                throw new IllegalArgumentException("catalogIdentity is invalid");
            }
        });
        if (expectedComponentCount < 0 || expectedComponentCount > 100_000
                || referencedComponentCount < 0
                || referencedComponentCount > expectedComponentCount
                || admissibleComponentCount < 0
                || rejectedComponentCount < 0
                || admissibleComponentCount + (long) rejectedComponentCount
                        != referencedComponentCount
                || components.size() != referencedComponentCount) {
            throw new IllegalArgumentException("component counts are inconsistent");
        }
        if (referencedBytes < 0 || admissibleBytes < 0 || rejectedBytes < 0
                || stagingBytes < 0 || unreferencedBytes < 0
                || admissibleBytes + rejectedBytes != referencedBytes) {
            throw new IllegalArgumentException("byte counts are inconsistent");
        }
        Set<Integer> ordinals = new HashSet<>();
        int previous = -1;
        int observedAdmissible = 0;
        long observedReferencedBytes = 0;
        long observedAdmissibleBytes = 0;
        for (DurableDerivedComponentReport component : components) {
            if (!ordinals.add(component.ordinal()) || component.ordinal() <= previous) {
                throw new IllegalArgumentException(
                        "components must have strictly increasing unique ordinals");
            }
            previous = component.ordinal();
            observedReferencedBytes = Math.addExact(
                    observedReferencedBytes, component.bytes());
            if (component.status() == DurableDerivedComponentStatus.ADMISSIBLE) {
                observedAdmissible++;
                observedAdmissibleBytes = Math.addExact(
                        observedAdmissibleBytes, component.bytes());
            }
        }
        if (observedAdmissible != admissibleComponentCount
                || observedReferencedBytes != referencedBytes
                || observedAdmissibleBytes != admissibleBytes) {
            throw new IllegalArgumentException(
                    "component reports disagree with aggregate counts or bytes");
        }
        if ((status == DurableDerivedStateStatus.NOT_APPLICABLE
                    && (expectedComponentCount != 0 || referencedComponentCount != 0))
                || (status == DurableDerivedStateStatus.ABSENT
                    && referencedComponentCount != 0)
                || (status == DurableDerivedStateStatus.VALID
                    && (expectedComponentCount != referencedComponentCount
                        || admissibleComponentCount != expectedComponentCount))
                || (status == DurableDerivedStateStatus.PARTIAL
                    && (admissibleComponentCount == 0
                        || admissibleComponentCount >= expectedComponentCount))) {
            throw new IllegalArgumentException(
                    "derived status disagrees with aggregate component state");
        }
        if (findings.size() > 100_000
                || !findings.stream().sorted(DurableDerivedFinding.CANONICAL_ORDER)
                        .toList().equals(findings)) {
            throw new IllegalArgumentException("findings must be bounded and canonical");
        }
        long text = 0;
        for (DurableDerivedFinding finding : findings) {
            text = Math.addExact(text, finding.code().length());
            text = Math.addExact(text, finding.member().length());
            text = Math.addExact(text, finding.detail().length());
        }
        for (DurableDerivedComponentReport component : components) {
            for (DurableDerivedFinding finding : component.findings()) {
                text = Math.addExact(text, finding.code().length());
                text = Math.addExact(text, finding.member().length());
                text = Math.addExact(text, finding.detail().length());
            }
        }
        if (text > 1024 * 1024) {
            throw new IllegalArgumentException("diagnostic text exceeds one MiB");
        }
    }
}
