package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53ApplicationImageTest {
    @TempDir Path temp;
    static final UUID HISTORY=UUID.fromString("11111111-2222-3333-4444-555555555555");
    static final TextField<Doc> TEXT=TextField.of(VALUE,SimpleAnalyzer.INSTANCE);
    static SearchEngineConfiguration<Integer,Doc> config(){return SearchEngine.builder(Doc.class,ID).index(IndexDefinition.text(TEXT)).configuration();}
    static DurableApplicationState<Doc> state(long sequence,List<IndexDefinition<Doc>> indexes) {
        return new DurableApplicationState<>(HISTORY,sequence,List.of(new Doc(7,"你好"),new Doc(2,"two")),indexes);
    }
    Map<String,String> inventory(Path directory)throws Exception {
        var result=new TreeMap<String,String>();try(var paths=Files.walk(directory)) {
            for(var p:paths.filter(Files::isRegularFile).toList())result.put(directory.relativize(p).toString(),MembershipFormat.hash(Files.readAllBytes(p)));
        }return result;
    }
    @Test void identicalRealExportsHaveIdenticalImagesAndRetainExactCorePayloads()throws Exception {
        for(int minor:List.of(0,1,2)) {
            var storage=storage(temp.resolve("anchor-"+minor),minor);var state=state(41,List.of(IndexDefinition.prefix(VALUE),IndexDefinition.range(ID)));
            Path first=temp.resolve("first-"+minor),second=temp.resolve("second-"+minor);
            byte[] a=MembershipApplicationImage.capture(config(),storage,state,first),b=MembershipApplicationImage.capture(config(),storage,state,second);
            assertFalse(Arrays.equals(Files.readAllBytes(first.resolve("gse-backup-manifest")),Files.readAllBytes(second.resolve("gse-backup-manifest"))));
            assertArrayEquals(a,b);var original=inventory(first);var members=MembershipApplicationImage.unpack(a);
            assertArrayEquals(Files.readAllBytes(first.resolve("gse-backup-checkpoint")),members.get(0));
            assertArrayEquals(Files.readAllBytes(first.resolve("gse-backup-metadata")),members.get(2));
            assertArrayEquals(a,MembershipApplicationImage.fromBackup(config(),storage,first));assertEquals(original,inventory(first));
            var loaded=MembershipApplicationImage.read(config(),storage,a,temp.resolve("read-"+minor));
            assertEquals(HISTORY,loaded.history());assertEquals(41,loaded.sequence());assertEquals(state.documents(),loaded.documents());
            assertEquals(state.indexes().stream().map(ReplicaApplication::descriptor).toList(),loaded.indexes().stream().map(ReplicaApplication::descriptor).toList());
            assertArrayEquals(a,MembershipApplicationImage.capture(config(),storage,loaded,temp.resolve("recapture-"+minor)));
            assertFalse(Files.exists(storage.directory()));
        }
    }
    @Test void fullBytesBindHistorySequenceDocumentOrderAndActiveIndexes()throws Exception {
        var storage=storage(temp.resolve("anchor"),2);var input=state(41,List.of(IndexDefinition.prefix(VALUE)));
        var variants=List.of(input,new DurableApplicationState<>(HISTORY,42,input.documents(),input.indexes()),
                new DurableApplicationState<>(new UUID(1,9),41,input.documents(),input.indexes()),
                new DurableApplicationState<>(HISTORY,41,input.documents().reversed(),input.indexes()),
                state(41,List.of(IndexDefinition.text(TEXT))),state(41,List.of()),state(Long.MAX_VALUE,List.of(IndexDefinition.range(ID))));
        var hashes=new HashSet<String>();int n=0;
        for(var variant:variants) {
            byte[] bytes=MembershipApplicationImage.capture(config(),storage,variant,temp.resolve("backup-"+n));
            assertTrue(hashes.add(MembershipFormat.hash(bytes)));var loaded=MembershipApplicationImage.read(config(),storage,bytes,temp.resolve("read-"+n++));
            assertEquals(variant.history(),loaded.history());assertEquals(variant.sequence(),loaded.sequence());assertEquals(variant.documents(),loaded.documents());
        }
    }
    @Test void rejectsHostileFramingAndNoncanonicalManifestBeforeCreatingScratch()throws Exception {
        var storage=storage(temp.resolve("anchor"),2);byte[] bytes=MembershipApplicationImage.capture(config(),storage,state(41,List.of()),temp.resolve("backup"));
        var corrupt=new ArrayList<byte[]>();corrupt.add(new byte[1]);corrupt.add(Arrays.copyOf(bytes,bytes.length-1));corrupt.add(Arrays.copyOf(bytes,bytes.length+1));
        for(int offset:List.of(0,4,6,8,12)) {byte[] altered=bytes.clone();altered[offset]^=1;corrupt.add(altered);}
        byte[] huge=bytes.clone();ByteBuffer.wrap(huge).putInt(12,Integer.MAX_VALUE);corrupt.add(huge);
        var members=new ArrayList<>(MembershipApplicationImage.unpack(bytes));byte[] manifest=members.get(1).clone();
        ByteBuffer.wrap(manifest).putLong(manifest.length-16,123);crc(manifest);members.set(1,manifest);corrupt.add(MembershipApplicationImage.pack(members));
        members=new ArrayList<>(MembershipApplicationImage.unpack(bytes));manifest=members.get(1).clone();manifest[0]^=1;members.set(1,manifest);corrupt.add(MembershipApplicationImage.pack(members));
        int n=0;for(byte[] invalid:corrupt) {Path scratch=temp.resolve("bad-"+n++);assertThrows(Exception.class,()->MembershipApplicationImage.read(config(),storage,invalid,scratch));assertFalse(Files.exists(scratch));}
    }
    @Test void rejectsChangedCheckpointAndIdentityUsingTheExistingSemanticVerifier()throws Exception {
        var storage=storage(temp.resolve("anchor"),2);byte[] bytes=MembershipApplicationImage.capture(config(),storage,state(41,List.of()),temp.resolve("backup"));
        var members=new ArrayList<>(MembershipApplicationImage.unpack(bytes));byte[] damaged=members.get(0).clone();damaged[damaged.length-1]^=1;members.set(0,damaged);
        assertThrows(DurableOperationException.class,()->MembershipApplicationImage.read(config(),storage,MembershipApplicationImage.pack(members),temp.resolve("bad-checkpoint")));
        var wrong=DurableStorageConfig.builder(temp.resolve("wrong-anchor"),new Codec()).storageIdentity("wrong-store").schemaIdentity("fixture-schema")
                .maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(65536).maxDocuments(10000).build();
        var error=assertThrows(DurableOperationException.class,()->MembershipApplicationImage.read(config(),wrong,bytes,temp.resolve("wrong-identity")));
        assertEquals(DurableOperationException.Reason.IDENTITY_MISMATCH,error.reason());assertFalse(Files.exists(wrong.directory()));
    }
    @Test void sourceInventoryLinksAndOccupiedOrAliasedScratchAreNeverRepairedOrDeleted()throws Exception {
        var storage=storage(temp.resolve("anchor"),2);Path source=temp.resolve("backup");byte[] bytes=MembershipApplicationImage.capture(config(),storage,state(41,List.of()),source);
        Files.writeString(source.resolve("keep"),"user");var before=inventory(source);
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.fromBackup(config(),storage,source));assertEquals(before,inventory(source));Files.delete(source.resolve("keep"));
        Path checkpoint=source.resolve("gse-backup-checkpoint"),moved=temp.resolve("checkpoint");Files.move(checkpoint,moved);Files.createLink(checkpoint,moved);
        assertThrows(ReplicationException.class,()->MembershipApplicationImage.fromBackup(config(),storage,source));Files.delete(checkpoint);Files.move(moved,checkpoint);
        Path link=temp.resolve("alias");Files.createSymbolicLink(link,temp);
        assertThrows(ReplicationException.class,()->MembershipApplicationImage.read(config(),storage,bytes,link.resolve("bad")));assertFalse(Files.exists(temp.resolve("bad")));
        assertThrows(ReplicationException.class,()->MembershipApplicationImage.read(config(),storage,bytes,source));assertEquals(3,inventory(source).size());
        assertThrows(ReplicationException.class,()->MembershipApplicationImage.capture(config(),storage,state(41,List.of()),source));
        assertThrows(ReplicationException.class,()->MembershipApplicationImage.read(config(),storage,bytes,storage.directory().resolve("nested")));assertFalse(Files.exists(storage.directory()));
    }
    @Test void imageCapIncludesContainerAndDoesNotAcceptHostileCounts() {
        assertEquals(64*1024*1024,MembershipApplicationImage.MAXIMUM);
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.pack(List.of(new byte[1],new byte[1])));
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.pack(List.of(new byte[0],new byte[1],new byte[1])));
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.unpack(new byte[MembershipApplicationImage.MAXIMUM+1]));
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.pack(Collections.nCopies(3,new byte[MembershipApplicationImage.MAXIMUM/3])));
    }
    @Test void foreignSchemaAndMetadataBoundsCannotBecomeAnApplication()throws Exception {
        var storage=storage(temp.resolve("anchor"),2);byte[] bytes=MembershipApplicationImage.capture(config(),storage,state(41,List.of(IndexDefinition.prefix(VALUE))),temp.resolve("backup"));
        var missing=SearchEngine.builder(Doc.class,ID).configuration();
        Path scratch=temp.resolve("missing-field");assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.read(missing,storage,bytes,scratch));assertFalse(Files.exists(scratch));
        var wrong=DurableStorageConfig.builder(temp.resolve("wrong"),new Codec()).storageIdentity("fixture-store").schemaIdentity("fixture-schema")
                .maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(65536).maxDocuments(9999).build();
        var error=assertThrows(DurableOperationException.class,()->MembershipApplicationImage.read(config(),wrong,bytes,temp.resolve("wrong-bound")));
        assertEquals(DurableOperationException.Reason.IDENTITY_MISMATCH,error.reason());
        var members=new ArrayList<>(MembershipApplicationImage.unpack(bytes));byte[] metadata=members.get(2).clone();metadata[11]=3;crc(metadata);members.set(2,metadata);
        final Path invalid=temp.resolve("unknown-version");
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.read(config(),storage,MembershipApplicationImage.pack(members),invalid));assertFalse(Files.exists(invalid));
    }
    @Test void sourceMutationDuringTypedDecodeIsDetectedWithoutRestoringOrDeletingIt()throws Exception {
        Path source=temp.resolve("backup");var original=storage(temp.resolve("anchor"),2);
        MembershipApplicationImage.capture(config(),original,state(41,List.of()),source);
        var delegate=new Codec();var changed=new java.util.concurrent.atomic.AtomicBoolean();
        DurableCodec<Integer,Doc> mutating=new DurableCodec<>() {
            public String codecId(){return delegate.codecId();}public int codecVersion(){return delegate.codecVersion();}
            public byte[] encodeKey(Integer key){return delegate.encodeKey(key);}public Integer decodeKey(byte[] value){return delegate.decodeKey(value);}
            public byte[] encodeDocument(Doc doc){return delegate.encodeDocument(doc);}
            public Doc decodeDocument(byte[] value){
                if(changed.compareAndSet(false,true))try{Files.writeString(source.resolve("unexpected"),"retain");}catch(Exception e){throw new RuntimeException(e);}
                return delegate.decodeDocument(value);
            }
        };
        var config=DurableStorageConfig.builder(temp.resolve("unused"),mutating).storageIdentity("fixture-store").schemaIdentity("fixture-schema")
                .maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(65536).maxDocuments(10000).build();
        assertThrows(RuntimeException.class,()->MembershipApplicationImage.fromBackup(config(),config,source));
        assertTrue(changed.get());assertEquals("retain",Files.readString(source.resolve("unexpected")));assertFalse(Files.exists(config.directory()));
    }
    static void crc(byte[] bytes) {var crc=new CRC32C();crc.update(bytes,0,bytes.length-4);ByteBuffer.wrap(bytes).putInt(bytes.length-4,(int)crc.getValue());}
}
