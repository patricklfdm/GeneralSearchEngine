package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original-plan predecessor deletion under exclusive ownership. All original
 * reservations remain charged until close or a future native owner handoff.
 * Completion is not a mutable journal, runtime admission or voting authority. */
final class MembershipLearnerJoinedRetirement implements AutoCloseable {
    static final int MAXIMUM=256*1024,DONE_MAXIMUM=64*1024;
    static final String PLAN="retirement.json",DONE="retired.json";
    private final MembershipLearnerPlan summary;
    private final MembershipLearnerJoinedRetirementPlan original;
    private final MembershipLearnerCustody custody;
    private final MembershipLearnerPlacement placement;
    private final MembershipResources resources;
    private final List<?> reservations;
    private final Path directory;
    private final Map<String,Object> binding;
    private final Map<Path,FileIdentity> proofs=new LinkedHashMap<>();
    private final Map<Path,Object> proofDirectories=new LinkedHashMap<>();
    private final Map<String,FileIdentity> records=new TreeMap<>();
    private final List<MembershipOwnership> locks=new ArrayList<>();
    private final Set<MembershipResources.Lease> leases=new LinkedHashSet<>();
    private Object directoryKey;
    private byte[] plan;
    private boolean closed,planForced,complete,transferred,transferring;

    static Path directory(MembershipLearnerPlan summary) {
        return summary.request().operationDirectory().resolveSibling(".gse-v53-learner-retired-"+summary.planDigest());
    }
    private MembershipLearnerJoinedRetirement(MembershipLearnerPlan summary,MembershipLearnerCustody custody,
            MembershipLearnerPlacement placement,MembershipResources resources,List<?> reservations)throws IOException {
        this.summary=summary;this.custody=custody;this.placement=placement;this.resources=resources;this.reservations=List.copyOf(reservations);
        original=new MembershipLearnerJoinedRetirementPlan(summary);original.accounting(reservations);
        directory=directory(summary);binding=AdmissionPaths.binding(directory);
        for(Path root:original.roots.values())require(!directory.startsWith(root) && !root.startsWith(directory),"joined retirement overlapping original root");
        for(Path dir:List.of(MembershipLearnerCustody.directory(summary),MembershipLearnerPlacement.directory(summary)))proofDirectories.put(dir,key(dir));
        for(Path file:List.of(MembershipLearnerCustody.directory(summary).resolve(MembershipLearnerCustody.FILE),
                MembershipLearnerPlacement.directory(summary).resolve(MembershipLearnerPlacement.PLAN),
                MembershipLearnerPlacement.directory(summary).resolve(MembershipLearnerPlacement.READY),
                MembershipLearnerPlacement.directory(summary).resolve(MembershipLearnerJoinedAdmission.FILE))) {
            byte[] bytes=AdmissionPaths.read(file,MAXIMUM);proofs.put(file,inspect(file,bytes.length,hash(bytes)));
        }
        var joined=object(parse(AdmissionPaths.read(MembershipLearnerPlacement.directory(summary).resolve(MembershipLearnerJoinedAdmission.FILE),
                MembershipLearnerJoinedAdmission.MAXIMUM),MembershipLearnerJoinedAdmission.MAXIMUM));
        Path materialization=Path.of((String)object(joined.get("materialization")).get("path"));
        AdmissionPaths.disjoint(List.of(directory,materialization));
        // Reject overflow before any directory/record creation.
        decision("x".repeat(4096),"x".repeat(4096));
    }
    static <K,T> MembershipLearnerJoinedRetirement retire(MembershipLearnerJoinedAdmission admission,
            SearchEngineConfiguration<K,T> captured,MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);MembershipLearnerJoinedOriginal.verify(admission,captured,config);
        var placement=admission.placement();var custody=placement.custody();require(custody.retirement()==null,"joined retirement already started; original resume required");
        var result=new MembershipLearnerJoinedRetirement(custody.summary(),custody,placement,null,custody.reservations());
        AdmissionPaths.absent(result.directory);require(result.original.project()==0,"joined retirement predecessors already missing");
        custody.attachRetirement(result);
        Files.createDirectory(result.directory);result.directoryKey=key(result.directory);AdmissionPaths.forceDirectory(result.directory.getParent());
        result.point(cut,"JOINED_RETIREMENT_DIRECTORY_FORCED");result.finish(cut);return result;
    }
    static MembershipLearnerJoinedRetirement resume(MembershipLearnerCustody custody,MembershipBallotAllocator.Cut cut)throws IOException {
        var result=custody.retirement();require(result!=null,"joined retirement live original absent");result.finish(Objects.requireNonNull(cut));return result;
    }
    /** Complete original decision required. No synthesized plan, measurements,
     * bootstrap receipt or remote source can authorize cold deletion. */
    static <K,T> MembershipLearnerJoinedRetirement recover(MembershipLearnerPlan summary,MembershipResources resources,
            SearchEngineConfiguration<K,T> captured,MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);resources.requireCompleteStorage(Set.of());
        Path dir=directory(summary);byte[] bytes=AdmissionPaths.read(dir.resolve(PLAN),MAXIMUM);var value=object(parse(bytes,MAXIMUM));
        var result=new MembershipLearnerJoinedRetirement(summary,null,null,resources,list(value.get("reservations")));
        try {
            result.directoryKey=key(dir);result.plan=result.decision(result.directoryKey.toString(),key(dir.resolve(PLAN)).toString());
            require(Arrays.equals(bytes,result.plan),"joined retirement original decision changed");
            for(String name:children(dir,2)) {
                require(Set.of(PLAN,DONE).contains(name),"joined retirement foreign record");byte[] record=AdmissionPaths.read(dir.resolve(name),name.equals(PLAN)?MAXIMUM:DONE_MAXIMUM);
                result.records.put(name,inspect(dir.resolve(name),record.length,hash(record)));
            }
            // Take the real root first; every acquisition is nonblocking. No
            // file is created and failure releases all acquired owners.
            Path root=summary.request().replicaDirectory().resolve("replica.lock");
            result.locks.add(MembershipOwnership.own(root,false));
            for(Path lock:result.original.locks)if(!lock.equals(root))result.locks.add(MembershipOwnership.own(lock,false));
            int n=0;for(Object row:result.reservations){var reservation=object(row);
                result.leases.add(resources.reserve(MembershipResources.Unit.valueOf((String)reservation.get("unit")),"joined-retirement-"+(n++),number(reservation.get("bytes"))));}
            result.checkOwner();MembershipLearnerJoinedOriginal.verifyRetirement(result,captured,config);
            result.point(cut,"JOINED_RETIREMENT_RECOVERY_VERIFIED");result.finish(cut);return result;
        }catch(IOException|RuntimeException|Error error){try{result.close();}catch(Exception close){error.addSuppressed(close);}throw error;}
    }
    static Map<Path,byte[]> completedRecords(MembershipLearnerPlan summary)throws IOException {
        Path dir=directory(summary);byte[] bytes=AdmissionPaths.read(dir.resolve(PLAN),MAXIMUM);var value=object(parse(bytes,MAXIMUM));
        var reader=new MembershipLearnerJoinedRetirement(summary,null,null,null,list(value.get("reservations")));
        reader.directoryKey=key(dir);reader.plan=reader.decision(reader.directoryKey.toString(),key(dir.resolve(PLAN)).toString());
        AdmissionPaths.exact(dir.resolve(PLAN),reader.plan);require(children(dir,2).equals(Set.of(PLAN,DONE)),"joined native retirement must be complete");
        reader.records.put(PLAN,inspect(dir.resolve(PLAN),reader.plan.length,hash(reader.plan)));
        byte[] completion=reader.completion(key(dir.resolve(DONE)));AdmissionPaths.exact(dir.resolve(DONE),completion);
        return Map.of(dir.resolve(PLAN),reader.plan,dir.resolve(DONE),completion);
    }
    MembershipResources resources()throws IOException {check();return custody==null?resources:custody.resources();}
    MembershipResources.StorageReplacement replacement(List<MembershipResources.StorageReservation> requested)throws IOException {
        check();return custody==null?resources.prepareCompleteReplacement(leases,requested):custody.replacement(requested);
    }
    boolean transferring(){return transferring;}
    List<AutoCloseable> transferOwners(MembershipJoinedOwner next)throws IOException {
        check();next.checkHandoff(this);transferring=true;var moved=new ArrayList<AutoCloseable>();
        try {
            // Replacement validation happens before any descriptor revocation.
            next.commitStorage();
            if(custody!=null)moved.addAll(custody.transferOwners(this));else for(var lock:locks)moved.add(lock.transfer());
            transferred=true;return List.copyOf(moved);
        }catch(IOException|RuntimeException|Error error){
            try{MembershipLearnerSource.closeChildren(moved.toArray(AutoCloseable[]::new));}catch(Exception close){error.addSuppressed(close);}
            try{close();}catch(Exception close){error.addSuppressed(close);}throw error;
        }finally{transferring=false;}
    }
    MembershipLearnerPlan summary(){return summary;}
    private static Map<String,Object> fingerprint(FileIdentity f){return Map.of("key",f.key().toString(),"size",f.bytes(),"sha256",f.digest());}
    private byte[] decision(String directoryKey,String recordKey) {
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-joined-retirement/1.3");value.put("plan",summary.planDigest());
        value.put("root",summary.request().root().manifestDigest());value.put("identity",MembershipBootstrapSeed.identity(summary.request().identity()));
        value.put("path",binding);value.put("directoryKey",directoryKey);value.put("recordKey",recordKey);
        value.put("joined",fingerprint(proofs.get(MembershipLearnerPlacement.directory(summary).resolve(MembershipLearnerJoinedAdmission.FILE))));
        value.put("deletions",original.deletions);value.put("reservations",reservations);return canonical(value,MAXIMUM);
    }
    private byte[] completion(Object inode) {
        return canonical(Map.of("schema","gse-v53-joined-retired/1.3","plan",hash(plan),"planKey",records.get(PLAN).key().toString(),
                "recordKey",inode.toString(),"deleted",(long)original.deletions.size()),DONE_MAXIMUM);
    }
    /** Called from custody's actual lock/accounting guard. No recursion into it. */
    void checkOriginals()throws IOException {
        require(!closed && !transferred,"joined retirement owner closed or transferred");if(placement!=null)placement.checkRecords();
        for(var dir:proofDirectories.entrySet())require(key(dir.getKey()).equals(dir.getValue()),"joined retirement original proof directory changed");
        for(var proof:proofs.entrySet()){var f=proof.getValue();require(f.equals(inspect(proof.getKey(),f.bytes(),f.digest())),"joined retirement original proof changed");}
        require(original.inventory.equals(MembershipLearnerPlacement.placedOriginalInventory(summary)),"joined retirement original inventory decision changed");
        AdmissionPaths.recheck(binding);
        if(directoryKey==null)AdmissionPaths.absent(directory);
        else {
            require(key(directory).equals(directoryKey) && children(directory,2).equals(records.keySet()),"joined retirement directory changed");
            for(var row:records.entrySet()){var f=row.getValue();require(f.equals(inspect(directory.resolve(row.getKey()),f.bytes(),f.digest())),"joined retirement record changed");}
        }
        int prefix=original.project();
        require(prefix==0 || plan!=null && records.containsKey(PLAN) && records.get(PLAN).bytes()==plan.length,"joined retirement deletion before complete decision");
        if(records.containsKey(DONE)) {
            require(prefix==original.deletions.size(),"joined retirement completion before deletion");
            byte[] wanted=completion(records.get(DONE).key()),actual=AdmissionPaths.read(directory.resolve(DONE),DONE_MAXIMUM);
            require(actual.length<=wanted.length && Arrays.equals(actual,Arrays.copyOf(wanted,actual.length)),"joined retirement completion original prefix changed");
        }
        require(!complete || records.containsKey(DONE) && records.get(DONE).bytes()==completion(records.get(DONE).key()).length,"joined retirement completion missing");
    }
    void checkOwner()throws IOException {
        require(!closed && !transferred,"joined retirement owner closed or transferred");
        if(custody!=null)custody.check();else {
            require(locks.size()==original.locks.size(),"joined retirement incomplete original locks");
            for(var lock:locks)require(lock.lock().isValid(),"joined retirement original lock unavailable");
            resources.requireCompleteStorage(leases);require(resources.describeCompleteStorage(leases).equals(reservations),"joined retirement accounting changed");checkOriginals();
        }
    }
    void check()throws IOException {checkOwner();require(complete,"joined retirement incomplete");}
    int deleted()throws IOException {check();return original.deletions.size();}
    private void point(MembershipBallotAllocator.Cut cut,String event)throws IOException {checkOwner();cut.at(event);checkOwner();}
    private void remember(String name,byte[] bytes,Object inode)throws IOException {
        var identity=inspect(directory.resolve(name),bytes.length,hash(bytes));require(identity.key().equals(inode),"joined retirement record replaced");records.put(name,identity);
    }
    private void write(String name,MembershipBallotAllocator.Cut cut)throws IOException {
        checkOwner();Path path=directory.resolve(name);var old=records.get(name);
        try(var channel=MembershipFileAccess.open(path,old==null?Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            Object inode=key(path);byte[] wanted=name.equals(PLAN)?decision(directoryKey.toString(),inode.toString()):completion(inode);
            if(name.equals(PLAN)){if(plan!=null)require(Arrays.equals(plan,wanted),"joined retirement plan replaced");plan=wanted;}
            if(old==null){remember(name,new byte[0],inode);point(cut,"JOINED_RETIREMENT_CREATED:"+name);}
            byte[] current=AdmissionPaths.read(path,name.equals(PLAN)?MAXIMUM:DONE_MAXIMUM);
            require(current.length<=wanted.length && Arrays.equals(current,Arrays.copyOf(wanted,current.length)),"joined retirement record original prefix");
            channel.position(current.length);
            if(current.length<wanted.length) {
                int half=current.length+(wanted.length-current.length)/2;AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,current.length,half));
                remember(name,Arrays.copyOf(wanted,half),inode);point(cut,"JOINED_RETIREMENT_PREFIX_WRITTEN:"+name);
                AdmissionPaths.write(channel,Arrays.copyOfRange(wanted,half,wanted.length));remember(name,wanted,inode);point(cut,"JOINED_RETIREMENT_WRITTEN:"+name);
            }
            channel.force(true);point(cut,"JOINED_RETIREMENT_FORCED:"+name);
        }
        AdmissionPaths.forceDirectory(directory);point(cut,"JOINED_RETIREMENT_PARENT_FORCED:"+name);
    }
    private void forceDeletedParent(Map<String,Object> entry)throws IOException {
        Path root=original.roots.get((String)entry.get("root")),parent=pathParent(entry);
        while(!Files.exists(parent,LinkOption.NOFOLLOW_LINKS)){require(!parent.equals(root),"joined retirement root missing");parent=parent.getParent();}
        require(parent.startsWith(root),"joined retirement parent escaped root");checkOwner();AdmissionPaths.forceDirectory(parent);
    }
    private Path pathParent(Map<String,Object> entry)throws IOException {return original.path(entry).getParent();}
    private void finish(MembershipBallotAllocator.Cut cut)throws IOException {
        checkOwner();write(PLAN,cut);AdmissionPaths.forceDirectory(directory);AdmissionPaths.forceDirectory(directory.getParent());planForced=true;
        point(cut,"JOINED_RETIREMENT_DECISION_FORCED");int prefix=original.project();
        for(int i=0;i<prefix;i++){forceDeletedParent(original.deletions.get(i));point(cut,"JOINED_RETIREMENT_RESEALED:"+i);}
        for(int i=prefix;i<original.deletions.size();i++) {
            require(planForced,"joined retirement decision not forced");var entry=original.deletions.get(i);
            point(cut,"JOINED_RETIREMENT_BEFORE_DELETE:"+i);Files.delete(original.path(entry));point(cut,"JOINED_RETIREMENT_DELETED:"+i);
            forceDeletedParent(entry);point(cut,"JOINED_RETIREMENT_DELETE_FORCED:"+i);
        }
        write(DONE,cut);complete=true;point(cut,"JOINED_RETIREMENT_COMPLETE");
    }
    @Override public void close()throws IOException {
        if(closed)return;
        if(custody!=null)custody.close();else {
            var reversed=new ArrayList<>(locks);Collections.reverse(reversed);MembershipLearnerSource.closeChildren(reversed.toArray(AutoCloseable[]::new));for(var lease:leases)lease.close();
        }
        closed=true;
    }
}
