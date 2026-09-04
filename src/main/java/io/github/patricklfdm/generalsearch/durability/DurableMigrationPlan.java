package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;

/** Immutable source/configuration/projection authority for one offline migration. */
public record DurableMigrationPlan(
        int schemaVersion,
        Path sourceDirectory,
        Path targetDirectory,
        DurableStorageFormat sourceFormat,
        DurableStorageFormat targetFormat,
        UUID sourceHistory,
        UUID targetHistory,
        long sourceSequence,
        long nextDocId,
        List<DurableMigrationSourceMember> sourceMembers,
        String sourceAuthorityIdentity,
        String sourceDescriptorDigest,
        String targetDescriptorDigest,
        DurableMigrationTransformDescriptor transformDescriptor,
        int documentCount,
        int sourceIndexCount,
        int targetIndexCount,
        DurableMigrationIndexChange indexChange,
        long targetAuthoritativeBytes,
        long peakTargetBytes,
        long capacitySafetyReserveBytes,
        String projectionDigest,
        String planDigest
) {
    private static final UUID ZERO = new UUID(0, 0);
    private static final Pattern HEX_IDENTITY = Pattern.compile(
            "[a-z0-9][a-z0-9-]{0,127}-[a-f0-9]{64}");

    public DurableMigrationPlan {
        if (schemaVersion != 1) {
            throw new IllegalArgumentException("schemaVersion must be 1");
        }
        sourceDirectory = normalized(sourceDirectory, "sourceDirectory");
        targetDirectory = normalized(targetDirectory, "targetDirectory");
        sourceFormat = Objects.requireNonNull(sourceFormat, "sourceFormat");
        targetFormat = Objects.requireNonNull(targetFormat, "targetFormat");
        sourceHistory = history(sourceHistory, "sourceHistory");
        targetHistory = history(targetHistory, "targetHistory");
        if (sourceHistory.equals(targetHistory)) {
            throw new IllegalArgumentException("target history must be fresh");
        }
        if (sourceSequence < 0 || nextDocId < 0 || documentCount < 0
                || sourceIndexCount < 0 || targetIndexCount < 0
                || targetAuthoritativeBytes < 0 || capacitySafetyReserveBytes <= 0) {
            throw new IllegalArgumentException("negative migration plan value");
        }
        if (documentCount > nextDocId) {
            throw new IllegalArgumentException(
                    "documentCount must not exceed nextDocId");
        }
        sourceMembers = canonicalMembers(sourceMembers);
        sourceAuthorityIdentity = identity(sourceAuthorityIdentity,
                "sourceAuthorityIdentity");
        sourceDescriptorDigest = identity(sourceDescriptorDigest,
                "sourceDescriptorDigest");
        targetDescriptorDigest = identity(targetDescriptorDigest,
                "targetDescriptorDigest");
        transformDescriptor = Objects.requireNonNull(
                transformDescriptor, "transformDescriptor");
        indexChange = Objects.requireNonNull(indexChange, "indexChange");
        projectionDigest = identity(projectionDigest, "projectionDigest");
        planDigest = identity(planDigest, "planDigest");
        if (Math.addExact(targetAuthoritativeBytes, capacitySafetyReserveBytes)
                > peakTargetBytes) {
            throw new IllegalArgumentException(
                    "peakTargetBytes must include the capacity reserve");
        }
    }

    private static Path normalized(Path path, String name) {
        Path value = Objects.requireNonNull(path, name);
        Path normalized = value.toAbsolutePath().normalize();
        if (!value.equals(normalized)) {
            throw new IllegalArgumentException(name + " must be normalized and absolute");
        }
        return normalized;
    }

    private static UUID history(UUID value, String name) {
        Objects.requireNonNull(value, name);
        if (value.equals(ZERO)) {
            throw new IllegalArgumentException(name + " must be non-zero");
        }
        return value;
    }

    private static String identity(String value, String name) {
        Objects.requireNonNull(value, name);
        if (!HEX_IDENTITY.matcher(value).matches()) {
            throw new IllegalArgumentException(name + " is not canonical");
        }
        return value;
    }

    private static List<DurableMigrationSourceMember> canonicalMembers(
            List<DurableMigrationSourceMember> members) {
        Objects.requireNonNull(members, "sourceMembers");
        List<DurableMigrationSourceMember> copy = List.copyOf(members);
        String previous = null;
        HashSet<String> names = new HashSet<>();
        for (DurableMigrationSourceMember member : copy) {
            Objects.requireNonNull(member, "sourceMembers entry");
            if (!names.add(member.name())
                    || (previous != null && previous.compareTo(member.name()) >= 0)) {
                throw new IllegalArgumentException(
                        "sourceMembers must be sorted and unique");
            }
            previous = member.name();
        }
        return java.util.Collections.unmodifiableList(new ArrayList<>(copy));
    }
}
