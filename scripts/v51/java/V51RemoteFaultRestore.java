package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.query.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.Map;

/** Separately compiled against the pinned published V4.4 core. */
public final class V51RemoteFaultRestore {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);
        var app=builder().plannerConfig(new PlannerConfig(RangePlanningMode.FORCE_SCAN))
                .config(new SnapshotEngineConfig(31,16,Duration.ofNanos(1234567)));
        var storage=DurableStorageConfig.builder(root.resolve("restored"),new Codec())
                .format(new DurableStorageFormat("gse-durable",1,2))
                .storageIdentity("public-runtime-store").schemaIdentity("public-runtime-schema")
                .maxDocuments(1024).maxBulkElements(16).maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(4096)
                .checkpointWalBytes(32L<<20).maxRetainedBytes(128L<<20).maxDerivedStateBytes(4L<<20).build();
        app.restoreDurableBackup(root.resolve("backup"),storage);
        try(var engine=app.buildDurable(storage)) {
            System.out.println(AdmissionJson.canonical(Map.of("sequence",engine.currentSequence(),
                    "coreSource",Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString(),
                    "documents",engine.search(d->true).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList())));
        }
    }
}
