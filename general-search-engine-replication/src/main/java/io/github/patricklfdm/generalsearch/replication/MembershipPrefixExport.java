package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Read-only current-prefix borrow. Replacement revokes it instead of pinning an obsolete
 * generation. Request view/ballot are correlation only; no PROMISE or historical Owned
 * observation is exported. The receiver must authenticate the complete capsule separately. */
final class MembershipPrefixExport implements MembershipTransferExport,MembershipImageBorrow {
    private final MembershipGrantJournal owner;
    final MembershipCurrentGeneration generation;
    private final Map<String,Object> ballot;
    private final String requestView;
    private final MembershipResources.Lease metadata;
    private final LongSupplier clock;
    private final long started,budget;
    private final Map<String,MembershipSourceExport.Content> references;
    private final boolean ancestry,completeGeneration;
    private boolean closed;

    MembershipPrefixExport(MembershipGrantJournal owner,MembershipCurrentGeneration generation,Map<String,Object> ballot,
            String requestView,MembershipResources resources,LongSupplier clock,long started,long budget,boolean ancestry) {
        this(owner,generation,ballot,requestView,resources,clock,started,budget,ancestry,false);
    }
    MembershipPrefixExport(MembershipGrantJournal owner,MembershipCurrentGeneration generation,Map<String,Object> ballot,
            String requestView,MembershipResources resources,LongSupplier clock,long started,long budget,boolean ancestry,boolean completeGeneration) {
        this(owner,generation,ballot,requestView,resources,clock,started,budget,ancestry,completeGeneration,false,false);
    }
    MembershipPrefixExport(MembershipGrantJournal owner,MembershipCurrentGeneration generation,Map<String,Object> ballot,
            String requestView,MembershipResources resources,LongSupplier clock,long started,long budget,boolean ancestry,boolean completeGeneration,
            boolean packetOnly,boolean metadataOnly) {
        require(!packetOnly || !ancestry && !completeGeneration,"packet-only prefix scope");
        require(!metadataOnly || completeGeneration,"generation metadata scope");
        require(budget>0 && budget<Long.MAX_VALUE/2,"prefix export budget");MembershipValidation.digest(requestView);
        this.owner=owner;this.generation=generation;this.ancestry=ancestry;this.completeGeneration=completeGeneration;this.ballot=Map.copyOf(ballot);this.requestView=requestView;
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        context().ballot(ballot,false);var contents=new TreeMap<>(completeGeneration?generation.generationContents():ancestry?generation.ancestryContents():generation.transferContents());
        if(packetOnly)contents.values().removeIf(v->v.kind()!=MembershipTransfer.Kind.CAPSULE);
        if(metadataOnly)contents.values().removeIf(v->v.kind()!=MembershipTransfer.Kind.RECORD);
        var first=ancestry || completeGeneration?contents.get(generation.manifest.digest()):contents.values().stream().filter(v->v.kind()==MembershipTransfer.Kind.CAPSULE).findFirst().orElseThrow();
        require(contents.putIfAbsent(packetOnly?packetReference(context()):metadataOnly?generationMetadataReference(context()):
                completeGeneration?generationReference(context()):ancestry?ancestryReference(context()):cutDigest(context().cut),first)==null,"prefix cut reference collision");references=Map.copyOf(contents);
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,MembershipSourceResources.export("prefix-export",generation.manifest.digest()),4096);
    }
    /** Derived lookup alias only, never an authority record or manifest digest. */
    static String ancestryReference(MembershipContext context) {
        return hash(canonical(Map.of("root",context.root,"cut",context.cut,"scope","retained-current-ancestry"),16384));
    }
    static String generationReference(MembershipContext context) {
        return hash(canonical(Map.of("root",context.root,"cut",context.cut,"scope","retained-current-generation"),16384));
    }
    static String packetReference(MembershipContext context) {
        return hash(canonical(Map.of("root",context.root,"cut",context.cut,"scope","retained-current-packet"),16384));
    }
    static String generationMetadataReference(MembershipContext context) {
        return hash(canonical(Map.of("root",context.root,"cut",context.cut,"scope","retained-current-generation-metadata"),16384));
    }
    static boolean reference(MembershipContext context,String digest) {
        return digest.equals(cutDigest(context.cut)) || digest.equals(ancestryReference(context)) || digest.equals(generationReference(context))
                || digest.equals(packetReference(context)) || digest.equals(generationMetadataReference(context));
    }
    boolean expired(){long elapsed=clock.getAsLong()-started;return closed || elapsed<0 || elapsed>=budget;}
    void revoke(){if(!closed){closed=true;metadata.close();}}
    @Override public MembershipContext context(){return generation.capsule.context;}
    @Override public MembershipIdentity identity(){return owner.activationIdentity();}
    @Override public Map<String,Object> ballot(){return ballot;}
    static void envelope(MembershipContext context,MembershipIdentity local,MembershipIdentity reader,Decoded request) {
        require(Set.of("CHUNK","TRANSFER_COMMIT").contains(request.kind()),"prefix transfer request kind");
        MembershipWire.envelope(request,context.root,reader,local);
        require(!reader.equals(local) && reader.equals(context.identities.get(reader.nodeId().value()))
                && local.equals(context.identities.get(local.nodeId().value())),"prefix permanent identities");
        context.ballot(request.value().get("ballot"),false);
    }
    @Override public void request(MembershipIdentity reader,Decoded request,UUID session) {
        envelope(context(),identity(),reader,request);
        require(request.value().get("view").equals(requestView) && request.value().get("ballot").equals(ballot)
                && request.value().get("trace").equals(session.toString()),"prefix original correlation");
    }
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
        synchronized(owner){owner.checkPrefixExport(this);return references;}
    }
    /** Reuse the exact accounted current image without copying it into receiving
     * scratch. Replacement revokes this borrow; it does not pin an obsolete
     * generation or establish any remote copy/voting observation. */
    @Override public String imageRoot()throws IOException {
        synchronized(owner){owner.checkPrefixExport(this);return context().root;}
    }
    @Override public boolean hasImage(String digest,long bytes)throws IOException {
        synchronized(owner) {
            owner.checkPrefixExport(this);MembershipValidation.digest(digest);
            require(bytes>0 && bytes<=MembershipResources.Unit.APPLICATION.bytes,"prefix borrowed image extent");
            var content=references.get(digest);
            return content!=null && content.kind()==MembershipTransfer.Kind.APPLICATION && content.bytes()==bytes;
        }
    }
    @Override public byte[] image(String digest,long bytes)throws IOException {
        synchronized(owner) {
            require(hasImage(digest,bytes),"prefix original image unavailable");byte[] result=new byte[Math.toIntExact(bytes)];
            for(int offset=0;offset<result.length;) {
                byte[] part=generation.transferChunk(digest,offset,4*1024*1024);
                System.arraycopy(part,0,result,offset,part.length);offset+=part.length;
            }
            require(hash(result).equals(digest),"prefix original image changed");owner.checkPrefixExport(this);return result;
        }
    }
    @Override public void checkImage(String digest,long bytes)throws IOException {
        // hasImage holds the owner monitor and checks the exact current generation,
        // including every original file's bytes/inode and this export's lifetime.
        // No bytes or validation result escape into a later invocation.
        require(hasImage(digest,bytes),"prefix original image unavailable");
    }
    @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner) {
            owner.checkPrefixExport(this);byte[] bytes=completeGeneration?generation.generationChunk(digest,offset,maximum):ancestry?generation.ancestryChunk(digest,offset,maximum):generation.transferChunk(digest,offset,maximum);owner.checkPrefixExport(this);return bytes;
        }
    }
    @Override public void close(){owner.releasePrefixExport(this);}
}
