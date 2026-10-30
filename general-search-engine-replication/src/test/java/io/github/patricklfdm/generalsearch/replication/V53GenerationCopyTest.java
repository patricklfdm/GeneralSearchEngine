package io.github.patricklfdm.generalsearch.replication;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Actual receiving primitives over conditional adopted fixtures; no full protocol claim. */
class V53GenerationCopyTest {
  @org.junit.jupiter.api.io.TempDir Path temp;
  @org.junit.jupiter.api.Test void partialImageBorrowStillFetchesCompleteOriginalAndClosesItsExport()throws Exception {
    for(boolean loseCommit:List.of(false,true)) {
      var capsule=new V53CapsuleFixture(3,"REPLACE",0);
      byte[] extra="fixture-retained-other-application".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
      capsule.source.images.put(hash(extra),extra);capsule.images.put(hash(extra),(long)extra.length);
      var fixture=new V53CurrentGenerationFixture(3,capsule);Path root=Files.createDirectory(temp.resolve("partial-"+loseCommit));
      fixture.provision(root.resolve("source"));V53FloorWorker.provision(root.resolve("reader"),3,0,3);var a=resources();var b=resources();
      try(var source=MembershipGrantJournal.openGenerations(root.resolve("source"),fixture.root(),V53DeclarationsTest.node(1),a,fixture::verify,e->{});
          var reader=MembershipGrantJournal.openGenerations(root.resolve("reader"),fixture.root(),V53DeclarationsTest.node(3),b,fixture::verify,e->{});
          var service=MembershipTransferService.prefix(source,a,bounds(),()->{},()->0L,0,BUDGET)) {
        var state=reader.discoveryState(b);var hint=new MembershipDiscovery.Hint(source.activationIdentity(),source.activationContext().cut,false);
        String borrowed=reader.activationCapsule().terminal().application();var lost=new AtomicBoolean();var retried=new ArrayList<String>();
        MembershipSourcePull.Link link=(peer,r,kind,deadline)->{try{
          assertEquals(BUDGET,deadline);var response=service.handle(reader.activationIdentity(),r);
          if(loseCommit && r.kind().equals("TRANSFER_COMMIT") && object(r.value().get("payload")).get("digest").equals(borrowed)) {
            retried.add(r.digest());if(lost.compareAndSet(false,true))throw new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost final ACK",null);
          }
          return CompletableFuture.completedFuture(response);
        }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}};
        var before=b.usage();
        try(var images=reader.exportPrefix(MembershipContext.cutDigest(state.context().cut),state.ballot(),state.context().authority(),b,()->0L,0,BUDGET)) {
          Path probe=root.resolve("probe");
          try(var prefix=MembershipSourcePull.prefix(reader,hint,b,bounds(),link,()->{},()->0L,0,BUDGET)) {
            assertThrows(MembershipSourcePull.MissingBorrowedImages.class,()->prefix.fetchBorrowedPrefix(probe,images));
          }
          assertFalse(Files.exists(probe));assertEquals(0,service.usage().live());
          try(var prefix=MembershipSourcePull.prefix(reader,hint,b,bounds(),link,()->{},()->0L,0,BUDGET);
              var generation=MembershipSourcePull.prefix(reader,hint,b,bounds(),link,()->{},()->0L,0,BUDGET)) {
            prefix.fetchPrefix(root.resolve("complete"),images);assertEquals(0,service.usage().live());
            assertEquals(before.counts().get(MembershipResources.Unit.APPLICATION)+1,b.usage().counts().get(MembershipResources.Unit.APPLICATION));
            var copy=generation.fetchGeneration(prefix);copy.check();assertEquals(0,service.usage().live());
            var original=source.floorCopyCurrent();assertEquals(original.fileNames(),copy.fileNames());
            for(String name:original.fileNames())assertArrayEquals(original.fileBytes(name),copy.fileBytes(name));
          }
        }
        assertEquals(before,b.usage());assertEquals(loseCommit,lost.get());
        if(loseCommit){assertEquals(2,retried.size());assertEquals(1,new HashSet<>(retried).size());}
      }
      assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());
    }
  }
  @org.junit.jupiter.api.Test void repeatedBorrowedCopiesReleaseRemoteExportsAtTheExactLastCommit()throws Exception {
    var fixture=new V53CurrentGenerationFixture(3,0,false);Path root=Files.createDirectory(temp.resolve("repeated"));
    fixture.provision(root.resolve("source"));V53FloorWorker.provision(root.resolve("reader"),3,0,3);var a=resources();var b=resources();
    try(var source=MembershipGrantJournal.openGenerations(root.resolve("source"),fixture.root(),V53DeclarationsTest.node(1),a,fixture::verify,e->{});
        var reader=MembershipGrantJournal.openGenerations(root.resolve("reader"),fixture.root(),V53DeclarationsTest.node(3),b,fixture::verify,e->{});
        var service=MembershipTransferService.prefix(source,a,bounds(),()->{},()->0L,0,BUDGET)) {
      var request=new AtomicReference<Decoded>();var reply=new AtomicReference<Decoded>();
      MembershipSourcePull.Link link=(peer,r,kind,deadline)->{try{var response=service.handle(reader.activationIdentity(),r);request.set(r);reply.set(response);
        return CompletableFuture.completedFuture(response);}catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}};
      var state=reader.discoveryState(b);var before=b.usage();
      try(var images=reader.exportPrefix(MembershipContext.cutDigest(state.context().cut),state.ballot(),state.context().authority(),b,()->0L,0,BUDGET)) {
        for(int i=0;i<8;i++) {
          var hint=new MembershipDiscovery.Hint(source.activationIdentity(),source.activationContext().cut,false);
          try(var prefix=MembershipSourcePull.prefix(reader,hint,b,bounds(),link,()->{},()->0L,0,BUDGET);
              var generation=MembershipSourcePull.prefix(reader,hint,b,bounds(),link,()->{},()->0L,0,BUDGET)) {
            prefix.fetchBorrowedPrefix(root.resolve("receive-"+i),images);assertEquals(0,service.usage().live());
            var copy=generation.fetchGeneration(prefix);copy.check();assertEquals(0,service.usage().live());
            assertEquals(before.counts().get(MembershipResources.Unit.APPLICATION),b.usage().counts().get(MembershipResources.Unit.APPLICATION));
            assertArrayEquals(reply.get().bytes(),service.handle(reader.activationIdentity(),request.get()).bytes(),"exact final retry");
            var changed=new TreeMap<>(request.get().value());changed.put("sequence",number(changed.get("sequence"))+1);
            assertThrows(IllegalArgumentException.class,()->service.handle(reader.activationIdentity(),decode(encode("wire","TRANSFER_COMMIT",changed),"wire","TRANSFER_COMMIT")));
          }
        }
      }
      assertEquals(before,b.usage());assertEquals(16,service.usage().traces());assertEquals(0,service.usage().live());
    }
    assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());
  }
  @org.junit.jupiter.api.Test void completeAdoptedCopiesAndBoundedOriginalLifetime()throws Exception {
    Path output=temp.resolve("adopted");Files.createDirectories(output);var rows=new ArrayList<Map<String,Object>>();
    for(String mode:List.of("complete","lost-offer","lost-data","lost-commit","exhausted","deadline","different-start","closed-prefix")) {
      var helper=new V53RetainedProvenanceTest();helper.temp=Files.createDirectory(output.resolve(mode));
      var sent=new ArrayList<String>();var lost=new AtomicBoolean();var calls=new AtomicInteger();
      try(var a=helper.new Adopted(false)) {
        var before=V53ReplayFilesTest.files(a.scratch.getParent().resolve("source"));
        MembershipSourcePull.Link link=(peer,request,kind,deadline)-> {
          try {
            calls.incrementAndGet();sent.add(request.digest());
            if(mode.equals("exhausted"))throw new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null);
            var reply=a.service.handle(a.reader.activationIdentity(),request);
            if(mode.equals("deadline") && request.kind().equals("TRANSFER_COMMIT"))a.clock.set(BUDGET);
            String drop=mode.equals("lost-offer")?"SOURCE_OFFER":mode.equals("lost-data")?"CHUNK":"TRANSFER_COMMIT";
            if(mode.startsWith("lost-") && kind.equals(drop) && lost.compareAndSet(false,true))throw new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null);
            return CompletableFuture.completedFuture(reply);
          }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
        };
        long started=mode.equals("different-start")?1:0;
        if(started!=0)a.clock.set(started);
        var hint=new MembershipDiscovery.Hint(a.source.activationIdentity(),a.source.activationContext().cut,false);
        try(var pull=MembershipSourcePull.prefix(a.reader,hint,a.b,bounds(),link,()->{},a.clock::get,started,BUDGET)) {
          if(mode.equals("closed-prefix"))a.pull.close();
          if(mode.equals("complete") || mode.startsWith("lost-")) {
            var copy=pull.fetchGeneration(a.pull);var original=a.source.floorCopyCurrent();
            assertArrayEquals(original.generation.bytes(),copy.generation.bytes());assertEquals(original.fileNames(),copy.fileNames());
            for(String name:original.fileNames())assertArrayEquals(original.fileBytes(name),copy.fileBytes(name),name);
            assertEquals(original.owner,copy.owner);copy.check();
            assertTrue(copy.capsule.verifiedAncestry(pull.ancestryBytes()).stream().allMatch(b->b.owned.isEmpty()));
            if(mode.startsWith("lost-")){assertTrue(lost.get());assertEquals(1,sent.size()-new HashSet<>(sent).size());}
          } else {
            assertThrows(Exception.class,()->pull.fetchGeneration(a.pull));
            if(mode.equals("exhausted"))assertEquals(3,calls.get());
            if(mode.equals("different-start") || mode.equals("closed-prefix"))assertEquals(0,calls.get());
          }
        }
        assertEquals(before,V53ReplayFilesTest.files(a.scratch.getParent().resolve("source")));
      }
      rows.add(Map.of("case",mode,"status","PASS","requests",calls.get()));System.out.println(canonicalString(rows.getLast()));
      Files.write(output.resolve("receipt.json"),canonical(Map.of("status",rows.size()==8?"DIAGNOSTIC_PASS":"INCOMPLETE","cases",rows,"qualification",false,"history","conditional-fixture"),65536));
    }
  }
  @org.junit.jupiter.api.Test void completeStableJointAndFinalCopiesPreserveOriginalTail()throws Exception {
    for(int size:List.of(3,4,5))for(int through:List.of(0,6,7))for(boolean tail:List.of(false,true)) {
      var fixture=new V53CurrentGenerationFixture(size,through,tail);Path root=Files.createDirectory(temp.resolve("shape-"+size+"-"+through+"-"+tail));
      fixture.provision(root.resolve("source"));V53FloorWorker.provision(root.resolve("reader"),size,0,3);var a=resources();var b=resources();
      try(var source=MembershipGrantJournal.openGenerations(root.resolve("source"),fixture.root(),V53DeclarationsTest.node(1),a,fixture::verify,e->{});
          var reader=MembershipGrantJournal.openGenerations(root.resolve("reader"),fixture.root(),V53DeclarationsTest.node(3),b,fixture::verify,e->{});
          var service=MembershipTransferService.prefix(source,a,bounds(),()->{},()->0L,0,BUDGET)) {
        MembershipSourcePull.Link link=(peer,request,kind,deadline)->{try{return CompletableFuture.completedFuture(service.handle(reader.activationIdentity(),request));}catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}};
        var hint=new MembershipDiscovery.Hint(source.activationIdentity(),source.activationContext().cut,false);
        try(var prefix=MembershipSourcePull.prefix(reader,hint,b,bounds(),link,()->{},()->0L,0,BUDGET);
            var generation=MembershipSourcePull.prefix(reader,hint,b,bounds(),link,()->{},()->0L,0,BUDGET)) {
          prefix.fetchPrefix(root.resolve("receive"));var copy=generation.fetchGeneration(prefix);var original=source.floorCopyCurrent();
          assertArrayEquals(original.generation.bytes(),copy.generation.bytes());assertEquals(original.fileNames(),copy.fileNames());
          for(String name:original.fileNames())assertArrayEquals(original.fileBytes(name),copy.fileBytes(name));
          assertEquals(fixture.accepted,copy.generation.value().get("ownedTail"));
          if(tail)assertArrayEquals(fixture.admitted.packet.objectBytes(fixture.accepted),copy.fileBytes("owned-tail.gsr"));
        }
      }
      assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());
    }
  }
  static String canonicalString(Object value){return new String(canonical(value,65536),java.nio.charset.StandardCharsets.UTF_8);}
}
