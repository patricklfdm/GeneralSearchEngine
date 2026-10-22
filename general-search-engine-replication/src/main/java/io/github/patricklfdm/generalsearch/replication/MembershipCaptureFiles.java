package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact current-source capture intent; covered by the current owner's MISC reservation.
 * The original generation must survive. This file cannot independently recreate authority. */
final class MembershipCaptureFiles {
    static final String FILE="source.capture.gsr";
    static final int MAXIMUM=4096+8192+16384;
    record Plan(Decoded selector,Decoded promise,Decoded basis,MembershipSourcePacket packet,Map<String,byte[]> images) {
        String id(){return (String)promise.value().get("basisId");}
        byte[] bytes(){var out=new java.io.ByteArrayOutputStream();out.writeBytes(selector.bytes());out.writeBytes(promise.bytes());out.writeBytes(basis.bytes());return out.toByteArray();}
    }
    private final Path parent,path;
    private FileIdentity pending;
    MembershipCaptureFiles(Path parent)throws IOException {this.parent=parent;path=parent.resolve(FILE);snapshot();}
    boolean pending(){return pending!=null;}
    static Plan plan(MembershipCurrentGeneration current,Decoded promise,MembershipIdentity identity)throws IOException {
        return plan(current,promise,identity,current.capsule.packet,current.accepted);
    }
    static Plan plan(MembershipCurrentGeneration current,Decoded promise,MembershipIdentity identity,MembershipSourcePacket packet,String accepted)throws IOException {
        current.check();require(promise!=null && promise.value().get("basisId")!=null,"capture requires original promise");
        require(!promise.digest().equals(current.manifest.value().get("promise")),"capture original grant is not newer than installed authority");
        var context=current.capsule.context;
        require(promise.value().get("root").equals(context.root) && promise.value().get("view").equals(context.authority())
                && context.voters().contains(identity.nodeId().value()),"capture original root/view/voter");
        context.ballot(promise.value().get("ballot"),true);
        var body=new TreeMap<String,Object>(promise.value());body.put("voter",identity.nodeId().value());body.put("cut",context.cut);
        body.put("capsule",packet.capsule().digest());body.put("inventory",packet.inventoryDigest());body.put("accepted",accepted);
        var basis=decode(encode("records","BASIS",body),"records","BASIS");packet.bind(basis);
        var result=new Plan(current.selector,promise,basis,packet,current.images());
        require(result.bytes().length<=MAXIMUM,"capture intent bound");current.check();return result;
    }
    private void snapshot()throws IOException {
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS)){pending=null;return;}
        byte[] bytes=AdmissionPaths.read(path,MAXIMUM);pending=inspect(path,bytes.length,hash(bytes));
    }
    void check()throws IOException {
        require(pending()==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"capture intent presence changed");
        if(pending!=null)require(pending.equals(inspect(path,pending.bytes(),pending.digest())),"capture intent inode changed");
    }
    void bind(Plan plan)throws IOException {
        check();require(pending!=null,"capture intent absent");byte[] actual=AdmissionPaths.read(path,MAXIMUM),expected=plan.bytes();
        require(actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length)),"capture requires exact original intent prefix");
        if(actual.length<expected.length)require(!Files.exists(parent.resolve(DIRECTORY).resolve(plan.id()),LinkOption.NOFOLLOW_LINKS),"partial capture intent already owns source files");
    }
    void write(Plan plan,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        check();owner.check();if(pending!=null)bind(plan);byte[] expected=plan.bytes();
        var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));if(pending==null)options.add(StandardOpenOption.CREATE_NEW);
        try(var channel=FileChannel.open(path,options)) {
            if(pending==null){snapshot();cut.at("CAPTURE_INTENT_CREATED");check();owner.check();}
            Object original=pending.key();int offset=Math.toIntExact(channel.size());channel.position(offset);
            int middle=offset+(expected.length-offset)/2;
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,offset,middle));snapshot();require(original.equals(pending.key()),"capture intent inode changed");
            cut.at("CAPTURE_INTENT_PREFIX_WRITTEN");check();owner.check();
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,middle,expected.length));snapshot();require(original.equals(pending.key()),"capture intent inode changed");
            cut.at("CAPTURE_INTENT_WRITTEN");check();owner.check();channel.force(true);
            cut.at("CAPTURE_INTENT_FORCED");check();owner.check();
        }
        AdmissionPaths.exact(path,expected);AdmissionPaths.forceDirectory(parent);cut.at("CAPTURE_INTENT_PARENT_FORCED");check();owner.check();
    }
    void clear(MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        check();owner.check();require(pending!=null,"capture intent absent");Files.delete(path);pending=null;
        cut.at("CAPTURE_INTENT_DELETED");check();owner.check();AdmissionPaths.forceDirectory(parent);
        cut.at("CAPTURE_INTENT_CLEARED");check();owner.check();
    }
}
