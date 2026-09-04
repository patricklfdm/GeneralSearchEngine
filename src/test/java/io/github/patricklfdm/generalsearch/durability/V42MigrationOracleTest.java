package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class V42MigrationOracleTest {
    private static final V42MigrationOracle.Format V1_0 =
            new V42MigrationOracle.Format("gse-durable", 1, 0);
    private static final V42MigrationOracle.Format V1_1 =
            new V42MigrationOracle.Format("gse-durable", 1, 1);
    private static final UUID TARGET =
            UUID.fromString("42000000-0000-4000-8000-000000000011");
    private final V42MigrationOracle oracle = new V42MigrationOracle();

    @Test
    void formatMigrationPreservesSlotsSequenceNextDocIdAndSource() {
        V42MigrationOracle.SourceState source = source(V1_0);
        V42MigrationOracle.SourceState before = source;
        V42MigrationOracle.Plan plan = oracle.plan(
                source, target(), TARGET, descriptor(), this::identity);
        V42MigrationOracle.Result result = oracle.apply(source, plan, this::identity);

        assertEquals(before, source);
        assertEquals(source.history(), result.sourceHistory());
        assertNotEquals(source.history(), result.targetHistory());
        assertEquals(source.sequence(), result.sequence());
        assertEquals(source.nextDocId(), result.nextDocId());
        assertEquals(List.of(0L, 3L), result.records().stream()
                .map(V42MigrationOracle.TargetRecord::slot).toList());
        assertTrue(result.sourceAuthorityIdentity()
                .startsWith("gse-v42-source-authority-model-v1-"));
        assertTrue(result.projectionDigest()
                .startsWith("gse-migration-projection-v1-"));
        assertTrue(result.planDigest().startsWith("gse-migration-plan-v1-"));
    }

    @Test
    void declaredSchemaKeyCodecAndIndexChangesRemainOneToOne() {
        V42MigrationOracle.SourceState source = source(V1_0);
        V42MigrationOracle.TargetDescriptor catalog =
                new V42MigrationOracle.TargetDescriptor(
                        V1_1, "catalog-v2", "product-v2", "binary-catalog", 2,
                        List.of("category:prefix", "name:text"));
        V42MigrationOracle.TransformDescriptor descriptor =
                new V42MigrationOracle.TransformDescriptor(
                        "catalog-schema-key-v1", 1);
        V42MigrationOracle.Transform transform = record -> {
            String key = "sku-" + record.key();
            return new V42MigrationOracle.TargetRecord(
                    record.slot(), key,
                    record.document().toUpperCase(Locale.ROOT), key);
        };

        V42MigrationOracle.Plan plan = oracle.plan(
                source, catalog, TARGET, descriptor, transform);
        V42MigrationOracle.Result result = oracle.apply(source, plan, transform);

        assertEquals(List.of("sku-alpha", "sku-beta"), result.records().stream()
                .map(V42MigrationOracle.TargetRecord::key).toList());
        assertEquals(List.of("RED APPLE", "BLUE BERRY"), result.records().stream()
                .map(V42MigrationOracle.TargetRecord::document).toList());
        assertEquals(List.of(0L, 3L), result.records().stream()
                .map(V42MigrationOracle.TargetRecord::slot).toList());
        assertEquals(source, plan.source());
    }

    @Test
    void sameFormatIndexChangeIsEligibleWithoutRecordByteChange() {
        V42MigrationOracle.SourceState source = source(V1_1);
        V42MigrationOracle.TargetDescriptor changedIndexes =
                new V42MigrationOracle.TargetDescriptor(
                        V1_1, "catalog", "product-v1", "utf8-json", 1,
                        List.of("category:prefix", "name:text"));
        V42MigrationOracle.Plan plan = oracle.plan(
                source, changedIndexes, TARGET, descriptor(), this::identity);

        assertEquals(source.records(), oracle.apply(source, plan, this::identity)
                .records().stream()
                .map(record -> new V42MigrationOracle.SourceRecord(
                        record.slot(), record.key(), record.document()))
                .toList());
    }

    @Test
    void applyRejectsChangedSourceAndChangedProjection() {
        V42MigrationOracle.SourceState source = source(V1_0);
        V42MigrationOracle.Plan plan = oracle.plan(
                source, target(), TARGET, descriptor(), this::identity);
        V42MigrationOracle.SourceState changed = new V42MigrationOracle.SourceState(
                source.format(), source.history(), source.sequence() + 1,
                source.nextDocId(), source.storageIdentity(), source.schemaIdentity(),
                source.codecIdentity(), source.codecVersion(), source.transformIdentity(),
                source.transformVersion(), source.indexes(),
                source.records());

        assertThrows(IllegalStateException.class,
                () -> oracle.apply(changed, plan, this::identity));
        assertThrows(IllegalStateException.class, () -> oracle.apply(
                source, plan, record -> new V42MigrationOracle.TargetRecord(
                        record.slot(), record.key(), record.document() + "-changed",
                        record.key())));
    }

    @Test
    void transformCollisionKeyMismatchAndInvocationDriftFailClosed() {
        V42MigrationOracle.SourceState source = source(V1_0);
        assertThrows(IllegalArgumentException.class, () -> oracle.plan(
                source, target(), TARGET, descriptor(), record ->
                        new V42MigrationOracle.TargetRecord(
                                record.slot(), "same", record.document(), "same")));
        assertThrows(IllegalArgumentException.class, () -> oracle.plan(
                source, target(), TARGET, descriptor(), record ->
                        new V42MigrationOracle.TargetRecord(
                                record.slot(), record.key(), record.document(), "other")));

        AtomicInteger invocations = new AtomicInteger();
        V42MigrationOracle.Transform drifting = record ->
                new V42MigrationOracle.TargetRecord(
                        record.slot(), record.key(),
                        record.document() + "-" + invocations.incrementAndGet(),
                        record.key());
        V42MigrationOracle.Plan plan = oracle.plan(
                source, target(), TARGET, descriptor(), drifting);
        assertThrows(IllegalStateException.class,
                () -> oracle.apply(source, plan, drifting));
    }

    @Test
    void onlyFrozenEdgesAndWritableSourceAreEligible() {
        assertThrows(IllegalArgumentException.class, () -> oracle.plan(
                source(V1_1), sameTarget(), TARGET, descriptor(), this::identity));
        V42MigrationOracle.SourceState exhausted = new V42MigrationOracle.SourceState(
                V1_0, source(V1_0).history(), Long.MAX_VALUE, 5,
                "catalog", "product-v1", "utf8-json", 1,
                "source-origin-v1", 0,
                List.of("name:text"), List.of());
        assertThrows(IllegalStateException.class, () -> oracle.plan(
                exhausted, target(), TARGET, descriptor(), this::identity));
    }

    private V42MigrationOracle.TargetRecord identity(
            V42MigrationOracle.SourceRecord record) {
        return new V42MigrationOracle.TargetRecord(
                record.slot(), record.key(), record.document(), record.key());
    }

    private static V42MigrationOracle.TransformDescriptor descriptor() {
        return new V42MigrationOracle.TransformDescriptor("identity-format-v1", 1);
    }

    private static V42MigrationOracle.SourceState source(V42MigrationOracle.Format format) {
        return new V42MigrationOracle.SourceState(
                format,
                UUID.fromString("41000000-0000-4000-8000-000000000010"),
                17,
                5,
                "catalog",
                "product-v1",
                "utf8-json",
                1,
                format.equals(V1_1) ? "identity-format-v1" : "source-origin-v1",
                format.equals(V1_1) ? 1 : 0,
                List.of("name:text"),
                List.of(
                        new V42MigrationOracle.SourceRecord(0, "alpha", "red apple"),
                        new V42MigrationOracle.SourceRecord(3, "beta", "blue berry")));
    }

    private static V42MigrationOracle.TargetDescriptor target() {
        return new V42MigrationOracle.TargetDescriptor(
                V1_1, "catalog", "product-v1", "utf8-json", 1,
                List.of("name:text"));
    }

    private static V42MigrationOracle.TargetDescriptor sameTarget() {
        return new V42MigrationOracle.TargetDescriptor(
                V1_1, "catalog", "product-v1", "utf8-json", 1,
                List.of("name:text"));
    }
}
