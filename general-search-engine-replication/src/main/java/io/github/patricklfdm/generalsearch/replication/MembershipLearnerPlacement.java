package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original-inode placement under transferred learner custody. This transaction
 * does not admit a voter or delete predecessors. Explicit cold recovery must
 * reopen original semantic owners; physical inspection is not that capability. */
final class MembershipLearnerPlacement implements AutoCloseable {
    static final int MAXIMUM=64*1024;
    static final String PLAN="placement.json",READY="placed.json";
    static final List<String> MOVES=List.of("genesis.gsr",MembershipBallotAllocator.CURRENT,"grants.gsr",
            MembershipPendingAccept.FILE,"sources","generations",MembershipCurrentGeneration.SELECTOR);
    private final MembershipLearnerCustody custody;
    private final Original original;
    private final Path directory;
    private final Map<String,Object> binding;
    private final Map<String,FileIdentity> records=new TreeMap<>();
    private Object directoryKey;
    private byte[] plan;
    private boolean planForced,complete;

    static Path directory(MembershipLearnerPlan summary) {
        return summary.request().operationDirectory().resolveSibling(".gse-v53-learner-placement-"+summary.planDigest());
    }
    private MembershipLearnerPlacement(MembershipLearnerCustody custody)throws IOException {
        this.custody=Objects.requireNonNull(custody);var summary=custody.summary();
        original=new Original(summary,custody.originalDecision());directory=directory(summary);binding=AdmissionPaths.binding(directory);
        AdmissionPaths.absent(directory);original.project();
        require(Files.getFileStore(original.stage).equals(Files.getFileStore(original.replica)),"learner placement requires atomic same-filesystem moves");
        original.plan(binding,"x".repeat(4096)); // Capacity refusal precedes any directory write.
    }
    static MembershipLearnerPlacement install(MembershipLearnerCustody custody,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);
        require(custody.placement()==null,"learner placement already started; original resume required");
        var result=new MembershipLearnerPlacement(custody);custody.attachPlacement(result);
        Files.createDirectory(result.directory);result.directoryKey=key(result.directory);result.plan=result.original.plan(result.binding,result.directoryKey.toString());
        AdmissionPaths.forceDirectory(result.directory.getParent());result.point(cut,"LEARNER_PLACEMENT_DIRECTORY_FORCED");
        result.forcePlan(cut,false);result.finish(cut);return result;
    }
    /** Continue only under the same live, exclusive installation custody. A
     * caller cannot replace missing/torn originals with a fresh transaction. */
    static MembershipLearnerPlacement resume(MembershipLearnerCustody custody,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);
        var result=custody.placement();require(result!=null,"learner placement has no live original transaction");
        result.forcePlan(cut,true);result.finish(cut);return result;
    }
    /** Reopen actual historical owners and validate their typed source and
     * matching INTENT without writes before transferring custody again. */
    static <K,T> MembershipLearnerPlacement recover(MembershipLearnerPlan summary,MembershipResources resources,
            io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);resources.requireCompleteStorage(Set.of());
        try(var recovery=new Recovery(summary);
                var store=MembershipLearnerStore.reopenPlacement(summary,resources,recovery)) {
            var receipt=recovery.receipt();long revision=number(object(object(receipt.value().get("receipt")).get("prepared")).get("revision"));
            var input=store.retiring()?MembershipLearnerPreparation.from(store.currentSource(),revision):MembershipLearnerPreparation.from(store,revision);
            try(var typed=MembershipLearnerMaterialization.prepare(input,captured,config,e->{})) {
                MembershipLearnerHead head=store.retiring()?typed.currentHead():typed.retainGeneration();
                require(Arrays.equals(head.receipt().bytes(),receipt.bytes()),"learner placement original typed receipt changed");
                try(var intent=MembershipLearnerIntent.resume(head,e->{});
                        var stage=MembershipLearnerVoterStage.reopenPlacement(intent.forced(),recovery)) {
                    stage.readyCapability().check();recovery.check();
                    recovery.checkJoined(intent.forced().source(),head.receipt(),captured,config);
                    cut.at("LEARNER_PLACEMENT_RECOVERY_VERIFIED");recovery.check();
                    var custody=MembershipLearnerCustody.recoverPlacement(stage.readyCapability(),recovery,cut);
                    try{return resume(custody,cut);}catch(IOException|RuntimeException|Error error){
                        try{custody.close();}catch(Exception close){error.addSuppressed(close);}throw error;
                    }
                }
            }
        }
    }
    private MembershipLearnerPlacement(MembershipLearnerCustody custody,Recovery recovery)throws IOException {
        recovery.check();this.custody=custody;original=recovery.original;directory=directory(original.summary);
        binding=AdmissionPaths.binding(directory);directoryKey=recovery.directoryKey;plan=recovery.plan.clone();
        records.putAll(recovery.records);planForced=true;
    }
    static MembershipLearnerPlacement restored(MembershipLearnerCustody custody,Recovery recovery)throws IOException {
        return new MembershipLearnerPlacement(custody,recovery);
    }
    /** Private, original-only read projection. Issued only by recover(), never
     * from a caller map. It cannot write, force, vote or outlive that reopen. */
    static final class Recovery implements AutoCloseable {
        private final Original original;
        private final byte[] plan;
        private final Object directoryKey;
        private final Map<String,FileIdentity> records=new TreeMap<>();
        private final int moved;
        private boolean closed;
        private Recovery(MembershipLearnerPlan summary)throws IOException {
            inspectOriginal(summary);
            original=new Original(summary,AdmissionPaths.read(MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE),MembershipLearnerCustody.MAXIMUM));
            Path directory=directory(summary);directoryKey=key(directory);plan=original.plan(AdmissionPaths.binding(directory),directoryKey.toString());
            for(String name:children(directory,3)) {
                byte[] bytes=AdmissionPaths.read(directory.resolve(name),MAXIMUM);records.put(name,inspect(directory.resolve(name),bytes.length,hash(bytes)));
            }
            moved=original.project();check();
        }
        // Internal getters run only within recover()'s read-only validation
        // scope. Full inventory checks bracket that scope and every subsequent
        // custody force through inventory(); no unverified owner escapes it.
        void readGuard(){require(!closed,"learner placement recovery projection expired");}
        void check()throws IOException {
            readGuard();original.checkDecision();
            require(original.project()==moved,"learner placement moved during read-only recovery");
            Path directory=directory(original.summary);
            require(directoryKey.equals(key(directory)) && children(directory,3).equals(records.keySet()),"learner placement recovery directory changed");
            AdmissionPaths.exact(directory.resolve(PLAN),plan);
            for(var row:records.entrySet())require(row.getValue().equals(inspect(directory.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),
                    "learner placement original recovery record changed");
        }
        Set<String> replicaNames()throws IOException {
            readGuard();var names=new TreeSet<String>();
            for(String name:Original.files(Original.root(original.inventory,"replica")).keySet())if(!name.equals(".") && !name.contains("/"))names.add(name);
            return names;
        }
        Path stageMember(String name)throws IOException {
            readGuard();Path relative=Path.of(name);require(!relative.isAbsolute() && relative.normalize().equals(relative)
                    && !name.startsWith(".."),"learner placement relative stage member");
            String first=relative.getName(0).toString();int index=MOVES.indexOf(first);
            return (index>=0 && index<moved?original.replica:original.stage).resolve(relative);
        }
        List<Object> inventory(Set<Path> managed)throws IOException {
            check();for(var row:original.inventory){var value=object(row);
                require(!Boolean.TRUE.equals(value.get("present")) || managed.contains(original.roots.get((String)value.get("name"))),
                        "learner placement recovery has unowned originals");}
            return new ArrayList<>(original.inventory);
        }
        Decoded receipt()throws IOException {
            check();Decoded result=null;
            for(String name:List.of("initialTyped","successorTyped","slotTyped")) {
                Path file=original.roots.get(name).resolve(MembershipLearnerMaterialization.RECEIPT);
                if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))continue;
                var decoded=decode(AdmissionPaths.read(file,16384),"records","LEARNER");
                if(decoded.digest().equals(original.value.get("receipt"))) {
                    require(result==null,"learner placement ambiguous original typed receipt");result=decoded;
                }
            }
            require(result!=null,"learner placement original typed receipt missing");check();return result;
        }
        private <K,T> void checkJoined(MembershipCapsule source,Decoded receipt,
                io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> captured,MembershipReplicaConfig<K,T> config)throws IOException {
            check();if(!records.containsKey(MembershipLearnerJoinedAdmission.FILE))return;
            byte[] expected=MembershipLearnerJoinedAdmission.original(original.summary,receipt,source);
            MembershipLearnerJoinedAdmission.configuration(original.summary,expected,captured,config);
            MembershipLearnerJoinedAdmission.prefix(directory(original.summary).resolve(MembershipLearnerJoinedAdmission.FILE),expected);
            check();
        }
        @Override public void close(){closed=true;}
    }
    private void forcePlan(MembershipBallotAllocator.Cut cut,boolean resume)throws IOException {
        custody.check();
        if(resume)require(plan!=null && records.containsKey(PLAN) && records.get(PLAN).bytes()==plan.length,
                "learner placement incomplete original decision");
        write(PLAN,plan,cut);AdmissionPaths.forceDirectory(directory);AdmissionPaths.forceDirectory(directory.getParent());
        planForced=true;point(cut,"LEARNER_PLACEMENT_DECISION_FORCED");
    }
    private void finish(MembershipBallotAllocator.Cut cut)throws IOException {
        custody.check();require(planForced,"learner placement decision not forced");
        int completed=original.project();
        for(int index=0;index<completed;index++) {
            custody.check();String name=MOVES.get(index);forceMoved(original.replica.resolve(name));
            AdmissionPaths.forceDirectory(original.stage);AdmissionPaths.forceDirectory(original.replica);
            point(cut,"LEARNER_PLACEMENT_PARENTS_FORCED:"+name);
        }
        AdmissionPaths.forceDirectory(original.stage);AdmissionPaths.forceDirectory(original.replica);
        point(cut,"LEARNER_PLACEMENT_PREFIX_RESEALED");
        for(int index=completed;index<MOVES.size();index++) {
            String name=MOVES.get(index);point(cut,"LEARNER_PLACEMENT_BEFORE_MOVE:"+name);
            Path from=original.stage.resolve(name),to=original.replica.resolve(name);AdmissionPaths.absent(to);
            Files.move(from,to,StandardCopyOption.ATOMIC_MOVE);point(cut,"LEARNER_PLACEMENT_MOVED:"+name);
            forceMoved(to);AdmissionPaths.forceDirectory(original.stage);AdmissionPaths.forceDirectory(original.replica);
            point(cut,"LEARNER_PLACEMENT_PARENTS_FORCED:"+name);
        }
        // A move may have completed immediately before an interruption. Always
        // re-force the complete original payload and both parents on resume.
        for(String name:MOVES){custody.check();forceMoved(original.replica.resolve(name));}
        AdmissionPaths.forceDirectory(original.stage);AdmissionPaths.forceDirectory(original.replica);
        point(cut,"LEARNER_PLACEMENT_PAYLOAD_FORCED");
        write(READY,original.ready(plan,records.get(PLAN).key()),cut);complete=true;point(cut,"LEARNER_PLACEMENT_COMPLETE");
    }
    private static void forceMoved(Path path)throws IOException {
        if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS)) {
            try(var files=Files.walk(path)) {
                for(Path member:files.sorted(Comparator.reverseOrder()).toList()) {
                    if(Files.isDirectory(member,LinkOption.NOFOLLOW_LINKS))AdmissionPaths.forceDirectory(member);
                    else try(var channel=MembershipFileAccess.open(member,StandardOpenOption.WRITE)){channel.force(true);}
                }
            }
        }else try(var channel=MembershipFileAccess.open(path,StandardOpenOption.WRITE)){channel.force(true);}
    }
    private void point(MembershipBallotAllocator.Cut cut,String event)throws IOException {custody.check();cut.at(event);custody.check();}
    private void remember(String name,byte[] bytes,Object inode)throws IOException {
        var identity=inspect(directory.resolve(name),bytes.length,hash(bytes));require(identity.key().equals(inode),"learner placement record replaced");records.put(name,identity);
    }
    private void write(String name,byte[] wanted,MembershipBallotAllocator.Cut cut)throws IOException {
        custody.check();Path file=directory.resolve(name);var prior=records.get(name);
        if(prior!=null)require(Arrays.equals(AdmissionPaths.read(file,MAXIMUM),Arrays.copyOf(wanted,Math.toIntExact(prior.bytes()))),"learner placement record differs from original prefix");
        try(var channel=MembershipFileAccess.open(file,prior==null?Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            Object inode=key(file);if(prior==null){remember(name,new byte[0],inode);point(cut,"LEARNER_PLACEMENT_CREATED:"+name);}
            int offset=Math.toIntExact(records.get(name).bytes());require(offset<=wanted.length,"learner placement record length");channel.position(offset);
            if(offset<wanted.length) {
                int half=offset+(wanted.length-offset)/2;AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,offset,half));
                remember(name,Arrays.copyOf(wanted,half),inode);point(cut,"LEARNER_PLACEMENT_PREFIX_WRITTEN:"+name);
                AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,half,wanted.length));remember(name,wanted,inode);point(cut,"LEARNER_PLACEMENT_WRITTEN:"+name);
            }
            channel.force(true);point(cut,"LEARNER_PLACEMENT_FORCED:"+name);
        }
        AdmissionPaths.forceDirectory(directory);point(cut,"LEARNER_PLACEMENT_RECORD_PARENT_FORCED:"+name);
    }
    /** Called by custody after validating its actual locks, leases and decision.
     * Only the original allowed inode relocations may change its inventory. */
    void checkOriginals()throws IOException {
        original.checkDecision();int moved=original.project();
        require(planForced || moved==0,"learner payload moved before forced decision");AdmissionPaths.recheck(binding);
        checkRecords();
        require(!complete || moved==MOVES.size() && records.containsKey(READY),"learner placement incomplete payload");
    }
    void checkRecords()throws IOException {
        original.checkDecision();AdmissionPaths.recheck(binding);
        if(directoryKey==null){AdmissionPaths.absent(directory);return;}
        require(directoryKey.equals(key(directory)) && children(directory,3).equals(records.keySet()),"learner placement directory changed");
        for(var row:records.entrySet())require(row.getValue().equals(inspect(directory.resolve(row.getKey()),row.getValue().bytes(),row.getValue().digest())),
                "learner placement original record changed");
    }
    void check()throws IOException {custody.check();require(complete,"learner placement not complete");}
    Path replica()throws IOException {check();return original.replica;}
    MembershipLearnerCustody custody()throws IOException {check();return custody;}
    void forceJoined(MembershipLearnerJoinedAdmission admission,MembershipBallotAllocator.Cut cut)throws IOException {
        check();Objects.requireNonNull(admission).checkPlacement(this);String name=MembershipLearnerJoinedAdmission.FILE;
        if(!records.containsKey(name)) {
            Path file=directory.resolve(name);
            try(var channel=MembershipFileAccess.open(file,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                remember(name,new byte[0],key(file));point(cut,"LEARNER_PLACEMENT_CREATED:"+name);
            }
        }
        byte[] bytes=admission.forPlacement(this);require(bytes.length<=MembershipLearnerJoinedAdmission.MAXIMUM,"learner joined admission capacity");
        write(name,bytes,cut);point(cut,"LEARNER_JOINED_ADMISSION_FORCED");
    }
    void checkJoined(byte[] expected)throws IOException {
        check();var file=records.get(MembershipLearnerJoinedAdmission.FILE);
        require(file!=null && file.bytes()==expected.length && file.digest().equals(hash(expected)),"learner joined admission original record changed");
    }
    @Override public void close()throws IOException {custody.close();}

    /** Physical inspection only: no lock/lease ownership, proof admission, file
     * mutation or restart permission is returned from a cold filesystem read. */
    record Inspection(String status,int moved,String source,String receipt) {}
    /** Original installed inventory derived only from the complete custody and
     * placement decisions. Does not tolerate missing installed files, inspect
     * predecessor deletion or return an ownership/deletion capability. */
    static Map<String,Object> installedOriginal(MembershipLearnerPlan summary)throws IOException {
        return Collections.unmodifiableMap(Original.files(Original.root(placedOriginalInventory(summary),"replica")));
    }
    static List<?> placedOriginalInventory(MembershipLearnerPlan summary)throws IOException {
        var original=new Original(summary,AdmissionPaths.read(MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE),MembershipLearnerCustody.MAXIMUM));
        Path directory=directory(summary);
        require(children(directory,3).equals(Set.of(PLAN,READY,MembershipLearnerJoinedAdmission.FILE)),"joined original placement inventory");
        byte[] plan=original.plan(AdmissionPaths.binding(directory),key(directory).toString());AdmissionPaths.exact(directory.resolve(PLAN),plan);
        AdmissionPaths.exact(directory.resolve(READY),original.ready(plan,key(directory.resolve(PLAN))));
        var installed=Original.files(Original.root(original.inventory,"replica"));
        for(var row:Original.files(Original.root(original.inventory,"voterStage")).entrySet()) {
            String name=row.getKey();if(MOVES.stream().anyMatch(move->name.equals(move)||name.startsWith(move+"/")))
                require(installed.putIfAbsent(name,row.getValue())==null,"joined installed duplicate original");
        }
        var staged=Original.files(Original.root(original.inventory,"voterStage"));
        staged.keySet().removeIf(name->MOVES.stream().anyMatch(move->name.equals(move)||name.startsWith(move+"/")));
        var projected=new ArrayList<Object>();
        for(Object raw:original.inventory) {
            var row=new TreeMap<>(object(raw));
            if(row.get("name").equals("replica"))row.put("files",Original.rows(installed));
            if(row.get("name").equals("voterStage"))row.put("files",Original.rows(staged));
            projected.add(Collections.unmodifiableMap(row));
        }
        original.checkDecision();return List.copyOf(projected);
    }
    /** The small original typed plan/receipt remain admission proof after its
     * backup and receiving images retire. Never infer configuration from only
     * the joined record's self-reported digest. */
    static Path typedOriginal(MembershipLearnerPlan summary,Decoded receipt)throws IOException {
        var original=new Original(summary,AdmissionPaths.read(MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE),MembershipLearnerCustody.MAXIMUM));
        Path selected=null;
        for(String name:List.of("initialTyped","successorTyped","slotTyped")) {
            var row=original.inventory.stream().map(MembershipFormat::object).filter(v->v.get("name").equals(name)).findFirst().orElseThrow();
            if(!Boolean.TRUE.equals(row.get("present")))continue;var files=Original.files(row);var expected=files.get(MembershipLearnerMaterialization.RECEIPT);
            if(expected==null || !object(expected).get("sha256").equals(receipt.digest()))continue;
            require(selected==null,"joined original ambiguous typed proof");selected=original.roots.get(name);
            require(key(selected).toString().equals(object(files.get(".")).get("key")),"joined original typed directory changed");
            for(String file:List.of(MembershipLearnerMaterialization.PLAN,MembershipLearnerMaterialization.RECEIPT)) {
                var identity=object(Objects.requireNonNull(files.get(file)));long size=number(identity.get("size"));
                require(size>0 && size<=(file.equals(MembershipLearnerMaterialization.PLAN)?MembershipLearnerMaterialization.MAXIMUM_PLAN:16384),"joined original typed proof capacity");
                var actual=inspect(selected.resolve(file),size,(String)identity.get("sha256"));
                require(actual.key().toString().equals(identity.get("key")),"joined original typed proof replaced");
            }
            AdmissionPaths.exact(selected.resolve(MembershipLearnerMaterialization.RECEIPT),receipt.bytes());
        }
        require(selected!=null,"joined original typed proof missing");original.checkDecision();return selected;
    }
    static Inspection inspectOriginal(MembershipLearnerPlan summary)throws IOException {
        var original=new Original(summary,AdmissionPaths.read(MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE),MembershipLearnerCustody.MAXIMUM));
        Path directory=directory(summary);var names=children(directory,3);require(names.contains(PLAN) && Set.of(PLAN,READY,MembershipLearnerJoinedAdmission.FILE).containsAll(names),"learner placement original plan missing");
        byte[] plan=original.plan(AdmissionPaths.binding(directory),key(directory).toString());AdmissionPaths.exact(directory.resolve(PLAN),plan);
        var identity=inspect(directory.resolve(PLAN),plan.length,hash(plan));int moved=original.project();boolean complete=false;
        if(names.contains(READY)) {
            byte[] ready=original.ready(plan,identity.key()),actual=AdmissionPaths.read(directory.resolve(READY),MAXIMUM);
            require(moved==MOVES.size() && actual.length<=ready.length && Arrays.equals(actual,Arrays.copyOf(ready,actual.length)),"learner placement invalid completion prefix");complete=Arrays.equals(actual,ready);
        }
        if(names.contains(MembershipLearnerJoinedAdmission.FILE)) {
            require(complete,"learner joined admission before complete placement");
            AdmissionPaths.read(directory.resolve(MembershipLearnerJoinedAdmission.FILE),MembershipLearnerJoinedAdmission.MAXIMUM);
        }
        original.checkDecision();require(identity.equals(inspect(directory.resolve(PLAN),plan.length,hash(plan))),"learner placement decision changed during inspection");
        return new Inspection(complete?"PLACED":"PARTIAL",moved,(String)original.value.get("source"),(String)original.value.get("receipt"));
    }

    private static final class Original {
        final MembershipLearnerPlan summary;
        final byte[] decision;
        final FileIdentity identity;
        final Map<String,Object> value;
        final Map<String,Path> roots;
        final List<?> inventory;
        final Path replica,stage;
        Original(MembershipLearnerPlan summary,byte[] decision)throws IOException {
            this.summary=summary;this.decision=decision.clone();value=object(parse(decision,MembershipLearnerCustody.MAXIMUM));
            require(value.keySet().equals(Set.of("schema","plan","path","receipt","source","roots","directoryKey"))
                    && value.get("schema").equals("gse-v53-learner-custody/1.3") && value.get("plan").equals(summary.planDigest())
                    && Arrays.equals(decision,canonical(value,MembershipLearnerCustody.MAXIMUM)),"learner placement original custody shape");
            MembershipValidation.digest((String)value.get("source"));MembershipValidation.digest((String)value.get("receipt"));
            roots=MembershipLearnerCustody.roots(summary);replica=roots.get("replica");stage=roots.get("voterStage");inventory=list(value.get("roots"));
            require(inventory.size()==roots.size(),"learner placement original roots");var seen=new HashSet<String>();
            for(Object raw:inventory) {
                var row=object(raw);String name=(String)row.get("name");boolean present=Boolean.TRUE.equals(row.get("present"));
                require(row.keySet().equals(present?Set.of("name","path","present","files"):Set.of("name","path","present"))
                        && row.get("present") instanceof Boolean && roots.containsKey(name) && seen.add(name)
                        && row.get("path").equals(AdmissionPaths.binding(roots.get(name))),"learner placement root binding");
                if(present)files(row); // Reject duplicate or escaping inventory names.
            }
            var source=files(root(inventory,"voterStage"));var destination=files(root(inventory,"replica"));
            require(source.keySet().containsAll(MOVES) && MOVES.stream().noneMatch(destination::containsKey),"learner placement original destinations");
            for(String preserved:List.of("root.gsr","node.gsr","replica.lock")) {
                var a=object(source.get(preserved));var b=object(destination.get(preserved));
                require(a.get("size").equals(b.get("size")) && a.get("sha256").equals(b.get("sha256")),"learner placement immutable replica differs");
            }
            Path file=MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE);identity=inspect(file,decision.length,hash(decision));checkDecision();
        }
        void checkDecision()throws IOException {
            Path directory=MembershipLearnerCustody.directory(summary);require(value.get("path").equals(AdmissionPaths.binding(directory))
                    && value.get("directoryKey").equals(key(directory).toString()) && children(directory,1).equals(Set.of(MembershipLearnerCustody.FILE))
                    && identity.equals(inspect(directory.resolve(MembershipLearnerCustody.FILE),decision.length,hash(decision))),"learner placement custody decision changed");
        }
        byte[] plan(Map<String,Object> path,String directoryKey) {
            return canonical(Map.of("schema","gse-v53-learner-placement/1.3","plan",summary.planDigest(),"path",path,"directoryKey",directoryKey,
                    "custody",Map.of("key",identity.key().toString(),"size",identity.bytes(),"sha256",identity.digest()),"moves",MOVES),MAXIMUM);
        }
        byte[] ready(byte[] plan,Object planKey) {
            return canonical(Map.of("schema","gse-v53-learner-placed/1.3","plan",hash(plan),"planKey",planKey.toString(),"custody",hash(decision),"moves",MOVES),MAXIMUM);
        }
        int project()throws IOException {
            var actual=MembershipLearnerCustody.capture(roots,null);var a=root(actual,"voterStage");var b=root(actual,"replica");
            var source=files(a);var destination=files(b);int moved=0;boolean stayed=false;
            for(String name:MOVES) {
                boolean from=source.containsKey(name),to=destination.containsKey(name);require(from!=to,"learner placement needs exactly one original location: "+name);
                if(from){stayed=true;continue;}require(!stayed,"learner placement nonprefix relocation");moved++;
                for(String path:new ArrayList<>(destination.keySet()))if(path.equals(name)||path.startsWith(name+"/")) {
                    require(!source.containsKey(path),"learner placement duplicate descendant");source.put(path,destination.remove(path));
                }
            }
            a.put("files",rows(source));b.put("files",rows(destination));require(actual.equals(inventory),"learner placement originals changed");return moved;
        }
        private static Map<String,Object> root(List<?> inventory,String name) {
            var row=inventory.stream().map(MembershipFormat::object).filter(r->r.get("name").equals(name)).findFirst().orElseThrow();
            require(Boolean.TRUE.equals(row.get("present")),"learner placement required root absent");return row;
        }
        private static TreeMap<String,Object> files(Map<String,Object> root) {
            var result=new TreeMap<String,Object>();
            for(Object raw:list(root.get("files"))) {
                var row=object(raw);String name=(String)row.get("name");
                require(row.keySet().equals(Set.of("name","identity")) && name!=null && name.length()<=4096 && !name.isEmpty()
                        && !Path.of(name).isAbsolute() && (name.equals(".") || Path.of(name).normalize().toString().equals(name)) && !name.startsWith("..")
                        && result.putIfAbsent(name,object(row.get("identity")))==null,"learner placement inventory path");
            }
            require(result.containsKey("."),"learner placement inventory root missing");return result;
        }
        private static List<Object> rows(Map<String,Object> files) {
            var rows=new ArrayList<Object>();files.forEach((name,identity)->rows.add(Map.of("name",name,"identity",identity)));return rows;
        }
    }
}
