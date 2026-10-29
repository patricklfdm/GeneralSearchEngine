package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Retain a complete certified CANCEL under the original prepared learner owner.
 * This consumes the receiving slot, never a voting generation or deletion grant.
 * A partial transaction blocks further acquisition; only exact original recovery
 * may finish it. Closing releases leases, but never removes cancellation evidence. */
final class MembershipLearnerCancellation implements AutoCloseable {
    static final String PLAN="cancellation.json",NEXT="cancellation.next.json",SOURCE="source";
    static final int MAXIMUM=64*1024;
    private final MembershipLearnerHead head;
    private final MembershipLearnerStore store;
    private final MembershipLearnerPlan summary;
    private final MembershipBallotAllocator.Cut cut;
    private final Path directory,staging,destination;
    private final byte[] plan;
    private final Map<String,Object> value,binding,stagingBinding;
    private final Map<String,FileIdentity> metadata=new TreeMap<>();
    private final Map<String,MembershipReceiveFile.Retained> retained=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private Object directoryKey;
    private boolean closed,failed,complete;
    private Map<String,Object> terminal;

    static Path directory(MembershipLearnerPlan plan) {
        return plan.request().operationDirectory().resolveSibling(".gse-v53-learner-cancel-"+plan.planDigest());
    }
    static MembershipLearnerStore store(MembershipLearnerHead head)throws IOException {
        return head instanceof MembershipLearnerMaterialization.PreparedGeneration prepared?prepared.store():
                ((MembershipLearnerMaterialization.CurrentHead)head).store();
    }
    static void requireActive(MembershipLearnerHead head)throws IOException {store(head).requireActive();}
    static boolean present(MembershipLearnerPlan plan) {return Files.exists(AdmissionPaths.safe(directory(plan)),LinkOption.NOFOLLOW_LINKS);}
    static void requireActive(MembershipLearnerPlan plan)throws IOException {
        requireActive(directory(plan));
    }
    static void requireActive(Path directory) {
        require(!Files.exists(AdmissionPaths.safe(directory),LinkOption.NOFOLLOW_LINKS),"learner cancellation requires original recovery; preparation stopped");
    }
    private static Map<String,Object> anchor(MembershipCapsule capsule) {
        return Map.of("source",hash(capsule.packet.bytes()),"cut",capsule.context.cut,
                "catalog",capsule.terminal().catalog(),"application",capsule.terminal().application());
    }
    static Map<String,Object> cancellation(MembershipLearnerHead head,MembershipFloor.Copy copy)throws IOException {
        head.check();copy.check();MembershipLearnerProgressAccess.original(copy.capsule.context,head.request(),copy.owner);
        MembershipLearnerSource.successor(head.source(),copy);
        var row=MembershipLearnerProgressAccess.operation(copy.capsule.context,head.request().identity());
        require(row.get("phase").equals("CANCELLED"),"learner requires certified CANCEL, not timeout or nonterminal progress");
        return row;
    }
    private MembershipLearnerCancellation(MembershipLearnerHead head,byte[] plan,MembershipBallotAllocator.Cut cut)throws IOException {
        this.head=head;this.store=store(head);summary=store.summary();this.cut=Objects.requireNonNull(cut);this.plan=plan.clone();
        value=object(parse(plan,MAXIMUM));require(Arrays.equals(plan,canonical(value,MAXIMUM)),"learner cancellation canonical plan");
        require(value.keySet().equals(Set.of("schema","plan","request","learner","anchor","peer","path","staging","sourceKey","files"))
                && value.get("schema").equals("gse-v53-learner-cancellation/1.3") && value.get("plan").equals(summary.planDigest())
                && value.get("request").equals(MembershipLearnerDiscovery.request(head.request().change()))
                && value.get("learner").equals(MembershipBootstrapSeed.identity(head.request().identity()))
                && value.get("anchor").equals(anchor(head.source())),"learner cancellation original prepared owner");
        require(MembershipLearnerSlot.METADATA_MAXIMUM+2L*MAXIMUM<=MembershipResources.Unit.MISC.bytes,"learner cancellation metadata capacity");
        binding=MembershipLearnerAdmissionPlan.binding(object(value.get("path")));
        stagingBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("staging")));
        directory=directory(summary);staging=MembershipLearnerAdmissionPlan.path(stagingBinding);destination=directory.resolve(SOURCE);
        require(directory.equals(MembershipLearnerAdmissionPlan.path(binding)),"learner cancellation fixed path");
        head.requireDisjoint(directory,staging);AdmissionPaths.recheck(binding);AdmissionPaths.recheck(stagingBinding);
        var rows=list(value.get("files"));require(!rows.isEmpty() && rows.size()<=32,"learner cancellation inventory capacity");
        String previous=null;long metadataBytes=0;int images=0;
        for(Object item:rows) {
            var row=object(item);String name=(String)row.get("path");
            require(row.keySet().equals(Set.of("path","size","sha256","key")) && name.matches("[a-z0-9-]+\\.(gsr|gscp|image|json)")
                    && (previous==null || previous.compareTo(name)<0),"learner cancellation inventory order/path");previous=name;
            MembershipValidation.digest((String)row.get("sha256"));
            require(row.get("key") instanceof String && !((String)row.get("key")).isBlank() && ((String)row.get("key")).length()<=4096
                    && number(row.get("size"))>0 && number(row.get("size"))<=MembershipGenerationFiles.limit(name),"learner cancellation member capacity");
            if(name.endsWith(".image"))images++;else metadataBytes=Math.addExact(metadataBytes,number(row.get("size")));
        }
        require(metadataBytes<=MembershipResources.Unit.LEARNER.bytes && images<=MembershipResources.Unit.APPLICATION.count,"learner cancellation resource envelope");
    }
    static MembershipLearnerCancellation install(MembershipLearnerHead head,MembershipSourceReceive receiver,
            MembershipFloor.Copy copy,MembershipBallotAllocator.Cut cut)throws IOException {
        requireActive(head);cancellation(head,copy);receiver.requireResources(head.resources());
        Path staging=receiver.completeLearnerDirectory(copy);var summary=store(head).summary();Path directory=directory(summary);
        var rows=new ArrayList<Map<String,Object>>();
        for(String name:new TreeSet<>(copy.fileNames())) {
            byte[] bytes=copy.fileBytes(name);var identity=inspect(staging.resolve(name),bytes.length,hash(bytes));
            rows.add(Map.of("path",name,"size",(long)bytes.length,"sha256",hash(bytes),"key",identity.key().toString()));
        }
        byte[] plan=canonical(Map.of("schema","gse-v53-learner-cancellation/1.3","plan",summary.planDigest(),
                "request",MembershipLearnerDiscovery.request(head.request().change()),"learner",MembershipBootstrapSeed.identity(head.request().identity()),
                "anchor",anchor(head.source()),"peer",MembershipBootstrapSeed.identity(copy.owner),"path",AdmissionPaths.binding(directory),
                "staging",AdmissionPaths.binding(staging),"sourceKey",key(staging).toString(),"files",rows),MAXIMUM);
        var result=new MembershipLearnerCancellation(head,plan,cut);
        try {
            AdmissionPaths.absent(directory);result.validate();result.store.attachCancellation(result);
            result.retained.putAll(receiver.detachLearner(copy));
            Files.createDirectory(directory);result.directoryKey=key(directory);AdmissionPaths.forceDirectory(directory.getParent());result.point("LEARNER_CANCEL_DIRECTORY_FORCED");
            result.writePlan();result.finish();return result;
        }catch(IOException|RuntimeException|Error error){result.failed=true;try{result.close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    static MembershipLearnerCancellation resume(MembershipLearnerHead head,MembershipBallotAllocator.Cut cut)throws IOException {
        var summary=store(head).summary();Path directory=AdmissionPaths.safe(directory(summary));
        var names=children(directory,3);require(Set.of(PLAN,NEXT,SOURCE).containsAll(names) && (names.contains(PLAN)||names.contains(NEXT)),"learner cancellation original plan missing");
        byte[] bytes=AdmissionPaths.read(directory.resolve(names.contains(PLAN)?PLAN:NEXT),MAXIMUM);
        if(names.contains(PLAN)&&names.contains(NEXT))AdmissionPaths.exact(directory.resolve(NEXT),bytes);
        var result=new MembershipLearnerCancellation(head,bytes,cut);
        try {
            result.directoryKey=key(directory);
            for(String name:List.of(PLAN,NEXT))if(names.contains(name))result.remember(name,bytes);
            result.reserve();result.validate();result.store.attachCancellation(result);result.finish();return result;
        }catch(IOException|RuntimeException|Error error){result.failed=true;try{result.close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private void reserve()throws IOException {
        long bytes=0;var resources=head.resources();
        for(Object item:list(value.get("files"))) {
            var row=object(item);String name=(String)row.get("path");
            if(name.endsWith(".image"))leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"cancel:"+name,number(row.get("size"))));
            else bytes=Math.addExact(bytes,number(row.get("size")));
        }
        leases.add(resources.reserve(MembershipResources.Unit.LEARNER,"learner-cancellation",bytes));
    }
    private Path location()throws IOException {
        AdmissionPaths.recheck(binding);AdmissionPaths.recheck(stagingBinding);
        boolean a=Files.exists(staging,LinkOption.NOFOLLOW_LINKS),b=Files.exists(destination,LinkOption.NOFOLLOW_LINKS);
        require(a!=b,"learner cancellation missing/duplicate original source");Path location=a?staging:destination;
        require(key(location).toString().equals(value.get("sourceKey")),"learner cancellation source replaced");
        var names=new TreeSet<String>();
        for(Object item:list(value.get("files"))) {
            var row=object(item);String name=(String)row.get("path");names.add(name);
            require(inspect(location.resolve(name),number(row.get("size")),(String)row.get("sha256")).key().toString().equals(row.get("key")),"learner cancellation member replaced");
        }
        require(children(location,32).equals(names),"learner cancellation original inventory changed");return location;
    }
    private void check()throws IOException {
        require(!closed && !failed,"learner cancellation owner closed/failed");head.check();location();
        if(directoryKey!=null) {
            require(directoryKey.equals(key(directory)),"learner cancellation directory replaced");var names=new TreeSet<>(metadata.keySet());
            if(Files.exists(destination,LinkOption.NOFOLLOW_LINKS))names.add(SOURCE);
            require(children(directory,3).equals(names),"learner cancellation metadata inventory changed");
            for(var row:metadata.entrySet())require(row.getValue().equals(inspect(directory.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),"learner cancellation metadata replaced");
        }
    }
    private void validate()throws IOException {
        check();Path source=location();var files=new TreeMap<String,byte[]>();
        for(Object item:list(value.get("files"))) {var row=object(item);files.put((String)row.get("path"),AdmissionPaths.read(source.resolve((String)row.get("path")),Math.toIntExact(number(row.get("size")))));}
        var packet=MembershipSourcePacket.decode(Objects.requireNonNull(files.get("source.gscp")));var images=new TreeMap<String,byte[]>();
        for(String digest:packet.images().keySet())images.put(digest,files.get(digest+".image"));
        var original=head.source();var root=decode(original.packet.objectBytes(original.context.recordRootDigest()),"records","ROOT");
        var token=new Stored(this,files);MembershipCapsule capsule;
        try{capsule=MembershipCapsule.verifyStored(root,packet,images,token);}finally{token.active=false;}
        var peer=MembershipContext.identity(object(value.get("peer")));
        MembershipFloor.Copy.validateMaterialization(decode(files.get("generation.gsr"),"records","GENERATION"),capsule,peer,files);
        MembershipLearnerProgressAccess.original(capsule.context,head.request(),peer);
        MembershipLearnerSource.successor(original,capsule,files.getOrDefault("ancestry.gsr",new byte[0]));
        var row=MembershipLearnerProgressAccess.operation(capsule.context,head.request().identity());
        require(row.get("phase").equals("CANCELLED"),"learner cancellation original terminal proof missing");terminal=row;check();
    }
    static final class Stored implements MembershipCapsule.StoredCopy {
        private final MembershipLearnerCancellation owner;private final Map<String,byte[]> files;private boolean active=true;
        private Stored(MembershipLearnerCancellation owner,Map<String,byte[]> files){this.owner=owner;this.files=files;}
        @Override public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            require(active,"learner cancellation stored verification expired");owner.check();
            require(Arrays.equals(root.bytes(),owner.head.source().packet.objectBytes(owner.head.source().context.recordRootDigest()))
                    && Arrays.equals(packet.bytes(),files.get("source.gscp")),"learner cancellation stored originals");
        }
        @Override public byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        @Override public Optional<byte[]> coverage(){return Optional.ofNullable(files.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        @Override public Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
    private void remember(String name,byte[] bytes)throws IOException {metadata.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));}
    private void point(String event)throws IOException {check();cut.at(event);check();}
    private void force(Path path)throws IOException {
        check();try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
    }
    private void writePlan()throws IOException {
        check();AdmissionPaths.absent(directory.resolve(NEXT));
        try(var channel=FileChannel.open(directory.resolve(NEXT),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            remember(NEXT,new byte[0]);point("LEARNER_CANCEL_PLAN_CREATED");int half=plan.length/2;
            AdmissionPaths.write(channel,Arrays.copyOf(plan,half));remember(NEXT,Arrays.copyOf(plan,half));point("LEARNER_CANCEL_PLAN_PREFIX_WRITTEN");
            AdmissionPaths.write(channel,Arrays.copyOfRange(plan,half,plan.length));remember(NEXT,plan);point("LEARNER_CANCEL_PLAN_WRITTEN");
            channel.force(true);point("LEARNER_CANCEL_PLAN_FORCED");AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_PLAN_PARENT_FORCED");
        }
    }
    private void finish()throws IOException {
        validate();
        if(!metadata.containsKey(PLAN)) {
            force(directory.resolve(NEXT));AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_RESEAL_FORCED");
            Files.move(directory.resolve(NEXT),directory.resolve(PLAN),StandardCopyOption.ATOMIC_MOVE);metadata.put(PLAN,metadata.remove(NEXT));point("LEARNER_CANCEL_PLAN_RENAMED");
        }
        force(directory.resolve(PLAN));AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_ACTIVE_PLAN_FORCED");
        if(location().equals(staging)) {
            Files.move(staging,destination,StandardCopyOption.ATOMIC_MOVE);point("LEARNER_CANCEL_SOURCE_MOVED");
        }
        // A complete write observed before death still requires its original
        // force on recovery; revalidate before any such write/rename.
        for(Object item:list(value.get("files"))){force(destination.resolve((String)object(item).get("path")));point("LEARNER_CANCEL_SOURCE_MEMBER_FORCED");}
        AdmissionPaths.forceDirectory(destination);AdmissionPaths.forceDirectory(directory);AdmissionPaths.forceDirectory(staging.getParent());
        point("LEARNER_CANCEL_SOURCE_PARENTS_FORCED");
        if(metadata.containsKey(NEXT)) {
            AdmissionPaths.exact(directory.resolve(NEXT),plan);Files.delete(directory.resolve(NEXT));metadata.remove(NEXT);
            AdmissionPaths.forceDirectory(directory);point("LEARNER_CANCEL_REDUNDANT_PLAN_REMOVED");
        }
        validate();point("LEARNER_CANCEL_BEFORE_RETURN");complete=true;
    }
    Map<String,Object> result()throws IOException {
        check();require(complete,"learner cancellation not forced");return object(parse(canonical(terminal,16384),16384));
    }
    boolean closed(){return closed;}
    @Override public void close()throws IOException {
        if(closed)return;closed=true;var children=new ArrayList<AutoCloseable>();children.addAll(retained.values());children.addAll(leases);
        MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
    }
}
