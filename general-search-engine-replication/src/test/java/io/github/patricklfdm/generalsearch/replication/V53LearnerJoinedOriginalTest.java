package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** The cold entry is read-only inspection, not runtime or retirement recovery.
 * The source fixtures still condition historical quorum observations. */
class V53LearnerJoinedOriginalTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53JoinedOriginalCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerJoinedAdmissionTest helper(){var value=new V53LearnerJoinedAdmissionTest();value.temp=temp;return value;}
    MembershipLearnerJoinedOriginal.Inspection inspect(V53LearnerCancellationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipLearnerJoinedOriginal.inspect(f.local.summary,f.local.captured,f.local.config,cut);
    }
    @Test void declaredNativeExtentsAndPathsAreBoundedBeforeFileReads() {
        var sample=new TreeMap<String,Object>();sample.put(".",Map.of("directory",true,"key","root"));
        sample.put("generations/a/source.gscp",Map.of("key","packet","size",1L,"sha256","0".repeat(64)));
        assertDoesNotThrow(()->MembershipLearnerJoinedOriginal.bounds(sample));
        for(String path:List.of("generations/a/../source.gscp","sources/foreign","generations/b/source.gscp")) {
            var invalid=new TreeMap<>(sample);invalid.put(path,sample.get("generations/a/source.gscp"));
            assertThrows(Exception.class,()->MembershipLearnerJoinedOriginal.bounds(invalid));
        }
        var tooLarge=new TreeMap<>(sample);tooLarge.put("generations/a/source.gscp",Map.of("key","packet","size",MembershipResources.Unit.GENERATION.bytes+1,"sha256","0".repeat(64)));
        assertThrows(Exception.class,()->MembershipLearnerJoinedOriginal.bounds(tooLarge));
        var combined=new TreeMap<>(sample);combined.put("generations/a/source.gscp",Map.of("key","packet","size",MembershipResources.Unit.GENERATION.bytes,"sha256","0".repeat(64)));
        combined.put("generations/a/generation.gsr",Map.of("key","manifest","size",1L,"sha256","1".repeat(64)));
        assertThrows(Exception.class,()->MembershipLearnerJoinedOriginal.bounds(combined));
        for(int n=0;n<8;n++)sample.put("generations/a/"+String.format("%064x",n)+".image",Map.of("key","image-"+n,"size",1L,"sha256",String.format("%064x",n)));
        assertThrows(Exception.class,()->MembershipLearnerJoinedOriginal.bounds(sample));
    }
    @Test void completeOriginalInstallationVerifiesWithoutPredecessorPayloadsButGrantsNoRetirement()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            MembershipLearnerJoinedOriginal.Inspection live;
            try(var placed=h.place(f)) {
                var admission=h.join(placed,f,e->{});var usage=f.local.source.client.usage();
                live=MembershipLearnerJoinedOriginal.verify(admission,f.local.captured,f.local.config);
                assertEquals(usage,f.local.source.client.usage());
                assertThrows(Exception.class,()->inspect(f,e->fail("cold reader must not overlap custody")));
                new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock"));admission.check();
            }
            var original=V53ReplayFilesTest.files(f.local.config.replicaDirectory());
            var moved=new LinkedHashMap<Path,Path>();
            try {
                // Model unavailable predecessors; this test mutation is NOT a
                // production retirement operation or authority to waive one.
                for(var entry:MembershipLearnerCustody.roots(f.local.summary).entrySet())if(!Set.of("replica","initialTyped").contains(entry.getKey()) && Files.exists(entry.getValue())) {
                    Path saved=temp.resolve("unavailable-"+entry.getKey());Files.move(entry.getValue(),saved);moved.put(entry.getValue(),saved);
                }
                Path backup=f.local.typed().resolve(MembershipLearnerMaterialization.BACKUP),saved=temp.resolve("unavailable-backup");
                Files.move(backup,saved);moved.put(backup,saved);
                for(String name:List.of("learner",MembershipLearnerStore.ADMISSION)) {
                    Path file=f.local.config.replicaDirectory().resolve(name);
                    if(Files.exists(file)){Path old=temp.resolve("unavailable-"+name);Files.move(file,old);moved.put(file,old);}
                }
                var beforeInspection=V53ReplayFilesTest.files(f.local.config.replicaDirectory());
                var events=new ArrayList<String>();var cold=inspect(f,e->{events.add(e);assertDoesNotThrow(()->new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock")));});
                assertEquals(live,cold);assertEquals(List.of("JOINED_ORIGINAL_BEFORE_READ","JOINED_ORIGINAL_VERIFIED"),events);
                assertEquals(beforeInspection,V53ReplayFilesTest.files(f.local.config.replicaDirectory()));
                for(Path absent:moved.keySet())assertFalse(Files.exists(absent));
                assertEquals(0,f.local.source.client.usage().leases());
                assertThrows(Exception.class,()->h.recover(f,e->fail("ordinary recovery must not synthesize missing predecessors")));
                assertFalse(Files.exists(f.local.config.replicaDirectory().resolve(MembershipBootstrapAdmissionData.FILE)));
            }finally {for(var entry:moved.entrySet())Files.move(entry.getValue(),entry.getKey());}
            assertEquals(original,V53ReplayFilesTest.files(f.local.config.replicaDirectory()));
            assertEquals(live,inspect(f,e->{}));
            assertTrue(MembershipCapsule.StoredCopy.class.isSealed());
            for(var c:MembershipLearnerJoinedOriginal.Stored.class.getDeclaredConstructors())assertTrue(java.lang.reflect.Modifier.isPrivate(c.getModifiers()));
        }
    }
    @Test void missingTornCopiedAndSemanticallyAlteredProofsRefuseWithoutRepair()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            try(var placed=h.place(f)){h.join(placed,f,e->{});}
            Path placement=MembershipLearnerPlacement.directory(f.local.summary),record=placement.resolve(MembershipLearnerJoinedAdmission.FILE);
            byte[] joined=Files.readAllBytes(record);var rootBefore=V53ReplayFilesTest.files(f.local.config.replicaDirectory());
            for(Path file:List.of(record,placement.resolve(MembershipLearnerPlacement.READY),placement.resolve(MembershipLearnerPlacement.PLAN),
                    MembershipLearnerCustody.directory(f.local.summary).resolve(MembershipLearnerCustody.FILE),
                    f.local.typed().resolve(MembershipLearnerMaterialization.PLAN),f.local.typed().resolve(MembershipLearnerMaterialization.RECEIPT))) {
                Path saved=temp.resolve("saved-original");Files.move(file,saved);
                try {
                    assertThrows(Exception.class,()->inspect(f,e->fail("missing proof cannot reach semantic inspection")));assertFalse(Files.exists(file));
                    Files.copy(saved,file);byte[] copied=Files.readAllBytes(file);
                    assertThrows(Exception.class,()->inspect(f,e->fail("copied proof cannot reach semantic inspection")));
                    assertArrayEquals(copied,Files.readAllBytes(file));Files.delete(file);
                }finally {Files.move(saved,file);}
            }
            for(byte[] torn:List.of(new byte[0],Arrays.copyOf(joined,joined.length/2))) {
                try {Files.write(record,torn);assertThrows(Exception.class,()->inspect(f,e->{}));assertArrayEquals(torn,Files.readAllBytes(record));}
                finally {Files.write(record,joined);}
            }
            var original=object(parse(joined,MembershipLearnerJoinedAdmission.MAXIMUM));
            for(String field:List.of("source","generation","promise","allocator","recordKey","root","plan","configuration","preparationSource")) {
                var changed=new TreeMap<>(original);changed.put(field,"0".repeat(64));byte[] corrupt=canonical(changed,MembershipLearnerJoinedAdmission.MAXIMUM);
                try {Files.write(record,corrupt);assertThrows(Exception.class,()->inspect(f,e->{}),field);assertArrayEquals(corrupt,Files.readAllBytes(record));}
                finally {Files.write(record,joined);}
            }
            var wrong=new TreeMap<>(original);wrong.put("sealed",Map.of());
            try {Files.write(record,canonical(wrong,MembershipLearnerJoinedAdmission.MAXIMUM));assertThrows(Exception.class,()->inspect(f,e->{}));}
            finally {Files.write(record,joined);}
            assertEquals(rootBefore,V53ReplayFilesTest.files(f.local.config.replicaDirectory()));inspect(f,e->{});
        }
    }
    @Test void installedInodeReplacementAndLastReadMutationNeverEscapeAValidatedResult()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            try(var placed=h.place(f)){h.join(placed,f,e->{});}
            Path root=f.local.config.replicaDirectory();
            for(String name:List.of("root.gsr","replica.lock","selector.gsr","allocator.gsr","grants.gsr","generations/a/source.gscp")) {
                Path file=root.resolve(name),saved=temp.resolve("installed-original");Files.move(file,saved);Files.copy(saved,file);
                try {assertThrows(Exception.class,()->inspect(f,e->{}),name);}
                finally {Files.delete(file);Files.move(saved,file);}
            }
            Path packet=root.resolve("generations/a/source.gscp");byte[] bytes=Files.readAllBytes(packet);var hit=new AtomicBoolean();
            try {
                assertThrows(Exception.class,()->inspect(f,e->{if(e.equals("JOINED_ORIGINAL_VERIFIED")){hit.set(true);Files.writeString(packet,"corrupt");}}));
                assertTrue(hit.get());assertEquals("corrupt",Files.readString(packet));
            }finally {Files.write(packet,bytes);}
            inspect(f,e->{});assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void completedReplacementPreservesFinalFenceAndOriginalIntentAsDifferentProofs()throws Exception {
        var h=helper();var initial=new V53LearnerIntentTest();initial.temp=temp;
        try(var f=initial.fixture("COMPLETED",5,"REPLACE",false)) {
            MembershipLearnerJoinedOriginal.Inspection live;
            try(var placed=h.place(f)) {
                var admission=h.join(placed,f,e->{});var value=object(parse(admission.originalRecord(),MembershipLearnerJoinedAdmission.MAXIMUM));
                var intent=decode(MembershipBootstrapPlanData.unbase(value.get("certificate"),16384),"records","CERTIFICATE");
                var fence=placed.custody().source().membershipCertificateFence().orElseThrow();
                assertNotEquals(intent.digest(),fence.digest());
                var entry=placed.custody().source().context.record((String)fence.value().get("entry"),"ENTRY");assertEquals("FINAL",entry.value().get("kind"));
                live=MembershipLearnerJoinedOriginal.verify(admission,f.local.captured,f.local.config);
            }
            assertEquals(live,inspect(f,e->{}));assertEquals(0,f.local.source.client.usage().leases());
        }
    }
}
