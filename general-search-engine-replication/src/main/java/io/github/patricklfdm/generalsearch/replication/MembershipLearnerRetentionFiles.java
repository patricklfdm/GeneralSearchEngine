package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private nonvoting learner intent storage under the native journal's existing exclusive lock.
 * A successful update is local durability only, not a quorum receipt or dispatch
 * permit. No caller may expose an update before replace/parent-force returns. */
final class MembershipLearnerRetentionFiles implements AutoCloseable {
    static final String FILE="learner-retention.gslr",NEXT="learner-retention.next.gslr";
    static final int MAGIC=0x47534c52,HEADER=44,MAXIMUM=32768;
    record State(long revision,String digest,MembershipLearnerRetentionPlan plan) {}
    private final MembershipGrantJournal.HistoryRead owner;
    private final Path directory;
    private final MembershipResources resources;
    private byte[] active,next;
    private FileIdentity activeIdentity,nextIdentity;
    private State state;
    private boolean failed,closed;

    MembershipLearnerRetentionFiles(MembershipGrantJournal.HistoryRead owner,MembershipResources resources,long allowance)throws IOException {
        this.owner=Objects.requireNonNull(owner);owner.check();directory=owner.directory();
        this.resources=Objects.requireNonNull(resources);sharedJournal();
        require(allowance>=0 && allowance<=MembershipResources.Unit.JOURNAL.bytes,"learner retention journal allowance");
            if(Files.exists(directory.resolve(FILE),LinkOption.NOFOLLOW_LINKS)) {
                active=AdmissionPaths.read(directory.resolve(FILE),MAXIMUM);state=decode(active);
                activeIdentity=inspect(directory.resolve(FILE),active.length,hash(active));
            }
            if(Files.exists(directory.resolve(NEXT),LinkOption.NOFOLLOW_LINKS)) {
                next=AdmissionPaths.read(directory.resolve(NEXT),MAXIMUM);candidate(next);
                nextIdentity=inspect(directory.resolve(NEXT),next.length,hash(next));
            }
        require(bytes()<=allowance,"learner retention retained journal capacity");check();
    }
    State state(){live();require(state!=null,"learner retention active record missing");return state;}
    byte[] activeBytes()throws IOException{owner.check();check();state();return active.clone();}
    boolean initialized(){live();return state!=null;}
    boolean pending(){live();return next!=null;}
    private void live(){require(!failed && !closed,"learner retention closed or failed; reopen required");}
    long bytes(){live();return (active==null?0L:active.length)+(next==null?0L:next.length);}
    long candidateBytes(){live();return next==null?0L:next.length;}
    private void sharedJournal(){require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,"learner retention requires shared journal reservation");}
    private byte[] encode(long revision,String previous,MembershipLearnerRetentionPlan plan) {
        return encode(owner.root().manifestDigest(),owner.identity(),revision,previous,plan);
    }
    private static byte[] encode(String root,MembershipIdentity owner,long revision,String previous,MembershipLearnerRetentionPlan plan) {
        var value=new TreeMap<String,Object>();value.put("root",root);
        value.put("owner",MembershipPeerRetentionPlan.identity(owner));value.put("revision",revision);
        value.put("previous",previous);value.put("plan",parse(plan.bytes(),MembershipLearnerRetentionPlan.MAXIMUM));byte[] body=canonical(value,MAXIMUM-HEADER);
        return ByteBuffer.allocate(HEADER+body.length).putInt(MAGIC).putShort((short)1).putShort((short)3)
                .putInt(HEADER+body.length).put(HexFormat.of().parseHex(hash(body))).put(body).array();
    }
    private static int extent(byte[] bytes) {
        byte[] fixed=ByteBuffer.allocate(8).putInt(MAGIC).putShort((short)1).putShort((short)3).array();
        for(int i=0;i<Math.min(bytes.length,8);i++)require(bytes[i]==fixed[i],"learner retention candidate framing");
        if(bytes.length<12)return -1;
        int length=ByteBuffer.wrap(bytes).getInt(8);
        require(length>HEADER && length<=MAXIMUM && bytes.length<=length,"learner retention candidate extent");return length;
    }
    private State decode(byte[] bytes) {
        return decodeOwned(bytes,owner.root().manifestDigest(),owner.identity());
    }
    /** Decoding an original copy is not a new durability observation. */
    static State decodeOwned(byte[] bytes,String root,MembershipIdentity owner) {
        require(extent(bytes)==bytes.length,"learner retention active incomplete");
        byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(HexFormat.of().formatHex(bytes,12,HEADER).equals(hash(body)),"learner retention checksum");
        var value=object(parse(body,MAXIMUM-HEADER));
        require(value.keySet().equals(Set.of("root","owner","revision","previous","plan")),"learner retention container fields");
        require(value.get("root").equals(root)
                && value.get("owner").equals(MembershipPeerRetentionPlan.identity(owner)),"learner retention foreign storage owner");
        long revision=number(value.get("revision"));require(revision>=0 && revision<=MembershipBallotAllocator.MAX,"learner retention revision capacity");
        Object previous=value.get("previous");require((revision==0)==(previous==null),"learner retention revision parent");
        if(previous!=null)MembershipValidation.digest((String)previous);
        require(object(value.get("plan")).get("root").equals(root),"learner retention plan root");
        var plan=MembershipLearnerRetentionPlan.decode(canonical(value.get("plan"),MembershipLearnerRetentionPlan.MAXIMUM));
        require(Arrays.equals(bytes,encode(root,owner,revision,(String)previous,plan)),"learner retention noncanonical container");
        return new State(revision,hash(bytes),plan);
    }
    static byte[] successor(byte[] before,String root,MembershipIdentity owner,MembershipLearnerRetentionPlan plan) {
        var state=decodeOwned(before,root,owner);require(state.revision()<MembershipBallotAllocator.MAX,"learner retention revision exhausted");
        return encode(root,owner,state.revision()+1,state.digest(),plan);
    }
    /** Bytes only; an original initialization transaction supplies authority. */
    static byte[] initial(String root,MembershipIdentity owner,MembershipLearnerRetentionPlan plan) {
        return encode(root,owner,0,null,plan);
    }
    private void candidate(byte[] bytes) {
        int length=extent(bytes);if(length<0 || bytes.length<length)return;
        var decoded=decode(bytes);var value=object(parse(Arrays.copyOfRange(bytes,HEADER,bytes.length),MAXIMUM-HEADER));
        require(decoded.revision()==(state==null?0:state.revision()+1)
                && Objects.equals(value.get("previous"),state==null?null:state.digest()),"learner retention candidate predecessor");
    }
    /** No candidate is dispatch-visible. The last active record stays conservative
     * for a cancelled narrowing or a not-yet-dispatched expansion. Reopening never
     * invents a missing active record from an incomplete candidate. */
    void discardUnexposed(MembershipBallotAllocator.Cut cut)throws IOException {
        owner.check();check();if(next==null)return;
        try {
            cut.at("LEARNER_RETENTION_DISCARD_VALIDATED");owner.check();check();
            Files.delete(directory.resolve(NEXT));next=null;nextIdentity=null;
            cut.at("LEARNER_RETENTION_DISCARDED");owner.check();check();AdmissionPaths.forceDirectory(directory);
            cut.at("LEARNER_RETENTION_DISCARD_PARENT_FORCED");owner.check();check();
        }catch(IOException|RuntimeException|Error e){failed=true;throw e;}
    }
    /** A complete active file seen after process death may precede the old parent
     * force. Seal both again before allowing the recovered owner to use it. */
    void reseal(MembershipBallotAllocator.Cut cut)throws IOException {
        owner.check();check();require(state!=null && next==null,"learner retention recovery state");
        try {
            try(var channel=MembershipFileAccess.open(directory.resolve(FILE),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
            event("LEARNER_RETENTION_RECOVERY_ACTIVE_FORCED",cut);AdmissionPaths.forceDirectory(directory);
            event("LEARNER_RETENTION_RECOVERY_PARENT_FORCED",cut);
        }catch(IOException|RuntimeException|Error e){failed=true;throw e;}
    }
    State install(MembershipLearnerRetentionPlan plan,long allowance,MembershipBallotAllocator.Cut cut)throws IOException {
        owner.check();check();require(next==null,"learner retention candidate recovery required");
        require(state==null || state.revision()<MembershipBallotAllocator.MAX,"learner retention revision exhausted");
        byte[] bytes=encode(state==null?0:state.revision()+1,state==null?null:state.digest(),plan);
        require(allowance>=bytes.length && allowance<=MembershipResources.Unit.JOURNAL.bytes,"learner retention completion journal capacity");
        try {
            cut.at("LEARNER_RETENTION_BEFORE_WRITE");owner.check();check();
            try(var channel=MembershipFileAccess.open(directory.resolve(NEXT),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                next=new byte[0];nextIdentity=inspect(directory.resolve(NEXT),0,hash(next));
                int half=bytes.length/2;AdmissionPaths.write(channel,Arrays.copyOf(bytes,half));remember(Arrays.copyOf(bytes,half));
                event("LEARNER_RETENTION_PREFIX_WRITTEN",cut);
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,half,bytes.length));remember(bytes);event("LEARNER_RETENTION_WRITTEN",cut);
                channel.force(true);event("LEARNER_RETENTION_FORCED",cut);
            }
            AdmissionPaths.forceDirectory(directory);event("LEARNER_RETENTION_CANDIDATE_PARENT_FORCED",cut);
            Files.move(directory.resolve(NEXT),directory.resolve(FILE),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            active=next;activeIdentity=nextIdentity;next=null;nextIdentity=null;state=decode(active);
            event("LEARNER_RETENTION_RENAMED",cut);AdmissionPaths.forceDirectory(directory);event("LEARNER_RETENTION_PARENT_FORCED",cut);
            return state;
        }catch(IOException|RuntimeException|Error e){failed=true;throw e;}
    }
    private void remember(byte[] bytes)throws IOException {next=bytes;nextIdentity=inspect(directory.resolve(NEXT),bytes.length,hash(bytes));}
    private void event(String event,MembershipBallotAllocator.Cut cut)throws IOException {cut.at(event);owner.check();check();}
    void check()throws IOException {
        live();sharedJournal();try {
            if(activeIdentity!=null)require(inspect(directory.resolve(FILE),activeIdentity.bytes(),activeIdentity.digest()).equals(activeIdentity),"learner retention active identity changed");
            else require(!Files.exists(directory.resolve(FILE),LinkOption.NOFOLLOW_LINKS),"learner retention active appeared");
            if(nextIdentity!=null)require(inspect(directory.resolve(NEXT),nextIdentity.bytes(),nextIdentity.digest()).equals(nextIdentity),"learner retention candidate identity changed");
            else require(!Files.exists(directory.resolve(NEXT),LinkOption.NOFOLLOW_LINKS),"learner retention candidate appeared");
        }catch(IOException|RuntimeException|Error e){failed=true;throw e;}
    }
    @Override public void close(){closed=true;}
}
