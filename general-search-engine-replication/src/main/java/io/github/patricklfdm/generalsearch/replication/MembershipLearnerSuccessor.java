package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Retains an original received successor under the parent learner owner. A
 * selected successor is certified nonvoting state, not a typed READY or INTENT.
 * Originals remain owned until the parent closes; retirement is separate. */
final class MembershipLearnerSuccessor implements AutoCloseable {
    static final String LOCK="successor.lock",PLAN="install.json",NEXT="install.next.json",SELECTED="selected.json",SOURCE="source";
    static final int MAXIMUM=256*1024;
    static final String HEAD="head.json",HEAD_NEXT="head.next.json";
    static final int HEAD_MAXIMUM=4096;
    private static final Set<String> MEMBERS=Set.of(LOCK,PLAN,NEXT,SELECTED,SOURCE,HEAD,HEAD_NEXT,MembershipLearnerRetirement.FILE);
    private final MembershipLearnerStore parent;
    private final MembershipBallotAllocator.Cut cut;
    private final Path directory,staging,destination;
    private final Map<String,Object> pathBinding,stagingBinding,value;
    private final byte[] plan,selector;
    private final Object directoryKey;
    private final Decoded generation;
    private final MembershipIdentity peer;
    private final Map<String,MembershipReceiveFile.Retained> received=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final Map<String,FileIdentity> metadata=new TreeMap<>();
    private MembershipOwnership lock;
    private MembershipLearnerMaterialization<?> typed;
    private MembershipResources.Lease typedImage;
    private Handoff handoff;
    private boolean closed,failed,selected;
    static Path directory(MembershipLearnerPlan summary) {
        return summary.request().operationDirectory().resolveSibling(".gse-v53-learner-successor-"+summary.planDigest());
    }
    static Path typedDirectory(MembershipLearnerPlan summary) {
        return summary.request().operationDirectory().resolveSibling(".gse-v53-learner-ready-"+summary.planDigest());
    }
    private MembershipLearnerSuccessor(MembershipLearnerStore parent,byte[] bytes,MembershipBallotAllocator.Cut cut)throws IOException {
        this.parent=parent;this.cut=cut;plan=bytes.clone();value=object(parse(plan,MAXIMUM));
        require(Arrays.equals(plan,canonical(value,MAXIMUM)) && value.keySet().equals(Set.of("schema","plan","previous","receipt","path","directoryKey",
                "staging","sourceKey","source","generation","files")) && value.get("schema").equals("gse-v53-learner-successor/1.3")
                && value.get("plan").equals(parent.summary().planDigest()),"learner successor original plan");
        directory=directory(parent.summary());pathBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("path")));
        require(directory.equals(MembershipLearnerAdmissionPlan.path(pathBinding)),"learner successor exact path");
        stagingBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("staging")));staging=MembershipLearnerAdmissionPlan.path(stagingBinding);
        destination=directory.resolve(SOURCE);AdmissionPaths.disjoint(List.of(directory,staging,parent.summary().request().replicaDirectory(),parent.summary().request().operationDirectory()));
        directoryKey=key(directory);require(directoryKey.toString().equals(text(value.get("directoryKey"))),"learner successor original directory");
        text(value.get("sourceKey"));require(value.get("receipt") instanceof String && ((String)value.get("receipt")).matches("[0-9a-f]{64}"),"learner successor receipt digest");
        peer=MembershipContext.identity(object(value.get("source")));require(value.get("source").equals(MembershipBootstrapSeed.identity(peer)),"learner successor source identity");
        generation=decode(MembershipBootstrapPlanData.unbase(value.get("generation"),65536),"records","GENERATION");
        var expected=new TreeMap<String,Map<String,Object>>();expected.put("generation.gsr",row("generation.gsr",generation.bytes()));long total=generation.size();
        for(Object raw:list(generation.value().get("files"))) {
            var item=object(raw);String name=(String)item.get("path");long size=number(item.get("size"));
            require(size>0 && size<=MembershipGenerationFiles.limit(name) && expected.putIfAbsent(name,item)==null,"learner successor original member");
            if(!name.endsWith(".image")){total=Math.addExact(total,size);require(total<=MembershipResources.Unit.GENERATION.bytes,"learner successor metadata capacity");}
        }
        var files=list(value.get("files"));require(files.size()==expected.size() && files.size()<=32,"learner successor file count");String previous=null;
        for(Object raw:files) {
            var item=object(raw);String name=(String)item.get("path");
            require(item.keySet().equals(Set.of("path","size","sha256","key")) && (previous==null || previous.compareTo(name)<0)
                    && Objects.equals(expected.get(name),Map.of("path",name,"size",item.get("size"),"sha256",item.get("sha256"))),"learner successor original inventory");
            text(item.get("key"));previous=name;
        }
        selector=canonical(Map.of("schema","gse-v53-learner-successor-selected/1.3","plan",hash(plan),"root",parent.summary().request().root().manifestDigest(),
                "identity",MembershipBootstrapSeed.identity(parent.summary().request().identity()),"generation",generation.digest(),"location",destination.toString()),16384);
        predecessor();
    }
    private static String text(Object value) {
        require(value instanceof String && !((String)value).isBlank() && ((String)value).getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=4096,
                "learner successor inode text");return (String)value;
    }
    private static Map<String,Object> row(String name,byte[] bytes){return Map.of("path",name,"size",(long)bytes.length,"sha256",hash(bytes));}
    private static Map<String,Object> anchor(MembershipCapsule capsule) {
        var a=capsule.terminal();return Map.of("source",hash(capsule.packet.bytes()),"cut",a.cut(),"catalog",a.catalog(),"application",a.application());
    }
    private void predecessor()throws IOException {
        require(value.get("previous").equals(parent.originalAnchor()),"learner successor predecessor changed");
    }
    static MembershipLearnerSuccessor install(MembershipLearnerMaterialization.PreparedGeneration prepared,MembershipSourceReceive receiver,
            MembershipFloor.Copy copy,MembershipBallotAllocator.Cut cut)throws IOException {
        prepared.check();var parent=prepared.store();parent.requireNewSuccessor();receiver.requireResources(parent.resources());copy.check();
        MembershipLearnerSource.successor(prepared.source(),copy);
        MembershipLearnerPrefixExport.originalReservation(copy.capsule.context,prepared.request(),copy.owner);
        Path staging=receiver.completeLearnerDirectory(copy),directory=directory(parent.summary());AdmissionPaths.absent(directory);
        prepared.requireDisjoint(directory,staging);
        AdmissionPaths.disjoint(List.of(directory,staging,parent.summary().request().replicaDirectory(),parent.summary().request().operationDirectory()));
        var files=new ArrayList<Map<String,Object>>();
        for(String name:new TreeSet<>(copy.fileNames())) {
            var file=new TreeMap<>(row(name,copy.fileBytes(name)));file.put("key",key(staging.resolve(name)).toString());files.add(file);
        }
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-learner-successor/1.3");value.put("plan",parent.summary().planDigest());
        value.put("previous",anchor(prepared.source()));value.put("receipt",prepared.receipt().digest());value.put("path",AdmissionPaths.binding(directory));
        value.put("staging",AdmissionPaths.binding(staging));value.put("sourceKey",key(staging).toString());value.put("source",MembershipBootstrapSeed.identity(copy.owner));
        value.put("generation",MembershipBootstrapPlanData.base(copy.generation.bytes()));value.put("files",files);
        // Bound metadata before creating a new path or detaching received bytes.
        value.put("directoryKey","x".repeat(4096));canonical(value,MAXIMUM);
        MembershipLearnerSuccessor result=null;
        try {
            Files.createDirectory(directory);value.put("directoryKey",key(directory).toString());
            result=new MembershipLearnerSuccessor(parent,canonical(value,MAXIMUM),cut);
            result.lock=MembershipOwnership.own(directory.resolve(LOCK),true);
            result.received.putAll(receiver.detachLearner(copy));parent.attachSuccessor(result);
            result.capture();result.check();AdmissionPaths.forceDirectory(directory.getParent());result.point("LEARNER_SUCCESSOR_DIRECTORY_FORCED");
            result.write(NEXT,result.plan,"LEARNER_SUCCESSOR_PLAN");result.finish(prepared);return result;
        }catch(IOException|RuntimeException|Error error) {
            if(result!=null){result.failed=true;if(!parent.ownsSuccessor(result))try{result.close();}catch(IOException cleanup){error.addSuppressed(cleanup);}}
            throw error;
        }
    }
    /** Parent reopen accounts even an unselected retained candidate before it
     * returns. It grants no capability until typed predecessor validation. */
    static MembershipLearnerSuccessor restore(MembershipLearnerStore parent,MembershipBallotAllocator.Cut cut)throws IOException {
        Path directory=directory(parent.summary());if(!Files.exists(AdmissionPaths.safe(directory),LinkOption.NOFOLLOW_LINKS))return null;
        var names=children(directory,8);require(names.contains(LOCK) && (names.contains(PLAN)||names.contains(NEXT))
                && MEMBERS.containsAll(names),"learner successor incomplete original inventory");
        var lock=MembershipOwnership.own(directory.resolve(LOCK),false);MembershipLearnerSuccessor result=null;
        try {
            byte[] bytes=AdmissionPaths.read(directory.resolve(names.contains(PLAN)?PLAN:NEXT),MAXIMUM);
            result=new MembershipLearnerSuccessor(parent,bytes,cut);result.lock=lock;result.capture();result.check();
            long metadata=0;var resources=parent.resources();
            for(var raw:list(result.value.get("files"))){var f=object(raw);if(!((String)f.get("path")).endsWith(".image"))metadata+=number(f.get("size"));}
            result.leases.add(resources.reserve(MembershipResources.Unit.GENERATION,"learner-successor",metadata));
            for(var raw:list(result.value.get("files"))){var f=object(raw);if(((String)f.get("path")).endsWith(".image"))
                result.leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"learner-successor:"+f.get("path"),number(f.get("size"))));}
            result.capsule();
            if(Files.exists(AdmissionPaths.safe(typedDirectory(parent.summary())),LinkOption.NOFOLLOW_LINKS))result.reserveTypedImage();
            if(names.contains(HEAD)||names.contains(HEAD_NEXT)) {
                require(names.contains(SELECTED) && result.metadata.get(SELECTED).bytes()==result.selector.length,"learner handoff requires complete source selection");
                var headBytes=AdmissionPaths.read(directory.resolve(names.contains(HEAD)?HEAD:HEAD_NEXT),HEAD_MAXIMUM);
                if(names.contains(HEAD)&&names.contains(HEAD_NEXT))AdmissionPaths.exact(directory.resolve(HEAD_NEXT),headBytes);
                result.handoff=result.new Handoff(headBytes);result.handoff.check();
            }
            return result;
        }catch(IOException|RuntimeException|Error error){try{if(result!=null)result.close();else lock.close();}catch(IOException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private Path locate()throws IOException {
        boolean before=Files.exists(staging,LinkOption.NOFOLLOW_LINKS),after=Files.exists(destination,LinkOption.NOFOLLOW_LINKS);
        require(before!=after,"learner successor requires original source location");Path location=before?staging:destination;
        if(before)AdmissionPaths.recheck(stagingBinding);
        require(text(value.get("sourceKey")).equals(key(location).toString()),"learner successor source directory replaced");
        var names=new TreeSet<String>();
        for(var raw:list(value.get("files"))) {
            var f=object(raw);String name=(String)f.get("path");names.add(name);
            require(f.get("key").equals(inspect(location.resolve(name),number(f.get("size")),(String)f.get("sha256")).key().toString()),"learner successor original source changed");
            if(received.containsKey(name))received.get(name).check(location.resolve(name));
        }
        require(children(location,32).equals(names),"learner successor source inventory");return location;
    }
    private void capture()throws IOException {
        var names=children(directory,8);require(names.contains(LOCK) && MEMBERS.containsAll(names),"learner successor inventory");
        for(String name:List.of(LOCK,PLAN,NEXT,SELECTED))if(names.contains(name)) {
            byte[] expected=name.equals(LOCK)?new byte[0]:name.equals(SELECTED)?selector:plan;
            byte[] bytes=AdmissionPaths.read(directory.resolve(name),expected.length);
            require(Arrays.equals(bytes,Arrays.copyOf(expected,bytes.length)) && (!(name.equals(PLAN) || name.equals(NEXT) && names.contains(PLAN)) || bytes.length==expected.length),"learner successor original metadata changed");
            metadata.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));
        }
        require(!names.contains(SELECTED) || names.contains(PLAN) && names.contains(SOURCE),"learner successor selector without complete plan/source");
        for(String name:List.of(HEAD,HEAD_NEXT,MembershipLearnerRetirement.FILE))if(names.contains(name)) {
            byte[] bytes=AdmissionPaths.read(directory.resolve(name),HEAD_MAXIMUM);metadata.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));
        }
    }
    private void check()throws IOException {
        require(!closed && !failed && lock!=null && lock.lock().isValid(),"learner successor owner closed or failed");predecessor();
        AdmissionPaths.recheck(pathBinding);require(directoryKey.equals(key(directory)),"learner successor directory replaced");Path source=locate();
        var names=new TreeSet<>(metadata.keySet());if(source.equals(destination))names.add(SOURCE);
        require(children(directory,8).equals(names),"learner successor live inventory changed");
        for(var f:metadata.entrySet())require(f.getValue().equals(inspect(directory.resolve(f.getKey()),f.getValue().bytes(),f.getValue().digest())),"learner successor metadata replaced");
    }
    private void point(String event)throws IOException{check();if(handoff!=null)handoff.checkFiles();cut.at(event);check();if(handoff!=null)handoff.checkFiles();}
    private void remember(String name,byte[] expected)throws IOException {
        byte[] bytes=AdmissionPaths.read(directory.resolve(name),expected.length);
        require(Arrays.equals(bytes,Arrays.copyOf(expected,bytes.length)),"learner successor writer changed originals");
        var before=metadata.get(name);var after=inspect(directory.resolve(name),bytes.length,hash(bytes));
        require(before==null || before.key().equals(after.key()),"learner successor writer inode changed");metadata.put(name,after);
    }
    private void write(String name,byte[] bytes,String event)throws IOException {
        check();boolean exists=metadata.containsKey(name);
        try(var channel=FileChannel.open(directory.resolve(name),exists?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            if(!exists){remember(name,bytes);point(event+"_CREATED");}
            int offset=Math.toIntExact(metadata.get(name).bytes());channel.position(offset);
            if(offset<bytes.length){int middle=offset+(bytes.length-offset)/2;
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,offset,middle));remember(name,bytes);point(event+"_PREFIX_WRITTEN");
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,middle,bytes.length));remember(name,bytes);point(event+"_WRITTEN");}
            channel.force(true);point(event+"_FORCED");AdmissionPaths.forceDirectory(directory);point(event+"_PARENT_FORCED");
        }
    }
    private void finish(MembershipLearnerMaterialization.PreparedGeneration prepared)throws IOException {
        prepared.check();require(prepared.store()==parent && value.get("receipt").equals(prepared.receipt().digest()),"learner successor original typed predecessor");
        prepared.requireDisjoint(directory,staging);
        try {
            MembershipResources.GenerationClaim claim=received.isEmpty()?null:received.get("source.gscp").prepareGeneration(locate().resolve("source.gscp"),"learner-successor");
            try(claim) {
                check();require(metadata.containsKey(PLAN) || metadata.containsKey(NEXT) && metadata.get(NEXT).bytes()==plan.length,"learner successor partial original plan");
                if(!metadata.containsKey(PLAN)) {
                    write(NEXT,plan,"LEARNER_SUCCESSOR_CANDIDATE");Files.move(directory.resolve(NEXT),directory.resolve(PLAN),StandardCopyOption.ATOMIC_MOVE);
                    metadata.put(PLAN,metadata.remove(NEXT));point("LEARNER_SUCCESSOR_PLAN_RENAMED");
                }
                write(PLAN,plan,"LEARNER_SUCCESSOR_ACTIVE");
                if(metadata.containsKey(NEXT)){check();Files.delete(directory.resolve(NEXT));metadata.remove(NEXT);AdmissionPaths.forceDirectory(directory);point("LEARNER_SUCCESSOR_REDUNDANT_FORCED");}
                if(locate().equals(staging)){check();Files.move(staging,destination,StandardCopyOption.ATOMIC_MOVE);point("LEARNER_SUCCESSOR_SOURCE_MOVED");}
                AdmissionPaths.forceDirectory(destination);
                if(Files.exists(staging.getParent(),LinkOption.NOFOLLOW_LINKS)){AdmissionPaths.recheck(stagingBinding);AdmissionPaths.forceDirectory(staging.getParent());}
                else require(metadata.containsKey(SELECTED) && metadata.get(SELECTED).bytes()==selector.length,"learner successor incomplete move lost original parent");
                AdmissionPaths.forceDirectory(directory);point("LEARNER_SUCCESSOR_SOURCE_PARENTS_FORCED");
                capsule();prepared.check();
                write(SELECTED,selector,"LEARNER_SUCCESSOR_SELECT");
                if(claim!=null){received.get("source.gscp").requireGenerationClaim(destination.resolve("source.gscp"),claim);claim.commit();}
                selected=true;point("LEARNER_SUCCESSOR_BEFORE_RETURN");
            }
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    View open(MembershipLearnerMaterialization.PreparedGeneration prepared)throws IOException {
        require(handoff==null || !metadata.containsKey(HEAD),"learner predecessor superseded by original handoff");
        prepared.requireDisjoint(directory,staging);
        if(!selected)finish(prepared);else {check();prepared.check();require(prepared.store()==parent,"learner successor foreign owner");}
        return new View(this,prepared);
    }
    /** A separate durable capability replaces dependence on the old typed HANDLE,
     * while original files stay retained and fully accounted for later retirement. */
    View promoted()throws IOException {
        check();require(handoff!=null && metadata.containsKey(HEAD),"learner original handoff not committed");
        try {handoff.seal(false);selected=true;return new View(this,null);}
        catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void retirePredecessor()throws IOException {
        try {
            check();require(handoff!=null && handoff.active && selected,"learner retirement requires forced head");
            handoff.check();parent.requirePredecessorClosed();
            if(!parent.retiring()) {
                require(!metadata.containsKey(HEAD_NEXT),"learner retirement redundant handoff");
                write(MembershipLearnerRetirement.FILE,parent.retirementBytes(),"LEARNER_RETIRE_DECISION");
                parent.beginRetirement();
            }
            finishRetirement();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** Reopened complete decisions are re-forced after current-source validation.
     * Missing old members alone never reach this method. */
    void finishRetirement()throws IOException {
        try {
            check();require(parent.retiring() && handoff!=null && metadata.containsKey(HEAD),"learner retirement original head missing");
            handoff.check();handoff.seal(false);selected=true;
            write(MembershipLearnerRetirement.FILE,parent.retirementBytes(),"LEARNER_RETIRE_DECISION");
            var remove=new ArrayList<>(parent.predecessorRemovalOrder());Path typed=MembershipLearnerMaterialization.directory(parent.summary());
            var paths=new ArrayList<>(typedPaths(true));paths.sort(Comparator.<String>comparingInt(n->n.equals(".")?0:n.split("/").length).reversed().thenComparing(n->n));
            for(String name:paths)remove.add(name.equals(".")?typed:typed.resolve(name));
            for(Path file:remove) {
                point("LEARNER_RETIRE_BEFORE_DELETE");
                if(Files.exists(file,LinkOption.NOFOLLOW_LINKS)){Files.delete(file);point("LEARNER_RETIRE_MEMBER_DELETED");}
                if(Files.exists(file.getParent(),LinkOption.NOFOLLOW_LINKS))AdmissionPaths.forceDirectory(file.getParent());
                point("LEARNER_RETIRE_MEMBER_PARENT_FORCED");
            }
            AdmissionPaths.forceDirectory(parent.summary().request().replicaDirectory());AdmissionPaths.forceDirectory(typed.getParent());
            point("LEARNER_RETIRE_PARENTS_FORCED");parent.releasePredecessor(this);point("LEARNER_RETIRE_RELEASED");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private View promote(MembershipLearnerMaterialization<?> current,MembershipLearnerMaterialization.PreparedGeneration previous)throws IOException {
        check();previous.check();require(current==typed && selected,"learner handoff foreign typed owner");
        current.receipt();var summary=parent.summary();
        var expected=canonical(Map.of("schema","gse-v53-learner-head/1.3","plan",summary.planDigest(),"installed",hash(plan),
                "source",hash(capsule().packet.bytes()),"generation",generation.digest(),"receipt",current.receipt().digest(),
                "previousFiles",fingerprints(MembershipLearnerMaterialization.directory(summary),true),
                "currentFiles",fingerprints(typedDirectory(summary),false)),HEAD_MAXIMUM);
        previous.check();current.receipt();
        try {
            if(handoff==null)handoff=new Handoff(expected);
            else require(Arrays.equals(expected,handoff.bytes),"learner handoff original decision changed");
            handoff.live=()->{previous.check();current.receipt();};
            handoff.check();handoff.seal(true);handoff.live=null;current.close();previous.closePredecessor();
            point("LEARNER_HEAD_BEFORE_RETURN");return new View(this,null);
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
        finally{if(handoff!=null)handoff.live=null;}
    }
    private static List<Map<String,String>> fingerprints(Path directory,boolean previous)throws IOException {
        return fingerprints(directory,previous,false);
    }
    private static SortedSet<String> typedPaths(boolean previous) {
        var paths=new TreeSet<>(List.of(".","preparation.lock","preparation.json","learner.gsr","backup"));
        if(previous)paths.add("prepared.json");for(String name:MembershipApplicationImage.MEMBERS)paths.add("backup/"+name);return paths;
    }
    private static List<Map<String,String>> fingerprints(Path directory,boolean previous,boolean remaining)throws IOException {
        AdmissionPaths.safe(directory);if(remaining && !Files.exists(directory,LinkOption.NOFOLLOW_LINKS))return List.of();
        var all=typedPaths(previous);var names=new TreeSet<>(all);names.removeIf(n->n.equals(".")||n.contains("/"));
        var actual=children(directory,6);
        require(remaining?names.containsAll(actual):actual.equals(names),"learner handoff exact typed inventory");
        if(actual.contains("backup")) {
            var backup=children(directory.resolve("backup"),3);
            require(remaining?new HashSet<>(MembershipApplicationImage.MEMBERS).containsAll(backup):backup.equals(new HashSet<>(MembershipApplicationImage.MEMBERS)),"learner handoff complete typed backup");
        }
        var result=new ArrayList<Map<String,String>>();
        for(String name:all) {
            Path path=name.equals(".")?directory:directory.resolve(name);Object value;
            if(remaining && !Files.exists(path,LinkOption.NOFOLLOW_LINKS))continue;
            if(name.equals(".") || name.equals("backup")) {
                require(Files.isDirectory(AdmissionPaths.safe(path),LinkOption.NOFOLLOW_LINKS),"learner handoff typed directory");
                value=Map.of("key",key(path).toString(),"directory",true);
            }else {
                int limit=name.startsWith("backup/")?MembershipApplicationImage.MAXIMUM:name.equals("preparation.json")?
                        (previous?MembershipLearnerMaterialization.MAXIMUM_PLAN:MembershipLearnerMaterialization.SUCCESSOR_PLAN):16384;
                byte[] bytes=AdmissionPaths.read(path,limit);value=Map.of("key",key(path).toString(),"bytes",(long)bytes.length,"sha256",hash(bytes));
            }
            result.add(Map.of("path",name,"sha256",hash(canonical(value,16384))));
        }
        return result;
    }
    private final class Handoff {
        private final byte[] bytes;
        private final Map<String,Object> record;
        private boolean active;
        private MembershipGenerationFiles.Guard live;
        Handoff(byte[] bytes) {
            this.bytes=bytes.clone();record=object(parse(bytes,HEAD_MAXIMUM));
            require(Arrays.equals(bytes,canonical(record,HEAD_MAXIMUM)) && record.keySet().equals(Set.of("schema","plan","installed","source","generation","receipt","previousFiles","currentFiles"))
                    && record.get("schema").equals("gse-v53-learner-head/1.3"),"learner original handoff shape");
        }
        void checkFiles()throws IOException {
            if(live!=null)live.check();
            var summary=parent.summary();
            var original=list(record.get("previousFiles")).stream().map(MembershipFormat::object).toList();
            require(original.stream().allMatch(r->r.keySet().equals(Set.of("path","sha256")) && r.get("sha256") instanceof String
                    && ((String)r.get("sha256")).matches("[0-9a-f]{64}")),"learner handoff predecessor fingerprint fields");
            require(original.stream().map(r->(String)r.get("path")).toList().equals(List.copyOf(typedPaths(true))),"learner handoff predecessor fingerprint paths");
            var remaining=fingerprints(MembershipLearnerMaterialization.directory(summary),true,parent.retiring());
            require((parent.retiring()?original.containsAll(remaining):original.equals(remaining))
                    && record.get("currentFiles").equals(fingerprints(typedDirectory(summary),false)),"learner handoff original typed members changed");
            if(live!=null)live.check();
        }
        void check()throws IOException {
            MembershipLearnerSuccessor.this.check();checkFiles();var summary=parent.summary();var source=capsule();
            require(record.get("plan").equals(summary.planDigest()) && record.get("installed").equals(hash(plan))
                    && record.get("source").equals(hash(source.packet.bytes())) && record.get("generation").equals(generation.digest()),"learner handoff original source binding");
            Path path=typedDirectory(summary);byte[] receipt=AdmissionPaths.read(path.resolve("learner.gsr"),16384);
            var decoded=decode(receipt,"records","LEARNER");long revision=number(object(object(decoded.value().get("receipt")).get("prepared")).get("revision"));
            require(record.get("receipt").equals(hash(receipt)) && Arrays.equals(receipt,MembershipLearnerPreparation.receiptBytes(source,summary.request(),revision).bytes()),
                    "learner handoff current receipt binding");
            var typedPlan=object(parse(AdmissionPaths.read(path.resolve("preparation.json"),MembershipLearnerMaterialization.SUCCESSOR_PLAN),MembershipLearnerMaterialization.SUCCESSOR_PLAN));
            require(typedPlan.get("schema").equals("gse-v53-successor-typed/1.3") && typedPlan.get("source").equals(record.get("source"))
                    && typedPlan.get("receipt").equals(record.get("receipt")) && typedPlan.get("plan").equals(summary.planDigest()),"learner handoff current typed plan");
            require(metadata.containsKey(SELECTED) && metadata.get(SELECTED).bytes()==selector.length,"learner handoff source not selected");
        }
        void seal(boolean candidate)throws IOException {
            check();
            if(!metadata.containsKey(HEAD)) {
                require(candidate,"learner original handoff not committed");
                write(HEAD_NEXT,bytes,"LEARNER_HEAD_CANDIDATE");
                Files.move(directory.resolve(HEAD_NEXT),directory.resolve(HEAD),StandardCopyOption.ATOMIC_MOVE);
                metadata.put(HEAD,metadata.remove(HEAD_NEXT));point("LEARNER_HEAD_RENAMED");
            }
            require(metadata.get(HEAD).bytes()==bytes.length && metadata.get(HEAD).digest().equals(hash(bytes)),"learner handoff active bytes differ");
            write(HEAD,bytes,"LEARNER_HEAD_ACTIVE");
            if(metadata.containsKey(HEAD_NEXT)) {
                require(metadata.get(HEAD_NEXT).bytes()==bytes.length && metadata.get(HEAD_NEXT).digest().equals(hash(bytes)),"learner handoff redundant bytes differ");
                Files.delete(directory.resolve(HEAD_NEXT));metadata.remove(HEAD_NEXT);AdmissionPaths.forceDirectory(directory);point("LEARNER_HEAD_REDUNDANT_FORCED");
            }
            check();active=true;
        }
    }
    static final class View {
        private final MembershipLearnerSuccessor owner;
        private final MembershipLearnerMaterialization.PreparedGeneration predecessor;
        private View(MembershipLearnerSuccessor owner,MembershipLearnerMaterialization.PreparedGeneration predecessor){this.owner=owner;this.predecessor=predecessor;}
        MembershipCapsule source()throws IOException {
            if(predecessor!=null)predecessor.check();
            else {require(owner.handoff!=null && owner.handoff.active,"learner handoff capability not forced");owner.handoff.check();}
            owner.check();require(owner.selected,"learner successor not selected");return owner.capsule();
        }
        MembershipLearnerStore store()throws IOException{source();return owner.parent;}
        byte[] originalImage(String digest,long size)throws IOException {
            var capsule=source();require(Objects.equals(capsule.packet.images().get(digest),size),"learner successor original image binding");
            byte[] bytes=AdmissionPaths.read(owner.destination.resolve(digest+".image"),Math.toIntExact(size));
            require(bytes.length==size && hash(bytes).equals(digest),"learner successor original image bytes");source();return bytes;
        }
        void requireTypedPaths(Path core,Path typed)throws IOException {
            source();
            if(predecessor!=null){predecessor.requireCorePath(core);predecessor.requireDisjoint(typed,owner.directory,owner.staging);}
            else {
                var value=object(parse(AdmissionPaths.read(typed.resolve("preparation.json"),MembershipLearnerMaterialization.SUCCESSOR_PLAN),MembershipLearnerMaterialization.SUCCESSOR_PLAN));
                var bound=MembershipLearnerAdmissionPlan.binding(object(value.get("materialization")));AdmissionPaths.recheck(bound);
                require(core.equals(MembershipLearnerAdmissionPlan.path(bound)),"learner successor changed reserved core path");
                var summary=owner.parent.summary();AdmissionPaths.disjoint(List.of(core,typed,owner.directory,owner.staging,MembershipLearnerMaterialization.directory(summary),summary.request().operationDirectory(),summary.request().replicaDirectory()));
            }
            require(typed.equals(typedDirectory(owner.parent.summary())),"learner successor typed path");
        }
        View promote(MembershipLearnerMaterialization<?> typed)throws IOException {
            source();require(predecessor!=null,"learner successor already promoted");return owner.promote(typed,predecessor);
        }
        void retirePredecessor()throws IOException {
            source();require(predecessor==null,"learner retirement requires promoted head");owner.retirePredecessor();
        }
        void reserveTypedImage()throws IOException{source();owner.reserveTypedImage();}
        void attachTyped(MembershipLearnerMaterialization<?> next)throws IOException {
            source();require(owner.typed==null || owner.typed.closed(),"learner successor typed preparation already owned");owner.typed=Objects.requireNonNull(next);
        }
    }
    private void reserveTypedImage()throws IOException {
        check();if(typedImage==null){typedImage=parent.resources().reserve(MembershipResources.Unit.APPLICATION,"learner-successor-typed",MembershipApplicationImage.MAXIMUM);leases.add(typedImage);}
    }
    private MembershipCapsule capsule()throws IOException {
        check();Path location=locate();var files=new TreeMap<String,byte[]>();
        for(Object raw:list(value.get("files"))){var file=object(raw);files.put((String)file.get("path"),AdmissionPaths.read(location.resolve((String)file.get("path")),Math.toIntExact(number(file.get("size")))));}
        var packet=MembershipSourcePacket.decode(files.get("source.gscp"));var images=new TreeMap<String,byte[]>();for(String hash:packet.images().keySet())images.put(hash,files.get(hash+".image"));
        var token=new Stored(this,files);MembershipCapsule capsule;
        try{capsule=MembershipCapsule.verifyStored(parent.root(),packet,images,token);}finally{token.active=false;}
        MembershipFloor.Copy.validateMaterialization(generation,capsule,peer,files);
        MembershipLearnerPrefixExport.originalReservation(capsule.context,parent.summary().request(),peer);
        var original=parent.originalAnchor();var prior=new MembershipCapsule.Anchor(object(original.get("cut")),(String)original.get("catalog"),(String)original.get("application"));
        require(number(capsule.context.cut.get("index"))>=number(prior.cut().get("index")),"learner refresh regressed or foreign history");
        capsule.verifyAncestry(files.getOrDefault("ancestry.gsr",new byte[0]),List.of(prior));check();return capsule;
    }
    static final class Stored implements MembershipCapsule.StoredCopy {
        private final MembershipLearnerSuccessor owner;private final Map<String,byte[]> files;private boolean active=true;
        private Stored(MembershipLearnerSuccessor owner,Map<String,byte[]> files){this.owner=owner;this.files=files;}
        @Override public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            owner.check();require(active && Arrays.equals(root.bytes(),owner.parent.root().bytes()) && Arrays.equals(packet.bytes(),files.get("source.gscp")),"learner successor stored original");
        }
        @Override public byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        @Override public Optional<byte[]> coverage(){return Optional.ofNullable(files.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        @Override public Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
    @Override public void close()throws IOException {
        if(closed)return;closed=true;var children=new ArrayList<AutoCloseable>();children.add(typed);children.addAll(received.values());children.addAll(leases);children.add(lock);
        MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
    }
}
