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
    private final String requestRoot,requestView;
    private final MembershipLearnerRequest learner;
    private final boolean learnerProgress;
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
    private final Map<String,Object> prefixCut;
    private volatile boolean closed;
    private CompletableFuture<Decoded> pending;
    private MembershipSourceReceive received;
    private MembershipFloorFiles.PendingPrefix borrowedFloor;
    private Record receivedRecord;
    private final List<MembershipResources.Lease> ancestryLeases=new ArrayList<>();
    private MembershipCapsule ancestryPrefix,ancestryResult;
    private Decoded ancestryManifest;
    private byte[] ancestryBytes;
    private boolean completeAncestry;

    MembershipSourcePull(MembershipCapsule verified,MembershipIdentity local,MembershipIdentity source,Map<String,Object> ballot,UUID session,
            MembershipResources resources,ReplicationBounds bounds,Link link,Guard guard,LongSupplier clock,long started,long budget) {
        this(verified,local,source,ballot,session,resources,bounds,link,guard,clock,started,budget,null);
    }
    /** Snapshot the actual local fence, independently of the unverified remote hint. */
    static MembershipSourcePull prefix(MembershipGrantJournal owner,MembershipDiscovery.Hint hint,MembershipResources resources,
            ReplicationBounds bounds,Link link,Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        synchronized(owner) {
            var state=owner.discoveryState(resources);var capsule=owner.readOnlyCapsule();
            return new MembershipSourcePull(capsule,owner.activationIdentity(),hint.peer(),state.ballot(),UUID.randomUUID(),resources,bounds,link,
                    ()->{guard.check();owner.checkReadOnlyBallot(state.context().authority(),state.ballot());},clock,started,budget,hint.cut());
        }
    }
    private MembershipSourcePull(MembershipCapsule verified,MembershipIdentity local,MembershipIdentity source,Map<String,Object> ballot,UUID session,
            MembershipResources resources,ReplicationBounds bounds,Link link,Guard guard,LongSupplier clock,long started,long budget,Map<String,Object> prefixCut) {
        this(verified,local,source,ballot,session,resources,bounds,link,guard,clock,started,budget,prefixCut,null,null,false);
    }
    /** No local owner/catalog exists yet. The hint and routes remain untrusted until
     * the complete received original source authenticates the exact reservation. */
    static MembershipSourcePull learner(MembershipLearnerRequest learner,Decoded root,MembershipDiscovery.Hint hint,
            MembershipResources resources,ReplicationBounds bounds,Link link,Guard guard,LongSupplier clock,long started,long budget) {
        return new MembershipSourcePull(null,learner.identity(),hint.peer(),MembershipLearnerDiscovery.correlation(learner.identity()),
                UUID.randomUUID(),resources,bounds,link,guard,clock,started,budget,hint.cut(),root,learner,false);
    }
    /** Read complete retained progress, including CANCEL/INTENT, without enabling installation. */
    static MembershipSourcePull learnerProgress(MembershipLearnerRequest learner,Decoded root,MembershipDiscovery.Hint hint,
            MembershipResources resources,ReplicationBounds bounds,Link link,Guard guard,LongSupplier clock,long started,long budget) {
        return new MembershipSourcePull(null,learner.identity(),hint.peer(),MembershipLearnerDiscovery.correlation(learner.identity()),
                UUID.randomUUID(),resources,bounds,link,guard,clock,started,budget,hint.cut(),root,learner,true);
    }
    private MembershipSourcePull(MembershipCapsule verified,MembershipIdentity local,MembershipIdentity source,Map<String,Object> ballot,UUID session,
            MembershipResources resources,ReplicationBounds bounds,Link link,Guard guard,LongSupplier clock,long started,long budget,
            Map<String,Object> prefixCut,Decoded root,MembershipLearnerRequest learner,boolean learnerProgress) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"source pull time budget");this.learner=learner;this.learnerProgress=learnerProgress;
        this.prefixCut=prefixCut==null?null:Map.copyOf(prefixCut);
        if(learner==null) {
            context=Objects.requireNonNull(verified).context;
            originalRoot=decode(verified.packet.objectBytes(context.recordRootDigest()),"records","ROOT");
            require(local.equals(context.identities.get(local.nodeId().value())) && source.equals(context.identities.get(source.nodeId().value()))
                    && !local.equals(source),"source pull permanent identities");context.ballot(ballot,prefixCut==null);
            requestRoot=context.root;requestView=context.authority();
        }else {
            context=null;originalRoot=Objects.requireNonNull(root);requestRoot=learner.root().manifestDigest();requestView=learner.change().expectedConfigurationDigest();
            require(verified==null && prefixCut!=null && root.family().equals("records") && root.kind().equals("ROOT")
                    && root.rootDigest().equals(requestRoot) && root.value().get("groupId").equals(learner.root().groupId().value().toString())
                    && root.value().get("historyId").equals(learner.root().historyId().toString())
                    && root.value().get("limits").equals(hash(canonical(CATALOG.get("resources"),16384))),"learner source original ROOT");
            require(local.equals(learner.identity()) && !local.equals(source) && learner.change().target().contains(source)
                    && ballot.equals(MembershipLearnerDiscovery.correlation(local)),"learner source contact route");
            checkView(object(prefixCut.get("view")));MembershipValidation.position(number(prefixCut.get("index")));
        }
        this.local=local;this.source=source;this.ballot=Map.copyOf(ballot);MembershipValidation.uuid(session);this.session=session;
        this.resources=Objects.requireNonNull(resources);this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;frameLimit=Math.min(FRAME,bounds.maxFrameBytes());
        require(frameLimit>=4096,"source pull frame limit");chunkLimit=Math.min(4*1024*1024,bounds.snapshotChunkBytes());
        maximumAttempts=Math.min(3,bounds.maxRetryAttempts());
    }
    private String learnerReference(String scope) {
        return learnerProgress?MembershipLearnerProgressAccess.reference(learner,prefixCut,scope):MembershipLearnerPrefixExport.reference(learner,prefixCut,scope);
    }
    private void checkLearner(MembershipContext current) {
        if(learnerProgress)MembershipLearnerProgressAccess.original(current,learner,source);
        else if(learner!=null)MembershipLearnerPrefixExport.originalReservation(current,learner,source);
    }
    private void check()throws IOException {
        if(closed)guard.check(); // A revoked parent can explain its cancellation.
        require(!closed,"source pull closed");long elapsed=clock.getAsLong()-started;
        require(elapsed>=0 && elapsed<budget,"original source pull deadline");guard.check();
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"original source pull deadline");
    }
    private Decoded request(String kind,Map<String,Object> payload)throws IOException {
        check();require(sequence<MembershipValidation.MAX,"source sequence exhausted");
        return decode(encode("wire",kind,Map.of("root",requestRoot,"view",requestView,"sender",MembershipBootstrapSeed.identity(local),
                "recipient",MembershipBootstrapSeed.identity(source),"ballot",ballot,"trace",session.toString(),"sequence",++sequence,"payload",payload)),"wire",kind);
    }
    private Decoded exchange(Decoded request,String kind)throws IOException {
        require(request.size()<=frameLimit,"source pull request frame limit");var retry=new MembershipExchange(request.digest(),started,budget);
        try(var held=resources.reserve(MembershipResources.Unit.CONTROL,"source-request-"+UUID.randomUUID(),request.size())) {
            for(;;) {
                // Attempt accounting cannot send or consume protocol data. Check
                // the complete guard after its clock read, immediately before
                // link.exchange, rather than twice around this pure bookkeeping.
                retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> future;
                synchronized(this){check();future=Objects.requireNonNull(link.exchange(source,request,kind,started+budget));pending=future;if(closed)future.cancel(true);}
                try {
                    long left=budget-(clock.getAsLong()-started);require(left>0,"original source pull deadline");
                    Decoded result=future.get(left,TimeUnit.NANOSECONDS);check();require(result.size()<=frameLimit,"source pull response frame limit");
                    MembershipWire.correlated(request,result,kind);
                    if(prefixCut==null)context.wire(result,source,local,ballot,session,number(request.value().get("sequence")));
                    else MembershipWire.envelope(result,requestRoot,source,local);
                    // Return the real rejection to the runtime; never turn it into a source or retry it.
                    if(result.kind().equals("REJECT"))throw new Rejected(result);
                    retry.complete(request.digest(),clock.getAsLong());return result;
                }catch(InterruptedException error){future.cancel(true);Thread.currentThread().interrupt();throw new IOException("source pull interrupted",error);}
                catch(CancellationException error){if(error instanceof MembershipCampaignLost.Cancelled revoked)throw revoked.loss;
                    throw new IOException("source pull cancelled",error);}
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
        require(prefixCut==null,"read-only prefix cannot fetch grant records");
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
    /** Exact raw ENTRY payload. Its digest grants no vote; the native journal
     * validates the entry, codec, parent and original installed selection. */
    byte[] fetchPayload(Decoded entry)throws IOException {
        synchronized(this){require(!used && !closed && prefixCut==null,"payload pull single use/current scope");used=true;}
        require(entry.family().equals("records") && entry.kind().equals("ENTRY") && entry.value().get("root").equals(context.root)
                && entry.value().get("authority").equals(context.authority()) && number(entry.value().get("index"))==number(context.cut.get("index"))+1,
                "payload entry context");check();String digest=(String)entry.value().get("payload");
        if(entry.value().get("kind").equals("BARRIER")){require(digest.equals(hash(new byte[0])),"barrier payload");return new byte[0];}
        return metadataBlob(offer(UUID.randomUUID(),digest,MembershipTransfer.Kind.RECORD,digest,null),FRAME);
    }
    /** Fetch the hash preimage served exclusively by the native original voter.
     * Generic retained record transfer cannot establish this observation. */
    Owned fetchVoteObservation(Decoded record)throws IOException {
        synchronized(this){require(!used && !closed && prefixCut==null,"vote observation single use/current scope");used=true;}
        require(record.value().get("ballot").equals(ballot),"vote observation ballot");
        byte[] expected=MembershipVoteReceipt.bytes(context,source,record);String digest=hash(expected);check();
        byte[] actual=metadataBlob(offer(UUID.randomUUID(),MembershipVoteReceipt.reference(expected),MembershipTransfer.Kind.RECORD,digest,(long)expected.length),2048);
        require(Arrays.equals(actual,expected),"original vote receipt bytes");check();
        return new Owned(source.nodeId().value(),source.storageId(),record.digest(),cutDigest(context.cut));
    }
    record CheckpointReceipt(Decoded acknowledgement,Owned owned) {}
    /** A checkpoint observation requires contacting the ACK's permanent owner.
     * Statement/ACK bytes from a source packet alone do not establish this receipt. */
    CheckpointReceipt fetchCheckpointAcknowledgement(Decoded statement,Decoded expected)throws IOException {
        require(prefixCut==null,"read-only prefix cannot observe checkpoint votes");
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
    /** A complete prefix export advertises every image, including locally borrowed
     * ones. Consume and authenticate those bytes without another disk reservation
     * so the last commit also releases the remote export. */
    private void completeBorrowedImage(String digest,long bytes)throws IOException {
        var offered=offer(UUID.randomUUID(),digest,MembershipTransfer.Kind.APPLICATION,digest,bytes);
        java.security.MessageDigest hash;
        try{hash=java.security.MessageDigest.getInstance("SHA-256");}
        catch(java.security.NoSuchAlgorithmException error){throw new AssertionError(error);}
        for(long offset=0;offset<bytes;) {check();byte[] part=chunk(offered,offset);hash.update(part);offset+=part.length;}
        require(HexFormat.of().formatHex(hash.digest()).equals(digest),"borrowed remote image digest");check();commit(offered);
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
    /** Borrowed untrusted bytes; receipt is neither a vote nor proof of historical force. */
    MembershipSourceReceive fetchPrefix(Path scratch)throws IOException {
        return fetchPrefix(scratch,null);
    }
    /** One bounded read-only metadata export. The owning caller must authenticate
     * its contents; no record, vote, prefix or historical ownership is minted. */
    byte[] fetchPrefixMetadata(String reference,int maximum)throws IOException {
        synchronized(this){require(prefixCut!=null && learner==null && !used && !closed,"prefix metadata single use");used=true;}
        try {
            require(maximum>0 && maximum<=FRAME,"prefix metadata capacity");
            return metadataBlob(offer(UUID.randomUUID(),reference,MembershipTransfer.Kind.RECORD,null,null),maximum);
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    MembershipSourceReceive fetchPrefix(Path scratch,MembershipImageBorrow originalImages)throws IOException {
        return fetchPrefix(scratch,originalImages,false);
    }
    /** Exact same-application maintenance borrows every image. Its narrower
     * remote scope can finish at the packet commit without pinning unused images. */
    MembershipSourceReceive fetchBorrowedPrefix(Path scratch,MembershipImageBorrow originalImages)throws IOException {
        Objects.requireNonNull(originalImages);require(learner==null,"borrowed packet requires voter prefix");
        return fetchPrefix(scratch,originalImages,true);
    }
    static final class MissingBorrowedImages extends IOException {
        private static final long serialVersionUID=1L;
        MissingBorrowedImages(){super("borrowed prefix requires every original image");}
    }
    /** A pending floor supplies only existing bytes. Fresh packet transfer and
     * original generation verification still authenticate the permanent owner;
     * no receiving SOURCE or application file is created over those charges. */
    void fetchBorrowedFloorPrefix(MembershipFloorFiles.PendingPrefix original)throws IOException {
        synchronized(this){require(prefixCut!=null && learner==null && !used && !closed,"borrowed floor prefix single use");used=true;borrowedFloor=Objects.requireNonNull(original);}
        try {
            check();original.check();require(original.resources()==resources && original.local().equals(local)
                    && original.identity.equals(source),"borrowed floor original owner/budget");
            byte[] bytes=original.packet().bytes();var cap=original.packet().capsule();
            require(cap.value().get("root").equals(requestRoot) && cap.value().get("cut").equals(prefixCut),"borrowed floor original cut");
            String reference=hash(canonical(Map.of("root",requestRoot,"cut",prefixCut,"scope","retained-current-packet"),16384));
            var packet=offer(UUID.randomUUID(),reference,MembershipTransfer.Kind.CAPSULE,hash(bytes),(long)bytes.length);
            int offset=0;
            while(offset<bytes.length) {
                check();original.check();byte[] part=chunk(packet,offset);
                require(Arrays.equals(part,0,part.length,bytes,offset,offset+part.length),"borrowed floor original packet bytes");offset+=part.length;
            }
            original.check();commit(packet);check();original.check();completeSource=true;
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private void checkPrefixCopy()throws IOException {
        require(received!=null || borrowedFloor!=null,"complete prefix bytes missing");
        if(received!=null)received.recheck();else borrowedFloor.check();
    }
    private MembershipSourcePacket prefixPacket()throws IOException {checkPrefixCopy();return received!=null?received.packet():borrowedFloor.packet();}
    private Map<String,byte[]> prefixImages()throws IOException {checkPrefixCopy();return received!=null?received.images():borrowedFloor.images();}
    private MembershipIdentity prefixIdentity()throws IOException {return received!=null?received.sourceIdentity():borrowedFloor.identity;}
    private MembershipSourceReceive fetchPrefix(Path scratch,MembershipImageBorrow originalImages,boolean packetOnly)throws IOException {
        synchronized(this){require(prefixCut!=null && !used && !closed,"read-only prefix single use");used=true;}
        try {
            String reference=packetOnly?hash(canonical(Map.of("root",requestRoot,"cut",prefixCut,"scope","retained-current-packet"),16384)):
                    learner==null?cutDigest(prefixCut):learnerReference("prefix");
            var packet=offer(UUID.randomUUID(),reference,MembershipTransfer.Kind.CAPSULE,null,null);
            MembershipSourceReceive staging;
            synchronized(this) {
                check();require(learner==null || originalImages==null,"learner must receive its original image");
                received=learner==null?new MembershipSourceReceive(scratch,requestRoot,source,prefixCut,session,packet.id,packet.content,
                        resources,chunkLimit,clock,started,budget,originalImages):
                        MembershipSourceReceive.learner(scratch,requestRoot,source,prefixCut,session,packet.id,packet.content,resources,chunkLimit,clock,started,budget);
                staging=received;
            }
            receiveFile(staging,staging.packetBinding(),packet);
            var missing=staging.imageBindings();
            if(packetOnly && !missing.isEmpty())throw new MissingBorrowedImages();
            for(var binding:missing) {
                var offer=offer(binding.transfer(),binding.digest(),MembershipTransfer.Kind.APPLICATION,binding.digest(),binding.bytes());receiveFile(staging,binding,offer);
            }
            if(!packetOnly && originalImages!=null)for(var image:staging.packet().images().entrySet())
                if(missing.stream().noneMatch(v->v.digest().equals(image.getKey())))completeBorrowedImage(image.getKey(),image.getValue());
            staging.recheck();check();completeSource=true;return staging;
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    /** One separately bounded read-only exchange. It copies the actual manifest and
     * its complete ancestry file; it never turns copied ACKs into new observations. */
    MembershipCapsule fetchAncestry(MembershipCapsule higher)throws IOException {return fetchAncestry(higher,false);}
    private MembershipCapsule fetchAncestry(MembershipCapsule higher,boolean completeGeneration)throws IOException {
        synchronized(this){require(prefixCut!=null && !used && !closed,"ancestry pull single use");used=true;}
        try {
            check();require(higher.context.root.equals(requestRoot) && higher.context.cut.equals(prefixCut)
                    && Arrays.equals(higher.packet.objectBytes(higher.context.recordRootDigest()),originalRoot.bytes()),"ancestry expected prefix");
            ancestryPrefix=higher;
            var reference=learner!=null?learnerReference(completeGeneration?"generation":"ancestry"):
                    completeGeneration?MembershipPrefixExport.generationMetadataReference(higher.context):MembershipPrefixExport.ancestryReference(higher.context);
            var manifestOffer=offer(UUID.randomUUID(),reference,MembershipTransfer.Kind.RECORD,null,null);
            ancestryManifest=decode(metadataBlob(manifestOffer,65536),"records","GENERATION");
            var fields=ancestryManifest.value();var cap=higher.packet.capsule();
            require(fields.get("node").equals(source.nodeId().value()) && fields.get("capsule").equals(cap.digest()),"ancestry manifest owner/capsule");
            for(String name:List.of("root","cut","catalog","application"))require(fields.get(name).equals(cap.value().get(name)),"ancestry manifest prefix binding");
            var files=new TreeMap<String,Map<String,Object>>();String previous=null;
            for(Object value:list(fields.get("files"))) {
                var row=object(value);String name=(String)row.get("path");
                require(previous==null || previous.compareTo(name)<0,"ancestry manifest file order");previous=name;files.put(name,row);
            }
            var packet=files.get(MembershipBasisSources.PACKET);
            require(packet!=null && packet.get("sha256").equals(hash(higher.packet.bytes()))
                    && number(packet.get("size"))==higher.packet.bytes().length,"ancestry manifest exact packet");
            var ancestry=files.get("ancestry.gsr");
            if(ancestry==null)ancestryBytes=new byte[0];
            else {
                long length=number(ancestry.get("size"));require(length>0 && length<=96*1024,"ancestry offered capacity");
                String digest=(String)ancestry.get("sha256");
                ancestryBytes=metadataBlob(offer(UUID.randomUUID(),digest,MembershipTransfer.Kind.RECORD,digest,length),96*1024);
            }
            check();completeAncestry=true;
            ancestryResult=higher.retainingAncestry(ancestryBytes,new RetainedAncestry(this));check();return ancestryResult;
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    /** Complete original current-generation copy from its actual permanent owner.
     * The observation covers this exact generation only, never a historical vote.
     * The caller retains both pulls through completion and stores its governing
     * floor before retiring any local original. */
    MembershipFloor.Copy fetchGeneration(MembershipSourcePull prefix)throws IOException {
        Objects.requireNonNull(prefix);require(prefix!=this,"generation requires separate complete prefix receive");
        try {
            check();prefix.check();
            require(prefix.prefixCut!=null && prefix.completeSource && (prefix.received!=null || prefix.borrowedFloor!=null)
                    && prefix.prefixCut.equals(prefixCut) && prefix.source.equals(source) && prefix.local.equals(local)
                    && prefix.requestRoot.equals(requestRoot) && prefix.requestView.equals(requestView) && Objects.equals(prefix.learner,learner) && prefix.learnerProgress==learnerProgress
                    && prefix.ballot.equals(ballot) && prefix.resources==resources && prefix.started==started && prefix.budget==budget,
                    "generation original prefix owner/deadline");
            var complete=fetchAncestry(prefix.verifiedPrefix(),true);prefix.checkPrefixCopy();
            var files=new TreeMap<String,byte[]>();files.put("generation.gsr",ancestryManifest.bytes());
            files.put("source.gscp",prefix.prefixPacket().bytes());
            for(var image:prefix.prefixImages().entrySet())files.put(image.getKey()+".image",image.getValue());
            var members=list(ancestryManifest.value().get("files"));require(members.size()<32,"generation complete file count");
            long metadata=ancestryManifest.size();
            for(Object value:members) {
                var member=object(value);String name=(String)member.get("path");long bytes=number(member.get("size"));
                long maximum=MembershipGenerationFiles.limit(name);require(bytes>0 && bytes<=maximum,"generation original member extent");
                if(!name.endsWith(".image")){metadata=Math.addExact(metadata,bytes);require(metadata<=MembershipResources.Unit.GENERATION.bytes,"generation original metadata capacity");}
            }
            for(Object value:members) {
                check();prefix.checkPrefixCopy();var member=object(value);String name=(String)member.get("path"),digest=(String)member.get("sha256");
                long bytes=number(member.get("size"));byte[] original=files.get(name);
                if(original==null) {
                    require(!name.equals("source.gscp") && !name.endsWith(".image"),"generation original image missing");
                    original=name.equals("ancestry.gsr")?ancestryBytes:metadataBlob(
                            offer(UUID.randomUUID(),digest,MembershipTransfer.Kind.RECORD,digest,bytes),Math.toIntExact(MembershipGenerationFiles.limit(name)));
                    files.put(name,original);
                }
                require(original.length==bytes && hash(original).equals(digest),"generation exact original member");
            }
            var original=new GenerationCopy(this,prefix,files);
            original.check(complete);
            complete=complete.retainingGeneration(original);
            MembershipFloor.Copy.validateMaterialization(ancestryManifest,complete,source,files);
            prefix.checkPrefixCopy();prefix.check();check();
            var forced=new Owned(source.nodeId().value(),source.storageId(),ancestryManifest.digest(),cutDigest(complete.context.cut));
            var result=MembershipFloor.Copy.verify(ancestryManifest,complete,source,Set.of(forced),files);
            prefix.checkPrefixCopy();prefix.check();check();return result;
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    /** Only a fully downloaded current-generation owner can mint this provenance.
     * It never authenticates a bare packet or creates historical voting receipts. */
    static final class GenerationCopy {
        private final MembershipSourcePull pull,prefix;
        private final Map<String,byte[]> files;
        private GenerationCopy(MembershipSourcePull pull,MembershipSourcePull prefix,Map<String,byte[]> files) {
            this.pull=pull;this.prefix=prefix;this.files=Map.copyOf(files);
        }
        void check(MembershipCapsule capsule)throws IOException {
            pull.check();prefix.check();prefix.checkPrefixCopy();
            require(pull.completeAncestry && pull.ancestryManifest!=null && prefix.completeSource
                    && capsule.context.cut.equals(pull.prefixCut) && capsule.context.root.equals(pull.requestRoot)
                    && Arrays.equals(capsule.packet.bytes(),prefix.prefixPacket().bytes())
                    && Arrays.equals(files.get("source.gscp"),capsule.packet.bytes())
                    && Arrays.equals(files.get("generation.gsr"),pull.ancestryManifest.bytes()),"generation original copy binding");
            var fields=pull.ancestryManifest.value();require(fields.get("node").equals(pull.source.nodeId().value()),"generation original owner");
            var expected=new TreeSet<String>();expected.add("generation.gsr");
            for(Object row:list(fields.get("files"))) {
                var file=object(row);String name=(String)file.get("path");byte[] bytes=files.get(name);
                require(expected.add(name) && bytes!=null && bytes.length==number(file.get("size"))
                        && hash(bytes).equals(file.get("sha256")),"generation complete original inventory");
            }
            require(expected.equals(files.keySet()),"generation original inventory extras");pull.check();prefix.check();
        }
        byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        Optional<byte[]> coverage(){return Optional.ofNullable(files.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
    private byte[] metadataBlob(Offer offer,int maximum)throws IOException {
        require(offer.content.bytes()<=maximum,"ancestry metadata capacity");
        synchronized(this){check();ancestryLeases.add(resources.reserve(MembershipResources.Unit.CONTROL,"ancestry-copy-"+UUID.randomUUID(),offer.content.bytes()));}
        byte[] bytes=new byte[Math.toIntExact(offer.content.bytes())];int offset=0;
        while(offset<bytes.length){check();byte[] part=chunk(offer,offset);System.arraycopy(part,0,bytes,offset,part.length);offset+=part.length;}
        require(hash(bytes).equals(offer.content.digest()),"ancestry metadata digest");commit(offer);check();return bytes;
    }
    static final class RetainedAncestry {
        private final MembershipSourcePull pull;
        private RetainedAncestry(MembershipSourcePull pull){this.pull=pull;}
        void check(MembershipCapsule prefix,byte[] bytes)throws IOException {
            pull.check();require(pull.completeAncestry && pull.ancestryManifest!=null && pull.ancestryPrefix!=null
                    && Arrays.equals(prefix.packet.bytes(),pull.ancestryPrefix.packet.bytes())
                    && Arrays.equals(bytes,pull.ancestryBytes),"complete retained ancestry exchange required");pull.check();
        }
    }
    Decoded ancestryManifest()throws IOException {check();require(ancestryResult!=null,"ancestry pull incomplete");return ancestryManifest;}
    byte[] ancestryBytes()throws IOException {check();require(ancestryResult!=null,"ancestry pull incomplete");return ancestryBytes.clone();}
    List<MembershipSelection.Bridge> ancestry()throws IOException {
        check();require(ancestryResult!=null,"ancestry pull incomplete");var result=ancestryResult.verifiedAncestry(ancestryBytes);check();return result;
    }
    static final class RetainedCopy {
        private final MembershipSourcePull pull;
        private RetainedCopy(MembershipSourcePull pull){this.pull=pull;}
        void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            pull.check();require(pull.completeSource && (pull.received!=null || pull.borrowedFloor!=null),"complete retained source exchange required");
            require(Arrays.equals(root.bytes(),pull.originalRoot.bytes()) && pull.prefixIdentity().equals(pull.source)
                    && Arrays.equals(packet.bytes(),pull.prefixPacket().bytes()),"retained copy original root/source/packet");
            if(pull.prefixCut!=null)require(packet.capsule().value().get("cut").equals(pull.prefixCut),"retained copy discovered cut");
            else {
                var basis=pull.received.basis();packet.bind(basis);
                require(basis.value().get("voter").equals(pull.source.nodeId().value()) && basis.value().get("view").equals(pull.context.authority())
                        && basis.value().get("ballot").equals(pull.ballot),"retained copy original grant");
            }
            pull.checkPrefixCopy();pull.check();
        }
    }
    private MembershipCapsule retainedCapsule()throws IOException {
        check();require(completeSource && (received!=null || borrowedFloor!=null),"complete retained source exchange required");
        return MembershipCapsule.verifyRetained(originalRoot,prefixPacket(),prefixImages(),new RetainedCopy(this));
    }
    /** Authenticate a complete historical copy from the exact current-generation
     * endpoint. Does not manufacture Owned observations for former voters. */
    MembershipCapsule verifiedPrefix()throws IOException {
        require(prefixCut!=null,"read-only prefix required");var result=retainedCapsule();
        checkLearner(result.context);
        check();return result;
    }
    /** Terminal retention stays separate from original enrollment admission. */
    MembershipSourceReceive completeLearnerCancellationSource(MembershipFloor.Copy original,MembershipBallotAllocator.Cut cut)throws IOException {
        check();require(learner!=null && learnerProgress && completeSource && received!=null,"learner source is not a progress transfer");
        MembershipLearnerProgressAccess.original(original.capsule.context,learner,source);
        require(MembershipLearnerProgressAccess.operation(original.capsule.context,learner.identity()).get("phase").equals("CANCELLED"),"learner progress completion requires CANCEL");
        received.completeLearnerGeneration(original,cut);check();return received;
    }
    MembershipSourceReceive completeLearnerIntentSource(MembershipLearnerHead head,MembershipFloor.Copy original,MembershipBallotAllocator.Cut cut)throws IOException {
        check();require(learner!=null && learnerProgress && completeSource && received!=null,"learner source is not a progress transfer");
        require(learner.equals(head.request()) && resources==head.resources(),"learner INTENT original receiving owner");
        MembershipLearnerIntent.match(head,original);received.completeLearnerGeneration(original,cut);check();return received;
    }
    MembershipSourceReceive completeLearnerPendingIntentSource(MembershipLearnerHead head,MembershipFloor.Copy original,MembershipBallotAllocator.Cut cut)throws IOException {
        check();require(learner!=null && learnerProgress && completeSource && received!=null,"joining source is not a progress transfer");
        require(learner.equals(head.request()) && resources==head.resources(),"joining original receiving owner");
        MembershipLearnerProgressAccess.original(original.capsule.context,learner,source);
        var row=MembershipLearnerProgressAccess.operation(original.capsule.context,learner.identity());
        require(row.get("phase").equals("SEALED") && head.receipt().value().get("receipt").equals(row.get("receipt")),"joining original SEALED receipt");
        received.completeLearnerGeneration(original,cut);check();return received;
    }
    MembershipSourceReceive completeLearnerSource(MembershipFloor.Copy original,MembershipBallotAllocator.Cut cut)throws IOException {
        check();require(learner!=null && !learnerProgress && completeSource && received!=null,"learner source is not an admission transfer");
        var prefix=verifiedPrefix();require(Arrays.equals(prefix.packet.bytes(),original.capsule.packet.bytes()),"learner retained source prefix");
        received.completeLearnerGeneration(original,cut);check();return received;
    }
    /** Caller supplies real historical provenance. Hashes/downloads alone cannot verify it. */
    MembershipCapsule verifiedPrefix(MembershipCurrentGeneration.Verifier verifier)throws IOException {
        check();require(prefixCut!=null && completeSource && received!=null,"complete read-only prefix required");
        var packet=received.packet();var capsule=Objects.requireNonNull(verifier.verify(originalRoot,packet,received.images()));
        require(capsule.context.root.equals(requestRoot) && capsule.context.cut.equals(prefixCut)
                && Arrays.equals(capsule.packet.bytes(),packet.bytes()),"prefix verifier substituted bytes/cut");
        checkLearner(capsule.context);
        received.recheck();check();return capsule;
    }
    /** Observe only this contacted owner's original frozen grant after every source
     * transfer commits. Generic records or a packet copied from another peer cannot
     * establish this observation. Historical evidence uses either the completed-copy
     * path or the separately supplied strict verifier; neither counts old votes anew. */
    MembershipSelection.Source verifiedOriginalSource()throws IOException {
        require(prefixCut==null,"original grant source required");return originalSource(retainedCapsule());
    }
    MembershipSelection.Source verifiedOriginalSource(MembershipCurrentGeneration.Verifier verifier)throws IOException {
        check();require(prefixCut==null && completeSource && received!=null,"complete original source exchange required");
        return originalSource(Objects.requireNonNull(verifier.verify(originalRoot,received.packet(),received.images())));
    }
    private MembershipSelection.Source originalSource(MembershipCapsule capsule)throws IOException {
        check();require(prefixCut==null && completeSource && received!=null,"complete original source exchange required");
        var basis=received.basis();var packet=received.packet();
        require(received.sourceIdentity().equals(source) && basis.value().get("voter").equals(source.nodeId().value())
                && basis.value().get("view").equals(context.authority()) && basis.value().get("ballot").equals(ballot),"original source owner/view/ballot");
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
        if(borrowedFloor!=null){borrowedFloor.close();borrowedFloor=null;}
        for(var lease:ancestryLeases)lease.close();ancestryLeases.clear();
        ancestryManifest=null;ancestryPrefix=null;ancestryResult=null;ancestryBytes=null;
    }
}
