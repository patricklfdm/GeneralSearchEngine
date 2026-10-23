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

/** One exact applied-end staging area. Caller owns the journal/fence and its remaining metadata allowance. */
final class MembershipAppliedEndFiles implements AutoCloseable {
    static final String DIRECTORY="applied-end",PLAN="plan.json",IMAGE="application.image",ACK="ack.gsr";
    static final String PARENT_STATEMENT="parent-statement.gsr",PARENT_ACK="parent-ack.gsr";
    static final String RETIREMENT="retirement.gsat",RETIREMENT_NEXT="retirement.gsat.next";
    static final int RETIREMENT_MAXIMUM=16*1024;
    private static final int RETIREMENT_MAGIC=0x47534154;
    static final int METADATA=4096*2+16384*8+2*1024*1024+2048*7+RETIREMENT_MAXIMUM;
    private static final Set<String> NAMES;
    static {
        var names=new HashSet<>(Set.of(PLAN,IMAGE,ACK,"selector.gsr","certificate.gsr","catalog.gsr","statement.gsr",PARENT_STATEMENT,PARENT_ACK,RETIREMENT,RETIREMENT_NEXT));
        for(int i=0;i<5;i++){names.add(ancestor(i,false));names.add(ancestor(i,true));}NAMES=Set.copyOf(names);
    }
    private static String ancestor(int n,boolean ack){return "ancestor-"+n+(ack?"-ack.gsr":"-statement.gsr");}
    record ParentEndorsement(Decoded statement,Decoded acknowledgement,Owned owned) {}
    record Endorsement(Decoded acknowledgement,Owned owned,Optional<ParentEndorsement> parent,List<ParentEndorsement> ancestors) {
        Endorsement {ancestors=List.copyOf(ancestors);}
        Endorsement(Decoded acknowledgement,Owned owned,Optional<ParentEndorsement> parent){this(acknowledgement,owned,parent,List.of());}
    }
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
        if(name.startsWith("ancestor-") && NAMES.contains(name))return name.endsWith("-ack.gsr")?2048:16384;
        return switch(name) {
            case PLAN,"selector.gsr" -> 4096;
            case "certificate.gsr","statement.gsr",PARENT_STATEMENT -> 16384;
            case "catalog.gsr" -> 2*1024*1024;
            case IMAGE -> MembershipApplicationImage.MAXIMUM;
            case ACK,PARENT_ACK -> 2048;
            case RETIREMENT,RETIREMENT_NEXT -> RETIREMENT_MAXIMUM;
            default -> throw new IllegalArgumentException("unknown applied-end file");
        };
    }
    private void snapshot()throws IOException {
        AdmissionPaths.recheck(binding);files.clear();exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);directoryKey=exists?key(path):null;
        if(!exists)return;
        long metadata=0;
        for(String name:children(path,NAMES.size())) {
            require(NAMES.contains(name),"applied-end inventory");byte[] bytes=AdmissionPaths.read(path.resolve(name),limit(name));
            files.put(name,inspect(path.resolve(name),bytes.length,hash(bytes)));if(!name.equals(IMAGE))metadata+=bytes.length;
        }
        require(!files.containsKey(RETIREMENT) || !files.containsKey(RETIREMENT_NEXT),"competing applied-end retirement markers");
        require(metadata<=maximumMetadata,"applied-end journal capacity");
    }
    private void reserve() {
        if(imageLease==null)imageLease=resources.reserve(MembershipResources.Unit.APPLICATION,"applied-end",MembershipResources.Unit.APPLICATION.bytes);
    }
    void reserveCompletion(){require(!closed,"applied-end closed");reserve();}
    boolean completionReserved(){return imageLease!=null;}
    void releaseEmptyCompletion()throws IOException {
        check();require(!present(),"applied-end files still present");
        if(imageLease!=null){imageLease.close();imageLease=null;}
    }
    boolean present(){return exists;}
    boolean retirementPending(){return files.containsKey(RETIREMENT) || files.containsKey(RETIREMENT_NEXT);}
    void check()throws IOException {
        require(!closed,"applied-end closed");AdmissionPaths.recheck(binding);
        require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,"applied-end lost shared journal reservation");
        require(exists==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"applied-end directory presence changed");
        if(exists) {
            require(directoryKey.equals(key(path)) && children(path,NAMES.size()).equals(files.keySet()),"applied-end directory identity/inventory changed");
            for(var row:files.entrySet())require(row.getValue().equals(inspect(path.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"applied-end inode changed");
        }
    }
    private static SortedMap<String,byte[]> materialization(MembershipCheckpointPlan plan,Decoded originalSelector,MembershipIdentity identity) {
        return materialization(plan.catalog,plan.statement,plan.originalParent(),plan.additionalParents(),plan.originalCertificate(),plan.application.image(),originalSelector,identity);
    }
    private static SortedMap<String,byte[]> materialization(Decoded catalog,Decoded statement,MembershipCapsule.Anchor parent,List<MembershipCapsule.Anchor> ancestors,
            Decoded certificate,byte[] image,Decoded originalSelector,MembershipIdentity identity) {
        var selector=decode(originalSelector.bytes(),"records","SELECTOR");String root=(String)catalog.value().get("root");
        require(selector.value().get("root").equals(root) && selector.value().get("node").equals(identity.nodeId().value()),"applied-end original selector owner");
        var cut=object(catalog.value().get("cut"));var view=object(cut.get("view"));
        var registered=list(catalog.value().get("identities")).stream().map(MembershipFormat::object).map(MembershipContext::identity).toList();
        require(registered.contains(identity) && (nodes(view,"old").contains(identity.nodeId().value()) || nodes(view,"new").contains(identity.nodeId().value())),"applied-end next-authority identity");
        require(hash(image).equals(catalog.value().get("application")),"applied-end exact image");
        var ack=acknowledgement(statement,identity);
        var result=new TreeMap<String,byte[]>();result.put("selector.gsr",selector.bytes());result.put("certificate.gsr",certificate.bytes());
        result.put("catalog.gsr",catalog.bytes());result.put("statement.gsr",statement.bytes());result.put(IMAGE,image);result.put(ACK,ack.bytes());
        MembershipCheckpointPlan.parentStatement(statement,parent).ifPresent(bridge->{
            result.put(PARENT_STATEMENT,bridge.bytes());result.put(PARENT_ACK,acknowledgement(bridge,identity).bytes());
        });
        require(ancestors.size()<=5,"applied-end ancestor capacity");long prior=-1;
        for(int i=0;i<ancestors.size();i++) {
            var lower=ancestors.get(i);long index=number(lower.cut().get("index"));require(index>prior,"applied-end ordered distinct ancestors");prior=index;
            var bridge=MembershipCheckpointPlan.ancestorStatement(statement,parent,lower);
            result.put(ancestor(i,false),bridge.bytes());result.put(ancestor(i,true),acknowledgement(bridge,identity).bytes());
        }
        var inventory=new ArrayList<Map<String,Object>>();result.forEach((name,bytes)->inventory.add(Map.of("path",name,"sha256",hash(bytes),"bytes",(long)bytes.length)));
        result.put(PLAN,canonical(Map.of("schema","gse-v53-applied-end/1.3","root",root,"node",identity.nodeId().value(),"files",inventory),4096));
        for(var row:result.entrySet())require(row.getValue().length<=limit(row.getKey()),"applied-end member capacity");return result;
    }
    private static Decoded acknowledgement(Decoded statement,MembershipIdentity identity) {
        return decode(encode("records","CHECKPOINT_ACK",Map.of("root",statement.value().get("root"),"cut",statement.value().get("end"),"statement",statement.digest(),
                "voter",identity.nodeId().value(),"incarnation",identity.storageId().toString())),"records","CHECKPOINT_ACK");
    }
    private static Owned observation(Decoded ack,MembershipIdentity identity) {
        return new Owned(identity.nodeId().value(),identity.storageId(),ack.digest(),cutDigest(object(ack.value().get("cut"))));
    }
    private static Optional<ParentEndorsement> parentEndorsement(Map<String,byte[]> expected,MembershipIdentity identity) {
        if(!expected.containsKey(PARENT_STATEMENT))return Optional.empty();
        var ack=decode(expected.get(PARENT_ACK),"records","CHECKPOINT_ACK");
        return Optional.of(new ParentEndorsement(decode(expected.get(PARENT_STATEMENT),"records","CHECKPOINT"),ack,observation(ack,identity)));
    }
    private static List<ParentEndorsement> ancestorEndorsements(Map<String,byte[]> expected,MembershipIdentity identity) {
        var result=new ArrayList<ParentEndorsement>();
        for(int i=0;i<5 && expected.containsKey(ancestor(i,false));i++) {
            var ack=decode(expected.get(ancestor(i,true)),"records","CHECKPOINT_ACK");
            result.add(new ParentEndorsement(decode(expected.get(ancestor(i,false)),"records","CHECKPOINT"),ack,observation(ack,identity)));
        }
        return List.copyOf(result);
    }
    private static void sameEndorsement(ParentEndorsement wanted,ParentEndorsement actual) {
        require(Arrays.equals(wanted.statement().bytes(),actual.statement().bytes()) && Arrays.equals(wanted.acknowledgement().bytes(),actual.acknowledgement().bytes())
                && wanted.owned().equals(actual.owned()),"publication original parent endorsement");
    }
    void completed(MembershipCheckpointPlan plan,Decoded selector,MembershipIdentity identity,Endorsement endorsement)throws IOException {
        check();require(!retirementPending(),"applied-end retirement pending");var expected=materialization(plan,selector,identity);
        require(exists && files.keySet().equals(expected.keySet()),"publication requires complete applied end");
        for(var row:expected.entrySet())require(files.get(row.getKey()).bytes()==row.getValue().length && files.get(row.getKey()).digest().equals(hash(row.getValue())),"publication differs from original applied end");
        var ack=decode(expected.get(ACK),"records","CHECKPOINT_ACK");
        require(Arrays.equals(ack.bytes(),endorsement.acknowledgement().bytes()) && endorsement.owned().equals(observation(ack,identity)),"publication original local end observation");
        var parent=parentEndorsement(expected,identity);require(parent.isPresent()==endorsement.parent().isPresent(),"publication original parent endorsement presence");
        if(parent.isPresent()) {
            sameEndorsement(parent.orElseThrow(),endorsement.parent().orElseThrow());
        }
        var ancestors=ancestorEndorsements(expected,identity);require(ancestors.size()==endorsement.ancestors().size(),"publication local ancestor observations");
        for(int i=0;i<ancestors.size();i++)sameEndorsement(ancestors.get(i),endorsement.ancestors().get(i));
    }
    /** The durable covering generation is authority; PLAN is kept until all listed members are gone. */
    void retireCovered(MembershipCapsule capsule,Map<String,byte[]> images,MembershipCapsule.Anchor parent,List<MembershipCapsule.Anchor> ancestors,MembershipPendingAccept.Vote vote,MembershipIdentity identity,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        check();guard.check();require(!retirementPending(),"applied-end retirement pending");var cap=capsule.packet.capsule().value();var last=object(list(cap.get("items")).getLast());
        var expected=materialization(capsule.context.record((String)cap.get("catalog"),"CATALOG"),capsule.context.record((String)last.get("statement"),"CHECKPOINT"),
                parent,ancestors,vote.certificate(),images.get(cap.get("application")),vote.selector(),identity);
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
        check();guard.check();require(!retirementPending(),"applied-end retirement pending");var expected=materialization(plan,selector,identity);long metadata=0;
        for(var row:expected.entrySet())if(!row.getKey().equals(IMAGE))metadata+=row.getValue().length;
        require(metadata<=maximumMetadata,"applied-end completion journal capacity");
        validateOriginal(expected,files);
        reserve();event("APPLY_VALIDATED",guard,cut);
        if(!exists){Files.createDirectory(path);snapshot();event("APPLY_DIRECTORY_CREATED",guard,cut);}
        complete(PLAN,expected.get(PLAN),"APPLY_PLAN",guard,cut);
        for(String name:List.of("selector.gsr","certificate.gsr","catalog.gsr","statement.gsr"))complete(name,expected.get(name),"APPLY_METADATA",guard,cut);
        if(expected.containsKey(PARENT_STATEMENT))complete(PARENT_STATEMENT,expected.get(PARENT_STATEMENT),"APPLY_PARENT_STATEMENT",guard,cut);
        for(int i=0;i<5 && expected.containsKey(ancestor(i,false));i++)complete(ancestor(i,false),expected.get(ancestor(i,false)),"APPLY_ANCESTOR_"+i+"_STATEMENT",guard,cut);
        complete(IMAGE,expected.get(IMAGE),"APPLY_IMAGE",guard,cut);
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(path.getParent());event("APPLY_END_FORCED",guard,cut);
        complete(ACK,expected.get(ACK),"APPLY_ACK",guard,cut);
        if(expected.containsKey(PARENT_ACK))complete(PARENT_ACK,expected.get(PARENT_ACK),"APPLY_PARENT_ACK",guard,cut);
        for(int i=0;i<5 && expected.containsKey(ancestor(i,true));i++)complete(ancestor(i,true),expected.get(ancestor(i,true)),"APPLY_ANCESTOR_"+i+"_ACK",guard,cut);
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(path.getParent());event("APPLY_ACK_DIRECTORY_FORCED",guard,cut);
        event("APPLY_BEFORE_RETURN",guard,cut);
        var ack=decode(expected.get(ACK),"records","CHECKPOINT_ACK");
        return new Endorsement(ack,observation(ack,identity),parentEndorsement(expected,identity),ancestorEndorsements(expected,identity));
    }
    /** Validate a saved original inventory, including partial members and ACK ordering. */
    private static void validateOriginal(Map<String,byte[]> expected,Map<String,FileIdentity> original) {
        for(var row:original.entrySet()) {
            byte[] full=expected.get(row.getKey());var found=row.getValue();
            require(full!=null && found.bytes()>=0 && found.bytes()<=full.length
                    && found.digest().equals(hash(Arrays.copyOf(full,Math.toIntExact(found.bytes())))),"applied-end requires exact original plan");
        }
        // An ACK (even a torn one) can only follow a complete exact forced end.
        var ackNames=new ArrayList<>(List.of(ACK));if(expected.containsKey(PARENT_ACK))ackNames.add(PARENT_ACK);
        for(int i=0;i<5 && expected.containsKey(ancestor(i,true));i++)ackNames.add(ancestor(i,true));
        if(ackNames.stream().anyMatch(original::containsKey))for(var row:expected.entrySet())if(!ackNames.contains(row.getKey()))
            require(original.containsKey(row.getKey()) && original.get(row.getKey()).bytes()==row.getValue().length
                    && original.get(row.getKey()).digest().equals(hash(row.getValue())),"applied-end ACK without complete original end");
        for(int i=1;i<ackNames.size();i++)if(original.containsKey(ackNames.get(i)))for(int j=0;j<i;j++) {
            String name=ackNames.get(j);require(original.containsKey(name) && original.get(name).bytes()==expected.get(name).length
                    && original.get(name).digest().equals(hash(expected.get(name))),"ancestor ACK without preceding complete ACK");
        }
    }
    private static byte[] retirementBytes(Map<String,byte[]> expected,Decoded selector,MembershipIdentity identity,
            Map<String,Object> authority,Map<String,FileIdentity> original) {
        var inventory=new ArrayList<Map<String,Object>>();
        new TreeMap<>(original).forEach((name,file)->inventory.add(Map.of("path",name,"type","file","bytes",file.bytes(),"sha256",file.digest())));
        byte[] body=canonical(Map.of("schema","gse-v53-applied-end-retirement/1.3","root",selector.value().get("root"),
                "node",identity.nodeId().value(),"storage",identity.storageId().toString(),"selector",selector.digest(),
                "plan",hash(expected.get(PLAN)),"authority",authority,"files",inventory),RETIREMENT_MAXIMUM-HEADER);
        var output=ByteBuffer.allocate(HEADER+body.length);
        output.putInt(RETIREMENT_MAGIC).putShort((short)1).putShort((short)3).putInt(0).putInt(body.length);
        output.put(sha(Arrays.copyOf(output.array(),16),body)).put(body);return output.array();
    }
    /** Only the active name may authorize deletion; a damaged active marker is never reconstructed. */
    private static Map<String,FileIdentity> retirementOriginal(byte[] bytes) {
        require(bytes.length>=HEADER && bytes.length<=RETIREMENT_MAXIMUM,"applied-end retirement framing");var input=ByteBuffer.wrap(bytes);
        require(input.getInt()==RETIREMENT_MAGIC && input.getShort()==1 && input.getShort()==3 && input.getInt()==0,"applied-end retirement version/flags");
        int length=input.getInt();require(length>0 && length==bytes.length-HEADER,"applied-end retirement length");
        byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),body)),"applied-end retirement checksum");
        var value=object(parse(body,RETIREMENT_MAXIMUM-HEADER));
        require(Arrays.equals(body,canonical(value,RETIREMENT_MAXIMUM-HEADER)),"applied-end retirement canonical body");
        var result=new TreeMap<String,FileIdentity>();String previous=null;
        for(Object item:list(value.get("files"))) {
            var row=object(item);require(row.keySet().equals(Set.of("path","type","bytes","sha256")) && row.get("path") instanceof String,"applied-end retirement inventory fields");
            String name=(String)row.get("path");require(NAMES.contains(name) && !name.equals(RETIREMENT) && !name.equals(RETIREMENT_NEXT)
                    && "file".equals(row.get("type")) && (previous==null || previous.compareTo(name)<0),"applied-end retirement ordered original inventory");
            long size=number(row.get("bytes"));require(size>=0 && size<=limit(name),"applied-end retirement original member capacity");checkType(row.get("sha256"),"hash");
            result.put(name,new FileIdentity(null,size,(String)row.get("sha256")));previous=name;
        }
        require(result.size()<=NAMES.size()-2,"applied-end retirement original inventory capacity");return result;
    }
    /**
     * Discard only private derived staging, never its original vote/source/generation.
     * The guard must bind the higher installed selection, unchanged old certified
     * entry and old source before admission and at every callback. It must keep
     * that exact durable cleanup authority valid during recovery without returning
     * an old ACK or imposing the old promise's voting fence.
     */
    void retireSuperseded(MembershipCheckpointPlan plan,Decoded oldSelector,MembershipIdentity identity,Map<String,Object> authority,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        check();guard.check();var expected=materialization(plan,oldSelector,identity);
        var bound=object(parse(canonical(authority,RETIREMENT_MAXIMUM-HEADER),RETIREMENT_MAXIMUM-HEADER));
        require(!bound.isEmpty(),"applied-end retirement requires explicit authority");
        if(!exists) {if(imageLease!=null){imageLease.close();imageLease=null;}return;}
        Map<String,FileIdentity> original;byte[] active=null;
        if(files.containsKey(RETIREMENT)) {
            active=AdmissionPaths.read(path.resolve(RETIREMENT),RETIREMENT_MAXIMUM);original=retirementOriginal(active);
        }else {
            original=new TreeMap<>(files);original.remove(RETIREMENT_NEXT);
        }
        // Validate all declared original bytes even after deletion; the remaining
        // files are only a subset, never the source for a replacement inventory.
        validateOriginal(expected,original);byte[] marker=retirementBytes(expected,oldSelector,identity,bound,original);
        if(active!=null)require(Arrays.equals(active,marker),"applied-end retirement authority/plan changed");
        else if(files.containsKey(RETIREMENT_NEXT))require(prefix(AdmissionPaths.read(path.resolve(RETIREMENT_NEXT),RETIREMENT_MAXIMUM),marker),"applied-end retirement requires exact original candidate");
        long metadata=marker.length;
        for(var row:original.entrySet())if(!row.getKey().equals(IMAGE))metadata=Math.addExact(metadata,row.getValue().bytes());
        require(metadata<=maximumMetadata,"applied-end retirement journal capacity");
        for(var row:files.entrySet())if(!row.getKey().equals(RETIREMENT) && !row.getKey().equals(RETIREMENT_NEXT)) {
            var declared=original.get(row.getKey());require(declared!=null && declared.bytes()==row.getValue().bytes()
                    && declared.digest().equals(row.getValue().digest()),"applied-end retirement changed/unlisted remaining member");
        }
        event("SUPERSEDED_END_VALIDATED",guard,cut);
        if(active==null) {
            complete(RETIREMENT_NEXT,marker,"SUPERSEDED_END_RETIREMENT",guard,cut);
            AdmissionPaths.forceDirectory(path);event("SUPERSEDED_END_RETIREMENT_PARENT_FORCED",guard,cut);
            require(!Files.exists(path.resolve(RETIREMENT),LinkOption.NOFOLLOW_LINKS),"applied-end retirement active target exists");
            var candidate=files.get(RETIREMENT_NEXT);
            Files.move(path.resolve(RETIREMENT_NEXT),path.resolve(RETIREMENT),StandardCopyOption.ATOMIC_MOVE);
            files.remove(RETIREMENT_NEXT);files.put(RETIREMENT,candidate);event("SUPERSEDED_END_RETIREMENT_RENAMED",guard,cut);
        }else {
            try(var channel=FileChannel.open(path.resolve(RETIREMENT),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
            event("SUPERSEDED_END_RETIREMENT_RESEALED",guard,cut);
        }
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(path.getParent());event("SUPERSEDED_END_AUTHORITY_FORCED",guard,cut);
        var names=new ArrayList<>(files.keySet());names.remove(RETIREMENT);names.remove(PLAN);if(files.containsKey(PLAN))names.add(PLAN);
        for(String name:names) {
            event("SUPERSEDED_END_BEFORE_DELETE",guard,cut);Files.delete(path.resolve(name));files.remove(name);
            AdmissionPaths.forceDirectory(path);event("SUPERSEDED_END_FILE_DELETED",guard,cut);
        }
        event("SUPERSEDED_END_BEFORE_RETIREMENT_DELETE",guard,cut);Files.delete(path.resolve(RETIREMENT));files.remove(RETIREMENT);
        AdmissionPaths.forceDirectory(path);event("SUPERSEDED_END_RETIREMENT_DELETED",guard,cut);
        event("SUPERSEDED_END_BEFORE_DIRECTORY_DELETE",guard,cut);Files.delete(path);exists=false;directoryKey=null;
        AdmissionPaths.forceDirectory(path.getParent());event("SUPERSEDED_END_DIRECTORY_DELETED",guard,cut);
        if(imageLease!=null){imageLease.close();imageLease=null;}
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
        var names=new TreeSet<>(files.keySet());names.add(changed);require(children(path,NAMES.size()).equals(names),"applied-end inventory changed while writing");
        for(var row:files.entrySet())if(!row.getKey().equals(changed))
            require(row.getValue().equals(inspect(path.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"applied-end prior inode changed while writing");
        files.put(changed,inspect(path.resolve(changed),expected.length,hash(expected)));
    }
    private static boolean prefix(byte[] actual,byte[] expected){return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));}
    @Override public void close(){if(imageLease!=null){imageLease.close();imageLease=null;}closed=true;}
}
