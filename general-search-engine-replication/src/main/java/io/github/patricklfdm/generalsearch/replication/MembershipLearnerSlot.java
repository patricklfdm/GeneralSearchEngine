package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** First inactive member of the bounded rolling pair. Installation owns a second
 * original generation; only an exact forced typed handoff replaces the head. Complete originals
 * can be resumed, while partial plans remain intact and fail closed. */
final class MembershipLearnerSlot implements AutoCloseable {
    static final String LOCK="slots.lock",PLAN="b.json",NEXT="b.next.json",INSTALLED="b.installed.json",SOURCE="source-b";
    static final int MAXIMUM=256*1024,RECORD_MAXIMUM=16*1024,HEAD_MAXIMUM=16*1024;
    static final String HEAD="head.json",HEAD_NEXT="head.next.json";
    // Original fully retired admission/current metadata plus both slot-plan
    // names, installed marker and compact typed plan/candidate/receipt.
    static final long METADATA_MAXIMUM=908L*1024+2L*MAXIMUM+RECORD_MAXIMUM+3L*MembershipLearnerMaterialization.SUCCESSOR_PLAN+2L*HEAD_MAXIMUM;
    private static final Set<String> MEMBERS=Set.of(LOCK,PLAN,NEXT,INSTALLED,SOURCE,HEAD,HEAD_NEXT);
    private final MembershipLearnerStore parent;
    private final MembershipBallotAllocator.Cut cut;
    private final byte[] plan,installed;
    private final Map<String,Object> value,pathBinding,stagingBinding,anchor;
    private final Path directory,staging,destination;
    private final Object directoryKey;
    private final Decoded generation;
    private final MembershipIdentity peer;
    private final Map<String,FileIdentity> metadata=new TreeMap<>();
    private final Map<String,MembershipReceiveFile.Retained> received=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private MembershipOwnership lock;
    private MembershipLearnerMaterialization<?> typed;
    private MembershipResources.Lease typedImage;
    private MembershipLearnerMaterialization.CurrentHead live;
    private MembershipGenerationFiles.Guard acquisition;
    private MembershipLearnerSeed seed;
    private Head head;
    private boolean closed,failed,complete,accounted;

    static Path directory(MembershipLearnerPlan summary) {
        return summary.request().operationDirectory().resolveSibling(".gse-v53-learner-slots-"+summary.planDigest());
    }
    static Path typedDirectory(MembershipLearnerPlan summary) {
        return summary.request().operationDirectory().resolveSibling(".gse-v53-learner-slot-b-"+summary.planDigest());
    }
    static boolean hasCommittedHead(MembershipLearnerPlan summary)throws IOException {
        return Files.exists(AdmissionPaths.safe(directory(summary)).resolve(HEAD),LinkOption.NOFOLLOW_LINKS);
    }
    private MembershipLearnerSlot(MembershipLearnerStore parent,byte[] bytes,MembershipBallotAllocator.Cut cut)throws IOException {
        this(parent,bytes,cut,null);
    }
    private MembershipLearnerSlot(MembershipLearnerStore parent,byte[] bytes,MembershipBallotAllocator.Cut cut,MembershipLearnerSeed seed)throws IOException {
        this.parent=parent;this.cut=cut;this.seed=seed;plan=bytes.clone();value=object(parse(plan,MAXIMUM));
        require(METADATA_MAXIMUM<=MembershipResources.Unit.MISC.bytes,"learner slot metadata capacity");
        require(Arrays.equals(plan,canonical(value,MAXIMUM)) && value.keySet().equals(Set.of("schema","plan","slot","sequence","anchor","path","directoryKey",
                "staging","sourceKey","source","generation","files")) && value.get("schema").equals("gse-v53-learner-slot/1.3")
                && value.get("plan").equals(parent.summary().planDigest()) && value.get("slot").equals("b") && number(value.get("sequence"))==1,
                "learner slot original plan");
        anchor=object(value.get("anchor"));require(anchor.equals(seed==null?parent.slotAnchor():seed.anchor(anchor.get("core"))),"learner slot original current head changed");
        directory=directory(parent.summary());destination=directory.resolve(SOURCE);
        pathBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("path")));
        stagingBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("staging")));staging=MembershipLearnerAdmissionPlan.path(stagingBinding);
        require(directory.equals(MembershipLearnerAdmissionPlan.path(pathBinding)),"learner slot exact path");
        paths(staging);directoryKey=key(directory);require(text(value.get("directoryKey")).equals(directoryKey.toString()),"learner slot directory replaced");
        text(value.get("sourceKey"));peer=MembershipContext.identity(object(value.get("source")));
        require(value.get("source").equals(MembershipBootstrapSeed.identity(peer)),"learner slot source identity");
        generation=decode(MembershipBootstrapPlanData.unbase(value.get("generation"),65536),"records","GENERATION");
        var expected=new TreeMap<String,Map<String,Object>>();expected.put("generation.gsr",row("generation.gsr",generation.bytes()));long total=generation.size();
        for(Object raw:list(generation.value().get("files"))) {
            var f=object(raw);String name=(String)f.get("path");long size=number(f.get("size"));
            require(size>0 && size<=MembershipGenerationFiles.limit(name) && expected.putIfAbsent(name,f)==null,"learner slot original member");
            if(!name.endsWith(".image")){total=Math.addExact(total,size);require(total<=MembershipResources.Unit.GENERATION.bytes,"learner slot metadata capacity");}
        }
        var files=list(value.get("files"));require(files.size()==expected.size() && files.size()<=32,"learner slot file count");String previous=null;
        for(Object raw:files) {
            var f=object(raw);String name=(String)f.get("path");
            require(f.keySet().equals(Set.of("path","size","sha256","key")) && (previous==null || previous.compareTo(name)<0)
                    && Objects.equals(expected.get(name),Map.of("path",name,"size",f.get("size"),"sha256",f.get("sha256"))),"learner slot original inventory");
            text(f.get("key"));previous=name;
        }
        installed=canonical(Map.of("schema","gse-v53-learner-slot-installed/1.3","plan",hash(plan),"generation",generation.digest(),
                "location",destination.toString()),RECORD_MAXIMUM);
    }
    private static String text(Object value) {
        require(value instanceof String && !((String)value).isBlank() && ((String)value).getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=4096,
                "learner slot inode text");return (String)value;
    }
    private static Map<String,Object> row(String name,byte[] bytes){return Map.of("path",name,"size",(long)bytes.length,"sha256",hash(bytes));}
    private void paths(Path receiving)throws IOException {
        var summary=parent.summary();var core=MembershipLearnerAdmissionPlan.binding(object(anchor.get("core")));AdmissionPaths.recheck(core);
        AdmissionPaths.disjoint(List.of(directory,receiving,typedDirectory(summary),MembershipLearnerAdmissionPlan.path(core),
                MembershipLearnerSuccessor.directory(summary),MembershipLearnerSuccessor.typedDirectory(summary),
                MembershipLearnerMaterialization.directory(summary),summary.request().replicaDirectory(),summary.request().operationDirectory()));
    }
    static View install(MembershipLearnerMaterialization.CurrentHead current,MembershipSourceReceive receiver,
            MembershipFloor.Copy copy,MembershipBallotAllocator.Cut cut)throws IOException {
        return install(current,receiver,copy,cut,()->{});
    }
    static View install(MembershipLearnerMaterialization.CurrentHead current,MembershipSourceReceive receiver,
            MembershipFloor.Copy copy,MembershipBallotAllocator.Cut cut,MembershipGenerationFiles.Guard acquisition)throws IOException {
        Objects.requireNonNull(acquisition).check();
        current.check();var parent=current.store();parent.requireNewSlot();receiver.requireResources(parent.resources());copy.check();
        MembershipLearnerSource.successor(current.source(),copy);MembershipLearnerPrefixExport.originalReservation(copy.capsule.context,current.request(),copy.owner);
        Path staging=receiver.completeLearnerDirectory(copy),directory=directory(parent.summary()),typed=typedDirectory(parent.summary());
        current.requireDisjoint(directory,typed,staging);var anchor=parent.slotAnchor();
        var files=new ArrayList<Map<String,Object>>();
        for(String name:new TreeSet<>(copy.fileNames())) {
            var f=new TreeMap<>(row(name,copy.fileBytes(name)));f.put("key",key(staging.resolve(name)).toString());files.add(f);
        }
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-learner-slot/1.3");value.put("plan",parent.summary().planDigest());
        value.put("slot","b");value.put("sequence",1L);value.put("anchor",anchor);value.put("path",AdmissionPaths.binding(directory));
        value.put("staging",AdmissionPaths.binding(staging));value.put("sourceKey",key(staging).toString());value.put("source",MembershipBootstrapSeed.identity(copy.owner));
        value.put("generation",MembershipBootstrapPlanData.base(copy.generation.bytes()));value.put("files",files);
        value.put("directoryKey","x".repeat(4096));canonical(value,MAXIMUM);
        require(METADATA_MAXIMUM<=MembershipResources.Unit.MISC.bytes,"learner slot metadata capacity");
        MembershipLearnerSlot result=null;
        try {
            Files.createDirectory(directory);value.put("directoryKey",key(directory).toString());
            result=new MembershipLearnerSlot(parent,canonical(value,MAXIMUM),cut);result.live=current;result.acquisition=acquisition;
            result.lock=MembershipOwnership.own(directory.resolve(LOCK),true);
            result.received.putAll(receiver.detachLearner(copy));result.accounted=true;parent.attachSlot(result);
            result.capture();result.check();AdmissionPaths.forceDirectory(directory.getParent());result.point("LEARNER_SLOT_DIRECTORY_FORCED");
            result.write(NEXT,result.plan,"LEARNER_SLOT_PLAN");result.finish();result.live=null;return new View(result);
        }catch(IOException|RuntimeException|Error error) {
            if(result!=null){result.failed=true;result.live=null;if(!parent.ownsSlot(result))try{result.close();}catch(IOException cleanup){error.addSuppressed(cleanup);}}
            throw error;
        }finally{if(result!=null)result.acquisition=null;}
    }
    static MembershipLearnerSlot restore(MembershipLearnerStore parent,MembershipBallotAllocator.Cut cut)throws IOException {
        Path directory=directory(parent.summary()),typed=typedDirectory(parent.summary());
        if(!Files.exists(AdmissionPaths.safe(directory),LinkOption.NOFOLLOW_LINKS)) {
            AdmissionPaths.absent(typed);return null;
        }
        var names=children(directory,7);require(names.contains(LOCK) && MEMBERS.containsAll(names) && (names.contains(PLAN)||names.contains(NEXT)),"learner slot incomplete original inventory");
        var lock=MembershipOwnership.own(directory.resolve(LOCK),false);MembershipLearnerSlot result=null;MembershipLearnerSeed seed=null;
        try {
            byte[] headBytes=null;
            if(names.contains(HEAD) || names.contains(HEAD_NEXT)) {
                headBytes=AdmissionPaths.read(directory.resolve(names.contains(HEAD)?HEAD:HEAD_NEXT),HEAD_MAXIMUM);
                var record=headRecord(headBytes);
                require(!(names.contains(HEAD) && names.contains(HEAD_NEXT)),"learner slot multiple original heads");
                seed=names.contains(HEAD)?MembershipLearnerSeed.restore(parent,record.get("seedFiles")):MembershipLearnerSeed.capture(parent);
            }
            result=new MembershipLearnerSlot(parent,AdmissionPaths.read(directory.resolve(names.contains(PLAN)?PLAN:NEXT),MAXIMUM),cut,seed);
            result.lock=lock;result.capture();if(headBytes!=null)result.head=result.new Head(headBytes);
            result.check();
            // Read-only original validation before the old parent's recovery
            // forces. This is not an exposed source or resource capability.
            result.capsule();if(result.head!=null)result.head.check();
            if(names.contains(HEAD))result.complete=true;return result;
        }catch(IOException|RuntimeException|Error error){try{if(result!=null)result.close();else MembershipLearnerSource.closeChildren(seed,lock);}catch(IOException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    /** Account this retained candidate only after the parent has re-forced
     * completed original retirement and released its conservative old charges.
     * No slot writes or public source view are possible before this succeeds. */
    void reserve()throws IOException {
        check();require(!accounted && received.isEmpty() && leases.isEmpty(),"learner slot resource owner already accounted");
        try {
            long metadata=0;var resources=parent.resources();
            for(Object raw:list(value.get("files"))){var f=object(raw);if(!((String)f.get("path")).endsWith(".image"))metadata=Math.addExact(metadata,number(f.get("size")));}
            leases.add(resources.reserve(MembershipResources.Unit.GENERATION,"learner-slot-b",metadata));
            for(Object raw:list(value.get("files"))){var f=object(raw);if(((String)f.get("path")).endsWith(".image"))
                leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"learner-slot-b:"+f.get("path"),number(f.get("size"))));}
            capsule();
            if(Files.exists(AdmissionPaths.safe(typedDirectory(parent.summary())),LinkOption.NOFOLLOW_LINKS))reserveTypedImage();
            if(seed!=null)seed.reserve();accounted=true;
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private Path locate()throws IOException {
        boolean before=Files.exists(staging,LinkOption.NOFOLLOW_LINKS),after=Files.exists(destination,LinkOption.NOFOLLOW_LINKS);
        require(before!=after,"learner slot requires original source location");Path location=before?staging:destination;
        if(before)AdmissionPaths.recheck(stagingBinding);
        require(text(value.get("sourceKey")).equals(key(location).toString()),"learner slot source directory replaced");var names=new TreeSet<String>();
        for(Object raw:list(value.get("files"))) {
            var f=object(raw);String name=(String)f.get("path");names.add(name);
            require(f.get("key").equals(inspect(location.resolve(name),number(f.get("size")),(String)f.get("sha256")).key().toString()),"learner slot original source changed");
            if(received.containsKey(name))received.get(name).check(location.resolve(name));
        }
        require(children(location,32).equals(names),"learner slot source inventory");return location;
    }
    private void capture()throws IOException {
        var names=children(directory,7);require(names.contains(LOCK) && MEMBERS.containsAll(names),"learner slot inventory");
        for(String name:List.of(LOCK,PLAN,NEXT,INSTALLED))if(names.contains(name)) {
            byte[] expected=name.equals(LOCK)?new byte[0]:name.equals(INSTALLED)?installed:plan;
            byte[] bytes=AdmissionPaths.read(directory.resolve(name),expected.length);
            require(Arrays.equals(bytes,Arrays.copyOf(expected,bytes.length)) && (!(name.equals(PLAN)||name.equals(NEXT)&&names.contains(PLAN)) || bytes.length==expected.length),"learner slot original metadata changed");
            metadata.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));
        }
        require(!names.contains(INSTALLED) || names.contains(PLAN) && names.contains(SOURCE),"learner slot installation without original source");
        for(String name:List.of(HEAD,HEAD_NEXT))if(names.contains(name)) {
            byte[] bytes=AdmissionPaths.read(directory.resolve(name),HEAD_MAXIMUM);metadata.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));
        }
    }
    private void check()throws IOException {
        require(!closed && !failed && lock!=null && lock.lock().isValid(),"learner slot owner closed or failed");
        if(acquisition!=null)acquisition.check();
        if(live!=null)live.check();
        if(committed()){require(seed!=null && head!=null,"learner slot selected seed missing");seed.checkMetadata();}
        else require(anchor.equals(parent.slotAnchor()),"learner slot original current head changed");
        AdmissionPaths.recheck(pathBinding);require(directoryKey.equals(key(directory)),"learner slot directory replaced");Path source=locate();
        var names=new TreeSet<>(metadata.keySet());if(source.equals(destination))names.add(SOURCE);
        require(children(directory,7).equals(names),"learner slot live inventory changed");
        for(var f:metadata.entrySet())require(f.getValue().equals(inspect(directory.resolve(f.getKey()),f.getValue().bytes(),f.getValue().digest())),"learner slot metadata replaced");
    }
    private void point(String event)throws IOException {check();if(head!=null)head.checkFiles();cut.at(event);check();if(head!=null)head.checkFiles();}
    private void remember(String name,byte[] expected)throws IOException {
        byte[] bytes=AdmissionPaths.read(directory.resolve(name),expected.length);
        require(Arrays.equals(bytes,Arrays.copyOf(expected,bytes.length)),"learner slot writer changed originals");
        var before=metadata.get(name);var after=inspect(directory.resolve(name),bytes.length,hash(bytes));
        require(before==null || before.key().equals(after.key()),"learner slot writer inode changed");metadata.put(name,after);
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
    private void finish()throws IOException {
        try {
            require(accounted,"learner slot retained resources not accounted");
            MembershipResources.GenerationClaim claim=received.isEmpty()?null:received.get("source.gscp").prepareGeneration(locate().resolve("source.gscp"),"learner-slot-b");
            try(claim) {
                check();require(metadata.containsKey(PLAN)||metadata.containsKey(NEXT)&&metadata.get(NEXT).bytes()==plan.length,"learner slot partial original plan");
                if(!metadata.containsKey(PLAN)) {
                    write(NEXT,plan,"LEARNER_SLOT_CANDIDATE");Files.move(directory.resolve(NEXT),directory.resolve(PLAN),StandardCopyOption.ATOMIC_MOVE);
                    metadata.put(PLAN,metadata.remove(NEXT));point("LEARNER_SLOT_PLAN_RENAMED");
                }
                write(PLAN,plan,"LEARNER_SLOT_ACTIVE");
                if(metadata.containsKey(NEXT)){check();Files.delete(directory.resolve(NEXT));metadata.remove(NEXT);AdmissionPaths.forceDirectory(directory);point("LEARNER_SLOT_REDUNDANT_FORCED");}
                if(locate().equals(staging)){check();Files.move(staging,destination,StandardCopyOption.ATOMIC_MOVE);point("LEARNER_SLOT_SOURCE_MOVED");}
                AdmissionPaths.forceDirectory(destination);
                if(Files.exists(staging.getParent(),LinkOption.NOFOLLOW_LINKS)){AdmissionPaths.recheck(stagingBinding);AdmissionPaths.forceDirectory(staging.getParent());}
                else require(metadata.containsKey(INSTALLED)&&metadata.get(INSTALLED).bytes()==installed.length,"learner slot incomplete move lost original parent");
                AdmissionPaths.forceDirectory(directory);point("LEARNER_SLOT_SOURCE_PARENTS_FORCED");capsule();
                write(INSTALLED,installed,"LEARNER_SLOT_INSTALL");
                if(claim!=null){received.get("source.gscp").requireGenerationClaim(destination.resolve("source.gscp"),claim);claim.commit();}
                complete=true;point("LEARNER_SLOT_BEFORE_RETURN");
            }
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    View open(MembershipLearnerMaterialization.CurrentHead current)throws IOException {
        require(!committed(),"learner pending slot superseded by selected head");
        current.check();require(current.store()==parent,"learner slot foreign current owner");
        require(accounted,"learner slot retained resources not accounted");
        try{live=current;if(!complete)finish();else check();return new View(this);}finally{live=null;}
    }
    boolean committed(){return metadata.containsKey(HEAD);}
    View promoted()throws IOException {
        check();require(committed() && head!=null && head.active && accounted && complete,"learner slot head not forced/accounted");
        head.check();return new View(this,true);
    }
    void resealHead()throws IOException {
        check();require(committed() && head!=null,"learner original slot head missing");
        try{head.seal(false);complete=true;seed.supersede();}
        catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private View promote(MembershipLearnerMaterialization<?> current,MembershipLearnerMaterialization.CurrentHead previous)throws IOException {
        check();require(!committed() && complete && accounted && current==typed,"learner slot handoff requires exact pending typed owner");
        previous.check();require(previous.store()==parent,"learner slot handoff foreign previous owner");current.receipt();
        if(seed==null)seed=MembershipLearnerSeed.capture(parent);
        var decision=new TreeMap<String,Object>(Map.of("schema","gse-v53-learner-slot-head/1.3","plan",hash(plan),
                "source",hash(capsule().packet.bytes()),"generation",generation.digest(),"receipt",current.receipt().digest(),
                "seedFiles",seed.metadata(),"previousFiles",seed.sourceFiles(),"previousTyped",seed.typedFiles(),
                "currentFiles",MembershipLearnerFingerprints.capture(typedDirectory(parent.summary()),MembershipLearnerFingerprints.typed(),Set.of(),false,MembershipApplicationImage.MAXIMUM)));
        decision.put("headKey","x".repeat(4096));canonical(decision,HEAD_MAXIMUM);previous.check();current.receipt();
        try {
            if(head==null) {
                check();AdmissionPaths.absent(directory.resolve(HEAD_NEXT));
                try(var candidate=FileChannel.open(directory.resolve(HEAD_NEXT),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                    remember(HEAD_NEXT,new byte[0]);decision.put("headKey",metadata.get(HEAD_NEXT).key().toString());
                    head=new Head(canonical(decision,HEAD_MAXIMUM));head.live=()->{previous.check();current.receipt();};
                    point("LEARNER_SLOT_HEAD_CANDIDATE_CREATED");
                }
            }else {
                decision.put("headKey",head.record.get("headKey"));
                require(Arrays.equals(canonical(decision,HEAD_MAXIMUM),head.bytes),"learner slot original handoff changed");
            }
            head.live=()->{previous.check();current.receipt();};head.check();head.seal(true);head.live=null;
            current.close();seed.supersede();point("LEARNER_SLOT_HEAD_BEFORE_RETURN");return new View(this,true);
        }catch(IOException|RuntimeException|Error error) {
            failed=true;
            if(committed())try{current.close();seed.supersede();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}
            throw error;
        }finally{if(head!=null)head.live=null;}
    }
    void retireSeed()throws IOException {
        try {
            check();require(committed() && head!=null && head.active && accounted,"learner seed retirement requires forced slot head");
            head.check();head.seal(false);seed.supersede();
            for(Path file:seed.removalOrder()) {
                point("LEARNER_SLOT_RETIRE_BEFORE_DELETE");
                if(Files.exists(file,LinkOption.NOFOLLOW_LINKS)){Files.delete(file);point("LEARNER_SLOT_RETIRE_MEMBER_DELETED");}
                if(Files.exists(file.getParent(),LinkOption.NOFOLLOW_LINKS))AdmissionPaths.forceDirectory(file.getParent());
                point("LEARNER_SLOT_RETIRE_MEMBER_PARENT_FORCED");
            }
            seed.forceParents();point("LEARNER_SLOT_RETIRE_PARENTS_FORCED");seed.release();point("LEARNER_SLOT_RETIRE_RELEASED");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private static Map<String,Object> headRecord(byte[] bytes) {
        var record=object(parse(bytes,HEAD_MAXIMUM));
        require(Arrays.equals(bytes,canonical(record,HEAD_MAXIMUM)) && record.keySet().equals(Set.of("schema","plan","source","generation","receipt",
                "seedFiles","previousFiles","previousTyped","currentFiles","headKey")) && record.get("schema").equals("gse-v53-learner-slot-head/1.3"),"learner slot original head shape");
        for(String name:List.of("plan","source","generation","receipt"))MembershipValidation.digest((String)record.get(name));text(record.get("headKey"));
        return record;
    }
    private final class Head {
        private final byte[] bytes;
        private final Map<String,Object> record;
        private MembershipGenerationFiles.Guard live;
        private boolean active;
        Head(byte[] bytes){this.bytes=bytes.clone();record=headRecord(bytes);}
        void checkFiles()throws IOException {
            if(live!=null)live.check();
            require(metadata.containsKey(HEAD)!=metadata.containsKey(HEAD_NEXT),"learner slot original head location");
            String name=committed()?HEAD:HEAD_NEXT;
            require(metadata.get(name).key().toString().equals(record.get("headKey")),"learner slot original head inode changed");
            require(seed!=null && record.get("seedFiles").equals(seed.metadata()),"learner slot seed metadata changed");
            seed.checkRemaining(record.get("previousFiles"),record.get("previousTyped"),committed());
            MembershipLearnerFingerprints.check(typedDirectory(parent.summary()),MembershipLearnerFingerprints.typed(),Set.of(),record.get("currentFiles"),false,MembershipApplicationImage.MAXIMUM);
            if(live!=null)live.check();
        }
        void check()throws IOException {
            MembershipLearnerSlot.this.check();checkFiles();var source=capsule();
            require(record.get("plan").equals(hash(plan)) && record.get("source").equals(hash(source.packet.bytes()))
                    && record.get("generation").equals(generation.digest()),"learner slot head source binding");
            require(metadata.containsKey(PLAN) && !metadata.containsKey(NEXT) && metadata.containsKey(INSTALLED)
                    && metadata.get(INSTALLED).bytes()==installed.length,"learner slot head requires complete installation");
            Path typed=typedDirectory(parent.summary());byte[] receipt=AdmissionPaths.read(typed.resolve("learner.gsr"),MembershipLearnerMaterialization.SUCCESSOR_PLAN);
            var decoded=decode(receipt,"records","LEARNER");long revision=number(object(object(decoded.value().get("receipt")).get("prepared")).get("revision"));
            require(record.get("receipt").equals(hash(receipt)) && Arrays.equals(receipt,MembershipLearnerPreparation.receiptBytes(source,parent.summary().request(),revision).bytes()),"learner slot head current receipt binding");
            var typedPlan=object(parse(AdmissionPaths.read(typed.resolve("preparation.json"),MembershipLearnerMaterialization.SUCCESSOR_PLAN),MembershipLearnerMaterialization.SUCCESSOR_PLAN));
            require(typedPlan.get("schema").equals("gse-v53-successor-typed/1.3") && typedPlan.get("plan").equals(parent.summary().planDigest())
                    && typedPlan.get("source").equals(record.get("source")) && typedPlan.get("receipt").equals(record.get("receipt"))
                    && typedPlan.get("materialization").equals(anchor.get("core")),"learner slot head current typed plan");
        }
        void seal(boolean candidate)throws IOException {
            check();
            if(!committed()) {
                require(candidate,"learner original slot head missing");write(HEAD_NEXT,bytes,"LEARNER_SLOT_HEAD_CANDIDATE");
                Files.move(directory.resolve(HEAD_NEXT),directory.resolve(HEAD),StandardCopyOption.ATOMIC_MOVE);
                metadata.put(HEAD,metadata.remove(HEAD_NEXT));point("LEARNER_SLOT_HEAD_RENAMED");
            }
            require(metadata.get(HEAD).bytes()==bytes.length && metadata.get(HEAD).digest().equals(hash(bytes)),"learner slot original active head differs");
            write(HEAD,bytes,"LEARNER_SLOT_HEAD_ACTIVE");
            check();active=true;
        }
    }
    private MembershipCapsule capsule()throws IOException {
        check();Path location=locate();var files=new TreeMap<String,byte[]>();
        for(Object raw:list(value.get("files"))){var f=object(raw);files.put((String)f.get("path"),AdmissionPaths.read(location.resolve((String)f.get("path")),Math.toIntExact(number(f.get("size")))));}
        var packet=MembershipSourcePacket.decode(files.get("source.gscp"));var images=new TreeMap<String,byte[]>();for(String hash:packet.images().keySet())images.put(hash,files.get(hash+".image"));
        var token=new Stored(this,files);MembershipCapsule capsule;
        try{capsule=MembershipCapsule.verifyStored(parent.root(),packet,images,token);}finally{token.active=false;}
        MembershipFloor.Copy.validateMaterialization(generation,capsule,peer,files);
        MembershipLearnerPrefixExport.originalReservation(capsule.context,parent.summary().request(),peer);
        var previous=object(anchor.get("previous"));var prior=new MembershipCapsule.Anchor(object(previous.get("cut")),(String)previous.get("catalog"),(String)previous.get("application"));
        require(number(capsule.context.cut.get("index"))>=number(prior.cut().get("index")),"learner refresh regressed or foreign history");
        capsule.verifyAncestry(files.getOrDefault("ancestry.gsr",new byte[0]),List.of(prior));check();return capsule;
    }
    static final class Stored implements MembershipCapsule.StoredCopy {
        private final MembershipLearnerSlot owner;private final Map<String,byte[]> files;private boolean active=true;
        private Stored(MembershipLearnerSlot owner,Map<String,byte[]> files){this.owner=owner;this.files=files;}
        @Override public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            owner.check();require(active && Arrays.equals(root.bytes(),owner.parent.root().bytes()) && Arrays.equals(packet.bytes(),files.get("source.gscp")),"learner slot stored original");
        }
        @Override public byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        @Override public Optional<byte[]> coverage(){return Optional.ofNullable(files.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        @Override public Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
    private void reserveTypedImage()throws IOException {
        check();if(typedImage==null){typedImage=parent.resources().reserve(MembershipResources.Unit.APPLICATION,"learner-slot-b-typed",MembershipApplicationImage.MAXIMUM);leases.add(typedImage);}
    }
    static final class View implements MembershipLearnerImageSource {
        private final MembershipLearnerSlot owner;
        private final boolean current;
        private View(MembershipLearnerSlot owner){this(owner,false);}
        private View(MembershipLearnerSlot owner,boolean current){this.owner=owner;this.current=current;}
        @Override public MembershipCapsule source()throws IOException {
            owner.check();require(owner.complete && owner.accounted,"learner slot installation not forced");
            require(current?owner.committed():!owner.committed() || owner.head!=null && !owner.head.active,"learner slot view superseded");
            if(current){require(owner.head!=null && owner.head.active,"learner slot head not forced");owner.head.checkFiles();}
            return owner.capsule();
        }
        @Override public MembershipLearnerStore store()throws IOException {source();return owner.parent;}
        @Override public Path typedDirectory()throws IOException {source();return MembershipLearnerSlot.typedDirectory(owner.parent.summary());}
        @Override public byte[] originalImage(String digest,long size)throws IOException {
            var source=source();require(Objects.equals(source.packet.images().get(digest),size),"learner slot original image binding");
            byte[] bytes=AdmissionPaths.read(owner.destination.resolve(digest+".image"),Math.toIntExact(size));
            require(bytes.length==size && hash(bytes).equals(digest),"learner slot original image bytes");source();return bytes;
        }
        @Override public void requireTypedPaths(Path core,Path typed)throws IOException {
            source();var binding=MembershipLearnerAdmissionPlan.binding(object(owner.anchor.get("core")));AdmissionPaths.recheck(binding);
            require(core.equals(MembershipLearnerAdmissionPlan.path(binding)) && typed.equals(typedDirectory()),"learner slot reserved typed/core path changed");owner.paths(owner.staging);
        }
        @Override public void reserveTypedImage()throws IOException {source();owner.reserveTypedImage();}
        @Override public void attachTyped(MembershipLearnerMaterialization<?> typed)throws IOException {
            source();require(owner.typed==null || owner.typed.closed(),"learner slot typed preparation already owned");owner.typed=Objects.requireNonNull(typed);
        }
        View promote(MembershipLearnerMaterialization<?> typed,MembershipLearnerMaterialization.CurrentHead previous)throws IOException {
            source();require(!current,"learner slot already current");return owner.promote(typed,previous);
        }
        void retirePredecessor()throws IOException {source();require(current,"learner slot retirement requires selected head");owner.retireSeed();}
        @Override public void requireCurrentTyped(MembershipLearnerMaterialization<?> typed)throws IOException {
            source();require(current && owner.typed==typed,"learner inactive slot is not the current head");
            require(owner.seed.retired(),"learner current slot requires forced seed retirement");
        }
        @Override public void requireRefreshPaths(Path... paths)throws IOException {
            source();require(current,"learner inactive slot cannot acquire another source");
            var summary=owner.parent.summary();var all=new ArrayList<>(List.of(paths));
            all.add(owner.directory);all.add(owner.staging);all.add(MembershipLearnerSlot.typedDirectory(summary));
            all.add(MembershipLearnerSuccessor.directory(summary));all.add(MembershipLearnerSuccessor.typedDirectory(summary));
            all.add(MembershipLearnerMaterialization.directory(summary));all.add(summary.request().operationDirectory());all.add(summary.request().replicaDirectory());
            AdmissionPaths.disjoint(all);
        }
    }
    @Override public void close()throws IOException {
        if(closed)return;closed=true;var children=new ArrayList<AutoCloseable>();children.add(typed);children.addAll(received.values());children.addAll(leases);children.add(seed);children.add(lock);
        MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
    }
}
