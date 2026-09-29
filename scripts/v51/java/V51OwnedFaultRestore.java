package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.query.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.Map;

/** Separately compiled against the pinned published V4.4 core. */
public final class V51OwnedFaultRestore {
    public record Doc(int id,String value) { }
    static final Field<Doc,Integer> ID=Field.of("id",Integer.class,Doc::id);
    static final Field<Doc,String> VALUE=Field.of("value",String.class,Doc::value);
    static SearchEngineBuilder<Integer,Doc> builder(){return SearchEngine.builder(Doc.class,ID).index(IndexDefinition.equality(VALUE));}
    static final class Codec implements DurableCodec<Integer,Doc> {
        public String codecId(){return "public-runtime-codec";}public int codecVersion(){return 1;}
        public byte[] encodeKey(Integer id){return ByteBuffer.allocate(4).putInt(id).array();}
        public Integer decodeKey(byte[] bytes){return ByteBuffer.wrap(bytes).getInt();}
        public byte[] encodeDocument(Doc doc){byte[] value=doc.value().getBytes(StandardCharsets.UTF_8);return ByteBuffer.allocate(4+value.length).putInt(doc.id()).put(value).array();}
        public Doc decodeDocument(byte[] bytes){return new Doc(ByteBuffer.wrap(bytes).getInt(),new String(bytes,4,bytes.length-4,StandardCharsets.UTF_8));}
    }
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
