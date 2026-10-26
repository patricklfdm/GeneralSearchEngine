package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53SourceReceiveTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(60);
    static MembershipResources budget(){return new MembershipResources(512*MIB);}
    static MembershipReceiveFile file(Path path,byte[] body,MembershipResources resources,AtomicLong clock,MembershipReceiveFile.Events events)throws Exception {
        return new MembershipReceiveFile(path,V53ResourceTransferTest.binding(body),resources,Unit.SOURCE,3,clock::get,0,100,events);
    }
    static void complete(MembershipReceiveFile file,byte[] bytes)throws Exception {
        var binding=V53ResourceTransferTest.binding(bytes);
        for(int at=0;at<bytes.length;at+=3){byte[] part=Arrays.copyOfRange(bytes,at,Math.min(at+3,bytes.length));file.chunk(binding,at,part,hash(part));}
    }
    @Test void exactFileStaysReservedThroughValidationAndDeletesBeforeReleasing()throws Exception {
        byte[] body={1,2,3,4,5,6};var binding=V53ResourceTransferTest.binding(body);var resources=budget();var events=new ArrayList<String>();Path path=temp.resolve("scratch");var calls=new AtomicInteger();
        try(var received=file(path,body,resources,new AtomicLong(),events::add)) {
            assertEquals(body.length,resources.usage().staging());assertEquals(0,Files.size(path));
            assertThrows(IllegalArgumentException.class,received::bytes);
            byte[] first=Arrays.copyOf(body,3);received.chunk(binding,0,first,hash(first));received.chunk(binding,0,first,hash(first));assertEquals(3,Files.size(path));
            byte[] last=Arrays.copyOfRange(body,3,6);received.chunk(binding,3,last,hash(last));
            received.finish(binding,p->{assertArrayEquals(body,Files.readAllBytes(p));calls.incrementAndGet();assertFalse(received.verified());});
            received.finish(binding,p->fail("duplicate semantic commit"));
            assertEquals(1,calls.get());assertTrue(received.verified());assertArrayEquals(body,received.bytes());
            assertEquals(List.of("CREATED","CHUNK_WRITTEN","CHUNK_WRITTEN","CHUNK_WRITTEN","FILE_FORCED","DIRECTORY_FORCED"),events);
            assertEquals(body.length,resources.usage().staging());
            assertThrows(IllegalArgumentException.class,()->received.chunk(binding,3,last,hash(last)));
        }
        assertFalse(Files.exists(path));assertEquals(0,resources.usage().leases());
    }
    @Test void invalidChunksAndIncompleteCommitCannotExposeOrAlterTheFile()throws Exception {
        byte[] body={1,2,3,4};var binding=V53ResourceTransferTest.binding(body);var resources=budget();Path path=temp.resolve("scratch");
        try(var received=file(path,body,resources,new AtomicLong(),MembershipReceiveFile.Events.NONE)) {
            var foreign=new MembershipTransfer.Binding(binding.root(),UUID.randomUUID(),binding.transfer(),binding.source(),binding.basisId(),binding.basisDigest(),binding.cutDigest(),binding.digest(),binding.bytes(),binding.kind());
            assertThrows(IllegalArgumentException.class,()->received.chunk(foreign,0,new byte[]{1},hash(new byte[]{1})));
            assertThrows(IllegalArgumentException.class,()->received.chunk(binding,1,new byte[]{1},hash(new byte[]{1})));
            assertThrows(IllegalArgumentException.class,()->received.chunk(binding,0,new byte[]{1},"00".repeat(32)));
            assertThrows(IllegalArgumentException.class,()->received.chunk(binding,Long.MAX_VALUE,new byte[]{1},hash(new byte[]{1})));
            assertThrows(IllegalArgumentException.class,()->received.finish(binding,p->fail("incomplete semantic call")));
            assertEquals(0,Files.size(path));complete(received,body);received.finish(binding,p->{});assertArrayEquals(body,received.bytes());
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void capacityAndOccupiedPathsRejectBeforeCreatingOrChangingAnything()throws Exception {
        byte[] body={1,2,3};Path path=temp.resolve("scratch");var clock=new AtomicLong();var tiny=new MembershipResources(2);
        assertThrows(IllegalArgumentException.class,()->file(path,body,tiny,clock,MembershipReceiveFile.Events.NONE));assertFalse(Files.exists(path));assertEquals(0,tiny.usage().leases());
        var resources=budget();Files.write(path,new byte[]{9});
        assertThrows(RuntimeException.class,()->file(path,body,resources,clock,MembershipReceiveFile.Events.NONE));assertArrayEquals(new byte[]{9},Files.readAllBytes(path));assertEquals(0,resources.usage().leases());
        Path alias=temp.resolve("alias");Files.createSymbolicLink(alias,path);
        assertThrows(RuntimeException.class,()->file(alias,body,resources,clock,MembershipReceiveFile.Events.NONE));assertEquals(0,resources.usage().leases());
    }
    @Test void semanticHashAndForceFailuresRetainOwnershipUntilExplicitCleanup()throws Exception {
        byte[] body={1,2,3};var binding=V53ResourceTransferTest.binding(body);
        for(String fault:List.of("semantic","hash","FILE_FORCED","DIRECTORY_FORCED")) {
            var resources=budget();Path path=temp.resolve(fault);
            try(var received=file(path,body,resources,new AtomicLong(),event->{if(event.equals(fault))throw new IOException("injected "+fault);})) {
                complete(received,body);
                if(fault.equals("hash"))Files.write(path,new byte[]{3,2,1});
                assertThrows(Exception.class,()->received.finish(binding,p->{if(fault.equals("semantic"))throw new IllegalArgumentException("invalid packet");}));
                assertFalse(received.verified());assertThrows(RuntimeException.class,received::bytes);
                assertTrue(Files.exists(path));assertEquals(body.length,resources.usage().staging());
            }
            assertFalse(Files.exists(path));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void originalDeadlineIncludesChunksSemanticValidationAndForceAndCannotRevive()throws Exception {
        byte[] body={1,2,3};var binding=V53ResourceTransferTest.binding(body);
        for(String at:List.of("CREATED","CHUNK_WRITTEN","semantic","FILE_FORCED","DIRECTORY_FORCED")) {
            Path path=temp.resolve(at);var resources=budget();var clock=new AtomicLong();
            if(at.equals("CREATED")) {
                assertThrows(IllegalArgumentException.class,()->file(path,body,resources,clock,event->clock.set(100)));
                assertFalse(Files.exists(path));assertEquals(0,resources.usage().leases());continue;
            }
            try(var received=file(path,body,resources,clock,event->{if(event.equals(at))clock.set(100);})) {
                if(at.equals("CHUNK_WRITTEN"))assertThrows(IllegalArgumentException.class,()->complete(received,body));
                else {complete(received,body);assertThrows(IllegalArgumentException.class,()->received.finish(binding,p->{if(at.equals("semantic"))clock.set(100);}));}
                clock.set(0);assertFalse(received.verified());assertThrows(IllegalArgumentException.class,received::bytes);assertEquals(body.length,resources.usage().staging());
            }
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void changedInodesLinksAndParentCannotBeDeletedAsOwnedScratch()throws Exception {
        byte[] body={1,2,3};
        for(String fault:List.of("inode","link","parent")) {
            Path dir=Files.createDirectory(temp.resolve(fault)),path=dir.resolve("scratch"),saved=temp.resolve(fault+"-original");var resources=budget();
            var received=file(path,body,resources,new AtomicLong(),MembershipReceiveFile.Events.NONE);complete(received,body);
            if(fault.equals("inode")){Files.move(path,saved);Files.write(path,new byte[]{8});}
            else if(fault.equals("link"))Files.createLink(saved,path);
            else {Files.move(dir,saved);Files.createDirectory(dir);Files.write(path,new byte[]{8});}
            assertThrows(Exception.class,received::close);assertEquals(body.length,resources.usage().staging());assertTrue(Files.exists(path));
            if(fault.equals("inode")){Files.delete(path);Files.move(saved,path);}
            else if(fault.equals("link"))Files.delete(saved);
            else {Files.delete(path);Files.delete(dir);Files.move(saved,dir);}
            received.close();received.close();assertEquals(0,resources.usage().leases());assertFalse(Files.exists(path));
        }
    }
    @Test void verifiedBytesAreRecheckedAfterCommitAndCannotBeSubstituted()throws Exception {
        byte[] body={1,2,3};Path path=temp.resolve("scratch");var resources=budget();
        try(var received=file(path,body,resources,new AtomicLong(),MembershipReceiveFile.Events.NONE)) {
            complete(received,body);received.finish(V53ResourceTransferTest.binding(body),p->{});
            byte[] copy=received.bytes();copy[0]=9;assertArrayEquals(body,received.bytes());Files.write(path,new byte[]{3,2,1});
            assertThrows(IllegalArgumentException.class,received::bytes);assertFalse(received.verified());
            Files.write(path,body);assertThrows(IllegalArgumentException.class,received::bytes);assertEquals(body.length,resources.usage().staging());
        }
        assertEquals(0,resources.usage().leases());
    }
    V53BootstrapPublicationTest.Fixture fixture(int size)throws Exception {
        Path dir=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
        return new V53BootstrapPublicationTest.Fixture(dir,Files.createDirectory(dir.resolve("raw")),size,false);
    }
    static MembershipSourceExport.Content packetOffer(MembershipSourceExport export)throws Exception {
        return export.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.CAPSULE).findFirst().orElseThrow();
    }
    static MembershipSourceReceive receiver(Path path,MembershipSourceExport export,MembershipResources resources,AtomicLong clock,long budget)throws Exception {
        var source=export.source();return new MembershipSourceReceive(path,source.capsule.context.root,source.owner,export.promise(),source.basis,
                UUID.randomUUID(),packetOffer(export),resources,1024,clock::get,0,budget);
    }
    static void send(MembershipSourceReceive received,MembershipSourceExport export,MembershipTransfer.Binding binding)throws Exception {
        for(long offset=0;offset<binding.bytes();) {
            byte[] bytes=export.read(binding.digest(),offset,1024);received.chunk(binding,offset,bytes,hash(bytes));
            received.chunk(binding,offset,bytes,hash(bytes));offset+=bytes.length;
        }
        received.finish(binding);received.finish(binding);
    }
    @Test void completeActualOriginalsStageAtEverySizeWithoutCreatingAnAuthority()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-source-receive/run-"+UUID.randomUUID()));
        System.out.println("v53SourceReceiveEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("size-"+size)),raw,size,false);var target=f.request.targets().getFirst();var resources=budget();
            try(var owner=f.open(target,"receive-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
                Path captured=Files.createDirectory(raw.resolve("captured"));for(var member:f.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
                Path output=Files.createDirectory(raw.resolve("exported"));var rows=new ArrayList<Map<String,Object>>();
                for(var content:export.contents()){Files.write(output.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));rows.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));}
                Files.write(raw.resolve("contents.json"),ReplicaJson.encode(rows,65536));Path scratch=temp.resolve("received-"+size);
                try(var received=receiver(scratch,export,resources,new AtomicLong(),100)) {
                    assertEquals(1,resources.usage().counts().get(Unit.SOURCE));assertEquals(0,resources.usage().counts().getOrDefault(Unit.APPLICATION,0));
                    assertThrows(IllegalArgumentException.class,received::images);send(received,export,received.packetBinding());
                    assertEquals(export.source().capsule.packet.images().size(),resources.usage().counts().get(Unit.APPLICATION));
                    for(var image:received.imageBindings())send(received,export,image);
                    assertArrayEquals(export.source().capsule.packet.bytes(),received.packet().bytes());received.packet().verifyImages(received.images());
                    assertArrayEquals(export.promise().bytes(),received.promise().bytes());assertArrayEquals(export.source().basis.bytes(),received.basis().bytes());
                    V53JournalApplicationTest.copy(scratch,raw.resolve("received"));
                }
                assertFalse(Files.exists(scratch));assertEquals(0,resources.usage().leases());
            }
            f.snapshot("after");cases.add(Map.of("size",size,"contents",4));
        }
        Files.write(evidence.resolve("receipt.json"),ReplicaJson.encode(Map.of("schema","gse-v53-source-receive-v1","status","PASS","cases",cases,
                "publicRuntime",false,"network",false,"scope","complete-source-scratch-only"),65536));
    }
    @Test void imageCapacityFailureNeverAdmitsAnApplicationChunkAndCloseReclaimsOnlyScratch()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();Path scratch=temp.resolve("scratch");
        try(var owner=f.open(target,"capacity-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
            var resources=new MembershipResources(packetOffer(export).bytes());var before=V53ReplayFilesTest.files(target.replicaDirectory());
            try(var received=receiver(scratch,export,resources,new AtomicLong(),100)) {
                assertThrows(IllegalArgumentException.class,()->send(received,export,received.packetBinding()));
                assertThrows(IllegalArgumentException.class,received::imageBindings);assertEquals(1,resources.usage().counts().get(Unit.SOURCE));
                assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            }
            assertEquals(0,resources.usage().leases());assertFalse(Files.exists(scratch));
        }
    }
    @Test void sourceDeadlineDoesNotRestartBetweenPacketAndImagesAndLateBytesCannotRevive()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();var resources=budget();var clock=new AtomicLong();
        try(var owner=f.open(target,"deadline-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET);
            var received=receiver(temp.resolve("scratch"),export,resources,clock,100)) {
            clock.set(90);send(received,export,received.packetBinding());var image=received.imageBindings().getFirst();clock.set(100);
            assertThrows(IllegalArgumentException.class,()->received.chunk(image,0,new byte[]{1},hash(new byte[]{1})));
            clock.set(0);assertThrows(IllegalArgumentException.class,received::imageBindings);assertTrue(resources.usage().staging()>0);
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void extraFilesAndReplacementDirectoriesBlockCleanupUntilOriginalInventoryIsRestored()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();var resources=budget();Path scratch=temp.resolve("scratch");
        try(var owner=f.open(target,"inventory-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
            var received=receiver(scratch,export,resources,new AtomicLong(),100);Path foreign=scratch.resolve("foreign");Files.write(foreign,new byte[]{9});
            assertThrows(IllegalArgumentException.class,received::close);assertTrue(Files.exists(foreign));assertTrue(resources.usage().leases()>0);
            Files.delete(foreign);Path moved=temp.resolve("moved");Files.move(scratch,moved);Files.createDirectory(scratch);
            assertThrows(IllegalArgumentException.class,received::close);Files.delete(scratch);Files.move(moved,scratch);received.close();assertEquals(0,resources.usage().leases());
        }
    }
    @Test void sixSourcesShareOneCountEachAndNeverStartAnUnboundedSecondSet()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();var resources=budget();var held=new ArrayList<MembershipSourceReceive>();
        try(var owner=f.open(target,"count-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
            try {
                for(int n=0;n<6;n++)held.add(receiver(temp.resolve("receive-"+n),export,resources,new AtomicLong(),100));
                assertEquals(6,resources.usage().counts().get(Unit.SOURCE));var full=resources.usage();
                assertThrows(IllegalArgumentException.class,()->receiver(temp.resolve("receive-6"),export,resources,new AtomicLong(),100));
                assertEquals(full,resources.usage());assertFalse(Files.exists(temp.resolve("receive-6")));
                held.removeFirst().close();held.add(receiver(temp.resolve("receive-replacement"),export,resources,new AtomicLong(),100));
            }finally{for(var received:held)received.close();}
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void completedSourceRechecksPacketBeforeImagesAreExposed()throws Exception {
        var f=fixture(3);var target=f.request.targets().getFirst();var resources=budget();Path scratch=temp.resolve("scratch");
        try(var owner=f.open(target,"recheck-source");var export=owner.exportSource(owner.beginActivation().basis,BUDGET);
            var received=receiver(scratch,export,resources,new AtomicLong(),100)) {
            send(received,export,received.packetBinding());for(var image:received.imageBindings())send(received,export,image);
            assertFalse(received.images().isEmpty());Path packet=scratch.resolve("source.gscp");byte[] bytes=Files.readAllBytes(packet);bytes[bytes.length-1]^=1;Files.write(packet,bytes);
            assertThrows(IllegalArgumentException.class,received::images);
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void validPacketBytesFromAnotherRootCannotBecomeAReceivedSource()throws Exception {
        var first=fixture(3);var other=fixture(3);var resources=budget();
        try(var owner=first.open(first.request.targets().getFirst(),"original");var export=owner.exportSource(owner.beginActivation().basis,BUDGET);
            var foreign=other.open(other.request.targets().getFirst(),"foreign");var changed=foreign.exportSource(foreign.beginActivation().basis,BUDGET)) {
            var source=export.source();
            try(var received=new MembershipSourceReceive(temp.resolve("scratch"),source.capsule.context.root,source.owner,export.promise(),source.basis,
                    UUID.randomUUID(),packetOffer(changed),resources,1024,()->0,0,100)) {
                assertThrows(IllegalArgumentException.class,()->send(received,changed,received.packetBinding()));
                assertThrows(IllegalArgumentException.class,received::packet);assertEquals(0,resources.usage().counts().getOrDefault(Unit.APPLICATION,0));
            }
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void actualTcpChunksPopulateCompleteBoundedFilesAndDuplicateDeliveryIsIdempotent()throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;
        try(var group=helper.new Group(3)) {
            var f=group.fixture;var target=f.request.targets().getFirst();var resources=budget();
            try(var owner=f.open(target,"tcp-export");var export=owner.exportSource(owner.beginActivation().basis,BUDGET)) {
                var before=V53ReplayFilesTest.files(target.replicaDirectory());
                group.start(0,(peer,request)->{
                    var p=MembershipFormat.object(request.value().get("payload"));assertEquals("REQUEST",p.get("action"));
                    byte[] bytes=export.read((String)p.get("digest"),MembershipFormat.number(p.get("offset")),1024);
                    return V53ActivationTest.response(request,"CHUNK",Map.of("id",p.get("id"),"action","DATA","offset",p.get("offset"),"digest",hash(bytes),"bytes",Base64.getEncoder().encodeToString(bytes)));
                },MembershipTransport.Events.NONE,V53MembershipTransportTest.bounds(2,10000,FRAME),f.resources);
                var transport=group.start(1,group::status,MembershipTransport.Events.NONE,V53MembershipTransportTest.bounds(2,10000,FRAME),resources);
                try(var received=receiver(temp.resolve("tcp-scratch"),export,resources,new AtomicLong(),100)) {
                    var pending=new ArrayList<MembershipTransfer.Binding>();pending.add(received.packetBinding());int sequence=0;
                    for(int n=0;n<pending.size();n++) {
                        var binding=pending.get(n);
                        for(long offset=0;offset<binding.bytes();) {
                            var fields=new TreeMap<>(group.request(1,0,"CHUNK",Map.of("id",binding.transfer().toString(),"action","REQUEST","offset",offset,"digest",binding.digest(),"bytes","")).value());
                            fields.put("trace",binding.session().toString());fields.put("sequence",(long)++sequence);var request=decode(encode("wire","CHUNK",fields),"wire","CHUNK");
                            byte[] actual=null;
                            for(int duplicate=0;duplicate<2;duplicate++) {
                                var reply=transport.exchange(group.identities.getFirst(),request,"CHUNK",V53MembershipTransportTest.deadline()).get(10,TimeUnit.SECONDS);
                                var payload=MembershipFormat.object(reply.value().get("payload"));assertEquals(binding.transfer().toString(),payload.get("id"));assertEquals(offset,MembershipFormat.number(payload.get("offset")));
                                actual=Base64.getDecoder().decode((String)payload.get("bytes"));received.chunk(binding,offset,actual,(String)payload.get("digest"));
                            }
                            offset+=actual.length;
                        }
                        received.finish(binding);if(n==0)pending.addAll(received.imageBindings());
                    }
                    assertArrayEquals(export.source().capsule.packet.bytes(),received.packet().bytes());received.packet().verifyImages(received.images());assertTrue(sequence>1);
                    assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
                }
            }
        }
    }
}
