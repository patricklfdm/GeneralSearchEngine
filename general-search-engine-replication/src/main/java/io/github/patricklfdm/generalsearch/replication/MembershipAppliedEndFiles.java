package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One exact applied-end staging area. Caller owns the journal/fence and its remaining metadata allowance. */
final class MembershipAppliedEndFiles implements AutoCloseable {
    static final String DIRECTORY="applied-end",PLAN="plan.json",IMAGE="application.image",ACK="ack.gsr";
    static final int METADATA=4096*2+16384*2+2*1024*1024+2048;
    private static final Set<String> NAMES=Set.of(PLAN,IMAGE,ACK,"selector.gsr","certificate.gsr","catalog.gsr","statement.gsr");
    record Endorsement(Decoded acknowledgement,Owned owned) {}
    private final Path path;
    private final Map<String,Object> binding;
    private final MembershipResources resources;
    private final long maximumMetadata;
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private MembershipResources.Lease imageLease;
    private Object directoryKey;
    private boolean exists,closed;

    MembershipAppliedEndFiles(Path requested,MembershipResources resources,long maximumMetadata)throws IOException {
        path=AdmissionPaths.safe(requested);binding=AdmissionPaths.binding(path);this.resources=Objects.requireNonNull(resources);
        require(maximumMetadata>=0 && maximumMetadata<=MembershipResources.Unit.JOURNAL.bytes,"applied-end journal allowance");
        this.maximumMetadata=maximumMetadata;
        require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,"applied-end requires shared journal reservation");
        try {snapshot();if(exists)reserve();}catch(IOException|RuntimeException|Error error){close();throw error;}
    }
    static int limit(String name) {
        return switch(name) {
            case PLAN,"selector.gsr" -> 4096;
            case "certificate.gsr","statement.gsr" -> 16384;
            case "catalog.gsr" -> 2*1024*1024;
            case IMAGE -> MembershipApplicationImage.MAXIMUM;
            case ACK -> 2048;
            default -> throw new IllegalArgumentException("unknown applied-end file");
        };
    }
    private void snapshot()throws IOException {
        AdmissionPaths.recheck(binding);files.clear();exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);directoryKey=exists?key(path):null;
        if(!exists)return;
        long metadata=0;
        for(String name:children(path,7)) {
            require(NAMES.contains(name),"applied-end inventory");byte[] bytes=AdmissionPaths.read(path.resolve(name),limit(name));
            files.put(name,inspect(path.resolve(name),bytes.length,hash(bytes)));if(!name.equals(IMAGE))metadata+=bytes.length;
        }
        require(metadata<=maximumMetadata,"applied-end journal capacity");
    }
    private void reserve() {
        if(imageLease==null)imageLease=resources.reserve(MembershipResources.Unit.APPLICATION,"applied-end",MembershipResources.Unit.APPLICATION.bytes);
    }
    void reserveCompletion(){require(!closed,"applied-end closed");reserve();}
    boolean present(){return exists;}
    void check()throws IOException {
        require(!closed,"applied-end closed");AdmissionPaths.recheck(binding);
        require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,"applied-end lost shared journal reservation");
        require(exists==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"applied-end directory presence changed");
        if(exists) {
            require(directoryKey.equals(key(path)) && children(path,7).equals(files.keySet()),"applied-end directory identity/inventory changed");
            for(var row:files.entrySet())require(row.getValue().equals(inspect(path.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"applied-end inode changed");
        }
    }
    private static SortedMap<String,byte[]> materialization(MembershipCheckpointPlan plan,Decoded originalSelector,MembershipIdentity identity) {
        return materialization(plan.catalog,plan.statement,plan.originalCertificate(),plan.application.image(),originalSelector,identity);
    }
    private static SortedMap<String,byte[]> materialization(Decoded catalog,Decoded statement,Decoded certificate,byte[] image,Decoded originalSelector,MembershipIdentity identity) {
        var selector=decode(originalSelector.bytes(),"records","SELECTOR");String root=(String)catalog.value().get("root");
        require(selector.value().get("root").equals(root) && selector.value().get("node").equals(identity.nodeId().value()),"applied-end original selector owner");
        var cut=object(catalog.value().get("cut"));var view=object(cut.get("view"));
        var registered=list(catalog.value().get("identities")).stream().map(MembershipFormat::object).map(MembershipContext::identity).toList();
        require(registered.contains(identity) && (nodes(view,"old").contains(identity.nodeId().value()) || nodes(view,"new").contains(identity.nodeId().value())),"applied-end next-authority identity");
        require(hash(image).equals(catalog.value().get("application")),"applied-end exact image");
        var ack=decode(encode("records","CHECKPOINT_ACK",Map.of("root",root,"cut",cut,"statement",statement.digest(),
                "voter",identity.nodeId().value(),"incarnation",identity.storageId().toString())),"records","CHECKPOINT_ACK");
        var result=new TreeMap<String,byte[]>();result.put("selector.gsr",selector.bytes());result.put("certificate.gsr",certificate.bytes());
        result.put("catalog.gsr",catalog.bytes());result.put("statement.gsr",statement.bytes());result.put(IMAGE,image);result.put(ACK,ack.bytes());
        var inventory=new ArrayList<Map<String,Object>>();result.forEach((name,bytes)->inventory.add(Map.of("path",name,"sha256",hash(bytes),"bytes",(long)bytes.length)));
        result.put(PLAN,canonical(Map.of("schema","gse-v53-applied-end/1.3","root",root,"node",identity.nodeId().value(),"files",inventory),4096));
        for(var row:result.entrySet())require(row.getValue().length<=limit(row.getKey()),"applied-end member capacity");return result;
    }
    void completed(MembershipCheckpointPlan plan,Decoded selector,MembershipIdentity identity,Endorsement endorsement)throws IOException {
        check();var expected=materialization(plan,selector,identity);
        require(exists && files.keySet().equals(expected.keySet()),"publication requires complete applied end");
        for(var row:expected.entrySet())require(files.get(row.getKey()).bytes()==row.getValue().length && files.get(row.getKey()).digest().equals(hash(row.getValue())),"publication differs from original applied end");
        var ack=decode(expected.get(ACK),"records","CHECKPOINT_ACK");
        require(Arrays.equals(ack.bytes(),endorsement.acknowledgement().bytes()) && endorsement.owned().equals(
                new Owned(identity.nodeId().value(),identity.storageId(),ack.digest(),cutDigest(object(plan.catalog.value().get("cut"))))),"publication original local end observation");
    }
    /** The durable covering generation is authority; PLAN is kept until all listed members are gone. */
    void retireCovered(MembershipCapsule capsule,Map<String,byte[]> images,MembershipPendingAccept.Vote vote,MembershipIdentity identity,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        check();guard.check();var cap=capsule.packet.capsule().value();var last=object(list(cap.get("items")).getLast());
        var expected=materialization(capsule.context.record((String)cap.get("catalog"),"CATALOG"),capsule.context.record((String)last.get("statement"),"CHECKPOINT"),
                vote.certificate(),images.get(cap.get("application")),vote.selector(),identity);
        require(files.isEmpty() || files.containsKey(PLAN),"covered end lost original plan before members");
        for(var row:files.entrySet())require(expected.containsKey(row.getKey()) && row.getValue().bytes()==expected.get(row.getKey()).length
                && row.getValue().digest().equals(hash(expected.get(row.getKey()))),"covered end differs from exact published state");
        event("COVERED_END_VALIDATED",guard,cut);
        var names=new ArrayList<>(files.keySet());names.remove(PLAN);if(files.containsKey(PLAN))names.add(PLAN);
        for(String name:names) {
            event("COVERED_END_BEFORE_DELETE",guard,cut);Files.delete(path.resolve(name));files.remove(name);
            AdmissionPaths.forceDirectory(path);event("COVERED_END_FILE_DELETED",guard,cut);
        }
        if(exists) {
            event("COVERED_END_BEFORE_DIRECTORY_DELETE",guard,cut);Files.delete(path);exists=false;directoryKey=null;
            AdmissionPaths.forceDirectory(path.getParent());event("COVERED_END_DIRECTORY_DELETED",guard,cut);
        }
        if(imageLease!=null){imageLease.close();imageLease=null;}
    }
    /** Guard must verify actual original selector/certificate ownership and the unchanged promise/fence at every call. */
    Endorsement force(MembershipCheckpointPlan plan,Decoded selector,MembershipIdentity identity,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        check();guard.check();var expected=materialization(plan,selector,identity);long metadata=0;
        for(var row:expected.entrySet())if(!row.getKey().equals(IMAGE))metadata+=row.getValue().length;
        require(metadata<=maximumMetadata,"applied-end completion journal capacity");
        for(var row:files.entrySet())require(prefix(AdmissionPaths.read(path.resolve(row.getKey()),limit(row.getKey())),expected.get(row.getKey())),"applied-end requires exact original plan");
        // An ACK (even a torn one) can only follow a complete exact forced end.
        if(files.containsKey(ACK))for(var row:expected.entrySet())if(!row.getKey().equals(ACK))
            require(files.containsKey(row.getKey()) && files.get(row.getKey()).bytes()==row.getValue().length
                    && files.get(row.getKey()).digest().equals(hash(row.getValue())),"applied-end ACK without complete original end");
        reserve();event("APPLY_VALIDATED",guard,cut);
        if(!exists){Files.createDirectory(path);snapshot();event("APPLY_DIRECTORY_CREATED",guard,cut);}
        complete(PLAN,expected.get(PLAN),"APPLY_PLAN",guard,cut);
        for(String name:List.of("selector.gsr","certificate.gsr","catalog.gsr","statement.gsr"))complete(name,expected.get(name),"APPLY_METADATA",guard,cut);
        complete(IMAGE,expected.get(IMAGE),"APPLY_IMAGE",guard,cut);
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(path.getParent());event("APPLY_END_FORCED",guard,cut);
        complete(ACK,expected.get(ACK),"APPLY_ACK",guard,cut);
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(path.getParent());event("APPLY_ACK_DIRECTORY_FORCED",guard,cut);
        event("APPLY_BEFORE_RETURN",guard,cut);
        var ack=decode(expected.get(ACK),"records","CHECKPOINT_ACK");
        return new Endorsement(ack,new Owned(identity.nodeId().value(),identity.storageId(),ack.digest(),cutDigest(object(plan.catalog.value().get("cut")))));
    }
    private void event(String name,MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        check();guard.check();cut.at(name);check();guard.check();
    }
    private void complete(String name,byte[] expected,String label,MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        check();guard.check();boolean present=files.containsKey(name);var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));
        if(!present)options.add(StandardOpenOption.CREATE_NEW);
        try(var channel=FileChannel.open(path.resolve(name),options)) {
            if(!present){updated(name,new byte[0]);event(label+"_CREATED",guard,cut);}
            Object originalKey=files.get(name).key();int offset=Math.toIntExact(files.get(name).bytes());channel.position(offset);int middle=offset+(expected.length-offset)/2;
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,offset,middle));updated(name,Arrays.copyOf(expected,middle));require(originalKey.equals(files.get(name).key()),"applied-end replaced write target");event(label+"_PREFIX_WRITTEN",guard,cut);
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,middle,expected.length));updated(name,expected);require(originalKey.equals(files.get(name).key()),"applied-end replaced write target");event(label+"_WRITTEN",guard,cut);
            require(files.get(name).bytes()==expected.length && files.get(name).digest().equals(hash(expected)),"applied-end written content");
            channel.force(true);event(label+"_FORCED",guard,cut);
        }
    }
    private void updated(String changed,byte[] expected)throws IOException {
        AdmissionPaths.recheck(binding);require(directoryKey.equals(key(path)),"applied-end directory changed while writing");
        var names=new TreeSet<>(files.keySet());names.add(changed);require(children(path,7).equals(names),"applied-end inventory changed while writing");
        for(var row:files.entrySet())if(!row.getKey().equals(changed))
            require(row.getValue().equals(inspect(path.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"applied-end prior inode changed while writing");
        files.put(changed,inspect(path.resolve(changed),expected.length,hash(expected)));
    }
    private static boolean prefix(byte[] actual,byte[] expected){return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));}
    @Override public void close(){if(imageLease!=null){imageLease.close();imageLease=null;}closed=true;}
}
