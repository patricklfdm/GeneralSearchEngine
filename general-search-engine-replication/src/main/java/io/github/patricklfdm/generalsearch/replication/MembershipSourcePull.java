package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded pull, retaining scratch until close. No unverified source becomes a vote.
 * The runtime must supply its live fencing guard and serialize use of the returned scratch. */
final class MembershipSourcePull implements AutoCloseable {
    @FunctionalInterface interface Link {CompletableFuture<Decoded> exchange(MembershipIdentity peer,Decoded request,String kind,long deadline);}
    @FunctionalInterface interface Guard {void check()throws IOException;}
    @FunctionalInterface interface RecordVerifier {void verify(Decoded original)throws IOException;}
    private record Offer(UUID id,MembershipSourceExport.Content content) {}
    private record Record(Decoded value,MembershipResources.Lease lease)implements AutoCloseable {
        @Override public void close(){lease.close();}
    }
    private final MembershipContext context;
    private final Decoded originalRoot;
    private final MembershipIdentity local,source;
    private final Map<String,Object> ballot;
    private final UUID session;
    private final MembershipResources resources;
    private final Link link;
    private final Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final int frameLimit,chunkLimit,maximumAttempts;
    private long sequence;
    private boolean used;
    private boolean completeSource;
    private volatile boolean closed;
    private CompletableFuture<Decoded> pending;
    private MembershipSourceReceive received;
    private Record receivedRecord;

    MembershipSourcePull(MembershipCapsule verified,MembershipIdentity local,MembershipIdentity source,Map<String,Object> ballot,UUID session,
            MembershipResources resources,ReplicationBounds bounds,Link link,Guard guard,LongSupplier clock,long started,long budget) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"source pull time budget");context=Objects.requireNonNull(verified).context;
        originalRoot=decode(verified.packet.objectBytes(context.recordRootDigest()),"records","ROOT");
        require(local.equals(context.identities.get(local.nodeId().value())) && source.equals(context.identities.get(source.nodeId().value()))
                && !local.equals(source),"source pull permanent identities");context.ballot(ballot,true);
        this.local=local;this.source=source;this.ballot=Map.copyOf(ballot);MembershipValidation.uuid(session);this.session=session;
        this.resources=Objects.requireNonNull(resources);this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;frameLimit=Math.min(FRAME,bounds.maxFrameBytes());
        require(frameLimit>=4096,"source pull frame limit");chunkLimit=Math.min(4*1024*1024,bounds.snapshotChunkBytes());
        maximumAttempts=Math.min(3,bounds.maxRetryAttempts());
    }
    private void check()throws IOException {
        require(!closed,"source pull closed");long elapsed=clock.getAsLong()-started;
        require(elapsed>=0 && elapsed<budget,"original source pull deadline");guard.check();
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"original source pull deadline");
    }
    private Decoded request(String kind,Map<String,Object> payload)throws IOException {
        check();require(sequence<MembershipValidation.MAX,"source sequence exhausted");
        return decode(encode("wire",kind,Map.of("root",context.root,"view",context.authority(),"sender",MembershipBootstrapSeed.identity(local),
                "recipient",MembershipBootstrapSeed.identity(source),"ballot",ballot,"trace",session.toString(),"sequence",++sequence,"payload",payload)),"wire",kind);
    }
    private Decoded exchange(Decoded request,String kind)throws IOException {
        require(request.size()<=frameLimit,"source pull request frame limit");var retry=new MembershipExchange(request.digest(),started,budget);
        try(var held=resources.reserve(MembershipResources.Unit.CONTROL,"source-request-"+UUID.randomUUID(),request.size())) {
            for(;;) {
                check();retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> future;
                synchronized(this){check();future=Objects.requireNonNull(link.exchange(source,request,kind,started+budget));pending=future;}
                try {
                    long left=budget-(clock.getAsLong()-started);require(left>0,"original source pull deadline");
                    Decoded result=future.get(left,TimeUnit.NANOSECONDS);check();require(result.size()<=frameLimit,"source pull response frame limit");
                    MembershipWire.correlated(request,result,kind);context.wire(result,source,local,ballot,session,number(request.value().get("sequence")));
                    // Return the real rejection to the runtime; never turn it into a source or retry it.
                    if(result.kind().equals("REJECT"))throw new Rejected(result);
                    retry.complete(request.digest(),clock.getAsLong());return result;
                }catch(InterruptedException error){future.cancel(true);Thread.currentThread().interrupt();throw new IOException("source pull interrupted",error);}
                catch(CancellationException error){throw new IOException("source pull cancelled",error);}
                catch(TimeoutException error){future.cancel(true);throw new IOException("source pull original deadline",error);}
                catch(ExecutionException error) {
                    Throwable cause=error.getCause();
                    if(!(cause instanceof MembershipTransport.Failure failure) || (failure.reason!=MembershipTransport.Reason.IO && failure.reason!=MembershipTransport.Reason.DEADLINE)) {
                        if(cause instanceof IOException io)throw io;if(cause instanceof RuntimeException runtime)throw runtime;throw new IOException("source pull failed",cause);
                    }
                    check();if(retry.attempts()>=maximumAttempts)throw failure;
                }finally{synchronized(this){if(pending==future)pending=null;}}
            }
        }
    }
    static final class Rejected extends IOException {
        private static final long serialVersionUID=1L;
        final Decoded response;
        Rejected(Decoded response){super("source pull rejected: "+object(response.value().get("payload")).get("reason"));this.response=response;}
    }
    private Offer offer(UUID id,String reference,MembershipTransfer.Kind kind,String exactDigest,Long exactBytes)throws IOException {
        var reply=exchange(request("CHUNK",Map.of("id",id.toString(),"action","REQUEST","offset",0L,"digest",reference,"bytes","")),"SOURCE_OFFER");
        var p=object(reply.value().get("payload"));String digest=(String)p.get("digest");long bytes=number(p.get("bytes"));
        require(p.get("id").equals(id.toString()) && p.get("kind").equals(kind.name()) && (exactDigest==null || exactDigest.equals(digest))
                && (exactBytes==null || exactBytes==bytes),"source offer reference/extent binding");
        long maximum=switch(kind){case RECORD->FRAME;case CAPSULE->32*MembershipResources.MIB;case APPLICATION->64*MembershipResources.MIB;};
        require(bytes>0 && bytes<=maximum,"source offer capacity");return new Offer(id,new MembershipSourceExport.Content(digest,bytes,kind));
    }
    private byte[] chunk(Offer offer,long offset)throws IOException {
        var reply=exchange(request("CHUNK",Map.of("id",offer.id.toString(),"action","REQUEST","offset",offset,"digest",offer.content.digest(),"bytes","")),"CHUNK");
        var p=object(reply.value().get("payload"));byte[] bytes=Base64.getDecoder().decode((String)p.get("bytes"));
        require(p.get("id").equals(offer.id.toString()) && p.get("action").equals("DATA") && number(p.get("offset"))==offset
                && bytes.length>0 && bytes.length<=chunkLimit && bytes.length<=offer.content.bytes()-offset && hash(bytes).equals(p.get("digest")),"source data binding/extent");return bytes;
    }
    private void commit(Offer offer)throws IOException {
        var p=Map.<String,Object>of("id",offer.id.toString(),"digest",offer.content.digest());
        require(exchange(request("TRANSFER_COMMIT",p),"TRANSFER_COMMIT").value().get("payload").equals(p),"source transfer commit binding");
    }
    private Record record(String reference,String kind)throws IOException {
        return record(reference,kind,value->{
            require(value.value().get("view").equals(context.authority()) && value.value().get("ballot").equals(ballot),"referenced grant root/view/ballot");
            if(kind.equals("BASIS"))require(value.value().get("voter").equals(source.nodeId().value()),"referenced basis source identity");
        });
    }
    private Record record(String reference,String kind,RecordVerifier verifier)throws IOException {
        require(MembershipRecordExport.KINDS.contains(kind),"referenced record kind");
        var offer=offer(UUID.randomUUID(),reference,MembershipTransfer.Kind.RECORD,reference,null);
        require(offer.content.bytes()<=number(object(object(CATALOG.get("records")).get(kind)).get("maximum")),"referenced record kind capacity");
        var lease=resources.reserve(MembershipResources.Unit.CONTROL,"source-record-"+UUID.randomUUID(),offer.content.bytes());
        try {
            byte[] bytes=new byte[Math.toIntExact(offer.content.bytes())];int offset=0;
            while(offset<bytes.length){byte[] part=chunk(offer,offset);System.arraycopy(part,0,bytes,offset,part.length);offset+=part.length;}
            require(hash(bytes).equals(reference),"referenced record digest");Decoded value=decode(bytes,"records",kind);
            require(value.value().get("root").equals(context.root),"referenced record root");verifier.verify(value);
            commit(offer);check();return new Record(value,lease);
        }catch(IOException|RuntimeException|Error error){lease.close();throw error;}
    }
    /** Borrowed actual bytes, not an Owned receipt. The protocol must validate its expected
     * context/parent/phase before commit; carried records may have an older original ballot. */
    Decoded fetchRecord(String reference,String kind,RecordVerifier verifier)throws IOException {
        Objects.requireNonNull(verifier);
        synchronized(this){require(!used && !closed,"source pull single use");used=true;}
        Record result=null;
        try {
            result=record(reference,kind,verifier);
            synchronized(this){check();receivedRecord=result;return result.value;}
        }catch(IOException|RuntimeException|Error error){
            if(result!=null)result.close();try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;
        }
    }
    record CheckpointReceipt(Decoded acknowledgement,Owned owned) {}
    /** A checkpoint observation requires contacting the ACK's permanent owner.
     * Statement/ACK bytes from a source packet alone do not establish this receipt. */
    CheckpointReceipt fetchCheckpointAcknowledgement(Decoded statement,Decoded expected)throws IOException {
        checkpointAcknowledgement(context,source,statement,expected);
        var actual=fetchRecord(expected.digest(),"CHECKPOINT_ACK",value->{
            require(Arrays.equals(value.bytes(),expected.bytes()),"checkpoint original ACK bytes");
            checkpointAcknowledgement(context,source,statement,value);
        });
        check();return new CheckpointReceipt(actual,new Owned(source.nodeId().value(),source.storageId(),actual.digest(),cutDigest(object(statement.value().get("end")))));
    }
    /** Semantic check only. Callers must separately obtain the actual owned record. */
    static void checkpointAcknowledgement(MembershipContext context,MembershipIdentity source,Decoded statement,Decoded acknowledgement) {
        require(statement.family().equals("records") && statement.kind().equals("CHECKPOINT")
                && acknowledgement.family().equals("records") && acknowledgement.kind().equals("CHECKPOINT_ACK"),"checkpoint observation record kinds");
        var s=statement.value();var a=acknowledgement.value();var end=object(s.get("end"));var view=object(end.get("view"));
        require(source.equals(context.identities.get(source.nodeId().value())) && a.get("voter").equals(source.nodeId().value())
                && a.get("incarnation").equals(source.storageId().toString()),"checkpoint observation original owner");
        require(s.get("root").equals(context.root) && a.get("root").equals(context.root) && a.get("statement").equals(statement.digest())
                && a.get("cut").equals(end),"checkpoint observation statement/end");
        require(nodes(view,"old").contains(source.nodeId().value()) || nodes(view,"new").contains(source.nodeId().value()),"checkpoint observation eligible owner");
    }
    private void receiveFile(MembershipSourceReceive receiver,MembershipTransfer.Binding binding,Offer offer)throws IOException {
        require(binding.transfer().equals(offer.id) && binding.digest().equals(offer.content.digest()) && binding.bytes()==offer.content.bytes(),"source file offer binding");
        for(long offset=0;offset<binding.bytes();) {check();byte[] bytes=chunk(offer,offset);receiver.chunk(binding,offset,bytes,hash(bytes));offset+=bytes.length;}
        check();receiver.finish(binding);check();commit(offer);
    }
    /** Result is borrowed from this pull and remains physically owned/reserved until close. */
    MembershipSourceReceive fetch(Path scratch,String originalBasisDigest)throws IOException {
        return fetch(scratch,originalBasisDigest,null);
    }
    MembershipSourceReceive fetch(Path scratch,String originalBasisDigest,MembershipSourceExport localImages)throws IOException {
        synchronized(this){require(!used && !closed,"source pull single use");used=true;}
        try(Record basis=record(originalBasisDigest,"BASIS")) {
            var fields=new TreeMap<String,Object>();for(String field:List.of("root","view","ballot","basisId"))fields.put(field,basis.value.value().get(field));
            // This derives a reference only. The exact original PROMISE still has to be fetched.
            String promised=hash(encode("records","PROMISE",fields));
            try(Record promise=record(promised,"PROMISE")) {
                var packet=offer(UUID.randomUUID(),(String)basis.value.value().get("capsule"),MembershipTransfer.Kind.CAPSULE,null,null);
                MembershipSourceReceive staging;
                synchronized(this) {
                    check();received=new MembershipSourceReceive(scratch,context.root,source,promise.value,basis.value,session,packet.id,packet.content,
                            resources,chunkLimit,clock,started,budget,localImages);
                    staging=received;
                }
                receiveFile(staging,staging.packetBinding(),packet);
                for(var binding:staging.imageBindings()) {
                    var offer=offer(binding.transfer(),binding.digest(),MembershipTransfer.Kind.APPLICATION,binding.digest(),binding.bytes());receiveFile(staging,binding,offer);
                }
                staging.images();check();completeSource=true;return staging;
            }
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    /** Observe only this contacted owner's original frozen grant after every source
     * transfer commits. Generic records or a packet copied from another peer cannot
     * establish this observation. Historical witnesses remain explicit verifier input. */
    MembershipSelection.Source verifiedOriginalSource(MembershipCurrentGeneration.Verifier verifier)throws IOException {
        check();require(completeSource && received!=null,"complete original source exchange required");
        var basis=received.basis();var packet=received.packet();var images=received.images();
        require(received.sourceIdentity().equals(source) && basis.value().get("voter").equals(source.nodeId().value())
                && basis.value().get("view").equals(context.authority()) && basis.value().get("ballot").equals(ballot),"original source owner/view/ballot");
        var capsule=Objects.requireNonNull(verifier.verify(originalRoot,packet,images));
        require(capsule.context.root.equals(context.root) && capsule.context.authority().equals(context.authority())
                && Arrays.equals(capsule.packet.bytes(),packet.bytes()),"original source verifier substituted prefix");
        String parent=cutDigest(object(basis.value().get("cut")));var owned=new HashSet<Owned>();
        owned.add(new Owned(source.nodeId().value(),source.storageId(),basis.digest(),parent));
        if(basis.value().get("accepted")!=null)owned.add(new Owned(source.nodeId().value(),source.storageId(),(String)basis.value().get("accepted"),parent));
        var result=MembershipSelection.Source.verify(capsule,basis,Map.of("voter",source.nodeId().value(),"basisId",basis.value().get("basisId"),"basisDigest",basis.digest()),source,owned);
        received.recheck();check();return result;
    }
    @Override public synchronized void close()throws IOException {
        closed=true;if(pending!=null)pending.cancel(true);
        if(receivedRecord!=null){receivedRecord.close();receivedRecord=null;}
        if(received!=null){received.close();received=null;}
    }
}
