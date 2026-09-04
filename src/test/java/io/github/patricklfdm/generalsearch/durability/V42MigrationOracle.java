package io.github.patricklfdm.generalsearch.durability;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/** Independent logical migration model; it never calls production storage code. */
final class V42MigrationOracle {
    private static final byte[] SOURCE_DOMAIN =
            "gse-v42-source-authority-model-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] PROJECTION_DOMAIN =
            "gse-migration-projection-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] PLAN_DOMAIN =
            "gse-migration-plan-v1\0".getBytes(StandardCharsets.US_ASCII);

    record Format(String family, int major, int minor) {
        Format {
            Objects.requireNonNull(family, "family");
            if (!family.equals("gse-durable") || major != 1 || minor < 0) {
                throw new IllegalArgumentException("invalid model format");
            }
        }
    }

    record SourceRecord(long slot, String key, String document) {
        SourceRecord {
            Objects.requireNonNull(key, "key");
            Objects.requireNonNull(document, "document");
            if (slot < 0) {
                throw new IllegalArgumentException("negative source slot");
            }
        }
    }

    record SourceState(
            Format format,
            UUID history,
            long sequence,
            long nextDocId,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            String transformIdentity,
            int transformVersion,
            List<String> indexes,
            List<SourceRecord> records
    ) {
        SourceState {
            Objects.requireNonNull(format, "format");
            Objects.requireNonNull(history, "history");
            Objects.requireNonNull(storageIdentity, "storageIdentity");
            Objects.requireNonNull(schemaIdentity, "schemaIdentity");
            Objects.requireNonNull(codecIdentity, "codecIdentity");
            Objects.requireNonNull(transformIdentity, "transformIdentity");
            indexes = List.copyOf(indexes);
            records = List.copyOf(records);
            if (history.equals(new UUID(0, 0)) || sequence < 0 || nextDocId < 0
                    || codecVersion < 0 || transformVersion < 0) {
                throw new IllegalArgumentException("invalid source authority");
            }
            long previous = -1;
            for (SourceRecord record : records) {
                if (record.slot() <= previous || record.slot() >= nextDocId) {
                    throw new IllegalArgumentException("source slots are not canonical");
                }
                previous = record.slot();
            }
        }
    }

    record TransformDescriptor(String identifier, int version) {
        TransformDescriptor {
            Objects.requireNonNull(identifier, "identifier");
            if (!identifier.matches("[a-z0-9][a-z0-9-]{0,127}") || version < 0) {
                throw new IllegalArgumentException("invalid transform descriptor");
            }
        }
    }

    record TargetRecord(long slot, String key, String document, String extractedKey) {
        TargetRecord {
            Objects.requireNonNull(key, "key");
            Objects.requireNonNull(document, "document");
            Objects.requireNonNull(extractedKey, "extractedKey");
        }
    }

    @FunctionalInterface
    interface Transform {
        TargetRecord transform(SourceRecord source);
    }

    record TargetDescriptor(
            Format format,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            List<String> indexes
    ) {
        TargetDescriptor {
            Objects.requireNonNull(format, "format");
            Objects.requireNonNull(storageIdentity, "storageIdentity");
            Objects.requireNonNull(schemaIdentity, "schemaIdentity");
            Objects.requireNonNull(codecIdentity, "codecIdentity");
            indexes = List.copyOf(indexes);
            if (codecVersion < 0) {
                throw new IllegalArgumentException("negative target codec version");
            }
        }
    }

    record Plan(
            SourceState source,
            TargetDescriptor target,
            UUID targetHistory,
            TransformDescriptor transform,
            List<TargetRecord> projection,
            String sourceAuthorityIdentity,
            String projectionDigest,
            String planDigest
    ) {
        Plan {
            projection = List.copyOf(projection);
        }
    }

    record Result(
            UUID sourceHistory,
            UUID targetHistory,
            long sequence,
            long nextDocId,
            List<TargetRecord> records,
            String sourceAuthorityIdentity,
            String projectionDigest,
            String planDigest
    ) {
        Result {
            records = List.copyOf(records);
        }
    }

    Plan plan(SourceState source, TargetDescriptor target, UUID targetHistory,
              TransformDescriptor descriptor, Transform transform) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(target, "target");
        Objects.requireNonNull(targetHistory, "targetHistory");
        Objects.requireNonNull(descriptor, "descriptor");
        Objects.requireNonNull(transform, "transform");
        requireEdge(source, target, descriptor);
        if (targetHistory.equals(new UUID(0, 0)) || targetHistory.equals(source.history())) {
            throw new IllegalArgumentException("target history must be distinct and non-zero");
        }
        if (source.sequence() == Long.MAX_VALUE || source.nextDocId() == Long.MAX_VALUE) {
            throw new IllegalStateException("source cannot continue at sequence or nextDocId");
        }
        List<TargetRecord> projection = project(source, transform);
        String sourceIdentity = sourceAuthorityIdentity(source);
        String projectionIdentity = projectionDigest(
                source, target, targetHistory, descriptor, projection);
        String planIdentity = planDigest(
                sourceIdentity, projectionIdentity, targetHistory, descriptor);
        return new Plan(source, target, targetHistory, descriptor, projection,
                sourceIdentity, projectionIdentity, planIdentity);
    }

    Result apply(SourceState source, Plan plan, Transform transform) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(plan, "plan");
        Objects.requireNonNull(transform, "transform");
        String sourceIdentity = sourceAuthorityIdentity(source);
        if (!source.equals(plan.source())
                || !sourceIdentity.equals(plan.sourceAuthorityIdentity())) {
            throw new IllegalStateException("plan stale: source authority changed");
        }
        List<TargetRecord> projection = project(source, transform);
        String projectionIdentity = projectionDigest(
                source, plan.target(), plan.targetHistory(), plan.transform(), projection);
        if (!projection.equals(plan.projection())
                || !projectionIdentity.equals(plan.projectionDigest())) {
            throw new IllegalStateException("transform non-deterministic");
        }
        String recomputedPlan = planDigest(sourceIdentity, projectionIdentity,
                plan.targetHistory(), plan.transform());
        if (!recomputedPlan.equals(plan.planDigest())) {
            throw new IllegalStateException("plan digest mismatch");
        }
        return new Result(source.history(), plan.targetHistory(), source.sequence(),
                source.nextDocId(), projection, sourceIdentity, projectionIdentity,
                recomputedPlan);
    }

    private static void requireEdge(SourceState source, TargetDescriptor target,
                                    TransformDescriptor descriptor) {
        if (source.format().major() != 1 || target.format().major() != 1
                || target.format().minor() != 1) {
            throw new IllegalArgumentException("migration path unsupported");
        }
        if (source.format().minor() == 0) {
            return;
        }
        if (source.format().minor() != 1) {
            throw new IllegalArgumentException("migration path unsupported");
        }
        boolean changed = !source.storageIdentity().equals(target.storageIdentity())
                || !source.schemaIdentity().equals(target.schemaIdentity())
                || !source.codecIdentity().equals(target.codecIdentity())
                || source.codecVersion() != target.codecVersion()
                || !source.transformIdentity().equals(descriptor.identifier())
                || source.transformVersion() != descriptor.version()
                || !source.indexes().equals(target.indexes());
        if (!changed) {
            throw new IllegalArgumentException("migration not required");
        }
    }

    private static List<TargetRecord> project(SourceState source, Transform transform) {
        List<TargetRecord> output = new ArrayList<>(source.records().size());
        Set<String> keys = new HashSet<>();
        for (SourceRecord record : source.records()) {
            TargetRecord target;
            try {
                target = transform.transform(record);
            } catch (RuntimeException failure) {
                throw new IllegalArgumentException("transform failed", failure);
            }
            if (target == null || target.slot() != record.slot()) {
                throw new IllegalArgumentException("transform cardinality or slot mismatch");
            }
            if (!target.key().equals(target.extractedKey())) {
                throw new IllegalArgumentException("target business key mismatch");
            }
            if (!keys.add(target.key())) {
                throw new IllegalArgumentException("target key collision");
            }
            output.add(target);
        }
        return List.copyOf(output);
    }

    private static String sourceAuthorityIdentity(SourceState source) {
        MessageDigest digest = digest(SOURCE_DOMAIN);
        update(digest, source.format().family());
        update(digest, source.format().major());
        update(digest, source.format().minor());
        update(digest, source.history().toString());
        update(digest, source.sequence());
        update(digest, source.nextDocId());
        update(digest, source.storageIdentity());
        update(digest, source.schemaIdentity());
        update(digest, source.codecIdentity());
        update(digest, source.codecVersion());
        update(digest, source.transformIdentity());
        update(digest, source.transformVersion());
        source.indexes().forEach(value -> update(digest, value));
        for (SourceRecord record : source.records()) {
            update(digest, record.slot());
            update(digest, record.key());
            update(digest, record.document());
        }
        return "gse-v42-source-authority-model-v1-"
                + HexFormat.of().formatHex(digest.digest());
    }

    private static String projectionDigest(
            SourceState source,
            TargetDescriptor target,
            UUID targetHistory,
            TransformDescriptor transform,
            List<TargetRecord> records
    ) {
        MessageDigest digest = digest(PROJECTION_DOMAIN);
        update(digest, targetHistory.toString());
        update(digest, source.sequence());
        update(digest, source.nextDocId());
        update(digest, target.format().family());
        update(digest, target.format().major());
        update(digest, target.format().minor());
        update(digest, target.storageIdentity());
        update(digest, target.schemaIdentity());
        update(digest, target.codecIdentity());
        update(digest, target.codecVersion());
        target.indexes().forEach(value -> update(digest, value));
        update(digest, transform.identifier());
        update(digest, transform.version());
        for (TargetRecord record : records) {
            update(digest, record.slot());
            update(digest, record.key());
            update(digest, record.document());
        }
        return "gse-migration-projection-v1-"
                + HexFormat.of().formatHex(digest.digest());
    }

    private static String planDigest(String sourceIdentity, String projectionIdentity,
                                     UUID targetHistory, TransformDescriptor transform) {
        MessageDigest digest = digest(PLAN_DOMAIN);
        update(digest, sourceIdentity);
        update(digest, projectionIdentity);
        update(digest, targetHistory.toString());
        update(digest, transform.identifier());
        update(digest, transform.version());
        return "gse-migration-plan-v1-" + HexFormat.of().formatHex(digest.digest());
    }

    private static MessageDigest digest(byte[] domain) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(domain);
            return digest;
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void update(MessageDigest digest, long value) {
        update(digest, Long.toString(value));
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        digest.update((byte) (bytes.length >>> 24));
        digest.update((byte) (bytes.length >>> 16));
        digest.update((byte) (bytes.length >>> 8));
        digest.update((byte) bytes.length);
        digest.update(bytes);
    }
}
