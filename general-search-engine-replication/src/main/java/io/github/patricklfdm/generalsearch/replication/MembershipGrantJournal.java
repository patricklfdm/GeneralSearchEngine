package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private grant journal. Retained mode seals original source bytes; public vote authorization remains disabled. */
final class MembershipGrantJournal implements AutoCloseable {
    static final String FILE="grants.gsr";
    static final int MAXIMUM=32*1024*1024, RESERVATION=8192+16384;
    private final Path directory,path;
    private final MembershipRoot root;
    private final MembershipIdentity identity;
    private final MembershipBallotAllocator allocator;
    private final MembershipBallotAllocator.Cut cut;
    private Object fileKey;
    private final int maximum;
    private final AtomicReference<Map<String,Object>> observed=new AtomicReference<>();
    private byte[] journal;
    private Decoded promise,basis,selection;
    private final Map<String,Decoded> promises=new TreeMap<>(), bases=new TreeMap<>();
    private final Map<String,Decoded> selections=new TreeMap<>();
    private MembershipBasisSources sources;
    private MembershipCurrentGeneration current;
    private MembershipCurrentGeneration.Verifier capsuleVerifier;
    private MembershipGenerationFiles inactive;
    private MembershipFloorFiles floors;
    private MembershipRetirementFiles retirement;
    private MembershipJournalRotationFiles rotation;
    private boolean floorReleaseEnabled;
    private MembershipSourceRetirementFiles sourceRetirement;
    private MembershipResources resources;
    private volatile boolean failed,closed;

    private MembershipGrantJournal(Path directory,MembershipRoot root,MembershipIdentity identity,
            MembershipBallotAllocator allocator,int maximum,MembershipBallotAllocator.Cut cut) throws IOException {
        this.directory=directory;this.path=directory.resolve(FILE);this.root=root;this.identity=identity;
        this.allocator=allocator;this.maximum=maximum;this.cut=cut;fileKey=key();
        journal=AdmissionPaths.read(path,maximum);replay();
        // A complete frame visible after process death is conservatively retained and sealed.
        try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {channel.force(true);}
        AdmissionPaths.forceDirectory(directory);
        if(promise!=null)observed.set(object(promise.value().get("ballot")));
    }

    static MembershipGrantJournal open(Path path,MembershipRoot root,MembershipIdentity identity) throws IOException {
        return open(path,root,identity,MAXIMUM,event->{});
    }

    /** Lower bounded capacity is used only by deterministic exhaustion tests. */
    static MembershipGrantJournal open(Path requested,MembershipRoot root,MembershipIdentity identity,int maximum,MembershipBallotAllocator.Cut cut) throws IOException {
        require(maximum>=RESERVATION && maximum<=MAXIMUM,"grant journal capacity");Objects.requireNonNull(cut);
        Path path=AdmissionPaths.safe(requested);
        var owner=MembershipBallotAllocator.openWithGrantJournal(path,root,identity,cut);
        try {return new MembershipGrantJournal(path,root,identity,owner,maximum,cut);}
        catch(IOException | RuntimeException | Error error) {
            try {owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;
        }
    }

    /** Requires pre-provisioned sources directory. Never falls back to metadata-only open. */
    static MembershipGrantJournal openRetained(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipBallotAllocator.Cut cut) throws IOException {
        Objects.requireNonNull(resources);Objects.requireNonNull(cut);Path path=AdmissionPaths.safe(requested);
        var owner=MembershipBallotAllocator.openWithRetainedGrants(path,root,identity,cut);
        try {
            var journal=new MembershipGrantJournal(path,root,identity,owner,MAXIMUM,cut);
            journal.sources=new MembershipBasisSources(path,resources,cut,journal.promises,journal.bases);return journal;
        } catch(IOException | RuntimeException | Error error) {
            try{owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;
        }
    }

    static MembershipGrantJournal openCurrent(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        Objects.requireNonNull(resources);Objects.requireNonNull(verifier);Objects.requireNonNull(cut);Path path=AdmissionPaths.safe(requested);
        var owner=MembershipBallotAllocator.openWithCurrentGeneration(path,root,identity,cut);MembershipGrantJournal journal=null;
        try {
            journal=new MembershipGrantJournal(path,root,identity,owner,MAXIMUM,cut);
            journal.sources=new MembershipBasisSources(path,resources,cut,journal.promises,journal.bases);
            journal.capsuleVerifier=verifier;
            journal.current=new MembershipCurrentGeneration(path,root,identity,resources,journal.promises.values(),journal.bases.values(),verifier,cut);
            journal.checkOwner();return journal;
        }catch(IOException | RuntimeException | Error error) {
            try{if(journal==null)owner.close();else journal.close();}catch(IOException close){error.addSuppressed(close);}throw error;
        }
    }

    static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,false,false,false,false);
    }
    static MembershipGrantJournal openFloors(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,false,false,false);
    }
    static MembershipGrantJournal openRetirement(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,false,false);
    }
    static MembershipGrantJournal openRotating(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,false);
    }
    static MembershipGrantJournal openMaintenance(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true);
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,MAXIMUM);
    }
    /** Lower capacity exercises the production admission path without a 32 MiB fixture. */
    static MembershipGrantJournal openMaintenance(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,int maximum,MembershipBallotAllocator.Cut cut) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true,maximum);
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum) throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,maximum,false);
    }
    static MembershipGrantJournal openReclaiming(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true,MAXIMUM,true);
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum,boolean withSourceRetirement) throws IOException {
        require(maximum>=RESERVATION && maximum<=MAXIMUM,"grant journal capacity");
        Objects.requireNonNull(resources);Objects.requireNonNull(verifier);Objects.requireNonNull(cut);Path path=AdmissionPaths.safe(requested);
        var owner=withSourceRetirement?MembershipBallotAllocator.openWithSourceRetirement(path,root,identity,cut):withRotation?MembershipBallotAllocator.openWithJournalRotation(path,root,identity,cut):withRetirement?MembershipBallotAllocator.openWithRetirement(path,root,identity,cut):withFloors?MembershipBallotAllocator.openWithFloorCopies(path,root,identity,cut):MembershipBallotAllocator.openWithGenerationInstall(path,root,identity,cut);MembershipGrantJournal journal=null;
        try {
            journal=new MembershipGrantJournal(path,root,identity,owner,maximum,cut);journal.resources=resources;journal.capsuleVerifier=verifier;journal.floorReleaseEnabled=withFloorRelease;
            if(withRotation)journal.rotation=new MembershipJournalRotationFiles(path);
            if(withSourceRetirement)journal.sourceRetirement=new MembershipSourceRetirementFiles(path);
            journal.sources=new MembershipBasisSources(path,resources,cut,journal.promises,journal.bases,withSourceRetirement?journal.sourceRetirement.decision().orElse(null):null);
            journal.reloadGenerations();
            if(withFloors) {
                journal.floors=new MembershipFloorFiles(path,root,identity,resources,verifier,withFloorRelease);
                var parents=new ArrayList<MembershipCapsule.Anchor>();journal.addFloorParent(parents);journal.current.verifyParents(parents);
            }
            if(withRetirement)journal.retirement=new MembershipRetirementFiles(path,resources);
            journal.checkOwner();
            if(withSourceRetirement && journal.sourceRetirement.pending()) {
                var decision=journal.sourceRetirement.decision();
                if(decision.isPresent())journal.retireSource(decision.get().id());
                else require(!journal.rotation.pending(),"partial source retirement cannot own a journal rotation");
            }
            if(withFloorRelease && journal.floors.releasing())journal.releaseFloor();if(withRotation && journal.rotation.pending())journal.rotateJournal();return journal;
        }catch(IOException | RuntimeException | Error error){try{if(journal==null)owner.close();else journal.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private void reloadGenerations() throws IOException {
        if(current!=null)current.close();if(inactive!=null)inactive.close();
        current=new MembershipCurrentGeneration(directory,root,identity,resources,promises.values(),bases.values(),selections.values(),capsuleVerifier,cut,true);
        inactive=new MembershipGenerationFiles(directory,current.generation,resources);
    }

    private Object key() throws IOException {
        Object key=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS).fileKey();
        require(key!=null,"grant file identity unavailable");return key;
    }
    private void live() {require(!closed && !failed,"grant journal closed or failed");}
    private void checkBaseOwner() throws IOException {
        live();allocator.checkOwner();require(fileKey.equals(key()),"grant journal inode changed");AdmissionPaths.exact(path,journal);
        if(sources!=null)sources.check();
        if(rotation!=null)rotation.check();
        if(sourceRetirement!=null)sourceRetirement.check();
    }
    private void checkWithoutFloor() throws IOException {
        checkBaseOwner();
        if(current!=null)current.check();
        if(inactive!=null)inactive.check();
    }
    private void checkWithoutRetirement() throws IOException {checkWithoutFloor();if(floors!=null)floors.check();}
    private void checkOwner() throws IOException {checkWithoutRetirement();if(retirement!=null)retirement.check();}
    private void sourceIdle(){if(sourceRetirement!=null)require(!sourceRetirement.pending(),"pending source retirement must finish before authority changes");}
    private void rotationIdle(){sourceIdle();if(floors!=null)require(!floors.releasing(),"pending floor release must finish before authority changes");if(rotation!=null)require(!rotation.pending(),"pending journal rotation must finish before authority changes");}
    private void floorIdle() throws IOException {
        rotationIdle();
        if(floors!=null)require(!floors.pending(),"pending floor must finish before authority changes");
        if(retirement!=null)require(!retirement.pending(),"pending retirement must finish before authority changes");
    }
    private void addFloorParent(Collection<MembershipCapsule.Anchor> parents) throws IOException {
        if(floors==null)return;var prior=floors.read();if(prior.isEmpty())return;
        var value=prior.get().value();var first=object(list(value.get("sources")).getFirst());
        parents.add(new MembershipCapsule.Anchor(object(value.get("cut")),(String)first.get("catalog"),(String)first.get("snapshot")));
    }
    synchronized Optional<Decoded> governingFloor() throws IOException {require(floors!=null,"floor storage owner required");checkOwner();return floors.read();}
    synchronized Decoded establishFloor(List<MembershipFloor.Copy> offered) throws IOException {
        require(floors!=null,"floor storage owner required");rotationIdle();
        if(retirement!=null)require(!retirement.pending(),"pending retirement must finish before authority changes");var own=floorCopyCurrent();
        // Validate and reserve before any persistent change; an interrupted transaction
        // may only resume with the same original full copies.
        try{return floors.establish(own,offered,this::checkWithoutFloor,cut);}
        catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    private MembershipFloor.Copy originalGeneration(Map<String,byte[]> files) throws IOException {
        require(files.containsKey("generation.gsr") && files.containsKey("source.gscp"),"complete retirement source required");
        var manifest=decode(files.get("generation.gsr"),"records","GENERATION");var packet=MembershipSourcePacket.decode(files.get("source.gscp"));
        var images=new TreeMap<String,byte[]>();packet.images().keySet().forEach(h->images.put(h,files.get(h+".image")));
        var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var capsule=Objects.requireNonNull(capsuleVerifier.verify(localRoot,packet,images));require(Arrays.equals(capsule.packet.bytes(),packet.bytes()),"retirement verifier substituted source");
        var value=manifest.value();
        require(promises.values().stream().anyMatch(p->p.digest().equals(value.get("promise"))),"retirement original promise absent");
        if(value.get("basis")!=null)require(bases.values().stream().anyMatch(p->p.digest().equals(value.get("basis"))),"retirement original basis absent");
        if(value.get("selection")!=null)require(selections.containsKey(value.get("selection")),"retirement original selection absent");
        // The caller keeps these original bytes under the exclusive owner and forces
        // the complete saved packet before publishing any deletion authority.
        var owned=new Owned(identity.nodeId().value(),identity.storageId(),manifest.digest(),cutDigest(capsule.context.cut));
        return MembershipFloor.Copy.verify(manifest,capsule,identity,Set.of(owned),files);
    }
    private void bindRetirement(Decoded record,MembershipFloorFiles.Retained floor) {
        var value=record.value();require(value.get("root").equals(root.manifestDigest()) && value.get("node").equals(identity.nodeId().value())
                && value.get("floor").equals(floor.floor().digest()) && value.get("selector").equals(current.selector.digest()),"retirement authority context changed");
        var names=new TreeSet<String>();String previous=null;long metadata=0;int images=0;String prefix="generations/"+inactive.slot()+"/";
        for(Object row:list(value.get("files"))) {
            var file=object(row);String path=(String)file.get("path");require(path.startsWith(prefix) && (previous==null || previous.compareTo(path)<0),"retirement inactive inventory order/path");previous=path;
            String name=path.substring(prefix.length());long size=number(file.get("size"));require(size>0 && size<=MembershipGenerationFiles.limit(name),"retirement file capacity");names.add(name);
            if(name.endsWith(".image")){images++;require(name.equals(file.get("sha256")+".image"),"retirement image binding");}else metadata=Math.addExact(metadata,size);
        }
        require(names.containsAll(Set.of("generation.gsr","source.gscp","promise.gsr")) && names.size()<=32 && images<=7 && metadata<=MembershipResources.Unit.SOURCE.bytes,"retirement complete bounded inventory");
    }
    /** Returns no record for an already-empty slot; never drops root promises or original BASIS sources. */
    synchronized Optional<Decoded> retireInactive() throws IOException {
        require(retirement!=null && floors!=null && inactive!=null,"retirement storage owner required");checkOwner();rotationIdle();
        require(!floors.pending() && !inactive.pending(),"pending floor/selector must finish before retirement");
        require(promise==null || promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest()),"uninstalled adoption fence; prefix recovery required");
        try {
            if(!inactive.exists() && (!retirement.pending() || retirement.empty())) {
                if(retirement.empty())retirement.clearEmpty(this::checkWithoutRetirement,cut);return Optional.empty();
            }
            var floor=floors.retained().orElseThrow(()->new IllegalArgumentException("durable governing floor required before retirement"));
            var saved=retirement.authority();Decoded record;
            if(saved.isEmpty()) {
                require(!(inactive.exists() && !current.adopted && current.manifest.value().get("selection")==null)
                        && !inactive.incompleteOrSelected(selection==null?null:selection.digest(),number(current.capsule.context.cut.get("index"))),"pending generation must finish before retirement");
                var original=originalGeneration(inactive.originalFiles());
                var plan=MembershipRetirementPlan.create(root,identity,current,floor,original);
                inactive.forceOriginal(cut);checkOwner();retirement.prepare(plan,this::checkWithoutRetirement,cut);record=plan.record;
            }else {
                record=saved.get();bindRetirement(record,floor);retirement.checkSaved(record);
                if(inactive.exists()) {
                    var original=originalGeneration(retirement.original());var plan=MembershipRetirementPlan.create(root,identity,current,floor,original);
                    require(Arrays.equals(record.bytes(),plan.record.bytes()),"retirement differs from saved original generation");
                }
                retirement.sealAuthority(record,this::checkWithoutRetirement,cut);
            }
            bindRetirement(record,floor);retirement.checkSaved(record);checkOwner();
            inactive.deleteAuthorized(record,this::checkOwner,cut);
            require(!inactive.exists(),"retirement original still exists");retirement.clearAfterDeletion(record,this::checkWithoutRetirement,cut);
            cut.at("RETIREMENT_BEFORE_RETURN");checkOwner();return Optional.of(record);
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Relinquish a completed old floor only after every inactive generation is gone. */
    synchronized void releaseFloor() throws IOException {
        require(floorReleaseEnabled && floors!=null && retirement!=null && rotation!=null,"floor release storage owner required");checkOwner();sourceIdle();
        require(!inactive.exists() && !inactive.pending() && !retirement.pending() && !rotation.pending(),"pending generation/retirement/rotation before floor release");
        require(promise==null || promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest()),"uninstalled adoption fence; prefix recovery required");
        try {
            if(!floors.exists())return;floors.release(current,this::checkOwner,cut);cut.at("FLOOR_RELEASE_BEFORE_RETURN");checkOwner();
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Read-only decision for a completed original source; does not publish deletion authority. */
    synchronized MembershipSourceRetirementPlan planSourceRetirement(String id) throws IOException {
        require(floorReleaseEnabled && floors!=null && retirement!=null && rotation!=null,"source retirement maintenance owner required");
        checkOwner();floorIdle();return sourceRetirementPlan(id);
    }
    private MembershipSourceRetirementPlan sourceRetirementPlan(String id)throws IOException {
        checkOwner();require(!inactive.exists() && !inactive.pending(),"inactive generation must retire before source planning");
        require(promise!=null && (promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest())),"uninstalled adoption fence; prefix recovery required");
        var originalBasis=bases.get(id);require(promises.containsKey(id) && sources.retainedIdentities().contains(id),"source retirement requires complete original source");
        var retained=floors.retained().orElseThrow(()->new IllegalArgumentException("durable governing floor required before source retirement"));
        var original=sources.original(id,promises.get(id),originalBasis);var rootRecord=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var capsule=Objects.requireNonNull(capsuleVerifier.verify(rootRecord,original.packet(),original.images()));
        require(Arrays.equals(capsule.packet.bytes(),original.packet().bytes()),"source retirement verifier substituted source");
        var plan=MembershipSourceRetirementPlan.create(root,identity,current,retained,promise,promises.get(id),originalBasis,capsule,original.images());
        checkOwner();return plan;
    }
    /** Complete one exact source retirement; all other writer mutations remain blocked. */
    synchronized Decoded retireSource(String id)throws IOException {
        require(sourceRetirement!=null,"source retirement owner required");checkOwner();
        require(!inactive.exists() && !inactive.pending() && !floors.pending() && !retirement.pending(),"pending generation/floor/retirement before source deletion");
        require(promise!=null && (promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest())),"uninstalled adoption fence; prefix recovery required");
        try {
            var retained=floors.retained().orElseThrow(()->new IllegalArgumentException("durable governing floor required before source retirement"));
            var saved=sourceRetirement.decision();MembershipSourceRetirementFiles.Decision decision;MembershipSourceRetirementPlan plan=null;
            if(promises.containsKey(id)) {
                plan=sourceRetirementPlan(id);var original=sources.original(id,plan.promise,plan.basis);
                decision=new MembershipSourceRetirementFiles.Decision(plan.record,plan.promise,plan.basis,original.packet().capsule());
                if(saved.isPresent())require(Arrays.equals(saved.get().bytes(),decision.bytes()),"source retirement differs from original source");
            }else {decision=saved.orElseThrow(()->new IllegalArgumentException("source retirement original decision absent"));require(decision.id().equals(id),"source retirement different original identity");}
            require(!rotation.pending() || saved.isPresent(),"journal rotation preceded source retirement authority");
            decision.bind(root,identity,current,retained,promise);sourceRetirement.publish(decision,this::checkOwner,cut);
            var protectedPromises=new HashSet<String>();protectedPromises.add((String)current.manifest.value().get("promise"));
            for(var copy:retained.copies())if(copy.owner.equals(identity))protectedPromises.add((String)copy.generation.value().get("promise"));
            byte[] compact;
            if(plan!=null)compact=MembershipJournalRotation.excludingSource(journal,protectedPromises,sources.retainedIdentities(),plan);
            else {var keep=new HashSet<>(sources.retainedIdentities());keep.remove(id);compact=MembershipJournalRotation.compact(journal,protectedPromises,keep);}
            if(rotation.pending() || !Arrays.equals(journal,compact)) {
                rotation.replace(compact,this::checkOwner,installed->{fileKey=installed.key();journal=compact;},cut);
                promise=null;basis=null;selection=null;promises.clear();bases.clear();selections.clear();replay();
                var bound=object(promise.value().get("ballot"));observed.updateAndGet(prior->prior==null || compareBallot(bound,prior)>0?bound:prior);
            }
            require(!promises.containsKey(id) && !bases.containsKey(id),"source retirement journal still references original");
            decision.bind(root,identity,current,retained,promise);checkOwner();cut.at("SOURCE_RETIREMENT_JOURNAL_PRUNED");checkOwner();
            sources.deleteRetired(decision,this::checkOwner,cut);require(!sources.retainedIdentities().contains(id),"source retirement still owns original files");
            sources.releaseRetiredLeases(id);
            decision.bind(root,identity,current,retained,promise);sourceRetirement.clear(this::checkOwner,cut);cut.at("SOURCE_RETIREMENT_BEFORE_RETURN");checkOwner();return decision.record();
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Compact exact original frames, retaining every original BASIS/SELECTED and live promise. */
    synchronized String rotateJournal() throws IOException {
        require(rotation!=null && current!=null && floors!=null && retirement!=null,"rotation storage owner required");checkOwner();sourceIdle();
        require(!inactive.exists() && !inactive.pending() && !floors.pending() && !retirement.pending(),"pending generation/floor/retirement before journal rotation");
        var protectedPromises=new HashSet<String>();protectedPromises.add((String)current.manifest.value().get("promise"));
        var retained=floors.retained();
        if(retained.isPresent())for(var copy:retained.get().copies())if(copy.owner.equals(identity))protectedPromises.add((String)copy.generation.value().get("promise"));
        byte[] compact=MembershipJournalRotation.compact(journal,protectedPromises,sources.retainedIdentities());
        if(!rotation.pending() && Arrays.equals(compact,journal))return hash(compact);
        try {
            rotation.replace(compact,this::checkOwner,installed->{fileKey=installed.key();journal=compact;},cut);
            promise=null;basis=null;selection=null;promises.clear();bases.clear();selections.clear();replay();
            // Compaction cannot lower an in-flight higher observation or its durable promise.
            var bound=object(promise.value().get("ballot"));observed.updateAndGet(prior->prior==null || compareBallot(bound,prior)>0?bound:prior);
            checkOwner();cut.at("JOURNAL_ROTATION_BEFORE_RETURN");checkOwner();return hash(compact);
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    private static Map<String,Object> ballot(Map<String,Object> value) {
        checkType(value,"ballot");require(number(value.get("counter"))<=MembershipBallotAllocator.MAX,"grant ballot counter capacity");
        return object(parse(canonical(value,4096),4096));
    }
    private void checkPromise(Decoded value) {
        require(value.value().get("root").equals(root.manifestDigest()),"grant promise root/basis identity");
        ballot(object(value.value().get("ballot")));
    }
    private static String promiseKey(Decoded value) {
        return value.value().get("basisId")==null?"adoption:"+value.digest():(String)value.value().get("basisId");
    }
    private void checkBasis(Decoded value,Decoded grant) {
        require(grant!=null,"orphan grant basis");var b=value.value();var p=grant.value();
        require(p.get("basisId")!=null,"adoption fence is not a grant");
        for(String field:List.of("root","view","ballot","basisId"))require(b.get(field).equals(p.get(field)),"grant basis binding: "+field);
        require(b.get("voter").equals(identity.nodeId().value()),"grant basis owner");
        var cut=object(b.get("cut"));var view=object(cut.get("view"));checkView(view);
        require(number(cut.get("index"))<=MembershipBallotAllocator.MAX && b.get("view").equals(viewDigest(root.manifestDigest(),view)),"grant basis cut/view");
    }
    private void checkSelection(Decoded selected) {
        require(promise!=null && basis!=null,"selection without complete local grant");var value=selected.value();
        for(String field:List.of("root","view","ballot"))require(value.get(field).equals(promise.value().get(field)),"selection grant binding: "+field);
        var selectedCut=object(value.get("cut"));var ownCut=object(basis.value().get("cut"));var view=object(ownCut.get("view"));
        require(selectedCut.get("view").equals(view) && number(selectedCut.get("index"))<=MembershipBallotAllocator.MAX
                && number(selectedCut.get("index"))>=number(ownCut.get("index")),"selection cut/view");
        if(selectedCut.get("index").equals(ownCut.get("index")))require(selectedCut.equals(ownCut),"selection conflicting local parent");
        var voters=new ArrayList<String>();boolean local=false;var ids=new HashSet<String>();
        for(Object row:list(value.get("sources"))) {
            var source=object(row);String voter=(String)source.get("voter");voters.add(voter);
            require(ids.add((String)source.get("basisId")),"selection duplicate basis identity");
            if(voter.equals(identity.nodeId().value())) {
                require(source.get("basisId").equals(basis.value().get("basisId")) && source.get("basisDigest").equals(basis.digest()),"selection original local basis");local=true;
            }
        }
        orderedNodes(voters);quorum(view,voters);
        require(local && voters.contains(object(value.get("ballot")).get("proposer")),"selection missing local voter/proposer");
    }
    private void replay() {
        int offset=0;
        while(offset<journal.length) {
            require(journal.length-offset>=HEADER,"torn grant journal header");
            byte[] header=Arrays.copyOfRange(journal,offset,offset+HEADER);
            int kind=Short.toUnsignedInt(ByteBuffer.wrap(header).getShort(8));
            require(kind==3 || kind==4 || kind==5,"unknown grant journal record");String name=kind==3?"PROMISE":kind==4?"BASIS":"SELECTED";
            int length=HEADER+header(header,"records",name);
            require(length<=journal.length-offset,"torn grant journal body");
            var value=decode(Arrays.copyOfRange(journal,offset,offset+length),"records",name);offset+=length;
            if(name.equals("PROMISE")) {
                checkPromise(value);
                require(promise==null || compareBallot(object(value.value().get("ballot")),object(promise.value().get("ballot")))>0,"non-increasing grant promise");
                require(promises.putIfAbsent(promiseKey(value),value)==null,"reused original basis identity");
                promise=value;basis=null;selection=null;
            } else if(name.equals("BASIS")) {require(basis==null,"duplicate grant basis");checkBasis(value,promise);basis=value;bases.put((String)value.value().get("basisId"),value);}
            else {require(selection==null,"duplicate persisted selection");checkSelection(value);selection=value;selections.put(value.digest(),value);}
        }
    }

    /** Does not acquire the writer monitor: a verified observation can fence an in-flight force. */
    void observe(MembershipContext context,Map<String,Object> incoming) {
        live();require(context.root.equals(root.manifestDigest()),"foreign observed root");
        require(current==null || context==current.capsule.context,"observation must use current generation");
        var next=ballot(context.ballot(incoming,true));
        observed.updateAndGet(prior->prior==null || compareBallot(next,prior)>0?next:prior);
    }
    private void fence(Map<String,Object> expected) {
        live();require(expected.equals(observed.get()),"higher ballot observed; fresh campaign required");
    }

    synchronized long reserveCounter() throws IOException {
        try {
            checkOwner();rotationIdle();var before=observed.get();long result=allocator.reserve(before==null?0:number(before.get("counter")));
            var after=observed.get();require(after==null || number(after.get("counter"))<result,"allocation fenced by higher observation");return result;
        } catch(IOException | RuntimeException | Error error) {failed=true;throw error;}
    }

    synchronized Decoded prepare(MembershipCapsule source,Map<String,Object> incoming,String accepted) throws IOException {
        require(sources==null,"retained grant requires application materializations");
        return prepare(source,incoming,accepted,null);
    }

    synchronized Decoded prepare(MembershipCapsule source,Map<String,Object> incoming,String accepted,Map<String,byte[]> images) throws IOException {
        require(current==null,"current grant does not accept caller source");
        return prepareBound(source,incoming,accepted,images);
    }

    /** The same writer monitor will own later generation installation; external changes are refused. */
    synchronized Decoded prepareCurrent(Map<String,Object> incoming) throws IOException {
        require(current!=null,"current generation required");checkOwner();floorIdle();cut.at("CURRENT_BEFORE_CAPTURE");checkOwner();
        if(inactive!=null)require(!inactive.pending() && !(inactive.exists() && !current.adopted && current.manifest.value().get("selection")==null)
                && !inactive.incompleteOrSelected(selection==null?null:selection.digest(),number(current.capsule.context.cut.get("index"))),"pending generation installation must finish before another grant");
        require(promise==null || promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest()),
                "uninstalled adoption fence; prefix recovery required");
        return prepareBound(current.capsule,incoming,current.accepted,current.images());
    }
    void observeCurrent(Map<String,Object> incoming) {live();require(current!=null,"current generation required");observe(current.capsule.context,incoming);}
    synchronized Optional<Owned> currentOwnedTail() throws IOException {
        require(current!=null,"current generation required");checkOwner();return current.ownedTail();
    }
    /** Observation of the whole rechecked, locally forced selected generation; never a deletion permit. */
    synchronized MembershipFloor.Copy floorCopyCurrent() throws IOException {
        require(current!=null && inactive!=null,"generation owner required");checkOwner();rotationIdle();
        require(!inactive.pending() && !(inactive.exists() && !current.adopted && current.manifest.value().get("selection")==null)
                && !inactive.incompleteOrSelected(selection==null?null:selection.digest(),number(current.capsule.context.cut.get("index"))),"pending generation installation must finish before floor copy");
        require(promise==null || promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest()),
                "uninstalled adoption fence; prefix recovery required");
        var forced=new Owned(identity.nodeId().value(),identity.storageId(),current.manifest.digest(),cutDigest(current.capsule.context.cut));
        var copy=MembershipFloor.Copy.verify(current.manifest,current.capsule,identity,Set.of(forced),current.copyFiles());
        cut.at("FLOOR_COPY_BEFORE_RETURN");checkOwner();return copy;
    }
    /** Certificate-derived root fence only. Prefix installation and any vote remain separate operations. */
    synchronized Decoded fenceMembershipPrefix(MembershipSourcePacket packet,Map<String,byte[]> images,List<MembershipSelection.Bridge> bridges) throws IOException {
        require(current!=null && inactive!=null,"generation owner required");checkOwner();rotationIdle();
        require(!inactive.pending() && !(inactive.exists() && !current.adopted && current.manifest.value().get("selection")==null)
                && !inactive.incompleteOrSelected(selection==null?null:selection.digest(),number(current.capsule.context.cut.get("index"))),"pending generation installation must finish before adoption");floorIdle();
        var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var incoming=Objects.requireNonNull(capsuleVerifier.verify(localRoot,packet,images));
        require(Arrays.equals(incoming.packet.bytes(),packet.bytes()),"adoption verifier substituted source");
        var ancestry=new java.io.ByteArrayOutputStream();require(bridges.size()<=6,"adoption ancestry count");
        for(var bridge:bridges){ancestry.writeBytes(bridge.statement.bytes());for(var ack:bridge.acknowledgements)ancestry.writeBytes(ack.bytes());}
        incoming.verifyAncestry(ancestry.toByteArray(),List.of(current.capsule.terminal()));
        var certificate=incoming.membershipCertificateFence().orElseThrow(()->new IllegalArgumentException("no authenticated membership certificate fence"));
        var floor=ballot(object(certificate.value().get("ballot")));checkOwner();cut.at("ADOPTION_VALIDATED");checkOwner();
        observed.updateAndGet(prior->prior==null || compareBallot(floor,prior)>0?floor:prior);
        if(promise!=null && compareBallot(object(promise.value().get("ballot")),floor)>=0)return promise;
        fence(floor);
        var value=new TreeMap<String,Object>();value.put("root",root.manifestDigest());value.put("view",certificate.value().get("authority"));
        value.put("ballot",floor);value.put("basisId",null);var adoption=decode(encode("records","PROMISE",value),"records","PROMISE");
        ensureJournalCapacity(adoption.bytes().length,"adoption journal rotation required");
        try {
            append(adoption,floor);promise=adoption;basis=null;selection=null;promises.put(promiseKey(adoption),adoption);
            cut.at("ADOPTION_BEFORE_RETURN");checkOwner();fence(floor);return adoption;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Adopts authenticated membership state, without granting a vote, installation ACK or READY. */
    synchronized Decoded adoptCurrent(MembershipSourcePacket packet,Map<String,byte[]> images,List<MembershipSelection.Bridge> bridges) throws IOException {
        require(current!=null && inactive!=null,"generation owner required");checkOwner();floorIdle();
        var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var incoming=Objects.requireNonNull(capsuleVerifier.verify(localRoot,packet,images));
        require(Arrays.equals(incoming.packet.bytes(),packet.bytes()),"adoption verifier substituted source");packet.verifyImages(images);
        var ancestors=new ArrayList<MembershipCapsule.Anchor>();ancestors.add(current.capsule.terminal());addFloorParent(ancestors);
        for(var original:bases.values()) {
            var cap=sources.original(original).packet().capsule().value();
            ancestors.add(new MembershipCapsule.Anchor(object(cap.get("cut")),(String)cap.get("catalog"),(String)cap.get("application")));
        }
        incoming.verifyAncestry(MembershipGenerationPlan.ancestry(bridges),ancestors);
        var certificate=incoming.membershipCertificateFence().orElseThrow(()->new IllegalArgumentException("no authenticated membership certificate fence"));
        if(current.adopted && Arrays.equals(current.capsule.packet.bytes(),packet.bytes())) {
            var saved=decode(AdmissionPaths.read(directory.resolve("generations").resolve(current.generation).resolve("promise.gsr"),8192),"records","PROMISE");
            var duplicate=MembershipGenerationPlan.adopted(root,identity,current.generation,saved,incoming,bridges,images);
            require(Arrays.equals(current.manifest.bytes(),duplicate.manifest.bytes()) && !inactive.pending(),"adopted generation differs from original plan");
            checkOwner();fence(object(promise.value().get("ballot")));return current.manifest;
        }
        require(number(incoming.context.cut.get("index"))>number(current.capsule.context.cut.get("index"))
                && !incoming.context.authority().equals(current.capsule.context.authority()),"adoption requires newer membership authority");
        if(current.accepted!=null) {
            var tail=current.capsule.context.record(current.accepted,"ACCEPT");
            require(number(tail.value().get("index"))<=number(incoming.context.cut.get("index")),"adoption would omit above-prefix owned tail");
        }
        var floor=ballot(object(certificate.value().get("ballot")));Decoded adoptedPromise=promise;
        if(promise==null || compareBallot(object(promise.value().get("ballot")),floor)<0) {
            var value=new TreeMap<String,Object>();value.put("root",root.manifestDigest());value.put("view",certificate.value().get("authority"));
            value.put("ballot",floor);value.put("basisId",null);adoptedPromise=decode(encode("records","PROMISE",value),"records","PROMISE");
            ensureJournalCapacity(adoptedPromise.bytes().length,"adoption journal rotation required");
        }
        var plan=MembershipGenerationPlan.adopted(root,identity,inactive.slot(),adoptedPromise,incoming,bridges,images);
        // Reject another pending plan or occupied old generation before modifying the root promise.
        inactive.checkPlan(plan);
        var bound=object(adoptedPromise.value().get("ballot"));
        try {
            inactive.reservePlan(plan);checkOwner();cut.at("ADOPTION_INSTALL_VALIDATED");checkOwner();
            observed.updateAndGet(prior->prior==null || compareBallot(bound,prior)>0?bound:prior);fence(bound);
            if(promise==null || !Arrays.equals(promise.bytes(),adoptedPromise.bytes())) {
                append(adoptedPromise,bound);promise=adoptedPromise;basis=null;selection=null;promises.put(promiseKey(promise),promise);
            }
            cut.at("ADOPTION_INSTALL_FENCED");checkOwner();fence(bound);
            inactive.install(plan,current.selector.bytes(),()->{checkBaseOwner();fence(bound);},current::check,cut);
            reloadGenerations();cut.at("ADOPTION_INSTALL_BEFORE_RETURN");checkOwner();fence(bound);return current.manifest;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Observation of this owner's forced original grant, not an assertion of remote force. */
    synchronized MembershipSelection.Source originalSource() throws IOException {
        require(current!=null && basis!=null,"complete current grant required");checkOwner();
        require(basis.value().get("view").equals(current.capsule.context.authority()),"obsolete original grant; fresh campaign required");
        var original=sources.original(basis);var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var capsule=Objects.requireNonNull(capsuleVerifier.verify(localRoot,original.packet(),original.images()));
        require(Arrays.equals(capsule.packet.bytes(),original.packet().bytes()),"original verifier substituted source");
        var reference=Map.<String,Object>of("voter",identity.nodeId().value(),"basisId",basis.value().get("basisId"),"basisDigest",basis.digest());
        var owned=new HashSet<Owned>();String parent=cutDigest(object(basis.value().get("cut")));
        owned.add(new Owned(identity.nodeId().value(),identity.storageId(),basis.digest(),parent));
        if(basis.value().get("accepted")!=null)owned.add(new Owned(identity.nodeId().value(),identity.storageId(),(String)basis.value().get("accepted"),parent));
        var result=MembershipSelection.Source.verify(capsule,basis,reference,identity,owned);checkOwner();return result;
    }
    private MembershipSelection.Decision decision(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges) throws IOException {
        require(current!=null && promise!=null && basis!=null,"complete current grant required");checkOwner();
        var ballot=object(promise.value().get("ballot"));fence(ballot);var local=originalSource();
        require(offered.size()>=2 && offered.size()<=6 && bridges.size()<=6,"selected source/ancestry capacity");
        var verified=new ArrayList<MembershipSelection.Source>();MembershipSelection.Source proposer=null;
        for(var source:offered) {
            if(source.owner.nodeId().equals(identity.nodeId())) {
                require(Arrays.equals(source.basis.bytes(),local.basis.bytes()) && Arrays.equals(source.capsule.packet.bytes(),local.capsule.packet.bytes()),"selection substituted local source");
                source=local;
            }
            verified.add(source);if(source.owner.nodeId().value().equals(ballot.get("proposer")))proposer=source;
        }
        require(proposer!=null,"selection missing proposer");
        var result=new MembershipSelection.Campaign(proposer).select(verified,bridges);checkSelection(result.selected());fence(ballot);checkOwner();return result;
    }
    /** Records the immutable selection only. No installation, ACCEPT or installation ACK is authorized. */
    synchronized Decoded selectCurrent(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges) throws IOException {
        floorIdle();var selected=decision(offered,bridges).selected();var ballot=object(selected.value().get("ballot"));
        if(selection!=null) {require(Arrays.equals(selection.bytes(),selected.bytes()),"selection already fixed; fresh ballot required");return selection;}
        ensureJournalCapacity(selected.bytes().length,"selection journal rotation required");
        try {
            append(selected,ballot);selection=selected;selections.put(selected.digest(),selected);cut.at("SELECTED_BEFORE_RETURN");checkOwner();fence(ballot);return selected;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Local installation receipt only after every materialized file and selector parent is forced. */
    synchronized Decoded installCurrent(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges,Map<String,byte[]> images) throws IOException {
        require(inactive!=null && selection!=null,"durable selection and generation owner required");floorIdle();
        var selected=decision(offered,bridges);require(Arrays.equals(selection.bytes(),selected.selected().bytes()),"installation differs from original selection");
        var ballot=object(selection.value().get("ballot"));boolean installed=selection.digest().equals(current.manifest.value().get("selection"));
        var plan=MembershipGenerationPlan.selected(root,identity,installed?current.generation:inactive.slot(),promise,basis,selected,bridges,images);
        var ancestors=new ArrayList<MembershipCapsule.Anchor>();ancestors.add(current.capsule.terminal());addFloorParent(ancestors);
        for(var original:bases.values()) {
            var value=sources.original(original).packet().capsule().value();ancestors.add(new MembershipCapsule.Anchor(object(value.get("cut")),(String)value.get("catalog"),(String)value.get("application")));
        }
        plan.verify(decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT"),identity,capsuleVerifier,ancestors);checkOwner();fence(ballot);
        if(installed) {
            require(Arrays.equals(current.manifest.bytes(),plan.manifest.bytes()) && !inactive.pending(),"installed generation differs from original plan");checkOwner();fence(ballot);return current.manifest;
        }
        try {
            inactive.install(plan,current.selector.bytes(),()->{checkBaseOwner();fence(ballot);},current::check,cut);
            reloadGenerations();cut.at("INSTALL_BEFORE_RETURN");checkOwner();fence(ballot);return current.manifest;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    private Decoded prepareBound(MembershipCapsule source,Map<String,Object> incoming,String accepted,Map<String,byte[]> images) throws IOException {
        require((sources==null)==(images==null),"grant source mode mismatch");
        live();var context=source.context;
        require(context.root.equals(root.manifestDigest()) && identity.equals(context.identities.get(identity.nodeId().value()))
                && context.voters().contains(identity.nodeId().value()),"grant local eligible identity");
        var next=ballot(context.ballot(incoming,true));observe(context,next);fence(next);checkOwner();
        if(promise!=null && promise.value().get("ballot").equals(next)) {
            require(promise.value().get("view").equals(context.authority()),"duplicate grant changed configuration");
            require(basis!=null,"incomplete original basis; fresh ballot required");fence(next);return basis;
        }
        // Reserve both maximum frames before PROMISE; never strand its BASIS on our own byte limit.
        ensureJournalCapacity(RESERVATION,"grant journal rotation required");
        var grant=decode(encode("records","PROMISE",Map.of("root",root.manifestDigest(),"view",context.authority(),
                "ballot",next,"basisId",UUID.randomUUID().toString())),"records","PROMISE");
        var body=new TreeMap<String,Object>(grant.value());body.put("voter",identity.nodeId().value());body.put("cut",context.cut);
        body.put("capsule",source.packet.capsule().digest());body.put("inventory",source.packet.inventoryDigest());body.put("accepted",accepted);
        var frozen=decode(encode("records","BASIS",body),"records","BASIS");source.packet.bind(frozen);checkBasis(frozen,grant);
        if(accepted!=null) {
            var tail=context.record(accepted,"ACCEPT");var entry=context.record((String)tail.value().get("entry"),"ENTRY");
            context.ballot(tail.value().get("ballot"),true);context.ballot(entry.value().get("origin"),true);
            context.control((String)entry.value().get("kind"),command((String)entry.value().get("kind"),source.packet.objectBytes((String)entry.value().get("payload"))));
        }
        var reservation=sources==null?null:sources.prepare(frozen,source,images);
        try(var retained=reservation) {
            append(grant,next);promise=grant;basis=null;selection=null;promises.put((String)grant.value().get("basisId"),grant);
            if(retained!=null){retained.capture();fence(next);}
            append(frozen,next);basis=frozen;bases.put((String)frozen.value().get("basisId"),frozen);cut.at("GRANT_BEFORE_RETURN");checkOwner();fence(next);return frozen;
        } catch(IOException | RuntimeException | Error error) {failed=true;throw error;}
    }

    private void ensureJournalCapacity(int bytes,String message) throws IOException {
        if(bytes<=maximum-journal.length)return;
        // One bounded maintenance attempt. Never release sources, generations or
        // pending recovery work to admit a new operation at the byte ceiling.
        if(bytes<=maximum && rotation!=null && current!=null && floors!=null && retirement!=null
                && !inactive.exists() && !inactive.pending() && !floors.pending() && !retirement.pending())rotateJournal();
        if(bytes>maximum-journal.length)throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,
                AutomaticReplicationException.Outcome.NOT_SUBMITTED,Optional.empty(),message,null);
    }
    private void append(Decoded record,Map<String,Object> expected) throws IOException {
        checkOwner();fence(expected);byte[] bytes=record.bytes();require(bytes.length<=maximum-journal.length,"grant journal overflow");
        cut.at(record.kind()+"_BEFORE_WRITE");fence(expected);
        try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            require(channel.size()==journal.length,"grant journal length changed");channel.position(journal.length);
            AdmissionPaths.write(channel,bytes);cut.at(record.kind()+"_WRITTEN");fence(expected);
            channel.force(true);cut.at(record.kind()+"_FORCED");fence(expected);
        }
        int offset=journal.length;journal=Arrays.copyOf(journal,offset+bytes.length);System.arraycopy(bytes,0,journal,offset,bytes.length);
    }

    synchronized Optional<Decoded> promised() {live();return Optional.ofNullable(promise);}
    synchronized Optional<Decoded> originalBasis() {live();return Optional.ofNullable(basis);}
    synchronized Optional<Decoded> originalSelection() {live();return Optional.ofNullable(selection);}
    @Override public synchronized void close() throws IOException {
        if(!closed){closed=true;try{if(retirement!=null)retirement.close();if(floors!=null)floors.close();if(inactive!=null)inactive.close();if(current!=null)current.close();if(sources!=null)sources.close();}finally{allocator.close();}}
    }
}
