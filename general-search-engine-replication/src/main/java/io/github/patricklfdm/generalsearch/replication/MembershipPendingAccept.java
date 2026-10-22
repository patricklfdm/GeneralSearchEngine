package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One original pending vote, charged with its candidate to the existing JOURNAL lease.
 * Private container framing does not introduce a record/wire kind or an application codec. */
final class MembershipPendingAccept {
    static final String FILE="pending.accept", NEXT="pending.accept.next";
    static final int MAGIC=0x47535056, PREFIX=12, PROOF_MAXIMUM=16384, CERTIFICATE_MAXIMUM=16384, MAXIMUM=PREFIX+4+4096+8192+65536+16384+8192+FRAME+PROOF_MAXIMUM+CERTIFICATE_MAXIMUM;
    static byte[] empty(){return ByteBuffer.allocate(PREFIX).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(PREFIX).array();}
    record Vote(Decoded selector,Decoded promise,Decoded selected,Decoded entry,Decoded accept,byte[] payload,Decoded proof,Decoded certificate) {
        Vote {payload=payload.clone();}
        Vote(Decoded selector,Decoded promise,Decoded selected,Decoded entry,Decoded accept,byte[] payload) {
            this(selector,promise,selected,entry,accept,payload,null,null);
        }
        Vote withProof(Decoded proof){return new Vote(selector,promise,selected,entry,accept,payload,proof,certificate);}
        Vote withCertificate(Decoded certificate){return new Vote(selector,promise,selected,entry,accept,payload,proof,certificate);}
        boolean sameAcceptance(Vote other){return Arrays.equals(new Vote(selector,promise,selected,entry,accept,payload).bytes(),
                new Vote(other.selector,other.promise,other.selected,other.entry,other.accept,other.payload).bytes());}
        boolean sameProof(Vote other){return Arrays.equals(withCertificate(null).bytes(),other.withCertificate(null).bytes());}
        String phase(){return certificate!=null?"CERTIFICATE":proof!=null?"PROOF":"ACCEPT";}
        @Override public byte[] payload(){return payload.clone();}
        byte[] bytes() {
            var out=new java.io.ByteArrayOutputStream();
            for(var frame:List.of(selector,promise,selected,entry,accept))out.writeBytes(frame.bytes());
            byte[] body=out.toByteArray();int length=Math.addExact(PREFIX+4+body.length+payload.length,(proof==null?0:proof.bytes().length)+(certificate==null?0:certificate.bytes().length));
            require(length<=MAXIMUM,"pending vote container capacity");
            return ByteBuffer.allocate(length).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(length)
                    .put(body).putInt(payload.length).put(payload).put(proof==null?new byte[0]:proof.bytes()).put(certificate==null?new byte[0]:certificate.bytes()).array();
        }
    }
    private final Path parent;
    private FileIdentity activeIdentity,nextIdentity;
    private byte[] activeBytes,nextBytes;
    private Vote active;
    MembershipPendingAccept(Path parent)throws IOException {
        this.parent=parent;activeBytes=AdmissionPaths.read(parent.resolve(FILE),MAXIMUM);
        activeIdentity=inspect(parent.resolve(FILE),activeBytes.length,hash(activeBytes));
        active=decode(activeBytes);
        if(Files.exists(parent.resolve(NEXT),LinkOption.NOFOLLOW_LINKS)) {
            nextBytes=AdmissionPaths.read(parent.resolve(NEXT),MAXIMUM);declared(nextBytes);
            nextIdentity=inspect(parent.resolve(NEXT),nextBytes.length,hash(nextBytes));
        }
    }
    Vote active(){return active;}
    boolean pending(){return nextIdentity!=null;}
    long bytes(){return activeBytes.length+(nextBytes==null?0:nextBytes.length);}
    long clearAllowance(){return Math.max(0,PREFIX-(nextBytes==null?0:nextBytes.length));}
    int activeLength(){return activeBytes.length;}
    Set<String> protectedPromises() {
        return active==null?Set.of():Set.of(active.promise().digest());
    }
    boolean protectsSource(String id){return active!=null && id.equals(active.promise().value().get("basisId"));}
    /** Incomplete candidate bytes are retained. Only a fully revalidated request matching
     * every surviving prefix byte may supply the absent suffix; unwritten bytes are not authority. */
    Optional<Vote> completeCandidate() {
        if(nextBytes==null)return Optional.empty();
        int length=declared(nextBytes);
        if(length<0 || nextBytes.length<length)return Optional.empty();
        var vote=decode(nextBytes);require(vote!=null,"candidate cannot erase an original vote");return Optional.of(vote);
    }
    private static int declared(byte[] bytes) {
        byte[] fixed=empty();
        for(int i=0;i<Math.min(8,bytes.length);i++)require(bytes[i]==fixed[i],"pending container version/magic");
        if(bytes.length<PREFIX)return -1;
        int size=ByteBuffer.wrap(bytes).getInt(8);
        require(size>=PREFIX && size<=MAXIMUM && bytes.length<=size,"pending container length");return size;
    }
    static Vote decode(byte[] bytes) {
        int size=declared(bytes);require(size==bytes.length && size>=PREFIX,"incomplete active pending vote");
        if(size==PREFIX){require(Arrays.equals(bytes,empty()),"invalid empty pending authority");return null;}
        var buffer=ByteBuffer.wrap(bytes);buffer.position(PREFIX);
        var selector=part(buffer,"SELECTOR");var promise=part(buffer,"PROMISE");var selected=part(buffer,"SELECTED");
        var entry=part(buffer,"ENTRY");var accept=part(buffer,"ACCEPT");
        require(buffer.remaining()>=4,"missing pending payload length");int count=buffer.getInt();
        require(count>=0 && count<=FRAME && count<=buffer.remaining(),"pending payload length");
        byte[] payload=new byte[count];buffer.get(payload);
        require(hash(payload).equals(entry.value().get("payload")),"pending payload hash");
        var proof=buffer.hasRemaining()?part(buffer,"PROOF"):null;
        var certificate=buffer.hasRemaining()?part(buffer,"CERTIFICATE"):null;
        require(!buffer.hasRemaining(),"pending certificate trailing bytes");
        return new Vote(selector,promise,selected,entry,accept,payload,proof,certificate);
    }
    private static Decoded part(ByteBuffer buffer,String kind) {
        require(buffer.remaining()>=HEADER,"pending original record header");byte[] header=new byte[HEADER];
        int offset=buffer.position();buffer.get(header);int length=HEADER+MembershipFormat.header(header,"records",kind);
        require(length<=buffer.limit()-offset,"pending original record length");byte[] bytes=new byte[length];buffer.position(offset);buffer.get(bytes);
        return MembershipFormat.decode(bytes,"records",kind);
    }
    static void verify(Vote vote,MembershipCurrentGeneration current,MembershipIdentity local,Collection<Decoded> promises,Collection<Decoded> selections) {
        verify(vote,current.capsule,local,promises,selections);
    }
    static void verify(Vote vote,MembershipCapsule original,MembershipIdentity local,Collection<Decoded> promises,Collection<Decoded> selections) {
        if(vote==null)return;var context=original.context;var e=vote.entry().value();var a=vote.accept().value();
        var s=vote.selected().value();var p=vote.promise().value();
        require(vote.selector().value().get("root").equals(context.root) && vote.selector().value().get("node").equals(local.nodeId().value()),"pending original selector owner");
        require(promises.stream().anyMatch(v->Arrays.equals(v.bytes(),vote.promise().bytes()))
                && selections.stream().anyMatch(v->Arrays.equals(v.bytes(),vote.selected().bytes())),"pending original decision absent from journal");
        require(local.equals(context.identities.get(local.nodeId().value())) && context.voters().contains(local.nodeId().value()),"pending local voter eligibility");
        require(s.get("root").equals(context.root) && p.get("root").equals(context.root)
                && s.get("view").equals(context.authority()) && p.get("view").equals(context.authority())
                && s.get("cut").equals(context.cut) && p.get("ballot").equals(s.get("ballot")),"pending original selected parent");
        require(e.get("root").equals(context.root) && a.get("root").equals(context.root)
                && e.get("authority").equals(context.authority()) && a.get("authority").equals(context.authority())
                && e.get("previous").equals(context.cut.get("entry")) && number(context.cut.get("index"))<MembershipValidation.MAX
                && number(e.get("index"))==number(context.cut.get("index"))+1 && e.get("index").equals(a.get("index"))
                && vote.entry().digest().equals(a.get("entry")) && a.get("ballot").equals(p.get("ballot")),"pending entry/ACCEPT binding");
        context.ballot(p.get("ballot"),true);context.ballot(e.get("origin"),true);
        require(compareBallot(object(e.get("origin")),object(a.get("ballot")))<=0,"pending origin exceeds acceptance ballot");
        require(s.get("nextEntry")==null?e.get("origin").equals(p.get("ballot")):vote.entry().digest().equals(s.get("nextEntry")),"pending entry differs from selected choice/origin");
        require(hash(vote.payload()).equals(e.get("payload")),"pending payload hash");
        context.control((String)e.get("kind"),command((String)e.get("kind"),vote.payload()));
        if(vote.proof()!=null)context.persistedProof(vote.proof(),vote.accept());
        if(vote.certificate()!=null)context.persistedCertificate(vote.certificate(),vote.proof(),vote.accept());
    }
    /** Union immutable originals. The higher accepted ballot owns the still-unsettled next slot. */
    static MembershipSourcePacket packet(MembershipCurrentGeneration current,Vote vote) {
        if(vote==null)return current.capsule.packet;
        var original=current.capsule.packet;var objects=new TreeMap<String,byte[]>();
        for(String digest:original.objectNames())objects.put(digest,original.objectBytes(digest));
        objects.put(vote.entry().digest(),vote.entry().bytes());objects.put(vote.accept().digest(),vote.accept().bytes());
        objects.put((String)vote.entry().value().get("payload"),vote.payload());
        if(vote.proof()!=null)objects.put(vote.proof().digest(),vote.proof().bytes());
        if(vote.certificate()!=null)objects.put(vote.certificate().digest(),vote.certificate().bytes());
        var capsule=new TreeMap<>(original.capsule().value());capsule.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(MembershipFormat.decode(encode("records","CAPSULE",capsule),"records","CAPSULE"),objects,original.images()));
    }
    static String accepted(MembershipCurrentGeneration current,Vote vote) {
        if(vote==null)return current.accepted;
        if(current.accepted==null)return vote.accept().digest();
        var old=current.capsule.context.record(current.accepted,"ACCEPT");int order=compareBallot(object(vote.accept().value().get("ballot")),object(old.value().get("ballot")));
        require(order!=0 || old.value().get("entry").equals(vote.accept().value().get("entry")),"pending equal-ballot conflict");
        return order>=0?vote.accept().digest():old.digest();
    }
    void check()throws IOException {
        require(activeIdentity.equals(inspect(parent.resolve(FILE),activeIdentity.bytes(),activeIdentity.digest())),"pending active inode changed");
        require(pending()==Files.exists(parent.resolve(NEXT),LinkOption.NOFOLLOW_LINKS),"pending candidate presence changed");
        if(pending())require(nextIdentity.equals(inspect(parent.resolve(NEXT),nextIdentity.bytes(),nextIdentity.digest())),"pending candidate inode changed");
    }
    void matches(Vote vote) {
        if(nextBytes!=null){byte[] expected=vote.bytes();require(nextBytes.length<=expected.length && Arrays.equals(nextBytes,Arrays.copyOf(expected,nextBytes.length)),"pending candidate requires exact original request");}
    }
    void install(Vote vote,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        check();owner.check();matches(vote);byte[] expected=vote.bytes();String phase=vote.phase();
        replace(vote,expected,phase,owner,cut);
    }
    /** Only a complete forced selector covering this exact certificate can authorize the caller's guard. */
    void clearCovered(Vote original,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        owner.check();checkCoveredCandidate(original);
        replace(null,empty(),"COVERED_VOTE",owner,cut);
    }
    void checkCoveredCandidate(Vote original)throws IOException {
        check();require(active!=null && original.certificate()!=null && Arrays.equals(activeBytes,original.bytes()),"covered vote original changed");
        byte[] expected=empty();require(nextBytes==null || nextBytes.length<=expected.length && Arrays.equals(nextBytes,Arrays.copyOf(expected,nextBytes.length)),"covered vote candidate differs from exact empty state");
    }
    private void replace(Vote vote,byte[] expected,String phase,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));if(!pending())options.add(StandardOpenOption.CREATE_NEW);
        try(var channel=FileChannel.open(parent.resolve(NEXT),options)) {
            if(!pending()){snapshotNext(new byte[0]);cut.at(phase+"_CANDIDATE_CREATED");check();owner.check();}
            Object key=nextIdentity.key();int offset=nextBytes.length;channel.position(offset);int middle=offset+(expected.length-offset)/2;
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,offset,middle));snapshotNext(Arrays.copyOf(expected,middle));require(key.equals(nextIdentity.key()),"pending candidate inode changed");
            cut.at(phase+"_PREFIX_WRITTEN");check();owner.check();
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,middle,expected.length));snapshotNext(expected);require(key.equals(nextIdentity.key()),"pending candidate inode changed");
            cut.at(phase+"_CANDIDATE_WRITTEN");check();owner.check();channel.force(true);
            cut.at(phase+"_CANDIDATE_FORCED");check();owner.check();
        }
        AdmissionPaths.forceDirectory(parent);cut.at(phase+"_CANDIDATE_PARENT_FORCED");check();owner.check();
        Files.move(parent.resolve(NEXT),parent.resolve(FILE),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        activeIdentity=nextIdentity;activeBytes=expected;active=vote;nextIdentity=null;nextBytes=null;
        cut.at(phase+"_RENAMED");check();owner.check();AdmissionPaths.forceDirectory(parent);
        cut.at(phase+"_PARENT_FORCED");check();owner.check();
    }
    private void snapshotNext(byte[] expected)throws IOException {
        nextIdentity=inspect(parent.resolve(NEXT),expected.length,hash(expected));nextBytes=expected;
    }
    void sealActive(MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        String phase=active==null?"ACCEPT":active.phase();
        check();owner.check();try(var channel=FileChannel.open(parent.resolve(FILE),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
        cut.at(phase+"_ACTIVE_FORCED");check();owner.check();AdmissionPaths.forceDirectory(parent);
        cut.at(phase+"_ACTIVE_PARENT_FORCED");check();owner.check();
    }
}
