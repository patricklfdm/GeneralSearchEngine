package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Original physical owner loss must invalidate a partially received generation. */
class V53GenerationCopyFaultTest {
 @TempDir Path temp;
 @Test void noCopyEscapesAfterManifestWhenActualOwnershipChanges()throws Exception {
  for(String fault:List.of("source-close","reader-close","source-bytes","source-inode","reader-fence")) {
   var helper=new V53RetainedProvenanceTest();helper.temp=Files.createDirectory(temp.resolve(fault));var injected=new AtomicBoolean();
   try(var a=helper.new Adopted(false)) {
    MembershipSourcePull.Link link=(peer,request,kind,deadline)-> {
     try {
      var response=a.service.handle(a.reader.activationIdentity(),request);
      if(request.kind().equals("TRANSFER_COMMIT") && injected.compareAndSet(false,true)) {
       if(fault.equals("source-close"))a.source.close();
       else if(fault.equals("reader-close"))a.reader.close();
       else if(fault.equals("reader-fence")) {
        var ballot=new TreeMap<>(a.reader.discoveryState(a.b).ballot());ballot.put("counter",100L);a.reader.observeCurrent(ballot);
       } else {
        Path source=a.scratch.getParent().resolve("source");var selector=decode(Files.readAllBytes(source.resolve("selector.gsr")),"records","SELECTOR");
        Path file=source.resolve("generations").resolve((String)selector.value().get("generation")).resolve("promise.gsr");byte[] original=Files.readAllBytes(file);
        if(fault.equals("source-bytes")){original[original.length-1]^=1;Files.write(file,original);}
        else {Path replaced=file.resolveSibling("replacement");Files.write(replaced,original);Files.move(replaced,file,StandardCopyOption.REPLACE_EXISTING);}
       }
      }
      return CompletableFuture.completedFuture(response);
     }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
    };
    var hint=new MembershipDiscovery.Hint(a.source.activationIdentity(),a.source.activationContext().cut,false);
    try(var pull=MembershipSourcePull.prefix(a.reader,hint,a.b,bounds(),link,()->{},a.clock::get,0,BUDGET)) {
     assertThrows(Exception.class,()->pull.fetchGeneration(a.pull));assertTrue(injected.get(),fault);
     assertThrows(IllegalArgumentException.class,pull::ancestryManifest);
    }
   }
  }
 }
 @Test void cancellationOfTheOriginalExchangeReleasesReceivingMetadata()throws Exception {
  var helper=new V53RetainedProvenanceTest();helper.temp=temp;
  try(var a=helper.new Adopted(false)) {
   var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);var before=a.b.usage();
   MembershipSourcePull.Link link=(peer,r,kind,deadline)-> {
    if(r.kind().equals("CHUNK") && r.value().get("sequence").equals(2L)){entered.countDown();return pending;}
    try{return CompletableFuture.completedFuture(a.service.handle(a.reader.activationIdentity(),r));}
    catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
   };
   var hint=new MembershipDiscovery.Hint(a.source.activationIdentity(),a.source.activationContext().cut,false);
   try(var pull=MembershipSourcePull.prefix(a.reader,hint,a.b,bounds(),link,()->{},a.clock::get,0,BUDGET);var executor=Executors.newVirtualThreadPerTaskExecutor()) {
    var work=executor.submit(()->pull.fetchGeneration(a.pull));assertTrue(entered.await(5,TimeUnit.SECONDS));pull.close();
    assertThrows(ExecutionException.class,()->work.get(5,TimeUnit.SECONDS));assertTrue(pending.isCancelled());
   }
   assertEquals(before,a.b.usage());
  }
 }
 @Test void malformedOriginalMetadataFailsWithoutRetryOrLeakingItsReservation()throws Exception {
  for(String fault:List.of("oversized-manifest","corrupt-manifest","changed-commit")) {
   var helper=new V53RetainedProvenanceTest();helper.temp=Files.createDirectory(temp.resolve(fault));var calls=new AtomicInteger();
   try(var a=helper.new Adopted(false)) {
    var before=a.b.usage();
    MembershipSourcePull.Link link=(peer,request,kind,deadline)-> {
     try {
      int attempt=calls.incrementAndGet();var response=a.service.handle(a.reader.activationIdentity(),request);
      int target=fault.equals("oversized-manifest")?1:fault.equals("corrupt-manifest")?2:3;
      if(attempt==target) {
       var value=new TreeMap<>(response.value());var payload=new TreeMap<>(object(value.get("payload")));
       if(fault.equals("oversized-manifest"))payload.put("bytes",65537L);
       else if(fault.equals("corrupt-manifest")) {
        byte[] data=Base64.getDecoder().decode((String)payload.get("bytes"));data[data.length-1]^=1;
        payload.put("bytes",Base64.getEncoder().encodeToString(data));payload.put("digest",hash(data));
       }else payload.put("digest","f".repeat(64));
       value.put("payload",payload);response=decode(encode("wire",response.kind(),value),"wire",response.kind());
      }
      return CompletableFuture.completedFuture(response);
     }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
    };
    var hint=new MembershipDiscovery.Hint(a.source.activationIdentity(),a.source.activationContext().cut,false);
    try(var pull=MembershipSourcePull.prefix(a.reader,hint,a.b,bounds(),link,()->{},a.clock::get,0,BUDGET)) {
     var failure=assertThrows(IllegalArgumentException.class,()->pull.fetchGeneration(a.pull));
     String reason=fault.equals("oversized-manifest")?"ancestry metadata capacity":fault.equals("corrupt-manifest")?"ancestry metadata digest":"source transfer commit binding";
     assertTrue(failure.getMessage().contains(reason),failure.toString());
     assertEquals(fault.equals("oversized-manifest")?1:fault.equals("corrupt-manifest")?2:3,calls.get());
    }
    assertEquals(before,a.b.usage());
   }
  }
 }
 @Test void removedOwnerMayServeHistoryButCannotSupplyAGoverningFloorCopy()throws Exception {
  var helper=new V53RetainedProvenanceTest();helper.temp=temp;
  try(var a=helper.new Adopted(false)) {
   a.reader.adoptCurrent(a.copied,a.received.images(),List.of());
   assertFalse(a.reader.activationContext().voters().contains(a.reader.activationIdentity().nodeId().value()));
   try(var service=MembershipTransferService.prefix(a.reader,a.b,bounds(),()->{},a.clock::get,0,BUDGET)) {
    MembershipSourcePull.Link link=(peer,request,kind,deadline)-> {
     try{return CompletableFuture.completedFuture(service.handle(a.source.activationIdentity(),request));}
     catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
    };
    var hint=new MembershipDiscovery.Hint(a.reader.activationIdentity(),a.reader.activationContext().cut,false);
    try(var prefix=MembershipSourcePull.prefix(a.source,hint,a.a,bounds(),link,()->{},a.clock::get,0,BUDGET);
        var generation=MembershipSourcePull.prefix(a.source,hint,a.a,bounds(),link,()->{},a.clock::get,0,BUDGET)) {
     prefix.fetchPrefix(temp.resolve("removed-copy"));
     assertEquals(a.copied.context.cut,prefix.verifiedPrefix().context.cut);
     var error=assertThrows(IllegalArgumentException.class,()->generation.fetchGeneration(prefix));
     assertTrue(error.getMessage().contains("floor copy is not a governing voter"),error.toString());
    }
   }
  }
 }
}
