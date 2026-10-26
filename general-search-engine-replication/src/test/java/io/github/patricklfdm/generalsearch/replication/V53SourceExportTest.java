package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SourceExportTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(30);
    V53BootstrapPublicationTest.Fixture fixture(int size)throws Exception {
        Path root=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
        return new V53BootstrapPublicationTest.Fixture(root,Files.createDirectory(root.resolve("raw")),size,false);
    }
    static byte[] complete(MembershipSourceExport export,MembershipSourceExport.Content content)throws Exception {
        var out=new ByteArrayOutputStream();
        for(long offset=0;offset<content.bytes();) {
            byte[] bytes=export.read(content.digest(),offset,1024);assertTrue(bytes.length>0 && bytes.length<=1024);
            out.write(bytes);offset+=bytes.length;
        }
        byte[] bytes=out.toByteArray();assertEquals(content.bytes(),bytes.length);assertEquals(content.digest(),hash(bytes));return bytes;
    }
    @Test void admittedOriginalsExportExactBytesWithoutChangingAnyFileOrStorageReservation()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-source-export/run-"+UUID.randomUUID()));
        System.out.println("v53SourceExportEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("size-"+size)),raw,size,false);
            var target=f.request.targets().getFirst();int count;
            try(var owner=f.open(target,"capture-and-export")) {
                var source=owner.beginActivation();Path captured=Files.createDirectory(raw.resolve("captured"));
                for(var member:f.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
                var before=V53ReplayFilesTest.files(target.replicaDirectory());var usage=f.resources.usage();
                var rows=new ArrayList<Map<String,Object>>();Path output=Files.createDirectory(raw.resolve("exported"));
                try(var export=owner.exportSource(source.basis,BUDGET)) {
                    assertArrayEquals(source.basis.bytes(),export.source().basis.bytes());assertArrayEquals(owner.promised().orElseThrow().bytes(),export.promise().bytes());
                    assertEquals(usage.metadata(),f.resources.usage().metadata());assertEquals(usage.staging(),f.resources.usage().staging());
                    assertEquals(usage.queued()+source.basis.size()+export.promise().size(),f.resources.usage().queued());
                    for(var content:export.contents()) {
                        byte[] bytes=complete(export,content);Files.write(output.resolve(content.digest()+".bin"),bytes);
                        rows.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                        byte[] exposed=export.read(content.digest(),0,1024);byte original=exposed[0];exposed[0]^=1;
                        assertEquals(original,export.read(content.digest(),0,1024)[0]);
                    }
                    count=rows.size();assertEquals(4,count);
                }
                assertEquals(usage,f.resources.usage());assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
                Files.write(raw.resolve("contents.json"),ReplicaJson.encode(rows,65536));
            }
            f.snapshot("after");cases.add(Map.of("size",size,"contents",count));
        }
        Files.write(evidence.resolve("receipt.json"),ReplicaJson.encode(Map.of("schema","gse-v53-source-export-v1","status","PASS","cases",cases,
                "publicRuntime",false,"network",false,"scope","read-only-original-source-lifetime"),65536));
    }
    @Test void repeatedReadersAndNewPromisesDoNotChangeOriginalBytesOrRenewTheBorrow()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();var clock=new AtomicLong(100);
        try(var owner=f.open(target,"stable-borrow")) {
            var source=owner.beginActivation();var baseline=f.resources.usage();var exports=new ArrayList<MembershipSourceExport>();
            try {
                for(int n=0;n<6;n++)exports.add(owner.exportSource(source.basis,clock::get,50));
                var held=f.resources.usage();assertThrows(IllegalArgumentException.class,()->owner.exportSource(source.basis,clock::get,50));assertEquals(held,f.resources.usage());
                var next=owner.beginActivation();assertNotEquals(source.basis.digest(),next.basis.digest());
                clock.set(149);assertArrayEquals(source.basis.bytes(),exports.getFirst().source().basis.bytes());
                assertArrayEquals(source.basis.bytes(),complete(exports.getFirst(),exports.getFirst().contents().stream().filter(v->v.digest().equals(source.basis.digest())).findFirst().orElseThrow()));
                clock.set(150);assertThrows(IllegalArgumentException.class,exports.getFirst()::contents);assertEquals(baseline.queued(),f.resources.usage().queued());
                try(var fresh=owner.exportSource(next.basis,clock::get,50)){assertEquals(next.basis.digest(),fresh.source().basis.digest());}
            }finally{exports.forEach(MembershipSourceExport::close);}
        }
    }
    @Test void exportPreventsRetirementBeforeAnyDecisionOrJournalPruningAndCloseRestoresIt()throws Exception {
        var helper=new V53SourceReleaseTest();helper.temp=temp;Path path=temp.resolve("retirement/authority");String old=helper.provision(path);var resources=helper.resources();
        try(var owner=helper.open(path,resources,event->{})) {
            var original=owner.planSourceRetirement(old).basis;var before=V53ReplayFilesTest.files(path);var baseline=resources.usage();
            try(var export=owner.exportSource(original,BUDGET)) {
                assertEquals("source export pins original files",assertThrows(IllegalArgumentException.class,()->owner.retireSource(old)).getMessage());
                assertEquals(before,V53ReplayFilesTest.files(path));assertFalse(Files.exists(path.resolve(MembershipSourceRetirementFiles.FILE)));
                owner.rotateJournal();assertArrayEquals(original.bytes(),complete(export,export.contents().stream().filter(v->v.digest().equals(original.digest())).findFirst().orElseThrow()));
            }
            assertEquals(baseline,resources.usage());owner.retireSource(old);assertFalse(Files.exists(path.resolve("sources").resolve(old)));
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void expiredBorrowCannotStrandRetirementAndCannotBeRevivedByClockRollback()throws Exception {
        var helper=new V53SourceReleaseTest();helper.temp=temp;Path path=temp.resolve("expiry/authority");String old=helper.provision(path);var resources=helper.resources();var clock=new AtomicLong();
        try(var owner=helper.open(path,resources,event->{})) {
            try(var export=owner.exportSource(owner.planSourceRetirement(old).basis,clock::get,10)) {
                clock.set(10);owner.retireSource(old);assertFalse(Files.exists(path.resolve("sources").resolve(old)));
                clock.set(0);assertThrows(IllegalArgumentException.class,export::contents);
            }
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void constructorAndReadBudgetsIncludeVerificationAndReleaseOnLateReturn()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();var clock=new AtomicLong();
        try(var owner=f.open(target,"expired-construction")) {
            var source=owner.beginActivation();var baseline=f.resources.usage();var before=V53ReplayFilesTest.files(target.replicaDirectory());
            assertThrows(IllegalArgumentException.class,()->owner.exportSource(source.basis,clock::getAndIncrement,1));
            assertEquals(baseline,f.resources.usage());assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            try(var export=owner.exportSource(source.basis,clock::getAndIncrement,7)) {
                // Entry, construction and read verification share one clock budget.
                assertThrows(IllegalArgumentException.class,()->{for(int n=0;n<8;n++)export.contents();});
                assertEquals(baseline.queued(),f.resources.usage().queued());
            }
        }
    }
    @Test void foreignBasisBadOffsetsAndClosedOwnersDoNotGrantARead()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();MembershipSourceExport kept;
        try(var owner=f.open(target,"invalid-export")) {
            var source=owner.beginActivation();var usage=f.resources.usage();var fields=new TreeMap<>(source.basis.value());fields.put("basisId",UUID.randomUUID().toString());
            var wrong=decode(encode("records","BASIS",fields),"records","BASIS");
            assertThrows(IllegalArgumentException.class,()->owner.exportSource(wrong,BUDGET));assertThrows(IllegalArgumentException.class,()->owner.exportSource(source.basis,0));
            assertEquals(usage,f.resources.usage());kept=owner.exportSource(source.basis,BUDGET);var member=kept.contents().getFirst();
            assertThrows(IllegalArgumentException.class,()->kept.read("0".repeat(64),0,1));
            for(long offset:List.of(-1L,member.bytes(),Long.MAX_VALUE))assertThrows(IllegalArgumentException.class,()->kept.read(member.digest(),offset,1));
            for(int count:List.of(0,-1,4*1024*1024+1,Integer.MAX_VALUE))assertThrows(IllegalArgumentException.class,()->kept.read(member.digest(),0,count));
        }
        assertEquals(0,f.resources.usage().leases());assertThrows(IllegalArgumentException.class,kept::contents);kept.close();
        try(var reopened=f.open(target,"reopen-no-transfer")){assertEquals(0,f.resources.usage().queued());assertNotNull(reopened.originalSource());}
    }
    @Test void changedOriginalInodeAndBytesAreDetectedBeforeAnotherChunkReturns()throws Exception {
        for(String fault:List.of("bytes","inode","link")) {
            var f=fixture(3);var target=f.request.targets().getFirst();
            try(var owner=f.open(target,"corrupt-export");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
                var member=export.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                Path path=target.replicaDirectory().resolve("sources").resolve(export.basisId()).resolve(member.digest()+".image");
                byte[] bytes=Files.readAllBytes(path);assertTrue(export.read(member.digest(),0,1).length>0);
                if(fault.equals("bytes")){bytes[bytes.length-1]^=1;Files.write(path,bytes);}
                else if(fault.equals("inode")){Files.move(path,path.resolveSibling("moved"));Files.write(path,bytes);Files.delete(path.resolveSibling("moved"));}
                else Files.createLink(temp.resolve("alias-"+UUID.randomUUID()),path);
                assertThrows(RuntimeException.class,()->export.read(member.digest(),0,1));
            }
            assertEquals(0,f.resources.usage().leases());
        }
    }
    @Test void globalControlCapacityRejectsBeforeCreatingABorrowAndReturnsAfterClose()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();
        try(var owner=f.open(target,"queue-full")) {
            var source=owner.beginActivation();var leases=new ArrayList<MembershipResources.Lease>();var before=V53ReplayFilesTest.files(target.replicaDirectory());
            try {
                for(int n=0;n<8;n++)leases.add(f.resources.reserve(MembershipResources.Unit.CONTROL,"held-"+n,MembershipResources.Unit.CONTROL.bytes));
                var full=f.resources.usage();assertThrows(IllegalArgumentException.class,()->owner.exportSource(source.basis,BUDGET));assertEquals(full,f.resources.usage());
                assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            }finally{leases.forEach(MembershipResources.Lease::close);}
            try(var export=owner.exportSource(source.basis,BUDGET)){assertEquals(source.basis.digest(),export.source().basis.digest());}
        }
    }
    @Test void actualTcpReaderKeepsOriginalFilesPinnedUntilReplyAndCanThenRetire()throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;
        try(var group=helper.new Group(3)) {
            var f=group.fixture;f.campaign(1);var copies=new ArrayList<MembershipFloor.Copy>();
            for(var target:f.request.targets())try(var peer=f.open(target,"floor-copy")){copies.add(peer.floorCopyCurrent());}
            var target=f.request.targets().getFirst();
            try(var owner=f.open(target,"tcp-source-owner")) {
                owner.establishFloor(copies.subList(0,2));owner.retireInactive();
                var original=owner.beginActivation();owner.beginActivation();String id=(String)original.basis.value().get("basisId");
                var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
                try(var export=owner.exportSource(original.basis,BUDGET)) {
                    var packet=export.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.CAPSULE).findFirst().orElseThrow();
                    group.start(0,(peer,request)->{
                        var payload=object(request.value().get("payload"));assertEquals(id,payload.get("id"));assertEquals(packet.digest(),payload.get("digest"));
                        entered.countDown();V53MembershipTransportTest.await(release);byte[] data=export.read(packet.digest(),number(payload.get("offset")),1024);
                        return V53ActivationTest.response(request,"CHUNK",Map.of("id",id,"action","DATA","offset",0L,"digest",hash(data),"bytes",Base64.getEncoder().encodeToString(data)));
                    },MembershipTransport.Events.NONE,V53MembershipTransportTest.bounds(2,10000,FRAME),V53MembershipTransportTest.resources(MembershipResources.QUEUE_LIMIT));
                    var reader=group.start(1);var request=group.request(1,0,"CHUNK",Map.of("id",id,"action","REQUEST","offset",0L,"digest",packet.digest(),"bytes",""));
                    var pending=reader.exchange(group.identities.getFirst(),request,"CHUNK",V53MembershipTransportTest.deadline());
                    assertTrue(entered.await(5,TimeUnit.SECONDS));var before=V53ReplayFilesTest.files(target.replicaDirectory());
                    assertEquals("source export pins original files",assertThrows(IllegalArgumentException.class,()->owner.retireSource(id)).getMessage());assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
                    release.countDown();var reply=pending.get(10,TimeUnit.SECONDS);byte[] actual=Base64.getDecoder().decode((String)object(reply.value().get("payload")).get("bytes"));
                    assertArrayEquals(export.read(packet.digest(),0,1024),actual);
                }
                owner.retireSource(id);assertFalse(Files.exists(target.replicaDirectory().resolve("sources").resolve(id)));
            }
        }
    }
}
