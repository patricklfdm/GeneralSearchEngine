package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One lock and bounded current/pending image owners. Installation owns a second
 * original generation; only an exact forced typed handoff replaces the head.
 * Complete originals can resume; partial plans remain intact and fail closed. */
final class MembershipLearnerSlot implements AutoCloseable {
    static final String LOCK="slots.lock",PLAN="b.json",NEXT="b.next.json",INSTALLED="b.installed.json",SOURCE="source-b";
    static final int MAXIMUM=256*1024,RECORD_MAXIMUM=16*1024,HEAD_MAXIMUM=16*1024;
    static final String HEAD="head.json",HEAD_NEXT="head.next.json";
    static final String CLEARED="cleared.json",CLEARED_NEXT="cleared.next.json";
    // Conservative retained metadata: immutable admission/seed; current plan,
    // inactive plan/candidate and both installed markers; current typed records,
    // pending typed plan/candidate/receipt; head and vacancy pairs. 1852 KiB. The
    // selected head forbids its own candidate; the third plan is the inactive candidate.
    static final long METADATA_MAXIMUM=908L*1024+2L*MAXIMUM+RECORD_MAXIMUM+3L*MembershipLearnerMaterialization.SUCCESSOR_PLAN+4L*HEAD_MAXIMUM+MAXIMUM+RECORD_MAXIMUM+2L*MembershipLearnerMaterialization.SUCCESSOR_PLAN;
    private static final Set<String> MEMBERS=Set.of(LOCK,PLAN,NEXT,INSTALLED,SOURCE,HEAD,HEAD_NEXT,CLEARED,CLEARED_NEXT,"a.json","a.next.json","a.installed.json");
    private final MembershipLearnerStore parent;
    private MembershipBallotAllocator.Cut cut;
    private final Path directory;
    private final Map<String,Object> pathBinding;
    private final Object directoryKey;
    private Image image,pending,retiring;
    private final Map<String,FileIdentity> metadata=new TreeMap<>();
    private MembershipOwnership lock;
    private MembershipLearnerMaterialization.CurrentHead live;
    private MembershipGenerationFiles.Guard acquisition;
    private MembershipLearnerSeed seed;
    private Head head,candidateHead;
    private Cleared cleared;
    private boolean closed,failed,checkingAcquisition;

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
        this(parent,bytes,cut,seed,null);
    }
    private MembershipLearnerSlot(MembershipLearnerStore parent,byte[] bytes,MembershipBallotAllocator.Cut cut,
            MembershipLearnerSeed seed,Map<String,Object> expectedAnchor)throws IOException {
        this.parent=parent;this.cut=cut;this.seed=seed;
        directory=directory(parent.summary());directoryKey=key(directory);
        var original=object(parse(bytes,MAXIMUM));pathBinding=MembershipLearnerAdmissionPlan.binding(object(original.get("path")));
        image=new Image(bytes,expectedAnchor);
    }
    private static String text(Object value) {
        require(value instanceof String && !((String)value).isBlank() && ((String)value).getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=4096,
                "learner slot inode text");return (String)value;
    }
    private static Map<String,Object> row(String name,byte[] bytes){return Map.of("path",name,"size",(long)bytes.length,"sha256",hash(bytes));}
    private void paths(Path receiving,Map<String,Object> anchor)throws IOException {
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
        current.check();var parent=current.store();parent.requireNewSlot();
        if(parent.slotOwner()!=null)return parent.slotOwner().installNext(current,receiver,copy,cut,acquisition);
        receiver.requireResources(parent.resources());copy.check();
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
            result.image.received.putAll(receiver.detachLearner(copy));result.image.accounted=true;parent.attachSlot(result);
            result.capture();result.check();AdmissionPaths.forceDirectory(directory.getParent());result.point("LEARNER_SLOT_DIRECTORY_FORCED");
            result.write(NEXT,result.image.plan,"LEARNER_SLOT_PLAN");result.finish();result.live=null;return new View(result);
        }catch(IOException|RuntimeException|Error error) {
            if(result!=null){result.failed=true;result.live=null;if(!parent.ownsSlot(result))try{result.close();}catch(IOException cleanup){error.addSuppressed(cleanup);}}
            throw error;
        }finally{if(result!=null)result.acquisition=null;}
    }
    void requireReusable()throws IOException {
        check();require(committed() && head!=null && head.active && cleared!=null && cleared.active
                && seed.retired() && pending==null,"learner inactive slot requires original resume or selection");
        nextSequence(image.sequence());head.check();cleared.check();
        if(head.rolling) {
            require(retiring!=null && retiring.released,"learner inactive resources not released");
            retiring.requireVacant();retiring.checkPlan(head.record.get("previousPlan"));AdmissionPaths.absent(directory.resolve(retiring.nextName));
        }else {
            seed.requireVacant();
            for(String name:List.of("a.json","a.next.json","a.installed.json"))AdmissionPaths.absent(directory.resolve(name));
        }
    }
    static long nextSequence(long sequence){require(sequence>0 && sequence<Long.MAX_VALUE,"learner slot sequence exhausted");return sequence+1;}
    private static String slot(long sequence){require(sequence>0,"learner slot sequence");return sequence%2==0?"a":"b";}
    private Map<String,Object> currentAnchor() {
        require(head!=null,"learner reuse current head missing");
        var generation=image.generation.value();
        return Map.of("head",hash(head.bytes),"receipt",head.record.get("receipt"),"core",image.anchor.get("core"),
                "previous",Map.of("source",head.record.get("source"),"cut",generation.get("cut"),
                        "catalog",generation.get("catalog"),"application",generation.get("application")));
    }
    private Map<String,Object> reuseVacancy() {
        require(cleared!=null && metadata.containsKey(CLEARED) && !metadata.containsKey(CLEARED_NEXT)
                && metadata.get(CLEARED).bytes()==cleared.bytes.length && metadata.get(CLEARED).digest().equals(hash(cleared.bytes)),
                "learner reuse requires complete original vacancy");
        return Map.of("head",hash(head.bytes),"headKey",head.record.get("headKey"),
                "cleared",hash(cleared.bytes),"clearKey",cleared.record.get("clearKey"));
    }
    private View installNext(MembershipLearnerMaterialization.CurrentHead current,MembershipSourceReceive receiver,
            MembershipFloor.Copy copy,MembershipBallotAllocator.Cut events,MembershipGenerationFiles.Guard guard)throws IOException {
        requireReusable();current.check();require(current.store()==parent,"learner slot foreign current owner");
        receiver.requireResources(parent.resources());copy.check();MembershipLearnerSource.successor(current.source(),copy);
        MembershipLearnerPrefixExport.originalReservation(copy.capsule.context,current.request(),copy.owner);
        Path staging=receiver.completeLearnerDirectory(copy);current.requireDisjoint(staging);
        var files=new ArrayList<Map<String,Object>>();
        for(String name:new TreeSet<>(copy.fileNames())) {
            var file=new TreeMap<>(row(name,copy.fileBytes(name)));file.put("key",key(staging.resolve(name)).toString());files.add(file);
        }
        long sequence=nextSequence(image.sequence());String next=slot(sequence)+".next.json";
        var value=new TreeMap<String,Object>();value.put("schema",sequence==2?"gse-v53-learner-slot-reuse/1.3":"gse-v53-learner-slot-rolling/1.3");value.put("plan",parent.summary().planDigest());
        value.put("slot",slot(sequence));value.put("sequence",sequence);value.put("anchor",currentAnchor());value.put("vacancy",reuseVacancy());
        if(sequence>2)value.put("replaces",head.record.get("previousPlan"));
        value.put("path",pathBinding);value.put("directoryKey",directoryKey.toString());value.put("staging",AdmissionPaths.binding(staging));
        value.put("sourceKey",key(staging).toString());value.put("source",MembershipBootstrapSeed.identity(copy.owner));
        value.put("generation",MembershipBootstrapPlanData.base(copy.generation.bytes()));value.put("files",files);
        value.put("planKey","x".repeat(4096));canonical(value,MAXIMUM);guard.check();requireReusable();
        cut=events;acquisition=guard;
        try {
            // Bind the original candidate inode before writing any of its plan.
            try(var candidate=FileChannel.open(directory.resolve(next),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                remember(next,new byte[0]);value.put("planKey",metadata.get(next).key().toString());
                pending=new Image(canonical(value,MAXIMUM));pending.received.putAll(receiver.detachLearner(copy));pending.accounted=true;retiring=null;
                point("LEARNER_SLOT_REUSE_PLAN_CREATED");
            }
            write(pending.nextName,pending.plan,"LEARNER_SLOT_REUSE_PLAN");finish(pending);return new View(this,pending,false);
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
        finally{acquisition=null;}
    }
    static MembershipLearnerSlot restore(MembershipLearnerStore parent,MembershipBallotAllocator.Cut cut)throws IOException {
        Path directory=directory(parent.summary()),typed=typedDirectory(parent.summary());
        if(!Files.exists(AdmissionPaths.safe(directory),LinkOption.NOFOLLOW_LINKS)) {
            AdmissionPaths.absent(typed);return null;
        }
        var names=children(directory,MEMBERS.size());require(names.contains(LOCK) && MEMBERS.containsAll(names) && (names.contains(PLAN)||names.contains(NEXT)),"learner slot incomplete original inventory");
        var lock=MembershipOwnership.own(directory.resolve(LOCK),false);MembershipLearnerSlot result=null;MembershipLearnerSeed seed=null;
        try {
            byte[] headBytes=null;Map<String,Object> selected=null;
            if(names.contains(HEAD) || names.contains(HEAD_NEXT)) {
                headBytes=AdmissionPaths.read(directory.resolve(names.contains(HEAD)?HEAD:HEAD_NEXT),HEAD_MAXIMUM);selected=headRecord(headBytes);
                seed=names.contains(HEAD)?MembershipLearnerSeed.restore(parent,selected.get("seedFiles")):MembershipLearnerSeed.capture(parent);
            }
            boolean rotated=selected!=null && rolling(selected);
            require(!rotated || names.contains(HEAD),"learner rolling candidate without original selected head");
            String selectedPlan=rotated?selected.get("slot")+".json":names.contains(PLAN)?PLAN:NEXT;
            result=new MembershipLearnerSlot(parent,AdmissionPaths.read(directory.resolve(selectedPlan),MAXIMUM),cut,seed,
                    rotated?object(selected.get("previousAnchor")):null);
            result.lock=lock;
            result.capture();if(headBytes!=null)result.head=result.new Head(headBytes);
            if(names.contains(CLEARED)||names.contains(CLEARED_NEXT)) {
                require(names.contains(HEAD),"learner slot original vacancy location");
                byte[] clear=AdmissionPaths.read(directory.resolve(names.contains(CLEARED_NEXT)?CLEARED_NEXT:CLEARED),HEAD_MAXIMUM);
                if(!rotated || object(parse(clear,HEAD_MAXIMUM)).get("head").equals(hash(headBytes)))result.cleared=result.new Cleared(clear);
                else require(!names.contains(CLEARED_NEXT),"learner rolling foreign vacancy candidate");
            }
            String inactive=result.image.slot.equals("a")?"b":"a",candidate=inactive+".next.json",plan=inactive+".json";
            if(names.contains(candidate) || names.contains(plan)) {
                byte[] bytes=AdmissionPaths.read(directory.resolve(names.contains(candidate)?candidate:plan),MAXIMUM);
                var value=object(parse(bytes,MAXIMUM));long sequence=number(value.get("sequence"));
                if(sequence==result.image.sequence()-1) {
                    require(rotated && !names.contains(candidate),"learner retired plan has unbound candidate");
                    // The selected head binds this exact older plan. Its former
                    // anchor is historical; it is never a current capability.
                    result.retiring=result.new Image(bytes,sequence>1?object(value.get("anchor")):null);
                    result.captureImage(result.retiring);
                }else {
                    require(sequence==nextSequence(result.image.sequence()),"learner slot original plan");
                    require(names.contains(HEAD) && result.cleared!=null && names.contains(CLEARED) && !names.contains(CLEARED_NEXT),"learner reuse without active original vacancy");
                    result.pending=result.new Image(bytes);result.captureImage(result.pending);
                }
            }
            if(names.contains(HEAD) && names.contains(HEAD_NEXT)) {
                require(result.pending!=null,"learner rolling candidate without pending original");
                result.candidateHead=result.new Head(AdmissionPaths.read(directory.resolve(HEAD_NEXT),HEAD_MAXIMUM));
                require(result.candidateHead.rolling,"learner slot multiple original heads");
            }
            result.check();
            // Read-only original validation before the old parent's recovery
            // forces. This is not an exposed source or resource capability.
            result.image.capsule();if(result.pending!=null)result.pending.capsule();if(result.head!=null)result.head.check();if(result.candidateHead!=null)result.candidateHead.check();if(result.cleared!=null)result.cleared.check();
            if(names.contains(HEAD))result.image.complete=true;return result;
        }catch(IOException|RuntimeException|Error error){try{if(result!=null)result.close();else MembershipLearnerSource.closeChildren(seed,lock);}catch(IOException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    /** Account this retained candidate only after the parent has re-forced
     * completed original retirement and released its conservative old charges.
     * No slot writes or public source view are possible before this succeeds. */
    void reserve()throws IOException {
        check();require(!image.accounted && image.received.isEmpty() && image.leases.isEmpty(),"learner slot resource owner already accounted");
        try {
            image.reserve();if(pending!=null)pending.reserve();if(retiring!=null && !(cleared!=null && cleared.active))retiring.reserveRetired();
            // Only the same original vacancy after resealing may avoid charging
            // a retired generation. Absence alone never waives ownership.
            if(seed!=null && retiring==null && !(cleared!=null && cleared.active))seed.reserve();image.accounted=true;
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void capture()throws IOException {
        var names=children(directory,MEMBERS.size());require(names.contains(LOCK) && MEMBERS.containsAll(names),"learner slot inventory");
        AdmissionPaths.exact(directory.resolve(LOCK),new byte[0]);metadata.put(LOCK,inspect(directory.resolve(LOCK),0,hash(new byte[0])));
        captureImage(image);if(retiring!=null)captureImage(retiring);
        for(String name:List.of(HEAD,HEAD_NEXT,CLEARED,CLEARED_NEXT))if(names.contains(name)) {
            byte[] bytes=AdmissionPaths.read(directory.resolve(name),HEAD_MAXIMUM);metadata.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));
        }
    }
    private void captureImage(Image target)throws IOException {
        for(String name:List.of(target.planName,target.nextName,target.installedName))if(Files.exists(directory.resolve(name),LinkOption.NOFOLLOW_LINKS)) {
            byte[] expected=name.equals(target.installedName)?target.installed:target.plan;
            byte[] bytes=AdmissionPaths.read(directory.resolve(name),target.replacing?MAXIMUM:expected.length);
            var identity=inspect(directory.resolve(name),bytes.length,hash(bytes));
            boolean covered=target==pending && target.covered(name,identity);
            require(covered || bytes.length<=expected.length && Arrays.equals(bytes,Arrays.copyOf(expected,bytes.length))
                    && (!name.equals(target.planName) && !(name.equals(target.nextName)&&Files.exists(directory.resolve(target.planName))) || bytes.length==expected.length),
                    "learner slot original metadata changed");
            metadata.put(name,identity);
        }
        require(!metadata.containsKey(target.installedName) || target==pending && target.covered(target.installedName,metadata.get(target.installedName)) || metadata.containsKey(target.planName)
                && (target==retiring || Files.exists(target.destination,LinkOption.NOFOLLOW_LINKS)),"learner slot installation without original source");
    }
    private void check()throws IOException {
        require(!closed && !failed && lock!=null && lock.lock().isValid(),"learner slot owner closed or failed");
        // Refreshing the current slot checks that same typed owner. Its guard
        // must re-enter structural validation without recursively calling itself.
        if(acquisition!=null && !checkingAcquisition) {
            checkingAcquisition=true;try{acquisition.check();}finally{checkingAcquisition=false;}
        }
        if(live!=null)live.check();
        if(committed()){require(seed!=null && head!=null,"learner slot selected seed missing");seed.checkMetadata();}
        else require(image.anchor.equals(parent.slotAnchor()),"learner slot original current head changed");
        AdmissionPaths.recheck(pathBinding);require(directoryKey.equals(key(directory)),"learner slot directory replaced");Path source=image.locate();
        if(pending!=null)pending.checkReuse();
        if(image.reused)require(metadata.get(image.planName)!=null && metadata.get(image.planName).key().toString().equals(image.value.get("planKey")),"learner selected plan inode changed");
        var names=new TreeSet<>(metadata.keySet());
        if(image.slot.equals("b") && source.equals(image.destination)
                || pending!=null && pending.slot.equals("b") && Files.exists(pending.destination,LinkOption.NOFOLLOW_LINKS)
                || retiring!=null && retiring.slot.equals("b") && Files.exists(retiring.destination,LinkOption.NOFOLLOW_LINKS))names.add(SOURCE);
        require(children(directory,MEMBERS.size()).equals(names),"learner slot live inventory changed");
        for(var f:metadata.entrySet())require(f.getValue().equals(inspect(directory.resolve(f.getKey()),f.getValue().bytes(),f.getValue().digest())),"learner slot metadata replaced");
    }
    private void point(String event)throws IOException {
        check();if(head!=null)head.checkFiles();if(candidateHead!=null)candidateHead.checkFiles();if(cleared!=null)cleared.check();cut.at(event);
        check();if(head!=null)head.checkFiles();if(candidateHead!=null)candidateHead.checkFiles();if(cleared!=null)cleared.check();
    }
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
    private void finish()throws IOException {finish(image);}
    private void finish(Image image)throws IOException {
        String PLAN=image.planName,NEXT=image.nextName,INSTALLED=image.installedName;
        try {
            require(image.accounted,"learner slot retained resources not accounted");
            MembershipResources.GenerationClaim claim=image.received.isEmpty()?null:image.received.get("source.gscp").prepareGeneration(image.locate().resolve("source.gscp"),"learner-slot-"+image.slot);
            try(claim) {
                check();require(image.planActive()||metadata.containsKey(NEXT)&&metadata.get(NEXT).bytes()==image.plan.length,"learner slot partial original plan");
                if(!image.planActive()) {
                    write(NEXT,image.plan,"LEARNER_SLOT_CANDIDATE");
                    Files.move(directory.resolve(NEXT),directory.resolve(PLAN),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                    metadata.put(PLAN,metadata.remove(NEXT));point("LEARNER_SLOT_PLAN_RENAMED");
                }
                write(PLAN,image.plan,"LEARNER_SLOT_ACTIVE");
                if(metadata.containsKey(NEXT)){check();Files.delete(directory.resolve(NEXT));metadata.remove(NEXT);AdmissionPaths.forceDirectory(directory);point("LEARNER_SLOT_REDUNDANT_FORCED");}
                if(image.replacing) {
                    if(image.covered(INSTALLED,metadata.get(INSTALLED))) {
                        check();Files.delete(directory.resolve(INSTALLED));metadata.remove(INSTALLED);point("LEARNER_SLOT_OLD_INSTALL_DELETED");
                    }
                    // Also re-force the parent after recovery from a deletion
                    // before its force. Never append new bytes to an old marker.
                    AdmissionPaths.forceDirectory(directory);point("LEARNER_SLOT_OLD_INSTALL_PARENT_FORCED");
                }
                if(image.locate().equals(image.staging)){check();Files.move(image.staging,image.destination,StandardCopyOption.ATOMIC_MOVE);point("LEARNER_SLOT_SOURCE_MOVED");}
                AdmissionPaths.forceDirectory(image.destination);
                if(Files.exists(image.staging.getParent(),LinkOption.NOFOLLOW_LINKS)){AdmissionPaths.recheck(image.stagingBinding);AdmissionPaths.forceDirectory(image.staging.getParent());}
                else require(metadata.containsKey(INSTALLED)&&metadata.get(INSTALLED).bytes()==image.installed.length,"learner slot incomplete move lost original parent");
                AdmissionPaths.forceDirectory(image.destination.getParent());AdmissionPaths.forceDirectory(directory);point("LEARNER_SLOT_SOURCE_PARENTS_FORCED");image.capsule();
                write(INSTALLED,image.installed,"LEARNER_SLOT_INSTALL");
                if(claim!=null){image.received.get("source.gscp").requireGenerationClaim(image.destination.resolve("source.gscp"),claim);claim.commit();}
                image.complete=true;point("LEARNER_SLOT_BEFORE_RETURN");
            }
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    View open(MembershipLearnerMaterialization.CurrentHead current)throws IOException {
        if(committed()) {
            current.check();require(current.store()==parent && pending!=null,"learner reusable pending slot missing");
            require(pending.accounted,"learner slot retained resources not accounted");
            if(!pending.complete)finish(pending);else check();return new View(this,pending,false);
        }
        current.check();require(current.store()==parent,"learner slot foreign current owner");
        require(image.accounted,"learner slot retained resources not accounted");
        try{live=current;if(!image.complete)finish();else check();return new View(this);}finally{live=null;}
    }
    boolean committed(){return metadata.containsKey(HEAD);}
    View promoted()throws IOException {
        check();require(committed() && head!=null && head.active && image.accounted && image.complete,"learner slot head not forced/accounted");
        head.check();return new View(this,true);
    }
    void resealHead()throws IOException {
        check();require(committed() && head!=null,"learner original slot head missing");
        try{head.seal(false);if(cleared!=null)cleared.seal();image.complete=true;seed.supersede();}
        catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private View promote(MembershipLearnerMaterialization<?> current,MembershipLearnerMaterialization.CurrentHead previous)throws IOException {
        check();require(!committed() && image.complete && image.accounted && current==image.typed,"learner slot handoff requires exact pending typed owner");
        previous.check();require(previous.store()==parent,"learner slot handoff foreign previous owner");current.receipt();
        if(seed==null)seed=MembershipLearnerSeed.capture(parent);
        var decision=new TreeMap<String,Object>(Map.of("schema","gse-v53-learner-slot-head/1.3","plan",hash(image.plan),
                "source",hash(image.capsule().packet.bytes()),"generation",image.generation.digest(),"receipt",current.receipt().digest(),
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
    private View promoteRolling(MembershipLearnerMaterialization<?> current,MembershipLearnerMaterialization.CurrentHead previous)throws IOException {
        check();require(head!=null && head.active && cleared!=null && cleared.active && retiring==null && pending!=null && pending.complete
                && pending.accounted && current==pending.typed,"learner rolling handoff requires exact typed pair");
        previous.check();require(previous.store()==parent,"learner rolling foreign current owner");current.receipt();
        var decision=new TreeMap<String,Object>(Map.of("schema","gse-v53-learner-rolling-head/1.3","slot",pending.slot,"sequence",pending.value.get("sequence"),
                "plan",hash(pending.plan),"source",hash(pending.capsule().packet.bytes()),"generation",pending.generation.digest(),"receipt",current.receipt().digest(),
                "seedFiles",seed.metadata(),"previousFiles",image.sourceFiles(),"previousTyped",image.typedFiles()));
        decision.put("currentFiles",pending.typedFiles());decision.put("previousPlan",image.planFiles());decision.put("previousAnchor",currentAnchor());decision.put("priorVacancy",reuseVacancy());
        decision.put("headKey","x".repeat(4096));canonical(decision,HEAD_MAXIMUM);previous.check();current.receipt();
        try {
            if(candidateHead==null) {
                AdmissionPaths.absent(directory.resolve(HEAD_NEXT));
                try(var file=FileChannel.open(directory.resolve(HEAD_NEXT),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                    remember(HEAD_NEXT,new byte[0]);decision.put("headKey",metadata.get(HEAD_NEXT).key().toString());
                    candidateHead=new Head(canonical(decision,HEAD_MAXIMUM));point("LEARNER_SLOT_ROLLING_HEAD_CREATED");
                }
            }else {
                decision.put("headKey",candidateHead.record.get("headKey"));require(Arrays.equals(canonical(decision,HEAD_MAXIMUM),candidateHead.bytes),"learner rolling original candidate changed");
            }
            candidateHead.live=()->{previous.check();current.receipt();};candidateHead.check();
            write(HEAD_NEXT,candidateHead.bytes,"LEARNER_SLOT_ROLLING_HEAD_CANDIDATE");candidateHead.check();candidateHead.live=null;
            Files.move(directory.resolve(HEAD_NEXT),directory.resolve(HEAD),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            metadata.put(HEAD,metadata.remove(HEAD_NEXT));retiring=image;image=pending;pending=null;head=candidateHead;candidateHead=null;cleared=null;
            point("LEARNER_SLOT_ROLLING_HEAD_RENAMED");head.seal(false);current.close();if(retiring.typed!=null)retiring.typed.close();
            point("LEARNER_SLOT_ROLLING_HEAD_BEFORE_RETURN");return new View(this,true);
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
        finally{if(candidateHead!=null)candidateHead.live=null;if(head!=null)head.live=null;}
    }
    void retireSeed()throws IOException {
        try {
            check();require(committed() && head!=null && head.active && image.accounted,"learner seed retirement requires forced slot head");
            head.check();head.seal(false);seed.supersede();
            if(retiring!=null) {
                if(retiring.typed!=null)retiring.typed.close();
                for(Path file:retiring.removalOrder()) {
                    point("LEARNER_SLOT_RETIRE_BEFORE_DELETE");
                    if(Files.exists(file,LinkOption.NOFOLLOW_LINKS)){Files.delete(file);point("LEARNER_SLOT_RETIRE_MEMBER_DELETED");}
                    if(Files.exists(file.getParent(),LinkOption.NOFOLLOW_LINKS))AdmissionPaths.forceDirectory(file.getParent());
                    point("LEARNER_SLOT_RETIRE_MEMBER_PARENT_FORCED");
                }
                retiring.forceParents();point("LEARNER_SLOT_RETIRE_PARENTS_FORCED");clearSeed();
                retiring.release();seed.releaseCleared();point("LEARNER_SLOT_RETIRE_RELEASED");return;
            }
            if(pending!=null) {
                require(cleared!=null && cleared.active,"learner reuse missing forced vacancy");
                pending.checkReuse();seed.releaseCleared();return;
            }
            for(Path file:seed.removalOrder()) {
                point("LEARNER_SLOT_RETIRE_BEFORE_DELETE");
                if(Files.exists(file,LinkOption.NOFOLLOW_LINKS)){Files.delete(file);point("LEARNER_SLOT_RETIRE_MEMBER_DELETED");}
                if(Files.exists(file.getParent(),LinkOption.NOFOLLOW_LINKS))AdmissionPaths.forceDirectory(file.getParent());
                point("LEARNER_SLOT_RETIRE_MEMBER_PARENT_FORCED");
            }
            seed.forceParents();point("LEARNER_SLOT_RETIRE_PARENTS_FORCED");
            clearSeed();seed.release();point("LEARNER_SLOT_RETIRE_RELEASED");
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** A durable vacancy separates covered old-file deletion from later reuse.
     * A pending original plan explicitly binds this exact boundary. */
    private void clearSeed()throws IOException {
        check();head.check();previousVacant();
        if(cleared==null) {
            var decision=vacancy("x".repeat(4096));canonical(decision,HEAD_MAXIMUM);
            AdmissionPaths.absent(directory.resolve(CLEARED_NEXT));if(!head.rolling)AdmissionPaths.absent(directory.resolve(CLEARED));
            try(var candidate=FileChannel.open(directory.resolve(CLEARED_NEXT),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                remember(CLEARED_NEXT,new byte[0]);
                cleared=new Cleared(canonical(vacancy(metadata.get(CLEARED_NEXT).key().toString()),HEAD_MAXIMUM));
                point("LEARNER_SLOT_CLEAR_CANDIDATE_CREATED");
            }
        }
        cleared.seal();
    }
    private void previousVacant()throws IOException {if(retiring==null)seed.requireVacant();else retiring.requireVacant();}
    private void previousParents()throws IOException {if(pending!=null)pending.forceParents();else if(retiring==null)seed.forceParents();else retiring.forceParents();}
    private Map<String,Object> vacancy(String key) {
        require(head!=null,"learner vacancy selected head missing");
        return Map.of("schema","gse-v53-learner-slot-cleared/1.3","plan",hash(image.plan),"head",hash(head.bytes),
                "headKey",head.record.get("headKey"),"clearKey",key,
                "previousFiles",hash(canonical(head.record.get("previousFiles"),HEAD_MAXIMUM)),
                "previousTyped",hash(canonical(head.record.get("previousTyped"),HEAD_MAXIMUM)),
                "seedFiles",hash(canonical(head.record.get("seedFiles"),HEAD_MAXIMUM)));
    }
    private final class Cleared {
        private final byte[] bytes;
        private final Map<String,Object> record;
        private boolean active;
        Cleared(byte[] bytes) {
            this.bytes=bytes.clone();record=object(parse(bytes,HEAD_MAXIMUM));
            require(record.keySet().equals(Set.of("schema","plan","head","headKey","clearKey","previousFiles","previousTyped","seedFiles"))
                    && record.equals(vacancy(text(record.get("clearKey")))) && Arrays.equals(bytes,canonical(record,HEAD_MAXIMUM)),
                    "learner slot original vacancy binding");
        }
        void check()throws IOException {
            require(committed() && head!=null,"learner slot original vacancy location");
            String name=metadata.containsKey(CLEARED_NEXT)?CLEARED_NEXT:CLEARED;
            require(metadata.containsKey(name) && (!metadata.containsKey(CLEARED_NEXT) || !metadata.containsKey(CLEARED) || head.rolling),"learner slot original vacancy location");
            require(record.equals(vacancy(text(record.get("clearKey")))) && metadata.get(name).key().toString().equals(record.get("clearKey")),
                    "learner slot original vacancy inode changed");
            if(pending==null)previousVacant();else pending.checkReuse();
        }
        void seal()throws IOException {
            MembershipLearnerSlot.this.check();head.check();check();
            require(head.active,"learner vacancy requires forced current head");
            // Re-force absence before this decision can waive any cold charges.
            // A retained reuse plan names newly owned originals at the old paths;
            // only a complete active clear record may authorize this state.
            previousParents();point("LEARNER_SLOT_CLEAR_PARENTS_FORCED");
            if(metadata.containsKey(CLEARED_NEXT)) {
                write(CLEARED_NEXT,bytes,"LEARNER_SLOT_CLEAR_CANDIDATE");
                Files.move(directory.resolve(CLEARED_NEXT),directory.resolve(CLEARED),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                metadata.put(CLEARED,metadata.remove(CLEARED_NEXT));point("LEARNER_SLOT_CLEAR_RENAMED");
            }
            require(metadata.get(CLEARED).bytes()==bytes.length && metadata.get(CLEARED).digest().equals(hash(bytes)),"learner slot original vacancy bytes changed");
            write(CLEARED,bytes,"LEARNER_SLOT_CLEAR_ACTIVE");check();active=true;
        }
    }
    private static boolean rolling(Map<String,Object> record){return "gse-v53-learner-rolling-head/1.3".equals(record.get("schema"));}
    private static Map<String,Object> headRecord(byte[] bytes) {
        var record=object(parse(bytes,HEAD_MAXIMUM));
        var fields=new HashSet<>(Set.of("schema","plan","source","generation","receipt","seedFiles","previousFiles","previousTyped","currentFiles","headKey"));
        if(rolling(record))fields.addAll(Set.of("slot","sequence","previousAnchor","previousPlan","priorVacancy"));
        require(Arrays.equals(bytes,canonical(record,HEAD_MAXIMUM)) && record.keySet().equals(fields)
                && (rolling(record) || record.get("schema").equals("gse-v53-learner-slot-head/1.3")),"learner slot original head shape");
        if(rolling(record))require(number(record.get("sequence"))>=2 && record.get("slot").equals(slot(number(record.get("sequence")))),"learner rolling head sequence");
        for(String name:List.of("plan","source","generation","receipt"))MembershipValidation.digest((String)record.get(name));text(record.get("headKey"));
        return record;
    }
    private final class Head {
        private final byte[] bytes;
        private final Map<String,Object> record;
        private MembershipGenerationFiles.Guard live;
        private boolean active;
        private final boolean rolling;
        Head(byte[] bytes){this.bytes=bytes.clone();record=headRecord(bytes);rolling=rolling(record);}
        Image selected(){return this==candidateHead?pending:image;}
        Image previous(){return this==candidateHead?image:retiring;}
        void priorVacancy() {
            var prior=object(record.get("priorVacancy"));
            require(prior.equals(selected().value.get("vacancy")),"learner rolling vacancy binding");
            // Once the new original clear has replaced this name, it is checked
            // against this selector instead. Until then the old original stays.
            if(cleared==null || metadata.containsKey(CLEARED_NEXT) || this==candidateHead) {
                var original=metadata.get(CLEARED);
                require(original!=null && original.digest().equals(prior.get("cleared")) && original.key().toString().equals(prior.get("clearKey")),"learner rolling prior vacancy changed");
            }
        }
        void checkFiles()throws IOException {
            if(live!=null)live.check();
            String name=this==candidateHead || !committed()?HEAD_NEXT:HEAD;
            require(metadata.containsKey(name) && (name.equals(HEAD_NEXT) || !metadata.containsKey(HEAD_NEXT) || candidateHead!=null),"learner slot original head location");
            require(metadata.get(name).key().toString().equals(record.get("headKey")),"learner slot original head inode changed");
            require(seed!=null && record.get("seedFiles").equals(seed.metadata()),"learner slot seed metadata changed");
            Image selected=selected();
            if(rolling) {
                Image old=previous();require(selected!=null,"learner rolling original pair missing");
                require(selected.anchor.equals(record.get("previousAnchor")) && selected.value.get("sequence").equals(record.get("sequence"))
                        && selected.slot.equals(record.get("slot")),"learner rolling source anchor changed");
                var anchor=object(record.get("previousAnchor"));
                if(this==head && pending!=null) {
                    require(pending.replacing && cleared!=null && pending.value.get("replaces").equals(record.get("previousPlan")),"learner replacement lacks covered previous plan");
                    // The original forced vacancy permits these old bytes to
                    // be gone. Validate the closed inventories, never interpret
                    // arbitrary record paths as deletion commands.
                    var names=new TreeSet<String>();
                    for(Object raw:list(record.get("previousFiles"))) {
                        String path=(String)object(raw).get("path");if(!path.equals("."))MembershipGenerationFiles.limit(path);names.add(path);
                    }
                    require(names.size()<=33 && names.containsAll(Set.of(".","generation.gsr","source.gscp")),"learner cleared source inventory");
                    MembershipLearnerFingerprints.shape(record.get("previousFiles"),names);
                    MembershipLearnerFingerprints.shape(record.get("previousTyped"),MembershipLearnerFingerprints.typed());pending.checkReuse();
                }else {
                    require(old!=null && old.sequence()==selected.sequence()-1,"learner rolling original pair missing");
                    var terminal=object(anchor.get("previous"));var generation=old.generation.value();
                    var packet=list(old.value.get("files")).stream().map(MembershipFormat::object).filter(f->f.get("path").equals("source.gscp")).findFirst().orElseThrow();
                    require(terminal.equals(Map.of("source",packet.get("sha256"),"cut",generation.get("cut"),"catalog",generation.get("catalog"),"application",generation.get("application"))),"learner rolling previous terminal changed");
                    require(!metadata.containsKey(old.nextName),"learner retired plan has unbound candidate");
                    old.checkPlan(record.get("previousPlan"));old.checkRemaining(record.get("previousFiles"),record.get("previousTyped"),this!=candidateHead);
                }
                if(this==candidateHead)require(anchor.equals(currentAnchor()),"learner rolling candidate previous head changed");
                priorVacancy();
            }else {
                seed.checkInventories(record.get("previousFiles"),record.get("previousTyped"));
                if(pending==null)seed.checkRemaining(record.get("previousFiles"),record.get("previousTyped"),committed());
                else {require(cleared!=null,"learner reuse missing vacancy");pending.checkReuse();}
            }
            if(this==head && cleared!=null)cleared.check();
            MembershipLearnerFingerprints.check(selected.typedDirectory,MembershipLearnerFingerprints.typed(),Set.of(),record.get("currentFiles"),false,MembershipApplicationImage.MAXIMUM);
            if(live!=null)live.check();
        }
        void check()throws IOException {
            MembershipLearnerSlot.this.check();checkFiles();Image image=selected();var source=image.capsule();
            require(record.get("plan").equals(hash(image.plan)) && record.get("source").equals(hash(source.packet.bytes()))
                    && record.get("generation").equals(image.generation.digest()),"learner slot head source binding");
            require(metadata.containsKey(image.planName) && !metadata.containsKey(image.nextName) && metadata.containsKey(image.installedName)
                    && image.installedComplete(),"learner slot head requires complete installation");
            Path typed=image.typedDirectory;byte[] receipt=AdmissionPaths.read(typed.resolve("learner.gsr"),MembershipLearnerMaterialization.SUCCESSOR_PLAN);
            var decoded=decode(receipt,"records","LEARNER");long revision=number(object(object(decoded.value().get("receipt")).get("prepared")).get("revision"));
            require(record.get("receipt").equals(hash(receipt)) && Arrays.equals(receipt,MembershipLearnerPreparation.receiptBytes(source,parent.summary().request(),revision).bytes()),"learner slot head current receipt binding");
            var typedPlan=object(parse(AdmissionPaths.read(typed.resolve("preparation.json"),MembershipLearnerMaterialization.SUCCESSOR_PLAN),MembershipLearnerMaterialization.SUCCESSOR_PLAN));
            require(typedPlan.get("schema").equals("gse-v53-successor-typed/1.3") && typedPlan.get("plan").equals(parent.summary().planDigest())
                    && typedPlan.get("source").equals(record.get("source")) && typedPlan.get("receipt").equals(record.get("receipt"))
                    && typedPlan.get("materialization").equals(image.anchor.get("core")),"learner slot head current typed plan");
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
    /** Exactly one retained generation and its typed application. No lock,
     * head selection or vacancy authority lives here. Views bind this identity. */
    private final class Image implements AutoCloseable {
        private final byte[] plan,installed;
        private final Map<String,Object> value,stagingBinding,anchor;
        private final Path staging,destination,typedDirectory;
        private final String slot,planName,nextName,installedName;
        private final boolean reused,replacing;
        private final Decoded generation;
        private final MembershipIdentity peer;
        private final Map<String,MembershipReceiveFile.Retained> received=new TreeMap<>();
        private final List<MembershipResources.Lease> leases=new ArrayList<>();
        private MembershipLearnerMaterialization<?> typed;
        private MembershipResources.Lease typedImage;
        private boolean complete,accounted,released;
        Image(byte[] bytes)throws IOException {this(bytes,null);}
        Image(byte[] bytes,Map<String,Object> expectedAnchor)throws IOException {
            plan=bytes.clone();value=object(parse(plan,MAXIMUM));
            require(METADATA_MAXIMUM<=MembershipResources.Unit.MISC.bytes,"learner slot metadata capacity");
            replacing="gse-v53-learner-slot-rolling/1.3".equals(value.get("schema"));
            reused=replacing || "gse-v53-learner-slot-reuse/1.3".equals(value.get("schema"));slot=slot(sequence());
            planName=slot+".json";nextName=slot+".next.json";installedName=slot+".installed.json";
            var fields=new HashSet<>(Set.of("schema","plan","slot","sequence","anchor","path","directoryKey","staging","sourceKey","source","generation","files"));
            if(reused)fields.addAll(Set.of("vacancy","planKey"));
            if(replacing)fields.add("replaces");
            require(Arrays.equals(plan,canonical(value,MAXIMUM)) && value.keySet().equals(fields)
                    && value.get("schema").equals(replacing?"gse-v53-learner-slot-rolling/1.3":reused?"gse-v53-learner-slot-reuse/1.3":"gse-v53-learner-slot/1.3")
                    && value.get("plan").equals(parent.summary().planDigest()) && value.get("slot").equals(slot)
                    && (replacing?sequence()>=3:sequence()==(reused?2:1)),"learner slot original plan");
            if(replacing)MembershipLearnerFingerprints.shape(value.get("replaces"),planNames());
            anchor=object(value.get("anchor"));
            require(anchor.equals(expectedAnchor!=null?expectedAnchor:reused?currentAnchor():seed==null?parent.slotAnchor():seed.anchor(anchor.get("core"))),"learner slot original current head changed");
            if(reused) {
                var vacancy=object(value.get("vacancy"));
                require(vacancy.keySet().equals(Set.of("head","headKey","cleared","clearKey")) && Objects.equals(anchor.get("head"),vacancy.get("head")),"learner reuse vacancy head binding");
                MembershipValidation.digest((String)vacancy.get("head"));MembershipValidation.digest((String)vacancy.get("cleared"));
                text(vacancy.get("headKey"));text(vacancy.get("clearKey"));
            }
            if(reused && expectedAnchor==null)require(value.get("vacancy").equals(reuseVacancy()),"learner reuse original vacancy changed");
            destination=slot.equals("a")?MembershipLearnerSuccessor.directory(parent.summary()).resolve(MembershipLearnerSuccessor.SOURCE):directory.resolve(SOURCE);
            typedDirectory=slot.equals("a")?MembershipLearnerSuccessor.typedDirectory(parent.summary()):MembershipLearnerSlot.typedDirectory(parent.summary());
            var originalPath=MembershipLearnerAdmissionPlan.binding(object(value.get("path")));
            stagingBinding=MembershipLearnerAdmissionPlan.binding(object(value.get("staging")));staging=MembershipLearnerAdmissionPlan.path(stagingBinding);
            require(directory.equals(MembershipLearnerAdmissionPlan.path(originalPath)),"learner slot exact path");
            paths(staging,anchor);require(text(value.get("directoryKey")).equals(directoryKey.toString()),"learner slot directory replaced");
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
        void reserve()throws IOException {
            long metadata=0;var resources=parent.resources();
            for(Object raw:list(value.get("files"))){var f=object(raw);if(!((String)f.get("path")).endsWith(".image"))metadata=Math.addExact(metadata,number(f.get("size")));}
            leases.add(resources.reserve(MembershipResources.Unit.GENERATION,"learner-slot-"+slot,metadata));
            for(Object raw:list(value.get("files"))){var f=object(raw);if(((String)f.get("path")).endsWith(".image"))
                leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"learner-slot-"+slot+":"+f.get("path"),number(f.get("size"))));}
            capsule();
            if(Files.exists(AdmissionPaths.safe(typedDirectory),LinkOption.NOFOLLOW_LINKS))reserveTypedImage();
            accounted=true;
        }
        SortedSet<String> sourceNames(){var names=new TreeSet<String>(List.of("."));for(Object raw:list(value.get("files")))names.add((String)object(raw).get("path"));return names;}
        SortedSet<String> planNames(){return new TreeSet<>(List.of(".",planName,installedName));}
        Set<String> otherNames(){var names=new HashSet<>(MEMBERS);names.remove(planName);names.remove(installedName);return names;}
        Object planFiles()throws IOException {return MembershipLearnerFingerprints.capture(directory,planNames(),otherNames(),false,MAXIMUM);}
        void checkPlan(Object expected)throws IOException {MembershipLearnerFingerprints.check(directory,planNames(),otherNames(),expected,false,MAXIMUM);}
        Object sourceFiles()throws IOException {return MembershipLearnerFingerprints.capture(destination,sourceNames(),Set.of(),false,MembershipApplicationImage.MAXIMUM);}
        Object typedFiles()throws IOException {return MembershipLearnerFingerprints.capture(typedDirectory,MembershipLearnerFingerprints.typed(),Set.of(),false,MembershipApplicationImage.MAXIMUM);}
        void checkRemaining(Object files,Object typed,boolean remaining)throws IOException {
            MembershipLearnerFingerprints.check(destination,sourceNames(),Set.of(),files,remaining,MembershipApplicationImage.MAXIMUM);
            MembershipLearnerFingerprints.check(typedDirectory,MembershipLearnerFingerprints.typed(),Set.of(),typed,remaining,MembershipApplicationImage.MAXIMUM);
        }
        List<Path> removalOrder(){var paths=new ArrayList<>(MembershipLearnerFingerprints.removalOrder(destination,sourceNames()));paths.addAll(MembershipLearnerFingerprints.removalOrder(typedDirectory,MembershipLearnerFingerprints.typed()));return paths;}
        void requireVacant()throws IOException {AdmissionPaths.absent(destination);AdmissionPaths.absent(typedDirectory);}
        void forceParents()throws IOException {AdmissionPaths.forceDirectory(destination.getParent());AdmissionPaths.forceDirectory(typedDirectory.getParent());}
        void reserveRetired()throws IOException {
            require(!accounted && received.isEmpty() && leases.isEmpty(),"learner retired image already accounted");
            long bytes=0;for(Object raw:list(value.get("files"))){var file=object(raw);if(!((String)file.get("path")).endsWith(".image"))bytes=Math.addExact(bytes,number(file.get("size")));}
            leases.add(parent.resources().reserve(MembershipResources.Unit.GENERATION,"learner-retired-"+slot,bytes));
            for(Object raw:list(value.get("files"))){var file=object(raw);if(((String)file.get("path")).endsWith(".image"))leases.add(parent.resources().reserve(MembershipResources.Unit.APPLICATION,"learner-retired-"+file.get("path"),number(file.get("size"))));}
            reserveTypedImage();accounted=true;
        }
        void release()throws IOException {requireVacant();close();received.clear();leases.clear();typed=null;typedImage=null;released=true;}
        long sequence(){return number(value.get("sequence"));}
        boolean planActive(){var file=metadata.get(planName);return file!=null && file.bytes()==plan.length && file.digest().equals(hash(plan)) && (!reused || file.key().toString().equals(value.get("planKey")));}
        boolean installedComplete(){var file=metadata.get(installedName);return file!=null && file.bytes()==installed.length && file.digest().equals(hash(installed));}
        boolean covered(String name,FileIdentity file) {
            if(!replacing || file==null || !(name.equals(planName)||name.equals(installedName)))return false;
            String fingerprint=hash(canonical(Map.of("key",file.key().toString(),"bytes",file.bytes(),"sha256",file.digest()),16384));
            return list(value.get("replaces")).contains(Map.of("path",name,"sha256",fingerprint));
        }
        void checkReuse()throws IOException {
            require(reused && sequence()==nextSequence(image.sequence()) && anchor.equals(currentAnchor()) && value.get("vacancy").equals(reuseVacancy()),"learner reuse original vacancy changed");
            String name=metadata.containsKey(nextName)?nextName:planName;
            require(metadata.containsKey(name) && text(value.get("planKey")).equals(metadata.get(name).key().toString()),"learner reuse original plan inode changed");
            if(metadata.containsKey(nextName))require(text(value.get("planKey")).equals(metadata.get(nextName).key().toString()),"learner reuse candidate inode changed");
            if(replacing) {
                require(head.rolling && value.get("replaces").equals(head.record.get("previousPlan")),"learner replacement lacks covered previous plan");
                require(list(value.get("replaces")).contains(Map.of("path",".","sha256",hash(canonical(Map.of("key",directoryKey.toString(),"directory",true),16384)))),"learner replacement directory binding");
                if(!planActive()) {
                    require(metadata.containsKey(nextName) && covered(planName,metadata.get(planName)) && covered(installedName,metadata.get(installedName)),"learner replacement original metadata changed");
                    require(Files.exists(staging,LinkOption.NOFOLLOW_LINKS),"learner replacement source moved before plan");
                }else {
                    require(!metadata.containsKey(nextName),"learner replacement duplicate candidate");
                    if(covered(installedName,metadata.get(installedName)))require(Files.exists(staging,LinkOption.NOFOLLOW_LINKS),"learner replacement old marker after source move");
                }
            }
            locate();
            // No old materialized application may survive into a new installation.
            if(!installedComplete())AdmissionPaths.absent(typedDirectory);
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
        private void reserveTypedImage()throws IOException {
            check();if(typedImage==null){typedImage=parent.resources().reserve(MembershipResources.Unit.APPLICATION,"learner-slot-"+slot+"-typed",MembershipApplicationImage.MAXIMUM);leases.add(typedImage);}
        }
        private MembershipLearnerSlot owner(){return MembershipLearnerSlot.this;}
        @Override public void close()throws IOException {
            var children=new ArrayList<AutoCloseable>();children.add(typed);children.addAll(received.values());children.addAll(leases);
            MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
        }
    }
    static final class Stored implements MembershipCapsule.StoredCopy {
        private final Image image;private final Map<String,byte[]> files;private boolean active=true;
        private Stored(Image image,Map<String,byte[]> files){this.image=image;this.files=files;}
        @Override public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            image.owner().check();require(active && Arrays.equals(root.bytes(),image.owner().parent.root().bytes()) && Arrays.equals(packet.bytes(),files.get("source.gscp")),"learner slot stored original");
        }
        @Override public byte[] ancestry(){return files.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        @Override public Optional<byte[]> coverage(){return Optional.ofNullable(files.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        @Override public Decoded record(String name,String kind){return decode(Objects.requireNonNull(files.get(name)),"records",kind);}
    }
    static final class View implements MembershipLearnerImageSource {
        private final MembershipLearnerSlot owner;
        private final Image image;
        private final boolean current;
        private View(MembershipLearnerSlot owner){this(owner,false);}
        private View(MembershipLearnerSlot owner,boolean current){this(owner,owner.image,current);}
        private View(MembershipLearnerSlot owner,Image image,boolean current){this.owner=owner;this.image=image;this.current=current;}
        @Override public MembershipCapsule source()throws IOException {
            owner.check();require(owner.image==image || owner.pending==image,"learner slot view superseded");require(image.complete && image.accounted,"learner slot installation not forced");
            require(current?owner.image==image && owner.committed():owner.pending==image || !owner.committed() || owner.head!=null && !owner.head.active,"learner slot view superseded");
            if(current){require(owner.head!=null && owner.head.active,"learner slot head not forced");owner.head.checkFiles();}
            return image.capsule();
        }
        @Override public MembershipLearnerStore store()throws IOException {source();return owner.parent;}
        @Override public Path typedDirectory()throws IOException {source();return image.typedDirectory;}
        @Override public byte[] originalImage(String digest,long size)throws IOException {
            var source=source();require(Objects.equals(source.packet.images().get(digest),size),"learner slot original image binding");
            byte[] bytes=AdmissionPaths.read(image.destination.resolve(digest+".image"),Math.toIntExact(size));
            require(bytes.length==size && hash(bytes).equals(digest),"learner slot original image bytes");source();return bytes;
        }
        @Override public void requireTypedPaths(Path core,Path typed)throws IOException {
            source();var binding=MembershipLearnerAdmissionPlan.binding(object(image.anchor.get("core")));AdmissionPaths.recheck(binding);
            require(core.equals(MembershipLearnerAdmissionPlan.path(binding)) && typed.equals(typedDirectory()),"learner slot reserved typed/core path changed");owner.paths(image.staging,image.anchor);
        }
        @Override public void reserveTypedImage()throws IOException {source();image.reserveTypedImage();}
        @Override public void attachTyped(MembershipLearnerMaterialization<?> typed)throws IOException {
            source();require(image.typed==null || image.typed.closed(),"learner slot typed preparation already owned");image.typed=Objects.requireNonNull(typed);
        }
        View promote(MembershipLearnerMaterialization<?> typed,MembershipLearnerMaterialization.CurrentHead previous)throws IOException {
            source();require(!current,"learner slot already current");
            return owner.pending==image?owner.promoteRolling(typed,previous):owner.promote(typed,previous);
        }
        void retirePredecessor()throws IOException {source();require(current,"learner slot retirement requires selected head");owner.retireSeed();}
        @Override public void requireCurrentTyped(MembershipLearnerMaterialization<?> typed)throws IOException {
            source();require(current && image.typed==typed,"learner inactive slot is not the current head");
            require(owner.seed.retired() && owner.cleared!=null && owner.cleared.active && (owner.retiring==null || owner.retiring.released),"learner current slot requires forced seed retirement");
        }
        @Override public void requireRefreshPaths(Path... paths)throws IOException {
            source();require(current,"learner inactive slot cannot acquire another source");
            var summary=owner.parent.summary();var all=new ArrayList<>(List.of(paths));
            all.add(owner.directory);all.add(image.staging);all.add(MembershipLearnerSlot.typedDirectory(summary));
            all.add(MembershipLearnerSuccessor.directory(summary));all.add(MembershipLearnerSuccessor.typedDirectory(summary));
            all.add(MembershipLearnerMaterialization.directory(summary));all.add(summary.request().operationDirectory());all.add(summary.request().replicaDirectory());
            AdmissionPaths.disjoint(all);
        }
    }
    @Override public void close()throws IOException {
        if(closed)return;closed=true;var children=new ArrayList<AutoCloseable>();children.add(pending);children.add(retiring);children.add(image);children.add(seed);children.add(lock);
        MembershipLearnerSource.closeChildren(children.toArray(AutoCloseable[]::new));
    }
}
