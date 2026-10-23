package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapAdmissionDataTest {
    @TempDir Path temp;
    static MembershipBootstrapAdmissionData inspect(byte[] raw,MembershipBootstrapCommitMetadata d,int n,byte[] prep,byte[] seal) {
        return new MembershipBootstrapAdmissionData(raw,d.plan.layout.root.bytes(),d.plan.layout.genesis.bytes(),prep,seal,d.plan.layout.identity,d.identities.get(n),d.targets.get(n),d.plan.summary().absentTargets().get(2*n+1));
    }
    static MembershipBootstrapCommitMetadata pinned(int n)throws Exception {
        return new MembershipBootstrapCommitMetadata(V53BootstrapCommitMetadataTest.metadata(object(list(V53BootstrapCommitMetadataTest.fixture().get("cases")).get(n))));
    }
    @Test void allSupportedTargetsBindRealCommittedOriginalBytesWithoutCopyingThePlanOrImage()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-admission/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();var helper=new V53BootstrapTransactionTest();helper.temp=temp;
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");var plan=helper.fixture(name,size,backup);V53BootstrapTransactionTest.run(plan,false,e->{});
            var data=new MembershipBootstrapCommitData(plan);byte[] raw=MembershipBootstrapAdmissionData.create(data.metadata);var before=V53BootstrapTransactionTest.files(plan);
            Path member=Files.createDirectory(evidence.resolve(name));V53BootstrapTransactionTest.copy(plan,member.resolve("final"));
            Files.write(member.resolve("original-plan.gsbp"),plan.bytes());Files.write(member.resolve("original-application.image"),plan.seed.application());Files.createDirectory(member.resolve("derived-admissions"));
            for(int n=0;n<size;n++) {
                var admitted=inspect(raw,data.metadata,n,Files.readAllBytes(data.targets.get(n).resolve(MembershipBootstrapCommitData.PREPARED)),Files.readAllBytes(data.targets.get(n).resolve(MembershipBootstrapCommitData.SEAL)));
                assertEquals(data.result(),admitted.result());assertArrayEquals(raw,admitted.bytes());
                Files.write(member.resolve("derived-admissions/target-"+n+".gsbp"),raw);
            }
            assertEquals(before,V53BootstrapTransactionTest.files(plan));assertFalse(Files.exists(data.targets.getFirst().resolve(MembershipBootstrapAdmissionData.FILE)));
            rows.add(Map.of("case",name,"size",size,"source",backup?"VERIFIED_DURABLE_BACKUP":"EMPTY","admissionBytes",raw.length,"plan",plan.digest(),"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-admission-data-v1","status","PASS","cases",rows,"storeIntegrated",false,"publicBootstrap",false),65536));
        System.out.println("v53BootstrapAdmissionDataEvidence="+evidence.toAbsolutePath());
    }
    @Test void originalLocalIdentityPathsAndHistoryAreRequired()throws Exception {
        var d=pinned(0);var other=pinned(1);byte[] raw=MembershipBootstrapAdmissionData.create(d);var first=d.identities.getFirst();Path authority=d.targets.getFirst(),core=d.plan.summary().absentTargets().get(1);
        assertThrows(RuntimeException.class,()->new MembershipBootstrapAdmissionData(raw,d.plan.layout.root.bytes(),d.plan.layout.genesis.bytes(),d.preparation(0),d.seal(0),other.plan.layout.identity,first,authority,core));
        assertThrows(RuntimeException.class,()->new MembershipBootstrapAdmissionData(raw,d.plan.layout.root.bytes(),d.plan.layout.genesis.bytes(),d.preparation(0),d.seal(0),d.plan.layout.identity,d.identities.get(1),authority,core));
        assertThrows(RuntimeException.class,()->new MembershipBootstrapAdmissionData(raw,d.plan.layout.root.bytes(),d.plan.layout.genesis.bytes(),d.preparation(0),d.seal(0),d.plan.layout.identity,first,authority.resolve("copy"),core));
        assertThrows(RuntimeException.class,()->new MembershipBootstrapAdmissionData(raw,d.plan.layout.root.bytes(),d.plan.layout.genesis.bytes(),d.preparation(0),d.seal(0),d.plan.layout.identity,first,authority,core.resolve("copy")));
        assertThrows(RuntimeException.class,()->inspect(raw,d,0,d.preparation(1),d.seal(1)));assertThrows(RuntimeException.class,()->inspect(raw,d,0,d.preparation(0),other.seal(0)));
    }
    @Test void boundedEnvelopeRejectsMissingTornCorruptDuplicateAndReorderedOriginals()throws Exception {
        var d=pinned(0);byte[] raw=MembershipBootstrapAdmissionData.create(d);var bad=new ArrayList<byte[]>();bad.add(new byte[0]);bad.add(Arrays.copyOf(raw,raw.length-1));bad.add(Arrays.copyOf(raw,raw.length+1));bad.add(new byte[65537]);
        for(int offset:List.of(0,4,6,8,10,12,16,48,raw.length-1)){byte[] copy=raw.clone();copy[offset]^=1;bad.add(copy);}
        bad.add(MembershipBootstrapAdmissionData.envelope(d.receipt(),d.row(4),d.row(3)));bad.add(MembershipBootstrapAdmissionData.envelope(d.receipt(),d.row(2),d.row(4)));bad.add(MembershipBootstrapAdmissionData.envelope(d.receipt(),d.row(3),d.row(3)));
        byte[] body=Arrays.copyOfRange(raw,48,raw.length);bad.add(repack(Arrays.copyOf(body,body.length+4)));ByteBuffer.wrap(body).putInt(Integer.MAX_VALUE);bad.add(repack(body));
        body=Arrays.copyOfRange(raw,48,raw.length);ByteBuffer.wrap(body).putInt(-1);bad.add(repack(body));
        for(byte[] input:bad)assertThrows(RuntimeException.class,()->inspect(input,d,0,d.preparation(0),d.seal(0)));
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapAdmissionData.envelope(new byte[65536],d.row(3),d.row(4)));
    }
    static byte[] repack(byte[] body) {
        byte[] prefix=ByteBuffer.allocate(16).putInt(MembershipBootstrapPlanData.MAGIC).putShort((short)1).putShort((short)3).putShort((short)5).putShort((short)0).putInt(body.length).array();
        return ByteBuffer.allocate(body.length+48).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    static Map<String,Object> mutable(Map<String,Object> value){return object(V53ContextFixture.mutable(value));}
    @Test void rehashedButMismatchingInventoryReceiptAndDecisionBindingsAreRejected()throws Exception {
        var d=pinned(0);
        for(String kind:List.of("inventory","receipt-plan","receipt-preparations","receipt-committing","decision-source","decision-order","decision-path","seal","extra-preparation","extra-receipt")) {
            var prep=mutable(MembershipBootstrapAdmissionData.privateFrame(d.preparation(0),2));var receipt=mutable(MembershipBootstrapAdmissionData.privateFrame(d.receipt(),3));
            var committing=mutable(decode(d.row(3),"records","BOOTSTRAP").value());var committed=mutable(decode(d.row(4),"records","BOOTSTRAP").value());
            switch(kind) {
                case "inventory"->object(list(prep.get("inventory")).getFirst()).put("bytes",999L);
                case "receipt-plan"->receipt.put("plan","0".repeat(64));
                case "receipt-preparations"->{var hashes=new ArrayList<Object>(list(receipt.get("preparations")));hashes.set(1,"0".repeat(64));receipt.put("preparations",hashes);}
                case "receipt-committing"->receipt.put("committing","0".repeat(64));
                case "decision-source"->{committing.put("source","VERIFIED_DURABLE_BACKUP");committed.put("source","VERIFIED_DURABLE_BACKUP");}
                case "decision-order"->{Collections.swap(list(committing.get("targets")),0,1);Collections.swap(list(committed.get("targets")),0,1);}
                case "decision-path"->{object(list(committing.get("targets")).getFirst()).put("authorityPath","wrong-path");object(list(committed.get("targets")).getFirst()).put("authorityPath","wrong-path");}
                case "extra-preparation"->prep.put("extra",true);case "extra-receipt"->receipt.put("extra",true);case "seal"->{}default->throw new AssertionError();
            }
            byte[] p=MembershipBootstrapCommitMetadata.container(2,prep);byte[] before=encode("records","BOOTSTRAP",committing),after=encode("records","BOOTSTRAP",committed);
            // Inventory and decision mutations are rehashed through the receipt/seal;
            // their semantic bindings must still fail. A different peer's preparation
            // digest alone is not locally provable, so keep the original local seal.
            if(!kind.equals("receipt-preparations")) {
                var hashes=new ArrayList<Object>(list(receipt.get("preparations")));hashes.set(0,hash(p));receipt.put("preparations",hashes);
                if(!kind.equals("receipt-committing"))receipt.put("committing",hash(before));receipt.put("committed",hash(after));
            }
            byte[] r=MembershipBootstrapCommitMetadata.container(3,receipt);var seal=mutable(MembershipBootstrapAdmissionData.privateFrame(d.seal(0),4));
            if(!kind.equals("receipt-preparations")){seal.put("prepared",hash(p));seal.put("receipt",hash(r));}
            if(kind.equals("seal"))seal.put("plan","0".repeat(64));byte[] s=MembershipBootstrapCommitMetadata.container(4,seal);byte[] raw=MembershipBootstrapAdmissionData.envelope(r,before,after);
            assertThrows(RuntimeException.class,()->inspect(raw,d,0,p,s),kind);
        }
    }
    @Test void worstAbsolutePathEscapingFitsTheCompactBoundAndReturnsDefensiveBytes()throws Exception {
        var original=pinned(5);var body=V53BootstrapPlanTest.body(original.plan.bytes());String parent="/"+"\n".repeat(4000);
        for(Object entry:list(object(body.get("descriptor")).get("paths"))) {var p=object(entry);p.put("path",parent+"/"+Path.of((String)p.get("path")).getFileName());p.put("parentRealPath",parent);}
        var d=new MembershipBootstrapCommitMetadata(new MembershipBootstrapPlanMetadata(MembershipBootstrapPlanData.encode(body)));byte[] raw=MembershipBootstrapAdmissionData.create(d);assertTrue(raw.length<=MembershipBootstrapAdmissionData.MAXIMUM);
        for(int i=0;i<5;i++) {var result=inspect(raw,d,i,d.preparation(i),d.seal(i));byte[] changed=result.bytes();changed[0]^=1;assertArrayEquals(raw,result.bytes());assertEquals(d.result(),result.result());}
    }
}
