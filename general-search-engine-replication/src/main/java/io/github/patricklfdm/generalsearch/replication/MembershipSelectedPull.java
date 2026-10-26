package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Receiver-side SELECTED assembly. All remote sources come from their original
 * owners, never from an in-process proposer object. The runtime serializes this
 * operation, supplies historical provenance/ancestry, and keeps its original budget.
 * Network waits run outside the journal monitor. Installation alone is not READY. */
final class MembershipSelectedPull implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipSelection.Source own;
    private final MembershipIdentity proposer;
    private final Decoded request;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final List<MembershipSourcePull> pulls=new ArrayList<>();
    private final List<MembershipSourceReceive> receives=new ArrayList<>();
    private final List<MembershipSelection.Source> sources=new ArrayList<>();
    private final Map<String,byte[]> images=new TreeMap<>();
    private final List<MembershipSelection.Bridge> ancestry,retained;
    private final Path scratch;
    private final Object directoryKey;
    private MembershipSourceExport localExport;
    private Decoded selected;
    private boolean closed,removed;

    MembershipSelectedPull(MembershipGrantJournal owner,MembershipIdentity proposer,Decoded request,
            MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            MembershipCurrentGeneration.Verifier verifier,List<MembershipSelection.Bridge> ancestry,
            List<MembershipSelection.Bridge> retained,Path scratch,MembershipSourcePull.Guard guard,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"selected pull time budget");
        this.owner=Objects.requireNonNull(owner);this.proposer=Objects.requireNonNull(proposer);this.request=Objects.requireNonNull(request);
        this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);this.link=Objects.requireNonNull(link);
        this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        this.ancestry=List.copyOf(ancestry);this.retained=List.copyOf(retained);require(ancestry.size()<=6 && retained.size()<=6,"selected pull ancestry capacity");
        MembershipActivation.incoming(owner,proposer,request,"SELECTED");own=owner.originalSource();
        require(!own.owner.equals(proposer) && own.basis.value().get("ballot").equals(request.value().get("ballot")),"selected pull original local grant");
        check();this.scratch=scratch.toAbsolutePath().normalize();AdmissionPaths.safe(this.scratch.getParent());Files.createDirectory(this.scratch);
        directoryKey=MembershipBasisSources.key(this.scratch);
        try {
            var decisionPull=pull(proposer);String digest=(String)object(request.value().get("payload")).get("selection");
            selected=decisionPull.fetchRecord(digest,"SELECTED",this::selection);
            localExport=(MembershipSourceExport)owner.exportTransfer(own.basis.digest(),own.capsule.context.authority(),object(own.basis.value().get("ballot")),clock,started,budget);
            for(Object value:list(selected.value().get("sources"))) {
                check();var reference=object(value);String node=(String)reference.get("voter");MembershipSelection.Source source;
                if(node.equals(own.owner.nodeId().value()))source=own;
                else {
                    var client=pull(own.capsule.context.identities.get(node));
                    var received=client.fetch(this.scratch.resolve("source-"+sources.size()),(String)reference.get("basisDigest"),localExport);receives.add(received);
                    source=client.verifiedOriginalSource(verifier);merge(received.images());
                }
                require(source.reference().equals(reference),"selected pull exact source reference");sources.add(source);
            }
            for(var content:localExport.contents())if(content.kind()==MembershipTransfer.Kind.APPLICATION && !images.containsKey(content.digest())) {
                check();byte[] bytes=new byte[Math.toIntExact(content.bytes())];int offset=0;
                while(offset<bytes.length){check();byte[] chunk=localExport.read(content.digest(),offset,4*1024*1024);System.arraycopy(chunk,0,bytes,offset,chunk.length);offset+=chunk.length;}
                require(hash(bytes).equals(content.digest()),"selected pull local image digest");images.put(content.digest(),bytes);
            }
            var original=sources.stream().filter(s->s.owner.equals(proposer)).findFirst().orElseThrow();
            var recomputed=new MembershipSelection.Campaign(original).select(sources,this.ancestry);
            require(Arrays.equals(recomputed.selected().bytes(),selected.bytes()),"selected pull decision differs from original");check();
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private MembershipSourcePull pull(MembershipIdentity peer) {
        var result=new MembershipSourcePull(own.capsule,own.owner,peer,object(own.basis.value().get("ballot")),UUID.randomUUID(),resources,bounds,link,
                this::check,clock,started,budget);pulls.add(result);return result;
    }
    private void selection(Decoded value) {
        var v=value.value();var context=own.capsule.context;
        require(v.get("view").equals(context.authority()) && v.get("ballot").equals(request.value().get("ballot")),"selected pull decision scope");
        var voters=new ArrayList<String>();boolean local=false;
        for(Object item:list(v.get("sources"))) {
            var ref=object(item);String node=(String)ref.get("voter");voters.add(node);
            require(context.identities.containsKey(node) && context.voters().contains(node),"selected pull ineligible source");
            if(node.equals(own.owner.nodeId().value())){require(ref.equals(own.reference()),"selected pull substituted local basis");local=true;}
        }
        require(local && voters.contains(proposer.nodeId().value()),"selected pull omitted local/proposer");context.quorum(voters);
    }
    private void merge(Map<String,byte[]> incoming) {
        for(var image:incoming.entrySet()) {
            byte[] prior=images.putIfAbsent(image.getKey(),image.getValue());
            require(prior==null || Arrays.equals(prior,image.getValue()),"selected pull conflicting image");
        }
    }
    private void check()throws IOException {
        require(!closed,"selected pull closed");long elapsed=clock.getAsLong()-started;
        require(elapsed>=0 && elapsed<budget,"original selected pull deadline");guard.check();owner.checkActivation(own.basis,null,false);
        for(var received:receives)received.recheck();if(localExport!=null)localExport.source();
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"original selected pull deadline");
    }
    Decoded install()throws IOException {
        check();var reply=MembershipActivation.install(owner,proposer,request,List.copyOf(sources),ancestry,retained,images);
        owner.checkActivation(own.basis,selected,true);check();return reply;
    }
    @Override public void close()throws IOException {
        if(removed)return;closed=true;IOException failure=null;
        for(var pull:pulls)try{pull.close();}catch(IOException|RuntimeException error){if(failure==null)failure=new IOException("selected pull cleanup",error);else failure.addSuppressed(error);}
        if(localExport!=null)localExport.close();images.clear();sources.clear();receives.clear();
        try {AdmissionPaths.safe(scratch);require(directoryKey.equals(MembershipBasisSources.key(scratch)),"selected pull scratch replaced");Files.delete(scratch);removed=true;}
        catch(IOException|RuntimeException error){if(failure==null)failure=new IOException("selected pull scratch cleanup",error);else failure.addSuppressed(error);}
        if(failure!=null)throw failure;
    }
}
