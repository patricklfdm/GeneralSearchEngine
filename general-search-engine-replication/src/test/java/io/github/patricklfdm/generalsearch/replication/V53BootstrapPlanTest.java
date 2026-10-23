package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapPlanTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("BOOTSTRAP_OPERATION_CREATED","BOOTSTRAP_OPERATION_LOCKED",
        "BOOTSTRAP_IMAGE_CREATED","BOOTSTRAP_IMAGE_PREFIX_WRITTEN","BOOTSTRAP_IMAGE_WRITTEN","BOOTSTRAP_IMAGE_FORCED","BOOTSTRAP_IMAGE_PARENT_FORCED",
        "BOOTSTRAP_PLAN_CREATED","BOOTSTRAP_PLAN_PREFIX_WRITTEN","BOOTSTRAP_PLAN_WRITTEN","BOOTSTRAP_PLAN_FORCED","BOOTSTRAP_PLAN_PARENT_FORCED",
        "BOOTSTRAP_RESEAL_IMAGE_FORCED","BOOTSTRAP_RESEAL_IMAGE_PARENT_FORCED","BOOTSTRAP_RESEAL_PLAN_FORCED","BOOTSTRAP_RESEAL_PLAN_PARENT_FORCED",
        "BOOTSTRAP_PLAN_RENAMED","BOOTSTRAP_ACTIVE_PLAN_FORCED","BOOTSTRAP_ACTIVE_PLAN_PARENT_FORCED","BOOTSTRAP_PLAN_BEFORE_RETURN");
    record Fixture(MembershipBootstrapRequest<Integer,Doc> request,MembershipBootstrapPlanData plan){}
    Fixture fixture(String name,int size,boolean backup)throws Exception {
        Path base=Files.createDirectory(temp.resolve(name));var helper=new V53BootstrapSeedTest();helper.temp=base;
        var request=helper.request(base,size,backup?helper.source("source",41):null);
        var seed=helper.project(request,base.resolve("scratch"));return new Fixture(request,MembershipBootstrapPlanData.create(seed,request));
    }
    @Test void completePlanRoundTripsExactHistoryRootAndEveryTargetWithoutCodecOrSource()throws Exception {
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var f=fixture("round-"+size+"-"+backup,size,backup);var plan=f.plan();var restored=MembershipBootstrapPlanData.decode(plan.bytes(),plan.seed.application());
            assertEquals(plan.digest(),restored.digest());assertEquals(plan.summary(),restored.summary());assertEquals(plan.seed.root,restored.seed.root);
            assertEquals(2*size,restored.summary().absentTargets().size());assertEquals(f.request().maxOperationBytes(),restored.maximumOperation);
            assertArrayEquals(plan.seed.capsule.packet.bytes(),restored.seed.capsule.packet.bytes());
            for(var target:f.request().targets())assertEquals(hashes(plan.seed.payloads(target.identity())),hashes(restored.seed.payloads(target.identity())));
            byte[] changed=restored.bytes();changed[0]^=1;assertEquals(plan.digest(),restored.digest());V53BootstrapSeedTest.absent(f.request());
        }
    }
    static Map<String,String> hashes(Map<String,byte[]> files){var result=new TreeMap<String,String>();files.forEach((name,raw)->result.put(name,hash(raw)));return result;}
    static Map<String,Object> body(byte[] bytes){return object(V53ContextFixture.mutable(parse(Arrays.copyOfRange(bytes,48,bytes.length),MembershipBootstrapPlanData.MAXIMUM)));}
    @Test void malformedHeadersBodiesImagesAndSelfConsistentInventorySubstitutionsFailClosed()throws Exception {
        var plan=fixture("malformed",3,true).plan();byte[] bytes=plan.bytes(),image=plan.seed.application();var bad=new ArrayList<byte[]>();
        bad.add(new byte[0]);bad.add(Arrays.copyOf(bytes,bytes.length-1));bad.add(Arrays.copyOf(bytes,bytes.length+1));
        for(int pos:List.of(0,4,6,8,10,12,16,bytes.length-1)){byte[] copy=bytes.clone();copy[pos]^=1;bad.add(copy);}
        for(String variant:List.of("extra","image","inventory","history","descriptor","source-cap","completion-cap","alias")) {
            var value=body(bytes);
            switch(variant) {
                case "extra"->value.put("unknown",true);
                case "image"->object(value.get("application")).put("bytes",1L);
                case "inventory"->object(list(object(list(value.get("targets")).getFirst()).get("files")).getFirst()).put("bytes",0L);
                case "history"->{var root=decode(MembershipBootstrapPlanData.unbase(value.get("root"),16384),"records","ROOT");var row=new TreeMap<>(root.value());row.put("historyId",new UUID(10,11).toString());value.put("root",MembershipBootstrapPlanData.base(encode("records","ROOT",row)));}
                case "descriptor"->object(object(value.get("descriptor")).get("core")).put("schemaIdentity","wrong-schema");
                case "source-cap"->value.put("maximumSource",1L);
                case "completion-cap"->value.put("maximumOperation",1L);
                case "alias"->{var paths=new ArrayList<Object>(list(object(value.get("descriptor")).get("paths")));paths.set(2,paths.get(3));object(value.get("descriptor")).put("paths",paths);}
                default->throw new AssertionError();
            }
            bad.add(MembershipBootstrapPlanData.encode(value));
        }
        for(byte[] invalid:bad)assertThrows(RuntimeException.class,()->MembershipBootstrapPlanData.decode(invalid,image));
        byte[] changed=image.clone();changed[changed.length-1]^=1;assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanData.decode(bytes,changed));
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanData.decode(new byte[MembershipBootstrapPlanData.MAXIMUM+1],image));
    }
    @Test void aChangedRequestCannotBorrowAnEarlierProjection()throws Exception {
        var f=fixture("request",3,false);var r=f.request();
        var wrong=new MembershipBootstrapRequest<>(r.groupId(),"wrong",r.source(),r.sourcePath(),r.targets(),r.operationDirectory(),r.maxSourceBytes(),r.maxOperationBytes());
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanData.create(f.plan().seed,wrong));
        var targets=new ArrayList<>(r.targets());var last=targets.getLast();targets.set(2,new MembershipBootstrapTarget<>(last.identity(),last.replicaDirectory(),storage(last.materialization().directory(),1)));
        var drift=new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),targets,r.operationDirectory(),r.maxSourceBytes(),r.maxOperationBytes());
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanData.create(f.plan().seed,drift));V53BootstrapSeedTest.absent(r);
    }
    @Test void forceImageThenPlanAndReopenUnderTheSameExclusiveCoordinator()throws Exception {
        var f=fixture("complete",5,true);var events=new ArrayList<String>();var plan=f.plan();
        try(var owner=MembershipBootstrapPlanFiles.create(plan,events::add)) {
            assertEquals(plan.summary(),owner.summary());assertEquals(plan.seed.root,owner.retained().seed.root);
            assertThrows(ReplicationException.class,()->MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),e->{}));
            assertThrows(ReplicationException.class,()->MembershipBootstrapPlanFiles.create(plan,e->{}));
        }
        assertTrue(events.indexOf("BOOTSTRAP_IMAGE_PARENT_FORCED")<events.indexOf("BOOTSTRAP_PLAN_CREATED"));
        assertTrue(events.indexOf("BOOTSTRAP_RESEAL_PLAN_PARENT_FORCED")<events.indexOf("BOOTSTRAP_PLAN_RENAMED"));
        assertTrue(events.indexOf("BOOTSTRAP_ACTIVE_PLAN_PARENT_FORCED")<events.indexOf("BOOTSTRAP_PLAN_BEFORE_RETURN"));
        var before=V53ReplayFilesTest.files(plan.operation());try(var owner=MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),e->{})){assertEquals(plan.summary(),owner.summary());}
        assertEquals(before,V53ReplayFilesTest.files(plan.operation()));assertEquals(Set.of("operation.lock","application.image","plan.gsbp"),before.keySet());
        for(var target:f.request().targets()){assertFalse(Files.exists(target.replicaDirectory()));assertFalse(Files.exists(target.materialization().directory()));}
    }
    @Test void allTwentyCreationCutsEitherRefuseOriginalIncompleteAuthorityOrResumeTheExactHistoryTwice()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-plan").resolve("run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(String cut:CUTS) {
            var f=fixture(cut,3,false);var plan=f.plan();Path member=Files.createDirectory(evidence.resolve(cut));
            var first=new ArrayList<String>();var recovery=new ArrayList<String>();var resume=new ArrayList<String>();
            assertThrows(IOException.class,()->MembershipBootstrapPlanFiles.create(plan,event->{first.add(event);if(event.equals(cut))throw new IOException(cut);}));
            V53JournalApplicationTest.copy(plan.operation(),member.resolve("crash"));var original=V53ReplayFilesTest.files(plan.operation());
            boolean complete=CUTS.indexOf(cut)>=CUTS.indexOf("BOOTSTRAP_PLAN_WRITTEN");
            if(!complete) {
                assertThrows(Exception.class,()->MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),recovery::add));
                assertEquals(original,V53ReplayFilesTest.files(plan.operation()));
            }else {
                assertThrows(IOException.class,()->MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),event->{recovery.add(event);if(event.equals("BOOTSTRAP_RESEAL_IMAGE_FORCED"))throw new IOException("again");}));
                assertEquals(original,V53ReplayFilesTest.files(plan.operation()));V53JournalApplicationTest.copy(plan.operation(),member.resolve("second-crash"));
                try(var owner=MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),resume::add)){assertEquals(plan.summary(),owner.summary());assertEquals(plan.seed.root,owner.retained().seed.root);}
            }
            V53JournalApplicationTest.copy(plan.operation(),member.resolve("final"));Files.write(member.resolve("original-plan.gsbp"),plan.bytes());Files.write(member.resolve("original-application.image"),plan.seed.application());
            Files.write(member.resolve("events.json"),canonical(Map.of("first",first,"recovery",recovery,"resume",resume),65536));
            rows.add(Map.of("cut",cut,"recovery",complete?"EXACT_PLAN_RESEALED":"INCOMPLETE_AUTHORITY_REFUSED","history",plan.seed.root.historyId().toString(),"plan",plan.digest(),"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-plan-files-v1","status","PASS","cases",rows,"offlineCommit",false,"freshProcesses",false),65536));
        System.out.println("v53BootstrapPlanEvidence="+evidence.toAbsolutePath());
    }
    @Test void missingCorruptOrPartialOriginalsAreNotRepairedFromTheSummaryOrGoodCandidate()throws Exception {
        for(String name:List.of("image","plan","lock","extra","active-corrupt","partial-next")) {
            var plan=fixture("missing-"+name,3,false).plan();try(var owner=MembershipBootstrapPlanFiles.create(plan,e->{})){assertEquals(plan.summary(),owner.summary());}
            Path path=plan.operation();switch(name) {
                case "image"->Files.delete(path.resolve("application.image"));case "plan"->Files.delete(path.resolve("plan.gsbp"));case "lock"->Files.delete(path.resolve("operation.lock"));
                case "extra"->Files.writeString(path.resolve("extra"),"retain");
                case "active-corrupt"->{Files.copy(path.resolve("plan.gsbp"),path.resolve("plan.next.gsbp"));Files.write(path.resolve("plan.gsbp"),new byte[1]);}
                case "partial-next"->Files.write(path.resolve("plan.next.gsbp"),Arrays.copyOf(plan.bytes(),13));default->throw new AssertionError();
            }
            var before=V53ReplayFilesTest.files(path);assertThrows(Exception.class,()->MembershipBootstrapPlanFiles.open(path,plan.summary(),e->{}));assertEquals(before,V53ReplayFilesTest.files(path));
        }
    }
    @Test void sameBytesAtDifferentInodesOrCoordinatorPathsNeverBorrowOwnership()throws Exception {
        for(String point:List.of("BOOTSTRAP_IMAGE_FORCED","BOOTSTRAP_PLAN_FORCED","BOOTSTRAP_ACTIVE_PLAN_FORCED")) {
            var plan=fixture(point,3,false).plan();String name=point.contains("IMAGE")?"application.image":point.contains("ACTIVE")?"plan.gsbp":"plan.next.gsbp";
            assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanFiles.create(plan,event->{if(event.equals(point)) {
                Path copy=plan.operation().resolveSibling("replacement");Files.copy(plan.operation().resolve(name),copy);Files.move(copy,plan.operation().resolve(name),StandardCopyOption.REPLACE_EXISTING);
            }}));
        }
        var plan=fixture("copied",3,false).plan();try(var owner=MembershipBootstrapPlanFiles.create(plan,e->{})){assertEquals(plan.summary(),owner.summary());}
        Path copied=temp.resolve("other-operation");V53JournalApplicationTest.copy(plan.operation(),copied);
        var summary=new MembershipBootstrapPlan(plan.digest(),plan.seed.root.groupId(),plan.summary().absentTargets(),copied);
        var before=V53ReplayFilesTest.files(copied);assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanFiles.open(copied,summary,e->{}));assertEquals(before,V53ReplayFilesTest.files(copied));
        var changed=fixture("directory",3,false).plan();assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanFiles.create(changed,event->{if(event.equals("BOOTSTRAP_OPERATION_CREATED")) {
            Files.move(changed.operation(),changed.operation().resolveSibling("old-operation"));Files.createDirectory(changed.operation());
        }}));assertFalse(Files.exists(changed.operation().resolve("operation.lock")));
    }
    @Test void redundantExactCandidateCanBeRemovedAfterActivePlanAndImageAreForced()throws Exception {
        for(String point:List.of("BOOTSTRAP_REDUNDANT_PLAN_DELETED","BOOTSTRAP_REDUNDANT_PLAN_PARENT_FORCED")) {
            var plan=fixture(point,3,false).plan();try(var ignored=MembershipBootstrapPlanFiles.create(plan,e->{})){}
            Files.write(plan.operation().resolve("plan.next.gsbp"),plan.bytes());
            assertThrows(IOException.class,()->MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),event->{if(event.equals(point))throw new IOException(point);}));
            try(var owner=MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),e->{})){assertEquals(plan.digest(),owner.retained().digest());}
            assertFalse(Files.exists(plan.operation().resolve("plan.next.gsbp")));
        }
    }
}
