package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Actual joined-member native storage ownership. Only a forced retirement can
 * create its original handoff; a cold open requires that exact original record.
 * Mutable generation/journal history is still checked by the native owners. */
final class MembershipJoinedOwner implements AutoCloseable {
    static final int MAXIMUM=64*1024;
    static final String FILE="native.json";
    private final MembershipLearnerPlan summary;
    private final MembershipResources resources;
    private final MembershipLearnerJoinedOriginal.Proof proof;
    private final MembershipLearnerJoinedRetirementPlan original;
    private final Map<String,Path> sidecars;
    private final List<Object> surviving;
    private final Map<Path,FileIdentity> retirement=new LinkedHashMap<>();
    private final Map<String,Object> binding;
    private final String retirementDirectoryKey;
    private final Path directory;
    private final List<MembershipResources.StorageReservation> targets;
    private final List<AutoCloseable> owners=new ArrayList<>();
    private MembershipOwnership root;
    private MembershipLearnerJoinedRetirement from;
    private MembershipResources.StorageReplacement replacement;
    private MembershipResources.StorageBatch storage;
    private Object directoryKey;
    private FileIdentity record;
    private byte[] decision;
    private boolean forced,transferred,closed;

    static Path directory(MembershipLearnerPlan summary){return summary.request().operationDirectory().resolveSibling(".gse-v53-joined-owner-"+summary.planDigest());}
    private <K,T> MembershipJoinedOwner(MembershipLearnerPlan summary,MembershipResources resources,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config)throws IOException {
        this.summary=summary;this.resources=resources;proof=MembershipLearnerJoinedOriginal.proof(summary,captured,config);
        original=new MembershipLearnerJoinedRetirementPlan(summary);directory=directory(summary);binding=AdmissionPaths.binding(directory);
        for(Path path:original.roots.values())AdmissionPaths.disjoint(List.of(directory,path));
        AdmissionPaths.disjoint(List.of(directory,config.materialization().directory()));
        for(var row:MembershipLearnerJoinedRetirement.completedRecords(summary).entrySet())retirement.put(row.getKey(),inspect(row.getKey(),row.getValue().length,hash(row.getValue())));
        retirementDirectoryKey=(String)object(parse(AdmissionPaths.read(MembershipLearnerJoinedRetirement.directory(summary).resolve(MembershipLearnerJoinedRetirement.PLAN),MembershipLearnerJoinedRetirement.MAXIMUM),MembershipLearnerJoinedRetirement.MAXIMUM)).get("directoryKey");
        sidecars=new TreeMap<>(original.roots);sidecars.remove("replica");surviving=new ArrayList<>();
        for(Object raw:original.inventory) {
            var row=new TreeMap<>(object(raw));String name=(String)row.get("name");if(name.equals("replica"))continue;
            if(Boolean.TRUE.equals(row.get("present"))) {
                var removed=new HashSet<String>();for(var deletion:original.deletions)if(deletion.get("root").equals(name))removed.add((String)deletion.get("name"));
                row.put("files",list(row.get("files")).stream().filter(v->!removed.contains(object(v).get("name"))).toList());
            }
            surviving.add(row);
        }
        targets=targets();decision("x".repeat(4096),"x".repeat(4096));checkProofs();
    }
    private List<MembershipResources.StorageReservation> targets() {
        var result=new ArrayList<MembershipResources.StorageReservation>();long metadata=0;
        result.add(new MembershipResources.StorageReservation(MembershipResources.Unit.JOURNAL,"membership-grants",MembershipGrantJournal.MAXIMUM));
        result.add(new MembershipResources.StorageReservation(MembershipResources.Unit.MISC,"current-authority",MembershipResources.Unit.MISC.bytes));
        for(var row:proof.installed().entrySet()) {
            if(!row.getKey().startsWith("generations/a/") || Boolean.TRUE.equals(object(row.getValue()).get("directory")))continue;
            long bytes=number(object(row.getValue()).get("size"));String name=row.getKey().substring("generations/a/".length());
            if(name.endsWith(".image"))result.add(new MembershipResources.StorageReservation(MembershipResources.Unit.APPLICATION,"generation-a:"+name,bytes));else metadata=Math.addExact(metadata,bytes);
        }
        result.add(new MembershipResources.StorageReservation(MembershipResources.Unit.GENERATION,"a",metadata));
        result.sort(Comparator.comparing((MembershipResources.StorageReservation v)->v.unit().name()).thenComparing(MembershipResources.StorageReservation::owner));
        // All private immutable proof files and root metadata share the native
        // MISC reservation. No surviving predecessor payload is hidden in it.
        long misc=MembershipLearnerCustody.MAXIMUM+2L*MembershipLearnerPlacement.MAXIMUM+MembershipLearnerJoinedAdmission.MAXIMUM
                +MembershipLearnerJoinedRetirement.MAXIMUM+MembershipLearnerJoinedRetirement.DONE_MAXIMUM+MAXIMUM;
        for(Object raw:surviving){var row=object(raw);if(Boolean.TRUE.equals(row.get("present")))for(Object file:list(row.get("files"))){var identity=object(object(file).get("identity"));if(!Boolean.TRUE.equals(identity.get("directory")))misc=Math.addExact(misc,number(identity.get("size")));}}
        for(var row:proof.installed().entrySet())if(!row.getKey().contains("/") && !row.getKey().equals("grants.gsr") && !Boolean.TRUE.equals(object(row.getValue()).get("directory")))misc=Math.addExact(misc,number(object(row.getValue()).get("size")));
        require(misc<=MembershipResources.Unit.MISC.bytes,"native joining immutable proof capacity");return List.copyOf(result);
    }
    static <K,T> MembershipJoinedOwner take(MembershipLearnerJoinedRetirement retired,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(cut);retired.check();MembershipLearnerJoinedOriginal.verifyRetirement(retired,captured,config);
        var next=new MembershipJoinedOwner(retired.summary(),retired.resources(),captured,config);next.from=retired;
        next.replacement=retired.replacement(next.targets); // Refuse capacity before any writes.
        try {
            next.force(retired,cut);next.owners.addAll(retired.transferOwners(next));next.selectRoot();next.transferred=true;next.from=null;
            next.check();cut.at("JOINED_NATIVE_TRANSFERRED");next.check();return next;
        }catch(IOException|RuntimeException|Error error){try{next.close();}catch(Exception close){error.addSuppressed(close);}throw error;}
    }
    static <K,T> MembershipJoinedOwner reopen(MembershipLearnerPlan summary,MembershipResources resources,SearchEngineConfiguration<K,T> captured,
            MembershipReplicaConfig<K,T> config)throws IOException {
        resources.requireCompleteStorage(Set.of());var next=new MembershipJoinedOwner(summary,resources,captured,config);
        try {
            next.directoryKey=key(next.directory);next.decision=next.decision(next.directoryKey.toString(),key(next.directory.resolve(FILE)).toString());
            require(children(next.directory,1).equals(Set.of(FILE)),"native joining original handoff inventory");AdmissionPaths.exact(next.directory.resolve(FILE),next.decision);
            next.record=inspect(next.directory.resolve(FILE),next.decision.length,hash(next.decision));
            Path root=summary.request().replicaDirectory().resolve("replica.lock");next.owners.add(MembershipOwnership.own(root,false));
            for(Path lock:next.original.locks)if(!lock.equals(root))next.owners.add(MembershipOwnership.own(lock,false));
            next.selectRoot();next.forced=true;next.transferred=true;next.check();return next;
        }catch(IOException|RuntimeException|Error error){try{next.close();}catch(Exception close){error.addSuppressed(close);}throw error;}
    }
    private void selectRoot() {
        Path wanted=summary.request().replicaDirectory().resolve("replica.lock");
        for(var owner:owners)if(owner instanceof MembershipOwnership lock && lock.path().equals(wanted)){require(root==null,"native joining duplicate root owner");root=lock;}
        require(root!=null,"native joining root descriptor missing");
    }
    private static Map<String,Object> fingerprint(FileIdentity value){return Map.of("key",value.key().toString(),"size",value.bytes(),"sha256",value.digest());}
    private byte[] decision(String directoryKey,String recordKey) {
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-native-joining/1.3");value.put("plan",summary.planDigest());
        value.put("root",summary.request().root().manifestDigest());value.put("identity",MembershipBootstrapSeed.identity(summary.request().identity()));
        value.put("path",binding);value.put("directoryKey",directoryKey);value.put("recordKey",recordKey);
        value.put("retirement",fingerprint(retirement.get(MembershipLearnerJoinedRetirement.directory(summary).resolve(MembershipLearnerJoinedRetirement.PLAN))));
        value.put("retired",fingerprint(retirement.get(MembershipLearnerJoinedRetirement.directory(summary).resolve(MembershipLearnerJoinedRetirement.DONE))));
        value.put("storage",targets.stream().map(v->Map.of("unit",v.unit().name(),"owner",v.owner(),"bytes",v.bytes())).toList());
        return canonical(value,MAXIMUM);
    }
    private void force(MembershipLearnerJoinedRetirement retired,MembershipBallotAllocator.Cut cut)throws IOException {
        // A complete original record may be re-forced after a pre-transfer
        // interruption. Missing/torn originals are never synthesized cold.
        boolean exists=Files.exists(directory,LinkOption.NOFOLLOW_LINKS);
        if(exists){directoryKey=key(directory);require(children(directory,1).equals(Set.of(FILE)),"native joining original handoff missing");
            decision=decision(directoryKey.toString(),key(directory.resolve(FILE)).toString());AdmissionPaths.exact(directory.resolve(FILE),decision);
        }else {Files.createDirectory(directory);directoryKey=key(directory);AdmissionPaths.forceDirectory(directory.getParent());}
        retired.check();checkProofs();
        try(var channel=MembershipFileAccess.open(directory.resolve(FILE),exists?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            Object inode=key(directory.resolve(FILE));decision=decision(directoryKey.toString(),inode.toString());
            if(!exists)AdmissionPaths.write(channel,decision);
            AdmissionPaths.exact(directory.resolve(FILE),decision);channel.force(true);record=inspect(directory.resolve(FILE),decision.length,hash(decision));
            retired.check();checkProofs();cut.at("JOINED_NATIVE_RECORD_FORCED");retired.check();checkProofs();
        }
        AdmissionPaths.forceDirectory(directory);AdmissionPaths.forceDirectory(directory.getParent());forced=true;
        checkHandoff(retired);cut.at("JOINED_NATIVE_DECISION_FORCED");checkHandoff(retired);
    }
    void checkHandoff(MembershipLearnerJoinedRetirement expected)throws IOException {require(from==expected && forced && !closed && !transferred,"native joining handoff not forced");checkProofs();checkRecord();}
    void commitStorage(){storage=replacement.commit();replacement=null;}
    private void checkRecord()throws IOException {
        AdmissionPaths.recheck(binding);require(directoryKey.equals(key(directory)) && children(directory,1).equals(Set.of(FILE))
                && record.equals(inspect(directory.resolve(FILE),decision.length,hash(decision))),"native joining original handoff changed");
    }
    private void checkProofs()throws IOException {
        proof.check();require(key(MembershipLearnerJoinedRetirement.directory(summary)).toString().equals(retirementDirectoryKey),"native joining retirement directory changed");require(surviving.equals(MembershipLearnerCustody.capture(sidecars,null)),"native joining surviving sidecars changed");
        for(var row:retirement.entrySet()){var f=row.getValue();require(f.equals(inspect(row.getKey(),f.bytes(),f.digest())),"native joining retirement original changed");}
        for(String name:List.of(".","root.gsr","genesis.gsr","node.gsr","replica.lock")) {
            Path path=name.equals(".")?summary.request().replicaDirectory():summary.request().replicaDirectory().resolve(name);var expected=object(proof.installed().get(name));
            require(key(path).toString().equals(expected.get("key")),"native joining immutable root replaced");
            if(!name.equals("."))inspect(path,number(expected.get("size")),(String)expected.get("sha256"));
        }
    }
    void check()throws IOException {
        require(!closed && transferred && forced && root!=null,"native joining owner unavailable");
        for(var owner:owners)require(owner instanceof MembershipOwnership lock?lock.lock().isValid():((MembershipFileAccess.Owned)owner).lock().isValid(),"native joining descriptor revoked");
        checkProofs();checkRecord();
    }
    void history(MembershipCapsule source)throws IOException {
        check();var value=proof.value();var receipt=decode(MembershipBootstrapPlanData.unbase(value.get("receipt"),16384),"records","LEARNER");
        MembershipLearnerIntent.matchJoinedReceipt(summary.request(),receipt,source);
        var originalCut=object(value.get("cut"));long index=number(source.context.cut.get("index")),minimum=number(originalCut.get("index"));
        require(index>=minimum && (index!=minimum || source.context.cut.equals(originalCut)),"native joining history predates original installation");
        for(String field:List.of("intent","certificate")){var record=decode(MembershipBootstrapPlanData.unbase(value.get(field),16384),"records",field.equals("intent")?"ENTRY":"CERTIFICATE");
            require(Arrays.equals(record.bytes(),source.packet.objectBytes(record.digest())),"native joining original INTENT provenance changed");}
        check();
    }
    /** Initialization eligibility only. A used or replaced original cannot
     * recreate missing ledgers from a later selector, even at the same cut. */
    void unused()throws IOException {
        check();
        for(var row:proof.installed().entrySet()) {
            Path path=row.getKey().equals(".")?summary.request().replicaDirectory():summary.request().replicaDirectory().resolve(row.getKey());
            var expected=object(row.getValue());
            require(key(path).toString().equals(expected.get("key")),"joining retention original installation replaced");
            if(!Boolean.TRUE.equals(expected.get("directory")))
                inspect(path,number(expected.get("size")),(String)expected.get("sha256"));
        }
        check();
    }
    MembershipOwnership root()throws IOException {check();return root;}
    MembershipLearnerPlan summary(){return summary;}
    MembershipResources resources(){return resources;}
    MembershipResources.StorageBatch storage(){return storage;}
    void claimed(){if(storage!=null)storage.complete();}
    @Override public void close()throws IOException {
        if(closed)return;
        try {var reversed=new ArrayList<>(owners);Collections.reverse(reversed);MembershipLearnerSource.closeChildren(reversed.toArray(AutoCloseable[]::new));}
        finally {if(storage!=null)storage.close();closed=true;}
    }
}
