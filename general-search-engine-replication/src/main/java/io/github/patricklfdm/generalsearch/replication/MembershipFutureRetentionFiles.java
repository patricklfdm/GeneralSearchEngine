package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One local unresolved application target with its dispatch intentions. Proof and
 * intentions share one atomic replacement; this is not a governing-quorum permit.
 * Empty active state remains mandatory after initialization. */
final class MembershipFutureRetentionFiles implements AutoCloseable {
    static final String FILE="future-retention.gsft",NEXT="future-retention.next.gsft";
    static final int MAGIC=0x47534654,HEADER=44,MAXIMUM=3*1024*1024,METADATA=131072;
    static final List<String> RECORDS=List.of("selector.gsr","promise.gsr","selected.gsr","entry.gsr","accept.gsr",
            "proof.gsr","certificate.gsr","catalog.gsr","statement.gsr","ack.gsr");
    static final List<String> DEPARTURE_RECORDS=RECORDS.subList(0,RECORDS.size()-1);
    private static final List<String> KINDS=List.of("SELECTOR","PROMISE","SELECTED","ENTRY","ACCEPT","PROOF","CERTIFICATE","CATALOG","CHECKPOINT","CHECKPOINT_ACK");
    private static final int[] LIMITS={4096,8192,65536,16384,8192,16384,16384,2*1024*1024,16384,2048};
    record Peer(MembershipIdentity identity,MembershipCapsule.Anchor lower) {}
    static final class State {
        final String root,previous,digest;final MembershipIdentity owner;final long revision;
        final MembershipCapsule.Anchor parent;final List<Peer> peers;private final Map<String,Decoded> records;
        private State(String root,MembershipIdentity owner,long revision,String previous,MembershipCapsule.Anchor parent,
                List<Peer> peers,Map<String,Decoded> records,String digest) {
            this.root=root;this.owner=owner;this.revision=revision;this.previous=previous;this.parent=parent;
            this.peers=List.copyOf(peers);this.records=Map.copyOf(records);this.digest=digest;
        }
        boolean pending(){return parent!=null;}
        boolean endorsed(){return records.containsKey("ack.gsr");}
        Decoded record(String name){return Objects.requireNonNull(records.get(name),"future original record missing");}
        MembershipCapsule.Anchor target() {
            var catalog=record("catalog.gsr");return new MembershipCapsule.Anchor(object(catalog.value().get("cut")),catalog.digest(),(String)catalog.value().get("application"));
        }
        Map<String,byte[]> originals(){var result=new TreeMap<String,byte[]>();records.forEach((k,v)->result.put(k,v.bytes()));return result;}
        void matchesOriginals(Map<String,byte[]> originals) {
            require(records.keySet().equals(originals.keySet()),"future retention changed original record inventory");
            for(var record:records.entrySet())require(Arrays.equals(record.getValue().bytes(),originals.get(record.getKey())),
                    "future retention changed original target proof");
        }
        void matches(MembershipPendingAccept.Vote vote) {
            require(vote!=null && vote.certificate()!=null,"future retention lost original certified vote");
            var wanted=List.of(vote.selector(),vote.promise(),vote.selected(),vote.entry(),vote.accept(),vote.proof(),vote.certificate());
            for(int i=0;i<wanted.size();i++)require(Arrays.equals(record(RECORDS.get(i)).bytes(),wanted.get(i).bytes()),"future retention changed original vote");
        }
    }
    private final MembershipGrantJournal.HistoryRead owner;private final Path directory;private final MembershipResources resources;
    private byte[] active,next;private FileIdentity activeIdentity,nextIdentity;private State state;private boolean failed,closed;
    MembershipFutureRetentionFiles(MembershipGrantJournal.HistoryRead owner,MembershipResources resources,long allowance)throws IOException {
        this.owner=Objects.requireNonNull(owner);owner.check();this.resources=resources;directory=owner.directory();shared();
        require(allowance>=0 && allowance<=MembershipResources.Unit.JOURNAL.bytes,"future retention journal allowance");
        if(Files.exists(directory.resolve(FILE),LinkOption.NOFOLLOW_LINKS)) {
            active=AdmissionPaths.read(directory.resolve(FILE),MAXIMUM);state=decodeOwned(active,owner.root().manifestDigest(),owner.identity());
            activeIdentity=inspect(directory.resolve(FILE),active.length,hash(active));
        }
        if(Files.exists(directory.resolve(NEXT),LinkOption.NOFOLLOW_LINKS)) {
            next=AdmissionPaths.read(directory.resolve(NEXT),MAXIMUM);candidate(next);
            nextIdentity=inspect(directory.resolve(NEXT),next.length,hash(next));
        }
        require(bytes()<=allowance,"future retention retained journal capacity");check();
    }
    private void live(){require(!closed && !failed,"future retention closed or failed; reopen required");}
    private void shared(){require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,"future retention requires shared journal reservation");}
    long bytes(){live();return (active==null?0L:active.length)+(next==null?0L:next.length);}
    long candidateBytes(){live();return next==null?0L:next.length;}
    long clearMaximum(){return encode(owner.root().manifestDigest(),owner.identity(),MembershipBallotAllocator.MAX,"0".repeat(64),null,List.of(),Map.of()).length;}
    boolean initialized(){live();return state!=null;}
    State state(){live();require(state!=null,"future retention active missing");return state;}
    boolean candidate(){live();return next!=null;}
    byte[] activeBytes()throws IOException{owner.check();check();state();return active.clone();}
    private static MembershipCapsule.Anchor anchor(Object value) {
        checkType(value,"retentionAnchor");var a=object(value);
        return new MembershipCapsule.Anchor(object(a.get("cut")),(String)a.get("catalog"),(String)a.get("application"));
    }
    private static int extent(byte[] bytes) {
        byte[] prefix=ByteBuffer.allocate(8).putInt(MAGIC).putShort((short)1).putShort((short)3).array();
        for(int i=0;i<Math.min(bytes.length,8);i++)require(bytes[i]==prefix[i],"future retention candidate framing");
        if(bytes.length<12)return -1;int size=ByteBuffer.wrap(bytes).getInt(8);
        require(size>HEADER+8 && size<=MAXIMUM && bytes.length<=size,"future retention extent");return size;
    }
    private static void part(ByteArrayOutputStream body,byte[] bytes,int maximum) {
        require(bytes.length>0 && bytes.length<=maximum,"future retention record bound");body.writeBytes(ByteBuffer.allocate(4).putInt(bytes.length).array());body.writeBytes(bytes);
    }
    private static byte[] part(ByteBuffer body,int maximum) {
        require(body.remaining()>=4,"future retention member length");int size=body.getInt();
        require(size>0 && size<=maximum && size<=body.remaining(),"future retention member extent");byte[] bytes=new byte[size];body.get(bytes);return bytes;
    }
    static byte[] encode(String root,MembershipIdentity owner,long revision,String previous,MembershipCapsule.Anchor parent,List<Peer> peers,Map<String,byte[]> records) {
        var metadata=new TreeMap<String,Object>();metadata.put("root",root);metadata.put("owner",MembershipPeerRetentionPlan.identity(owner));
        metadata.put("revision",revision);metadata.put("previous",previous);metadata.put("parent",parent==null?null:MembershipRetentionIntent.anchor(parent));
        metadata.put("peers",peers.stream().map(p->Map.of("identity",MembershipPeerRetentionPlan.identity(p.identity),"lower",MembershipRetentionIntent.anchor(p.lower))).toList());
        var body=new ByteArrayOutputStream();part(body,canonical(metadata,METADATA),METADATA);body.writeBytes(ByteBuffer.allocate(4).putInt(records.size()).array());
        require(records.isEmpty() || records.keySet().equals(Set.copyOf(RECORDS))
                || records.keySet().equals(Set.copyOf(DEPARTURE_RECORDS)),"future retention exact original inventory");
        if(!records.isEmpty())for(int i=0;i<records.size();i++)part(body,records.get(RECORDS.get(i)),LIMITS[i]);
        byte[] content=body.toByteArray();require(HEADER+content.length<=MAXIMUM,"future retention total capacity");
        return ByteBuffer.allocate(HEADER+content.length).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(HEADER+content.length).put(sha(content)).put(content).array();
    }
    static State decodeOwned(byte[] bytes,String root,MembershipIdentity owner) {
        require(extent(bytes)==bytes.length,"future retention active incomplete");byte[] content=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(Arrays.copyOfRange(bytes,12,HEADER),sha(content)),"future retention checksum");var body=ByteBuffer.wrap(content);
        var value=object(parse(part(body,METADATA),METADATA));require(value.keySet().equals(Set.of("root","owner","revision","previous","parent","peers")),"future retention metadata fields");
        require(root.equals(value.get("root")) && value.get("owner").equals(MembershipPeerRetentionPlan.identity(owner)),"future retention foreign owner");
        long revision=number(value.get("revision"));require(revision>=0 && revision<=MembershipBallotAllocator.MAX,"future retention revision capacity");
        var previous=(String)value.get("previous");require((revision==0)==(previous==null),"future retention predecessor");if(previous!=null)MembershipValidation.digest(previous);
        var parent=value.get("parent")==null?null:anchor(value.get("parent"));var peers=new ArrayList<Peer>();String prior="";
        for(Object row:list(value.get("peers"))) {
            var p=object(row);require(p.keySet().equals(Set.of("identity","lower")),"future retention peer fields");
            var identity=MembershipContext.identity(object(p.get("identity")));
            require(p.get("identity").equals(MembershipPeerRetentionPlan.identity(identity)) && identity.nodeId().value().compareTo(prior)>0,"future retention peer order/identity");
            prior=identity.nodeId().value();peers.add(new Peer(identity,anchor(p.get("lower"))));
        }
        require(body.remaining()>=4,"future retention record count");int count=body.getInt();var originals=new TreeMap<String,Decoded>();
        require(parent==null?count==0 && peers.isEmpty():(count==RECORDS.size() || count==DEPARTURE_RECORDS.size())
                && !peers.isEmpty() && peers.size()<=6,"future retention empty/pending shape");
        require(parent==null || revision<MembershipBallotAllocator.MAX,"future retention completion revision exhausted");
        for(int i=0;i<count;i++)originals.put(RECORDS.get(i),decode(part(body,LIMITS[i]),"records",KINDS.get(i)));
        require(!body.hasRemaining(),"future retention trailing bytes");var state=new State(root,owner,revision,previous,parent,peers,originals,hash(bytes));
        if(state.pending())verifyRecords(state);
        require(Arrays.equals(bytes,encode(root,owner,revision,previous,parent,peers,state.originals())),"future retention noncanonical bytes");return state;
    }
    private static void verifyRecords(State s) {
        for(var frame:s.records.values())require(s.root.equals(frame.value().get("root")),"future retention original root");
        var entry=s.record("entry.gsr");var target=s.target();var statement=s.record("statement.gsr");
        require(s.record("selector.gsr").value().get("node").equals(s.owner.nodeId().value()),"future retention original selector owner");
        require(number(target.cut().get("index"))==Math.addExact(number(s.parent.cut().get("index")),1)
                && target.cut().get("entry").equals(entry.digest()) && entry.value().get("index").equals(target.cut().get("index"))
                && entry.value().get("previous").equals(s.parent.cut().get("entry")),"future retention immediate original target");
        require(statement.value().get("end").equals(target.cut()) && statement.value().get("catalogAfter").equals(target.catalog())
                && statement.value().get("applicationAfter").equals(target.application()),"future retention checkpoint target");
        var view=object(target.cut().get("view"));
        boolean eligible=MembershipContext.nodes(view,"old").contains(s.owner.nodeId().value())
                || MembershipContext.nodes(view,"new").contains(s.owner.nodeId().value());
        require(eligible==s.endorsed(),"future retention owner eligibility/completion kind");
        if(s.endorsed()) {
            var ack=s.record("ack.gsr").value();
            require(ack.get("voter").equals(s.owner.nodeId().value()) && ack.get("incarnation").equals(s.owner.storageId().toString())
                    && ack.get("statement").equals(statement.digest()) && ack.get("cut").equals(target.cut()),"future retention original application acknowledgement");
        }else MembershipAppliedEndFiles.departing(s.record("catalog.gsr"),statement,s.parent,s.record("certificate.gsr"),entry,s.owner);
        var accept=s.record("accept.gsr").value();var proof=s.record("proof.gsr").value();var certificate=s.record("certificate.gsr").value();
        var proofAccept=new TreeMap<>(proof);proofAccept.remove("accepts");var certificateProof=new TreeMap<>(certificate);certificateProof.remove("proofs");
        require(accept.get("entry").equals(entry.digest()) && accept.get("index").equals(entry.value().get("index"))
                && accept.equals(proofAccept) && proof.equals(certificateProof),"future retention original phases");
        require(s.record("promise.gsr").value().get("ballot").equals(accept.get("ballot"))
                && s.record("selected.gsr").value().get("ballot").equals(accept.get("ballot")),"future retention original ballot");
        for(var peer:s.peers)require(number(peer.lower.cut().get("index"))<number(target.cut().get("index")),"future retention peer does not advance");
    }
    private void candidate(byte[] bytes) {
        int n=extent(bytes);if(n<0 || n>bytes.length)return;var candidate=decodeOwned(bytes,owner.root().manifestDigest(),owner.identity());
        require(candidate.revision==(state==null?0:state.revision+1) && Objects.equals(candidate.previous,state==null?null:state.digest),"future retention candidate predecessor");
    }
    byte[] proposal(MembershipCapsule.Anchor parent,List<Peer> peers,Map<String,byte[]> originals) {
        live();require(state==null || state.revision<MembershipBallotAllocator.MAX,"future retention revision exhausted");
        return encode(owner.root().manifestDigest(),owner.identity(),state==null?0:state.revision+1,state==null?null:state.digest,parent,peers,originals);
    }
    void install(byte[] proposed,long allowance,MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        guard.check();owner.check();check();require(next==null,"future retention candidate recovery required");candidate(proposed);
        require(extent(proposed)==proposed.length,"future retention proposed incomplete");
        require(allowance>=proposed.length && allowance<=MembershipResources.Unit.JOURNAL.bytes,"future retention completion journal capacity");
        try {
            cut.at("FUTURE_RETENTION_BEFORE_WRITE");guard.check();owner.check();check();
            try(var channel=FileChannel.open(directory.resolve(NEXT),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                remember(new byte[0]);int half=proposed.length/2;
                AdmissionPaths.write(channel,Arrays.copyOf(proposed,half));remember(Arrays.copyOf(proposed,half));event("FUTURE_RETENTION_PREFIX_WRITTEN",guard,cut);
                AdmissionPaths.write(channel,Arrays.copyOfRange(proposed,half,proposed.length));remember(proposed);event("FUTURE_RETENTION_WRITTEN",guard,cut);
                channel.force(true);event("FUTURE_RETENTION_FORCED",guard,cut);
            }
            AdmissionPaths.forceDirectory(directory);event("FUTURE_RETENTION_CANDIDATE_PARENT_FORCED",guard,cut);
            Files.move(directory.resolve(NEXT),directory.resolve(FILE),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            active=next;activeIdentity=nextIdentity;next=null;nextIdentity=null;state=decodeOwned(active,owner.root().manifestDigest(),owner.identity());
            event("FUTURE_RETENTION_RENAMED",guard,cut);AdmissionPaths.forceDirectory(directory);event("FUTURE_RETENTION_PARENT_FORCED",guard,cut);
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    void recover(MembershipBallotAllocator.Cut cut)throws IOException {
        owner.check();check();try {
            if(next!=null) {
                Files.delete(directory.resolve(NEXT));next=null;nextIdentity=null;event("FUTURE_RETENTION_DISCARDED",()->{},cut);
                AdmissionPaths.forceDirectory(directory);event("FUTURE_RETENTION_DISCARD_PARENT_FORCED",()->{},cut);
            }
            if(active!=null) {
                try(var channel=FileChannel.open(directory.resolve(FILE),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
                event("FUTURE_RETENTION_RECOVERY_FORCED",()->{},cut);AdmissionPaths.forceDirectory(directory);event("FUTURE_RETENTION_RECOVERY_PARENT_FORCED",()->{},cut);
            }
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void remember(byte[] bytes)throws IOException{next=bytes;nextIdentity=inspect(directory.resolve(NEXT),bytes.length,hash(bytes));}
    private void event(String name,MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException{cut.at(name);guard.check();owner.check();check();}
    void check()throws IOException {
        live();shared();
        try {
        require(activeIdentity==null?!Files.exists(directory.resolve(FILE),LinkOption.NOFOLLOW_LINKS):activeIdentity.equals(inspect(directory.resolve(FILE),active.length,hash(active))),"future retention active identity changed");
        require(nextIdentity==null?!Files.exists(directory.resolve(NEXT),LinkOption.NOFOLLOW_LINKS):nextIdentity.equals(inspect(directory.resolve(NEXT),next.length,hash(next))),"future retention candidate identity changed");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    @Override public void close(){closed=true;}
}
