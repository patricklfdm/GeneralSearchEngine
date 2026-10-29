package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Forced transfer of the actual prepared learner's locks and storage. This
 * owner is an installation transaction, not a voter. Original files remain in
 * place and charged until a separate original-plan installation/retirement. */
final class MembershipLearnerCustody implements AutoCloseable {
    static final String FILE="custody.json";
    static final int MAXIMUM=256*1024;
    static final class Collected {
        final Set<MembershipOwnership> locks=new LinkedHashSet<>();
        final Set<MembershipFileAccess.Owned> files=new LinkedHashSet<>();
        final Set<MembershipResources.Lease> leases=new LinkedHashSet<>();
        final Set<Path> roots=new HashSet<>();
    }
    private final MembershipLearnerPlan summary;
    private final MembershipResources resources;
    private final MembershipResources.Usage usage;
    private final Map<String,Path> roots;
    private final List<Object> originals;
    private final Path directory;
    private final Map<String,Object> binding;
    private final Object directoryKey;
    private final byte[] plan;
    private final MembershipCapsule source;
    private final Decoded receipt;
    private final List<AutoCloseable> owners=new ArrayList<>();
    private final Set<MembershipResources.Lease> leases=new LinkedHashSet<>();
    private FileIdentity decision;
    private MembershipLearnerPlacement placement;
    private MembershipLearnerJoinedRetirement retirement;
    private final MembershipLearnerPlacement.Recovery recovery;
    private boolean closed,transferred,failed;

    static Path directory(MembershipLearnerPlan summary) {
        return summary.request().operationDirectory().resolveSibling(".gse-v53-learner-custody-"+summary.planDigest());
    }
    static Map<String,Path> roots(MembershipLearnerPlan summary) {
        var result=new TreeMap<String,Path>();result.put("replica",summary.request().replicaDirectory());result.put("operation",summary.request().operationDirectory());
        result.put("initialTyped",MembershipLearnerMaterialization.directory(summary));result.put("successor",MembershipLearnerSuccessor.directory(summary));
        result.put("successorTyped",MembershipLearnerSuccessor.typedDirectory(summary));result.put("slots",MembershipLearnerSlot.directory(summary));
        result.put("slotTyped",MembershipLearnerSlot.typedDirectory(summary));result.put("intent",MembershipLearnerIntent.directory(summary));
        result.put("voterStage",MembershipLearnerVoterStage.directory(summary));return Collections.unmodifiableMap(result);
    }
    static List<Object> capture(Map<String,Path> roots,Set<Path> managed)throws IOException {
        var result=new ArrayList<Object>();int count=0;long bytes=0;
        for(var row:roots.entrySet()) {
            Path root=AdmissionPaths.safe(row.getValue());var value=new TreeMap<String,Object>();value.put("name",row.getKey());value.put("path",AdmissionPaths.binding(root));
            boolean present=Files.exists(root,LinkOption.NOFOLLOW_LINKS);value.put("present",present);
            if(present) {
                require(managed==null || managed.contains(root),"learner custody has an unowned sidecar");
                require(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS),"learner custody root type");var files=new TreeMap<String,Object>();
                try(var paths=Files.walk(root,8)) {
                    var iterator=paths.iterator();while(iterator.hasNext()) {
                        Path path=AdmissionPaths.safe(iterator.next());require(++count<=512,"learner custody inventory count");
                        String name=path.equals(root)?".":root.relativize(path).toString();require(name.length()<=4096,"learner custody inventory path");
                        if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))files.put(name,Map.of("directory",true,"key",key(path).toString()));
                        else {
                            AdmissionPaths.regular(path);long size=Files.size(path);require(size<=MembershipApplicationImage.MAXIMUM,"learner custody file bound");
                            bytes=Math.addExact(bytes,size);require(bytes<=MembershipResources.METADATA_LIMIT+7L*MembershipApplicationImage.MAXIMUM,"learner custody inventory extent");
                            // Stream the hash; do not allocate a second application image.
                            var identity=inspect(path,size,digest(path,size));
                            files.put(name,Map.of("key",identity.key().toString(),"size",size,"sha256",identity.digest()));
                        }
                    }
                }
                // Paths are values, not schema keys: the canonical codec only
                // accepts fixed field identifiers, not '.', '/' or filenames.
                var inventory=new ArrayList<Object>();
                for(var file:files.entrySet())inventory.add(Map.of("name",file.getKey(),"identity",file.getValue()));
                value.put("files",List.copyOf(inventory));
            }
            result.add(value);
        }
        return List.copyOf(result);
    }
    private static String digest(Path path,long size)throws IOException {
        try {
            var digest=java.security.MessageDigest.getInstance("SHA-256");long count=0;
            try(var channel=MembershipFileAccess.open(path,StandardOpenOption.READ)) {
                var buffer=java.nio.ByteBuffer.allocate(64*1024);int n;
                while((n=channel.read(buffer))>0){count=Math.addExact(count,n);require(count<=size,"learner custody file grew");buffer.flip();digest.update(buffer);buffer.clear();}
                require(count==size,"learner custody file shortened");
            }
            return java.util.HexFormat.of().formatHex(digest.digest());
        }catch(java.security.NoSuchAlgorithmException impossible){throw new AssertionError(impossible);}
    }
    private MembershipLearnerCustody(MembershipLearnerVoterStage.Ready ready,Collected collected,boolean resume,MembershipBallotAllocator.Cut cut,MembershipLearnerPlacement.Recovery recovery)throws IOException {
        this.recovery=recovery;var intent=ready.intent();summary=intent.plan();resources=intent.head().resources();usage=resources.usage();
        resources.requireCompleteStorage(collected.leases);source=intent.source();receipt=intent.head().receipt();
        roots=roots(summary);originals=recovery==null?capture(roots,collected.roots):recovery.inventory(collected.roots);directory=directory(summary);
        intent.head().requireDisjoint(directory,MembershipLearnerPlacement.directory(summary));
        binding=AdmissionPaths.binding(directory);
        var fields=new TreeMap<String,Object>();fields.put("schema","gse-v53-learner-custody/1.3");fields.put("plan",summary.planDigest());fields.put("path",binding);
        fields.put("receipt",receipt.digest());fields.put("source",hash(source.packet.bytes()));fields.put("roots",originals);
        // Prove the bound before creating a directory; file keys have the same
        // existing 4096-byte bound as other original ownership records.
        fields.put("directoryKey","x".repeat(4096));canonical(fields,MAXIMUM);
        if(resume){require(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"learner custody original directory missing");}
        else {AdmissionPaths.absent(directory);Files.createDirectory(directory);AdmissionPaths.forceDirectory(directory.getParent());cut.at("LEARNER_CUSTODY_DIRECTORY_FORCED");}
        directoryKey=key(directory);fields.put("directoryKey",directoryKey.toString());plan=canonical(fields,MAXIMUM);
        if(resume) {
            require(children(directory,1).equals(Set.of(FILE)),"learner custody original decision missing");AdmissionPaths.exact(directory.resolve(FILE),plan);
        }else require(children(directory,1).isEmpty(),"learner custody unexpected decision");
    }
    static MembershipLearnerCustody take(MembershipLearnerVoterStage.Ready ready,MembershipBallotAllocator.Cut cut)throws IOException {return take(ready,cut,false);}
    static MembershipLearnerCustody resume(MembershipLearnerVoterStage.Ready ready,MembershipBallotAllocator.Cut cut)throws IOException {return take(ready,cut,true);}
    private static MembershipLearnerCustody take(MembershipLearnerVoterStage.Ready ready,MembershipBallotAllocator.Cut cut,boolean resume)throws IOException {
        return take(ready,cut,resume,null);
    }
    static MembershipLearnerCustody recoverPlacement(MembershipLearnerVoterStage.Ready ready,MembershipLearnerPlacement.Recovery recovery,
            MembershipBallotAllocator.Cut cut)throws IOException {
        recovery.check();return take(ready,cut,true,recovery);
    }
    private static MembershipLearnerCustody take(MembershipLearnerVoterStage.Ready ready,MembershipBallotAllocator.Cut cut,boolean resume,
            MembershipLearnerPlacement.Recovery recovery)throws IOException {
        Objects.requireNonNull(ready);Objects.requireNonNull(cut);ready.check();var head=ready.intent().head();var store=MembershipLearnerDisposition.store(head);
        var collected=new Collected();store.collectCustody(collected);MembershipLearnerCustody result=null;boolean moving=false;
        try {
            result=new MembershipLearnerCustody(ready,collected,resume,cut,recovery);result.force(ready,collected,resume,cut);
            // No user callback or file mutation occurs within the ownership
            // transfer. The original forced decision precedes every revocation.
            result.original(collected);ready.check();moving=true;
            int index=0;var names=new LinkedHashMap<MembershipResources.Lease,String>();for(var lease:collected.leases)names.put(lease,"learner-custody-"+(index++));
            result.leases.addAll(result.resources.transferCompleteStorage(names).values());
            for(var owner:collected.locks)result.owners.add(owner.transfer());
            for(var owner:collected.files)result.owners.add(owner.transfer());
            store.close(); // All its old lock/lease closes are now harmless.
            result.transferred=true;
            if(recovery!=null)result.placement=MembershipLearnerPlacement.restored(result,recovery);
            result.check();cut.at("LEARNER_CUSTODY_TRANSFERRED");result.check();return result;
        }catch(IOException|RuntimeException|Error error) {
            if(moving) {
                // A partial in-memory transfer exposes no voter. Close both
                // sides and retain all original bytes for explicit cold recovery.
                try{store.close();}catch(Exception close){error.addSuppressed(close);}
                if(result!=null)try{result.close();}catch(Exception close){error.addSuppressed(close);}
            }
            throw error;
        }
    }
    private void original(Collected collected)throws IOException {
        resources.requireCompleteStorage(collected.leases);require(resources.usage().equals(usage),"learner custody reservation changed");
        for(var lock:collected.locks)require(lock.lock().isValid(),"learner custody lock revoked");
        for(var file:collected.files)require(file.lock().isValid(),"learner custody receive lock revoked");
        require(originals.equals(recovery==null?capture(roots,collected.roots):recovery.inventory(collected.roots)),"learner custody original files changed");
        AdmissionPaths.recheck(binding);require(directoryKey.equals(key(directory)),"learner custody decision directory changed");
        if(decision!=null)require(children(directory,1).equals(Set.of(FILE)) && decision.equals(inspect(directory.resolve(FILE),decision.bytes(),decision.digest())),
                "learner custody decision changed before transfer");
    }
    private void point(Collected collected,MembershipBallotAllocator.Cut cut,String name)throws IOException {original(collected);cut.at(name);original(collected);}
    private void force(MembershipLearnerVoterStage.Ready ready,Collected collected,boolean resume,MembershipBallotAllocator.Cut cut)throws IOException {
        original(collected);Path file=directory.resolve(FILE);
        try(var channel=MembershipFileAccess.open(file,resume?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
            Object inode=key(file);decision=inspect(file,resume?plan.length:0,hash(resume?plan:new byte[0]));
            if(!resume) {
                point(collected,cut,"LEARNER_CUSTODY_CREATED");int half=plan.length/2;
                AdmissionPaths.write(channel,Arrays.copyOf(plan,half));rememberDecision(Arrays.copyOf(plan,half),inode);point(collected,cut,"LEARNER_CUSTODY_PREFIX_WRITTEN");
                AdmissionPaths.write(channel,Arrays.copyOfRange(plan,half,plan.length));rememberDecision(plan,inode);point(collected,cut,"LEARNER_CUSTODY_WRITTEN");
            }
            AdmissionPaths.exact(file,plan);require(key(file).equals(inode),"learner custody decision inode changed");channel.force(true);
            decision=inspect(file,plan.length,hash(plan));require(decision.key().equals(inode),"learner custody forced different decision");
            point(collected,cut,"LEARNER_CUSTODY_FORCED");
        }
        AdmissionPaths.forceDirectory(directory);point(collected,cut,"LEARNER_CUSTODY_PARENT_FORCED");
        ready.check();require(decision.equals(inspect(file,plan.length,hash(plan))),"learner custody decision changed after force");
        point(collected,cut,"LEARNER_CUSTODY_BEFORE_TRANSFER");
    }
    private void rememberDecision(byte[] bytes,Object inode)throws IOException {
        var next=inspect(directory.resolve(FILE),bytes.length,hash(bytes));require(next.key().equals(inode),"learner custody decision replaced");decision=next;
    }
    synchronized void check()throws IOException {
        require(!closed && !failed && transferred,"learner installation custody unavailable");
        try {
            resources.requireCompleteStorage(leases);require(resources.usage().equals(usage),"learner installation custody accounting changed");
            for(var owner:owners) {
                boolean valid=owner instanceof MembershipOwnership lock?lock.lock().isValid():((MembershipFileAccess.Owned)owner).lock().isValid();
                require(valid,"learner installation custody lock revoked");
            }
            AdmissionPaths.recheck(binding);require(directoryKey.equals(key(directory)) && children(directory,1).equals(Set.of(FILE)),"learner installation decision changed");
            require(decision.equals(inspect(directory.resolve(FILE),plan.length,hash(plan))),"learner installation decision changed");
            if(retirement!=null)retirement.checkOriginals();
            else if(placement==null)require(originals.equals(capture(roots,null)),"learner installation originals changed");
            else placement.checkOriginals();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    MembershipCapsule source()throws IOException {check();return source;}
    Decoded receipt()throws IOException {check();return receipt;}
    Path replica()throws IOException {check();return summary.request().replicaDirectory();}
    MembershipResources.Usage usage()throws IOException {check();return usage;}
    MembershipLearnerPlan summary()throws IOException {check();return summary;}
    byte[] originalDecision()throws IOException {check();return plan.clone();}
    synchronized void attachPlacement(MembershipLearnerPlacement next)throws IOException {
        check();require(placement==null,"learner placement already started; original resume required");placement=Objects.requireNonNull(next);
    }
    synchronized MembershipLearnerPlacement placement()throws IOException {check();return placement;}
    synchronized MembershipResources resources()throws IOException {check();return resources;}
    synchronized MembershipResources.StorageReplacement replacement(List<MembershipResources.StorageReservation> requested)throws IOException {
        check();return resources.prepareCompleteReplacement(leases,requested);
    }
    synchronized List<AutoCloseable> transferOwners(MembershipLearnerJoinedRetirement expected)throws IOException {
        require(retirement==expected && expected.transferring(),"native custody transfer requires original forced handoff");
        // Called only after the consumer has committed complete replacement
        // accounting. Old handles must remain revocable without a re-open.
        var moved=new ArrayList<AutoCloseable>();
        try {
            for(var owner:owners)moved.add(owner instanceof MembershipOwnership lock?lock.transfer():((MembershipFileAccess.Owned)owner).transfer());
            transferred=false;return List.copyOf(moved);
        }catch(IOException|RuntimeException|Error error){
            try{MembershipLearnerSource.closeChildren(moved.toArray(AutoCloseable[]::new));}catch(Exception close){error.addSuppressed(close);}
            try{close();}catch(Exception close){error.addSuppressed(close);}throw error;
        }
    }
    synchronized List<Map<String,Object>> reservations()throws IOException {check();return resources.describeCompleteStorage(leases);}
    synchronized MembershipLearnerJoinedRetirement retirement()throws IOException {check();return retirement;}
    synchronized void attachRetirement(MembershipLearnerJoinedRetirement next)throws IOException {
        check();require(retirement==null && placement!=null,"joined retirement already attached");retirement=Objects.requireNonNull(next);
    }
    @Override public synchronized void close()throws IOException {
        if(closed)return;var reversed=new ArrayList<>(owners);Collections.reverse(reversed);
        MembershipLearnerSource.closeChildren(reversed.toArray(AutoCloseable[]::new));
        for(var lease:leases)lease.close();closed=true;
    }
}
