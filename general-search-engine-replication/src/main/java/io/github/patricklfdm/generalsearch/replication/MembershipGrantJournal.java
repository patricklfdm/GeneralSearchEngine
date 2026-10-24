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
    private byte[] tornBasis=new byte[0];
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
    private MembershipCaptureFiles capture;
    private MembershipPendingAccept pendingAccept;
    private MembershipPendingContextFiles pendingContext;
    private MembershipReplayFiles replayFiles;
    private MembershipAppliedEndFiles appliedEnd;
    private int applicationMetadata;
    private MembershipResources.Lease publicationImage;
    private volatile boolean failed,closed;

    private MembershipGrantJournal(Path directory,MembershipRoot root,MembershipIdentity identity,
            MembershipBallotAllocator allocator,int maximum,MembershipBallotAllocator.Cut cut) throws IOException {
        this(directory,root,identity,allocator,maximum,cut,false);
    }
    private MembershipGrantJournal(Path directory,MembershipRoot root,MembershipIdentity identity,
            MembershipBallotAllocator allocator,int maximum,MembershipBallotAllocator.Cut cut,boolean captureRecovery)throws IOException {
        this.directory=directory;this.path=directory.resolve(FILE);this.root=root;this.identity=identity;
        this.allocator=allocator;this.maximum=maximum;this.cut=cut;fileKey=key();
        journal=AdmissionPaths.read(path,maximum);
        if(captureRecovery && Files.exists(directory.resolve(MembershipCaptureFiles.FILE),LinkOption.NOFOLLOW_LINKS)) {
            int complete=completePrefix(journal);
            tornBasis=Arrays.copyOfRange(journal,complete,journal.length);journal=Arrays.copyOf(journal,complete);
        }
        replay();
        // A complete frame visible after process death is conservatively retained and sealed.
        // A torn tail is never truncated or forced as a substitute for its original BASIS.
        if(tornBasis.length==0) {
            try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {channel.force(true);}
            AdmissionPaths.forceDirectory(directory);
        }
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
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,maximum,withSourceRetirement,false);
    }
    static MembershipGrantJournal openCapturing(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true,MAXIMUM,true,true);
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,
            boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum,boolean withSourceRetirement,boolean withCapture)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,maximum,withSourceRetirement,withCapture,false);
    }
    static MembershipGrantJournal openVoting(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut)throws IOException {
        return openVoting(requested,root,identity,resources,verifier,MAXIMUM,cut);
    }
    static MembershipGrantJournal openVoting(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true,maximum,true,true,true);
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,
            boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum,boolean withSourceRetirement,boolean withCapture,boolean withVotes)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,maximum,withSourceRetirement,withCapture,withVotes,false);
    }
    static MembershipGrantJournal openApplying(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut)throws IOException {
        return openApplying(requested,root,identity,resources,verifier,MAXIMUM,cut);
    }
    static MembershipGrantJournal openApplying(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true,maximum,true,true,true,true);
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,
            boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum,boolean withSourceRetirement,boolean withCapture,boolean withVotes,boolean withApplication)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,
                maximum,withSourceRetirement,withCapture,withVotes,withApplication,false);
    }
    /** Opt-in local context owner. Exact floor maintenance may retire the old generation;
     * the context, backing source and vote stay pinned before any later campaign. */
    static MembershipGrantJournal openContextual(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true,maximum,true,true,true,true,true);
    }
    /** Initial-voter storage entry with actual immutable bootstrap admission.
     * This does not enable the public runtime or admit later learner identities. */
    static MembershipGrantJournal openBootstrapped(Path requested,Path materialization,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,true,true,true,true,maximum,true,true,true,true,true,Objects.requireNonNull(materialization));
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,
            boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum,boolean withSourceRetirement,boolean withCapture,boolean withVotes,boolean withApplication,boolean withContext)throws IOException {
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,maximum,withSourceRetirement,withCapture,withVotes,withApplication,withContext,null);
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,
            boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum,boolean withSourceRetirement,boolean withCapture,boolean withVotes,boolean withApplication,boolean withContext,Path materialization)throws IOException {
        require(maximum>=RESERVATION && maximum<=MAXIMUM,"grant journal capacity");
        Objects.requireNonNull(resources);Objects.requireNonNull(verifier);Objects.requireNonNull(cut);Path path=AdmissionPaths.safe(requested);
        var owner=materialization!=null?MembershipBallotAllocator.openBootstrapped(path,materialization,root,identity,cut):withContext?MembershipBallotAllocator.openWithPendingContext(path,root,identity,cut):withApplication?MembershipBallotAllocator.openWithAppliedEnd(path,root,identity,cut):withVotes?MembershipBallotAllocator.openWithPendingAccept(path,root,identity,cut):withCapture?MembershipBallotAllocator.openWithCaptureRecovery(path,root,identity,cut):withSourceRetirement?MembershipBallotAllocator.openWithSourceRetirement(path,root,identity,cut):withRotation?MembershipBallotAllocator.openWithJournalRotation(path,root,identity,cut):withRetirement?MembershipBallotAllocator.openWithRetirement(path,root,identity,cut):withFloors?MembershipBallotAllocator.openWithFloorCopies(path,root,identity,cut):MembershipBallotAllocator.openWithGenerationInstall(path,root,identity,cut);MembershipGrantJournal journal=null;
        try {
            journal=new MembershipGrantJournal(path,root,identity,owner,maximum,cut,withCapture);journal.resources=resources;journal.capsuleVerifier=verifier;journal.floorReleaseEnabled=withFloorRelease;
            journal.applicationMetadata=withApplication?MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA:0;
            if(withRotation)journal.rotation=new MembershipJournalRotationFiles(path);
            if(withSourceRetirement)journal.sourceRetirement=new MembershipSourceRetirementFiles(path);
            if(withCapture)journal.capture=new MembershipCaptureFiles(path);
            if(withVotes) {
                journal.pendingAccept=new MembershipPendingAccept(path);journal.reloadGenerations();
                // An active context may own the old vote after its physical generation
                // retired. Validate it below, after reserving/resealing its real source
                // and opening the governing floor. Candidates never get this deferral.
                if((!withContext || !Files.exists(path.resolve(MembershipPendingContextFiles.FILE),LinkOption.NOFOLLOW_LINKS))
                        && !journal.settledVoteCandidate(journal.pendingAccept.active()))
                    journal.verifyVote(journal.pendingAccept.active());
                require(journal.pendingBytes()<=maximum-journal.storedJournal().length,"combined pending/grant journal capacity");
            }
            MembershipCaptureFiles.Plan pending=null;
            boolean protectedCapture=withCapture && journal.capture.pending() && withContext
                    && Files.exists(path.resolve(MembershipPendingContextFiles.FILE),LinkOption.NOFOLLOW_LINKS);
            if(withCapture && journal.capture.pending()) {
                require(!journal.rotation.pending() && !journal.sourceRetirement.pending(),"capture conflicts with other pending authority");
                if(journal.current==null)journal.reloadGenerations();
                require(journal.pendingAccept==null || !journal.pendingAccept.pending(),"capture conflicts with incomplete pending vote");
                require(!journal.inactive.pending(),"capture conflicts with pending selector");
                if(!protectedCapture) {
                    pending=journal.capturePlan(journal.promise);
                    journal.checkBasis(pending.basis(),journal.promise);
                    journal.capture.bind(pending);
                }
            }
            if(protectedCapture) {
                var ownerJournal=journal;var plan=new MembershipCaptureFiles.Plan[1];
                journal.sources=new MembershipBasisSources(path,resources,cut,journal.promises,journal.bases,null,journal.promise,originals->{
                    ownerJournal.pendingContext=new MembershipPendingContextFiles(path,root,identity,resources,
                            Math.min(MembershipPendingContextFiles.MAXIMUM_METADATA,maximum-ownerJournal.storedJournal().length-ownerJournal.pendingBytes()));
                    plan[0]=ownerJournal.contextCapturePlan(ownerJournal.promise,originals);
                    ownerJournal.checkBasis(plan[0].basis(),ownerJournal.promise);ownerJournal.capture.bind(plan[0]);return plan[0];
                });pending=plan[0];
            }else journal.sources=new MembershipBasisSources(path,resources,cut,journal.promises,journal.bases,
                    withSourceRetirement?journal.sourceRetirement.decision().orElse(null):null,pending);
            if(withContext && journal.pendingContext==null)journal.pendingContext=new MembershipPendingContextFiles(path,root,identity,resources,
                    Math.min(MembershipPendingContextFiles.MAXIMUM_METADATA,maximum-journal.storedJournal().length-journal.pendingBytes()));
            if(journal.current==null)journal.reloadGenerations();
            if(withFloors) {
                journal.floors=new MembershipFloorFiles(path,root,identity,resources,verifier,withFloorRelease);
                var parents=new ArrayList<MembershipCapsule.Anchor>();journal.addFloorParent(parents);journal.current.verifyParents(parents);
            }
            if(withRetirement)journal.retirement=new MembershipRetirementFiles(path,resources,journal.floors);
            if(withApplication) {
                journal.replayFiles=new MembershipReplayFiles(path.resolve(MembershipReplayFiles.DIRECTORY),resources);
                journal.appliedEnd=new MembershipAppliedEndFiles(path.resolve(MembershipAppliedEndFiles.DIRECTORY),resources,MembershipAppliedEndFiles.METADATA);
                require(!journal.replayFiles.present() && !journal.appliedEnd.present() || journal.pendingAccept.active()!=null
                        && journal.pendingAccept.active().certificate()!=null,"application files without original local certificate");
                if(journal.coveredVote(journal.pendingAccept.active()))require(!journal.replayFiles.present(),"published generation cannot retain replay scratch");
                else if(journal.pendingAccept.active()!=null || journal.pendingAccept.pending()) {
                    // A durable floor/retirement may own the three empty application slots.
                    // Resume maintenance before admitting another vote or application.
                    if(journal.floors.exists() && !journal.appliedEnd.present() && !journal.replayFiles.present()) {
                        journal.reservePublicationImage();
                    }else journal.reserveApplicationCompletion();
                }
            }
            journal.checkOwner();
            if(protectedCapture) {
                journal.contextCaptureIdle(true);journal.retainedContextOriginal(false,true);
                journal.resumeCapture(pending);pending=null;
            }
            if(withContext && (journal.pendingContext.active().isPresent() || journal.pendingContext.pending())) {
                if(!journal.recoverContextAcceptance())journal.retainPendingContext();
            }
            if(withVotes)journal.recoverVote();
            if(pending!=null) {
                require(!journal.floors.pending() && !journal.floors.releasing() && !journal.retirement.pending(),"capture conflicts with pending floor/retirement");
                journal.resumeCapture(pending);
            }
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

    private long pendingBytes(){return (pendingAccept==null?0:pendingAccept.bytes()+(applicationMetadata>0?pendingAccept.clearAllowance():0))+applicationMetadata+(pendingContext==null?0:pendingContext.bytes());}

    /** Exact private persistence under the real local owner and forced source. No old ACK.
     * Original generation deletion additionally requires explicit governing-floor maintenance. */
    synchronized MembershipPendingContext.Reconstructed retainPendingContext()throws IOException {
        require(pendingContext!=null,"context-aware storage owner required");checkOwner();
        if(pendingContext.active().isPresent())return resealPendingContext();
        otherAuthorityTransactionsIdle();applicationReferencesIdle();
        require(!inactive.pending() && !pendingAccept.pending(),"context requires complete original authorities");
        var vote=pendingAccept.active();require(voteReferencesInactive(vote) && carriedVoteUntransferred(),"context requires installed carried vote");
        verifyVote(vote);var originals=inactive.originalFiles();
        require(promise!=null && basis!=null && selection!=null && promise.digest().equals(current.manifest.value().get("promise"))
                && basis.digest().equals(current.manifest.value().get("basis")) && selection.digest().equals(current.manifest.value().get("selection"))
                && vote.entry().digest().equals(selection.value().get("nextEntry")),"context requires exact installed carried selection");
        var local=originalSource();var source=sources.original(basis);
        var expected=MembershipPendingContext.create(root,identity,vote.selector(),originals,vote,promise,local,source.images(),capsuleVerifier);
        byte[] encoded=MembershipPendingContext.encode(expected);
        if(pendingContext.activeBytes().isPresent())require(Arrays.equals(pendingContext.activeBytes().orElseThrow(),encoded),"context original request changed");
        long remaining=pendingContext.completionAllowance(expected);
        require(remaining<=maximum-storedJournal().length-pendingBytes(),"combined context/grant journal completion capacity");
        MembershipGenerationFiles.Guard guard=()->{
            checkOwner();otherAuthorityTransactionsIdle();applicationReferencesIdle();
            require(!pendingAccept.pending() && !inactive.pending() && pendingAccept.active()!=null
                    && Arrays.equals(vote.bytes(),pendingAccept.active().bytes()),"context original vote changed");
        };
        try {
            cut.at("CONTEXT_OWNER_VALIDATED");guard.check();sources.resealOriginal(basis,guard);
            // No fence(promise.ballot): retaining already owned bytes under a higher volatile
            // observation is recovery work, and must not acknowledge the old authority.
            pendingContext.install(expected,null,guard,cut);
            cut.at("CONTEXT_OWNER_BEFORE_RETURN");guard.check();
            return MembershipPendingContext.reconstruct(pendingContext.active().orElseThrow(),root,identity,promise,local,source.images(),capsuleVerifier);
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** Reconstruct old authority from an already forced local context/source; never
     * manufacture a current-generation ownership receipt from these metadata. */
    private MembershipPendingContext.Reconstructed retainedContextOriginal()throws IOException {
        return retainedContextOriginal(false);
    }
    private Decoded retainedContextBasis() {
        return retainedContextBasis(false);
    }
    private Decoded retainedContextBasis(boolean rebinding) {
        require(pendingContext!=null && pendingContext.active().isPresent() && (rebinding || !pendingContext.pending()),"complete retained context required");
        var context=pendingContext.active().orElseThrow();
        var backingPromise=MembershipPendingContext.backingPromise(context);var backingBasis=MembershipPendingContext.backingBasis(context);
        String id=(String)backingBasis.value().get("basisId");var savedPromise=promises.get(id);var savedBasis=bases.get(id);
        var installed=selections.get(current.manifest.value().get("selection"));
        require(savedPromise!=null && savedBasis!=null && Arrays.equals(savedPromise.bytes(),backingPromise.bytes())
                && Arrays.equals(savedBasis.bytes(),backingBasis.bytes()),"retained context exact backing grant missing");
        require(promise!=null && installed!=null && promise.value().get("view").equals(current.capsule.context.authority())
                && compareBallot(object(promise.value().get("ballot")),object(backingPromise.value().get("ballot")))>=0
                && compareBallot(object(backingPromise.value().get("ballot")),object(installed.value().get("ballot")))>=0,
                "retained context backing/installed/latest order changed");
        current.capsule.context.ballot(promise.value().get("ballot"),true);
        return backingBasis;
    }
    private MembershipPendingContext.Reconstructed retainedContextOriginal(boolean replacingVote)throws IOException {
        return retainedContextOriginal(replacingVote,false);
    }
    private MembershipPendingContext.Reconstructed retainedContextOriginal(boolean replacingVote,boolean rebinding)throws IOException {
        require(pendingContext!=null && pendingContext.active().isPresent() && (rebinding || !pendingContext.pending()),"complete retained context required");
        boolean installing=contextInstallationPending();
        require((replacingVote || !pendingAccept.pending()) && (installing || !inactive.pending()),"retained context installed authority changed");
        var backing=retainedContextBasis(rebinding);var installed=selections.get(current.manifest.value().get("selection"));
        var original=MembershipPendingContext.reconstruct(pendingContext.active().orElseThrow(),root,identity,
                promises.get((String)backing.value().get("basisId")),retainedSource(backing),sources.original(backing).images(),capsuleVerifier);
        require(pendingAccept.active()!=null && (replacingVote || Arrays.equals(pendingAccept.active().bytes(),original.vote().bytes()))
                && !Arrays.equals(original.selector().bytes(),current.selector.bytes())
                && original.capsule().terminal().equals(current.capsule.terminal())
                && original.vote().entry().digest().equals(installed.value().get("nextEntry"))
                && compareBallot(object(installed.value().get("ballot")),object(original.vote().promise().value().get("ballot")))>0,
                "retained context original/current binding changed");
        MembershipContextTail.selected(original,current.capsule.packet,current.accepted);
        var expected=original.originalFiles();var record=retirement.authority();
        if(installing) {
            // The inactive slot may contain only part of the caller's exact
            // selected installation. Opening/re-sealing the old context cannot
            // complete or acknowledge that plan. installCurrent checks every byte.
            require(!retirement.pending(),"context installation conflicts with retirement");
            contextRetirementFloor(original);
        }else if(record.isPresent()) {
            var floor=contextRetirementFloor(original);bindRetirement(record.orElseThrow(),floor);retirement.checkSaved(record.orElseThrow());
            var manifest=list(record.orElseThrow().value().get("files")).stream().map(MembershipFormat::object)
                    .filter(row->row.get("path").equals("generations/"+inactive.slot()+"/generation.gsr")).findFirst().orElseThrow();
            if(manifest.get("sha256").equals(original.selector().value().get("digest"))) {
                var inventory=new ArrayList<Map<String,Object>>();
                for(var row:expected.entrySet())inventory.add(Map.of("path","generations/"+inactive.slot()+"/"+row.getKey(),
                        "size",(long)row.getValue().length,"sha256",hash(row.getValue())));
                require(inventory.equals(record.orElseThrow().value().get("files")),"retained context retirement inventory changed");
            }else if(inactive.exists()) {
                var old=contextIntermediate(original,retirement.original());
                var plan=MembershipRetirementPlan.create(root,identity,current,floor,old,original);
                require(Arrays.equals(plan.record.bytes(),record.orElseThrow().bytes()),"context intermediate retirement inventory changed");
            }
            if(inactive.exists()) {
                var originals=manifest.get("sha256").equals(original.selector().value().get("digest"))?expected:retirement.original();
                for(var row:inactive.originalFiles().entrySet())require(Arrays.equals(originals.get(row.getKey()),row.getValue()),"retained context original physical bytes changed");
            }
        }else if(inactive.exists()) {
            var physical=inactive.originalFiles();
            if(Arrays.equals(physical.get("generation.gsr"),expected.get("generation.gsr"))) {
                require(original.selector().value().get("generation").equals(inactive.slot()) && physical.keySet().equals(expected.keySet()),"retained context incomplete original without retirement authority");
                for(var row:physical.entrySet())require(Arrays.equals(expected.get(row.getKey()),row.getValue()),"retained context original physical bytes changed");
            }else MembershipRetirementPlan.create(root,identity,current,contextRetirementFloor(original),contextIntermediate(original,physical),original);
        }else contextRetirementFloor(original);
        return original;
    }
    private boolean contextInstallationPending() {
        if(selection==null || selection.digest().equals(current.manifest.value().get("selection")))return false;
        var installed=selections.get(current.manifest.value().get("selection"));
        return installed!=null && basis!=null && pendingContext.active().isPresent()
                && Arrays.equals(basis.bytes(),MembershipPendingContext.backingBasis(pendingContext.active().orElseThrow()).bytes())
                && selection.value().get("cut").equals(current.capsule.context.cut)
                && Objects.equals(selection.value().get("nextEntry"),installed.value().get("nextEntry"))
                && compareBallot(object(selection.value().get("ballot")),object(installed.value().get("ballot")))>0;
    }
    private MembershipFloorFiles.Retained contextRetirementFloor(MembershipPendingContext.Reconstructed original)throws IOException {
        var floor=floors.retained().orElseThrow(()->new IllegalArgumentException("retained context missing governing retirement floor"));
        var local=floor.copies().stream().filter(c->c.owner.equals(identity)).findFirst().orElseThrow();
        MembershipFloor.verify(floor.floor(),root,local,floor.copies());
        var floorBallot=object(decode(local.fileBytes("promise.gsr"),"records","PROMISE").value().get("ballot"));
        var installed=selections.get(current.manifest.value().get("selection"));
        require(local.capsule.terminal().equals(original.capsule().terminal())
                && original.vote().accept().digest().equals(local.generation.value().get("ownedTail"))
                && compareBallot(floorBallot,object(original.vote().promise().value().get("ballot")))>0
                && compareBallot(floorBallot,object(installed.value().get("ballot")))<=0,"retained context retirement floor changed");
        current.verifyParents(List.of(local.capsule.terminal()));return floor;
    }
    private MembershipFloor.Copy contextIntermediate(MembershipPendingContext.Reconstructed original,Map<String,byte[]> files)throws IOException {
        var old=originalGeneration(files);var ballot=object(decode(files.get("promise.gsr"),"records","PROMISE").value().get("ballot"));
        var installed=selections.get(current.manifest.value().get("selection"));
        require(old.generation.value().get("generation").equals(inactive.slot()) && old.capsule.terminal().equals(original.capsule().terminal())
                && compareBallot(ballot,object(original.vote().promise().value().get("ballot")))>0
                && compareBallot(ballot,object(installed.value().get("ballot")))<0,"context intermediate generation changed");
        MembershipContextTail.selected(original,old.capsule.packet,(String)old.generation.value().get("ownedTail"));return old;
    }
    private MembershipPendingContext.Reconstructed resealPendingContext()throws IOException {
        var original=retainedContextOriginal();applicationReferencesIdle();
        MembershipGenerationFiles.Guard guard=()->{checkOwner();retainedContextOriginal();applicationReferencesIdle();};
        try {
            cut.at("CONTEXT_OWNER_VALIDATED");guard.check();sources.resealOriginal(retainedContextBasis(),guard);
            pendingContext.install(pendingContext.active().orElseThrow(),null,guard,cut);
            cut.at("CONTEXT_OWNER_BEFORE_RETURN");guard.check();return original;
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** The only extra permissions are exact floor copying/establishment and old
     * generation retirement. Context/source/vote and the floor remain pinned. */
    private void contextMaintenanceIdle()throws IOException {
        checkOwner();retainedContextOriginal();applicationReferencesIdle();
        require(!contextInstallationPending() && !inactive.pending(),"pending context installation requires exact original completion");
        require(!capture.pending() && !sourceRetirement.pending() && !rotation.pending() && !floors.releasing(),
                "context maintenance conflicts with another authority transaction");
    }
    private void contextTransactionIdle() {
        require(pendingContext==null || pendingContext.active().isEmpty() && !pendingContext.pending(),
                "retained pending context requires transferred lifetime completion");
    }
    /** Only the exact carried entry may replace context-backed old voting authority.
     * The backing source stays retained; a reacceptance is not a context/source rebind. */
    synchronized Owned acceptRetainedCurrent(Decoded proposed,byte[] payload)throws IOException {
        require(pendingContext!=null,"context-aware storage owner required");checkOwner();
        if(pendingContext.active().isEmpty() && !pendingContext.pending()) {
            var active=pendingAccept.active();
            require(active!=null && Arrays.equals(active.selector().bytes(),current.selector.bytes())
                    && Arrays.equals(active.entry().bytes(),proposed.bytes()) && Arrays.equals(active.payload(),payload)
                    && selection!=null && active.entry().digest().equals(selection.value().get("nextEntry")),
                    "context acceptance retry requires exact installed successor");
            verifyVote(active);releaseFloor();return acceptCurrent(proposed,payload);
        }
        var original=retainedContextOriginal(true);
        require(Arrays.equals(original.vote().entry().bytes(),proposed.bytes()) && Arrays.equals(original.vote().payload(),payload),
                "context acceptance changed original entry/payload");
        var vote=contextAcceptance(original);var bound=object(vote.accept().value().get("ballot"));fence(bound);
        completeContextAcceptance(original,vote,true);
        cut.at("CONTEXT_ACCEPT_BEFORE_RETURN");checkOwner();fence(bound);
        return new Owned(identity.nodeId().value(),identity.storageId(),vote.accept().digest(),cutDigest(current.capsule.context.cut));
    }
    private MembershipPendingAccept.Vote contextAcceptance(MembershipPendingContext.Reconstructed original)throws IOException {
        checkOwner();otherAuthorityTransactionsIdle();applicationReferencesIdle();
        require(promise!=null && basis!=null && selection!=null && promise.digest().equals(current.manifest.value().get("promise"))
                && basis.digest().equals(current.manifest.value().get("basis")) && selection.digest().equals(current.manifest.value().get("selection")),
                "context acceptance requires installed current ballot");
        require(!inactive.exists() && !inactive.pending() && !pendingContext.pending(),"context acceptance requires retired original and complete context");
        var old=original.vote();var bound=object(promise.value().get("ballot"));
        require(compareBallot(bound,object(old.accept().value().get("ballot")))>0,"context acceptance requires newer installed ballot");
        var value=Map.<String,Object>of("root",root.manifestDigest(),"authority",current.capsule.context.authority(),
                "ballot",bound,"entry",old.entry().digest(),"index",old.entry().value().get("index"));
        var vote=new MembershipPendingAccept.Vote(current.selector,promise,selection,old.entry(),decode(encode("records","ACCEPT",value),"records","ACCEPT"),old.payload());
        MembershipPendingAccept.verify(vote,current,identity,promises.values(),selections.values());
        bindInstalledVote(vote);pendingAccept.matches(vote);floors.checkRelease(current,vote);
        require(Arrays.equals(pendingAccept.active().bytes(),old.bytes()) || Arrays.equals(pendingAccept.active().bytes(),vote.bytes()),
                "context acceptance active vote differs from exact predecessor/successor");
        return vote;
    }
    /** Reopen can finish only a prefix of the uniquely selected successor, never issue an ACK. */
    private boolean recoverContextAcceptance()throws IOException {
        if(pendingContext.active().isEmpty() || pendingContext.pending())return false;
        var original=retainedContextOriginal(true);
        if(!pendingAccept.pending() && Arrays.equals(pendingAccept.active().bytes(),original.vote().bytes()))return false;
        completeContextAcceptance(original,contextAcceptance(original),false);return true;
    }
    private void completeContextAcceptance(MembershipPendingContext.Reconstructed original,MembershipPendingAccept.Vote vote,boolean acknowledge)throws IOException {
        byte[] context=pendingContext.activeBytes().orElseThrow(),prior=original.vote().bytes(),next=vote.bytes();
        var bound=object(vote.accept().value().get("ballot"));
        boolean installed=Arrays.equals(pendingAccept.active().bytes(),next);
        publicationCapacity(vote,acknowledge && !pendingAccept.pending() && !installed
                ?AutomaticReplicationException.Outcome.NOT_SUBMITTED:AutomaticReplicationException.Outcome.INDETERMINATE);
        long peak=Math.max((long)pendingAccept.activeLength()+next.length,2L*(next.length+MembershipPendingAccept.PROOF_MAXIMUM)+MembershipPendingAccept.CERTIFICATE_MAXIMUM);
        require(peak-pendingAccept.bytes()+RESERVATION<=maximum-storedJournal().length-pendingBytes(),
                "context acceptance and phased completion exceed shared journal capacity");
        MembershipGenerationFiles.Guard guard=()->{
            checkOwner();otherAuthorityTransactionsIdle();applicationReferencesIdle();
            if(pendingContext.active().isPresent()) {
                require(Arrays.equals(context,pendingContext.activeBytes().orElseThrow()),"context acceptance original context changed");
                require(Arrays.equals(prior,retainedContextOriginal(true).vote().bytes()),"context acceptance reconstructed original changed");
            }else require(!pendingAccept.pending() && Arrays.equals(next,pendingAccept.active().bytes()),"context removed without complete successor");
            require(Arrays.equals(prior,pendingAccept.active().bytes()) || Arrays.equals(next,pendingAccept.active().bytes()),"context acceptance active vote changed");
        };
        try {
            cut.at("CONTEXT_ACCEPT_VALIDATED");guard.check();if(acknowledge)fence(bound);
            if(!installed || pendingAccept.pending())pendingAccept.install(vote,()->{guard.check();if(acknowledge)fence(bound);},cut);
            // Re-force even after rename/lost return before discarding the sole old metadata.
            pendingAccept.sealActive(guard,cut);guard.check();
            require(!pendingAccept.pending() && Arrays.equals(next,pendingAccept.active().bytes()),"context acceptance successor incomplete");
            cut.at("CONTEXT_ACCEPT_SUCCESSOR_FORCED");guard.check();
            pendingContext.clearRedundant(context,guard,cut);
            cut.at("CONTEXT_ACCEPT_CLEARED");guard.check();
            // Floor copies were required while the old vote depended on the context.
            // The fully forced current vote now owns its exact selector/entry instead.
            // Reclaim those copies before reserving replay input/output + applied end;
            // no acknowledgement is returned until all completion slots are owned.
            releaseFloor();reserveApplicationCompletion();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }

    /** Roll back the optional duplicate metadata only while its complete originals still exist.
     * Safe after a lost cleanup return: an absent context grants no new authority. */
    synchronized void discardRedundantPendingContext()throws IOException {
        require(pendingContext!=null,"context-aware storage owner required");checkOwner();
        require(!pendingContext.pending(),"pending context must complete before redundant cleanup");
        if(pendingContext.active().isEmpty())return;
        var original=retainPendingContext();byte[] exact=pendingContext.activeBytes().orElseThrow();
        MembershipGenerationFiles.Guard guard=()->{
            checkOwner();otherAuthorityTransactionsIdle();applicationReferencesIdle();
            require(!inactive.pending() && !pendingAccept.pending() && pendingAccept.active()!=null
                    && Arrays.equals(original.vote().bytes(),pendingAccept.active().bytes()),"redundant context original vote changed");
            verifyVote(pendingAccept.active());
            var files=inactive.originalFiles();var expected=original.originalFiles();
            require(files.keySet().equals(expected.keySet()),"redundant context original inventory changed");
            for(String name:expected.keySet())require(Arrays.equals(expected.get(name),files.get(name)),"redundant context original bytes changed");
        };
        try{guard.check();pendingContext.clearRedundant(exact,guard,cut);}
        catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void reserveApplicationCompletion() {
        if(appliedEnd==null)return;
        boolean end=appliedEnd.completionReserved(),replay=replayFiles.completionReserved();
        try{appliedEnd.reserveCompletion();replayFiles.reserveCompletion();reservePublicationImage();}
        catch(RuntimeException|Error error) {
            // Failed admission must not consume the slots needed to finish maintenance.
            try{if(!replay)replayFiles.releaseCompletion();if(!end)appliedEnd.releaseEmptyCompletion();}
            catch(IOException|RuntimeException|Error cleanup){failed=true;error.addSuppressed(cleanup);}throw error;
        }
    }
    private void reservePublicationImage() {
        if(publicationImage==null && !inactive.reservePublicationImage())
            publicationImage=resources.reserve(MembershipResources.Unit.APPLICATION,"publication-completion",MembershipResources.Unit.APPLICATION.bytes);
    }
    private void releasePublicationImage() {
        if(publicationImage!=null){publicationImage.close();publicationImage=null;}
    }
    private boolean coveredVote(MembershipPendingAccept.Vote vote)throws IOException {
        return vote!=null && vote.certificate()!=null && current.publishedCertificate().filter(vote.certificate().digest()::equals).isPresent();
    }
    private boolean voteReferencesInactive(MembershipPendingAccept.Vote vote)throws IOException {
        return vote!=null && !coveredVote(vote) && !Arrays.equals(vote.selector().bytes(),current.selector.bytes());
    }
    /** Only a classification for deferred validation, never permission to erase. */
    private boolean settledVoteCandidate(MembershipPendingAccept.Vote vote)throws IOException {
        return vote!=null && !Arrays.equals(vote.selector().bytes(),current.selector.bytes()) && !coveredVote(vote)
                && number(vote.entry().value().get("index"))<=number(current.capsule.context.cut.get("index"));
    }
    private void verifySettledVote(MembershipPendingAccept.Vote vote)throws IOException {
        require(settledVoteCandidate(vote) && !inactive.pending(),"settled vote requires completed installed selector");
        verifySettlement(vote,inactive.originalFiles(),current.capsule,current.copyFiles());
    }
    /** The exact original minority source stays pinned after clearing the vote.
     * It is reclaimed later only by the normal independently forced floor path. */
    private void verifySettlement(MembershipPendingAccept.Vote vote,Map<String,byte[]> originals,
            MembershipCapsule next,Map<String,byte[]> installed)throws IOException {
        require(vote!=null && vote.proof()==null && vote.certificate()==null,"settlement requires bare original ACCEPT");
        require(appliedEnd!=null && replayFiles!=null && !appliedEnd.present() && !replayFiles.present()
                && (pendingContext==null || pendingContext.active().isEmpty() && !pendingContext.pending()),"settlement conflicts with derived or protected authority");
        var old=originalGeneration(originals);var selector=vote.selector().value();
        require(selector.get("root").equals(root.manifestDigest()) && selector.get("node").equals(identity.nodeId().value())
                && selector.get("generation").equals(old.generation.value().get("generation")) && selector.get("digest").equals(old.generation.digest()),"settlement original selector changed");
        require(Arrays.equals(originals.get("promise.gsr"),vote.promise().bytes()) && Arrays.equals(originals.get("selected.gsr"),vote.selected().bytes()),"settlement original decision changed");
        MembershipPendingAccept.verify(vote,old.capsule,originals.get(MembershipSelectionCoverage.FILE),originals.getOrDefault("ancestry.gsr",new byte[0]),identity,promises.values(),selections.values());
        require(!installed.containsKey(MembershipSelectionCoverage.FILE) && !installed.containsKey(MembershipGenerationPlan.ADOPTION)
                && next.context.authority().equals(old.capsule.context.authority()) && next.context.view.get("operation")==null
                && number(next.context.cut.get("index"))>=number(vote.entry().value().get("index")),"settlement requires advanced stable selected prefix");
        next.verifyAncestry(installed.getOrDefault("ancestry.gsr",new byte[0]),List.of(old.capsule.terminal()));
        var p=decode(installed.get("promise.gsr"),"records","PROMISE");var b=decode(installed.get("basis.gsr"),"records","BASIS");var s=decode(installed.get("selected.gsr"),"records","SELECTED");
        require(promise!=null && basis!=null && selection!=null && Arrays.equals(p.bytes(),promise.bytes())
                && Arrays.equals(b.bytes(),basis.bytes()) && Arrays.equals(s.bytes(),selection.bytes())
                && compareBallot(object(p.value().get("ballot")),object(vote.promise().value().get("ballot")))>0
                && s.value().get("cut").equals(next.context.cut),"settlement installed decision changed");
        require(b.value().get("voter").equals(identity.nodeId().value()) && vote.accept().digest().equals(b.value().get("accepted"))
                && b.value().get("cut").equals(old.capsule.context.cut)
                && list(s.value().get("sources")).stream().map(MembershipFormat::object).anyMatch(row->row.get("voter").equals(identity.nodeId().value())
                    && row.get("basisId").equals(b.value().get("basisId")) && row.get("basisDigest").equals(b.digest())),"settlement missing exact original local source");
        var source=sources.original(b);source.packet().bind(b);
        var expected=MembershipPendingAccept.packet(old.capsule.packet,vote);
        require(Arrays.equals(expected.bytes(),source.packet().bytes()),"settlement source changed original vote");
        source.packet().verifyImages(source.images());
    }
    private void retireSettledVote()throws IOException {
        var original=pendingAccept.active();verifySettledVote(original);
        otherAuthorityTransactionsIdle();
        MembershipGenerationFiles.Guard guard=()->{
            checkOwner();verifySettledVote(original);otherAuthorityTransactionsIdle();
            require(pendingAccept.active()==null || Arrays.equals(pendingAccept.active().bytes(),original.bytes()),"settled vote changed during retirement");
        };
        cut.at("SETTLED_VOTE_VALIDATED");guard.check();pendingAccept.clearSettled(original,guard,cut);
        replayFiles.releaseCompletion();appliedEnd.releaseEmptyCompletion();releasePublicationImage();
        cut.at("SETTLED_VOTE_BEFORE_RETURN");checkOwner();
    }
    private void verifyVote(MembershipPendingAccept.Vote vote)throws IOException {
        if(pendingContext!=null && pendingContext.active().isPresent()) {
            require(vote!=null && Arrays.equals(vote.bytes(),retainedContextOriginal().vote().bytes()),"pending vote differs from retained context");
        }
        else if(applicationMetadata>0 && coveredVote(vote))verifyCoveredVote(vote);
        else if(settledVoteCandidate(vote))verifySettledVote(vote);
        else if(voteReferencesInactive(vote)) {
            // A new selected generation has the same parent but a different round.
            // The old vote still needs its own retained selector and round coverage.
            var originals=inactive.originalFiles();var old=originalGeneration(originals);var selector=vote.selector().value();
            require(current.capsule.terminal().equals(old.capsule.terminal()) && selector.get("generation").equals(inactive.slot())
                    && selector.get("digest").equals(old.generation.digest()) && selector.get("root").equals(root.manifestDigest())
                    && selector.get("node").equals(identity.nodeId().value()),"carried vote original selector/parent changed");
            var installedPromise=promises.values().stream().filter(p->p.digest().equals(current.manifest.value().get("promise"))).findFirst().orElseThrow();
            require(Arrays.equals(originals.get("promise.gsr"),vote.promise().bytes()) && Arrays.equals(originals.get("selected.gsr"),vote.selected().bytes())
                    && current.manifest.value().get("selection")!=null && compareBallot(object(installedPromise.value().get("ballot")),object(vote.promise().value().get("ballot")))>0,
                    "carried vote original decision changed");
            MembershipPendingAccept.verify(vote,old.capsule,originals.get(MembershipSelectionCoverage.FILE),originals.getOrDefault("ancestry.gsr",new byte[0]),identity,promises.values(),selections.values());
        }
        else MembershipPendingAccept.verify(vote,current,identity,promises.values(),selections.values());
    }
    private void verifyCoveredVote(MembershipPendingAccept.Vote vote)throws IOException {
        require(coveredVote(vote) && !inactive.pending(),"pending vote lacks exact covering selector");
        var originals=inactive.originalFiles();var old=originalGeneration(originals);
        require(current.publishedParent().equals(old.capsule.terminal()),"covering generation changed original parent state");
        var selector=vote.selector().value();
        require(selector.get("generation").equals(inactive.slot()) && selector.get("digest").equals(old.generation.digest())
                && selector.get("root").equals(root.manifestDigest()) && selector.get("node").equals(identity.nodeId().value()),"covered vote original selector");
        require(Arrays.equals(originals.get("promise.gsr"),vote.promise().bytes()) && Arrays.equals(originals.get("selected.gsr"),vote.selected().bytes())
                && current.manifest.value().get("selection").equals(vote.selected().digest()) && current.manifest.value().get("promise").equals(vote.promise().digest()),"covered vote original decision changed");
        MembershipPendingAccept.verify(vote,old.capsule,originals.get(MembershipSelectionCoverage.FILE),originals.getOrDefault("ancestry.gsr",new byte[0]),identity,promises.values(),selections.values());
        for(var frame:List.of(vote.entry(),vote.accept(),vote.proof(),vote.certificate()))
            require(Arrays.equals(frame.bytes(),current.capsule.packet.objectBytes(frame.digest())),"covered vote missing original phase");
        require(Arrays.equals(vote.payload(),current.capsule.packet.objectBytes((String)vote.entry().value().get("payload")))
                && current.capsule.context.cut.get("entry").equals(vote.entry().digest()) && current.capsule.context.cut.get("index").equals(vote.entry().value().get("index")),"covered vote exact published entry");
    }
    private String voteAccepted(){return MembershipPendingAccept.accepted(current,pendingAccept==null?null:pendingAccept.active());}
    private MembershipSourcePacket votePacket(){return MembershipPendingAccept.packet(current,pendingAccept==null?null:pendingAccept.active());}
    private MembershipCaptureFiles.Plan capturePlan(Decoded grant)throws IOException {
        return MembershipCaptureFiles.plan(current,grant,identity,votePacket(),voteAccepted());
    }
    /** A pending source is derived only from already validated complete backing bytes.
     * Source inventory admission has not forced anything and supplies no Owned receipt. */
    private MembershipCaptureFiles.Plan contextCapturePlan(Decoded grant,MembershipBasisSources.Originals originals)throws IOException {
        var context=pendingContext.active().orElseThrow();var backingPromise=MembershipPendingContext.backingPromise(context);
        var backingBasis=MembershipPendingContext.backingBasis(context);String id=(String)backingBasis.value().get("basisId");
        require(promises.containsKey(id) && bases.containsKey(id) && Arrays.equals(promises.get(id).bytes(),backingPromise.bytes())
                && Arrays.equals(bases.get(id).bytes(),backingBasis.bytes()),"context capture backing grant absent");
        var stored=originals.read(backingBasis);var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var backing=Objects.requireNonNull(capsuleVerifier.verify(localRoot,stored.packet(),stored.images()));
        require(Arrays.equals(backing.packet.bytes(),stored.packet().bytes()),"context capture verifier substituted backing");
        var original=MembershipPendingContext.reconstructStored(context,root,identity,backingPromise,backingBasis,backing,stored.images(),capsuleVerifier);
        require(pendingAccept.active()!=null && Arrays.equals(original.vote().bytes(),pendingAccept.active().bytes()),"context capture original vote changed");
        var protectedSource=MembershipPendingTransfer.capture(original,current.capsule,current.images(),capsuleVerifier);
        var plan=MembershipCaptureFiles.plan(current,grant,identity,protectedSource.capsule().packet,MembershipPendingAccept.accepted(current,original.vote()),protectedSource.images());
        MembershipPendingContext.Context expected=context;
        if(!Arrays.equals(backingBasis.bytes(),plan.basis().bytes()))expected=MembershipPendingContext.rebindStored(context,root,identity,
                backingPromise,backingBasis,backing,stored.images(),grant,plan.basis(),protectedSource.capsule(),plan.images(),capsuleVerifier);
        // Validate even a well-framed foreign candidate before resuming the source or
        // appending its BASIS. A syntactic context prefix is never repair authority.
        long remainingBasis=basis==null?plan.basis().bytes().length-tornBasis.length:0;
        require(pendingContext.completionAllowance(expected)+remainingBasis<=maximum-storedJournal().length-pendingBytes(),"context capture completion capacity");
        return plan;
    }
    private void contextCaptureIdle(boolean recovering)throws IOException {
        checkOwner();applicationReferencesIdle();
        require(!inactive.exists() && !inactive.pending() && !pendingAccept.pending() && !sourceRetirement.pending()
                && !rotation.pending() && !floors.pending() && !floors.releasing() && !retirement.pending()
                && (recovering || !capture.pending() && !pendingContext.pending()),"context capture requires idle retired original generation");
        var original=retainedContextOriginal(false,recovering);
        require(!sources.retainedIdentities().contains(original.vote().promise().value().get("basisId")),"context capture requires retired predecessor source");
    }
    private void completeContextCapture(MembershipCaptureFiles.Plan plan)throws IOException {
        contextCaptureIdle(true);var prior=pendingContext.active().orElseThrow();var oldBasis=retainedContextBasis(true);
        var oldPromise=promises.get((String)oldBasis.value().get("basisId"));MembershipPendingContext.Context expected=prior;
        if(!Arrays.equals(oldBasis.bytes(),plan.basis().bytes())) {
            expected=MembershipPendingContext.rebind(prior,root,identity,oldPromise,retainedSource(oldBasis),sources.original(oldBasis).images(),
                    plan.promise(),retainedSource(plan.basis()),sources.original(plan.basis()).images(),capsuleVerifier);
        }
        require(pendingContext.completionAllowance(expected)<=maximum-storedJournal().length-pendingBytes(),"context capture completion capacity");
        MembershipGenerationFiles.Guard guard=()->{checkOwner();contextCaptureIdle(true);};
        sources.resealOriginal(plan.basis(),guard);
        pendingContext.install(expected,MembershipPendingContext.encode(prior),guard,cut);
        require(Arrays.equals(retainedContextBasis().bytes(),plan.basis().bytes()),"context capture did not install exact backing");
    }
    private MembershipCapsule verifiedPacket(MembershipSourcePacket packet)throws IOException {
        var rootRecord=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var result=Objects.requireNonNull(capsuleVerifier.verify(rootRecord,packet,current.images()));
        require(Arrays.equals(packet.bytes(),result.packet.bytes()),"pending verifier substituted original packet");return result;
    }
    private MembershipCapsule voteCapsule()throws IOException {
        return pendingAccept==null || pendingAccept.active()==null?current.capsule:verifiedPacket(votePacket());
    }
    private void voteTransactionIdle()throws IOException {
        applicationTransactionIdle();require(!inactive.pending(),"pending ACCEPT conflicts with pending selector");
    }
    private void applicationTransactionIdle()throws IOException {
        applicationRetirementIdle();otherApplicationTransactionsIdle();
    }
    private void applicationRetirementIdle() {
        require(appliedEnd==null || !appliedEnd.retirementPending(),"staged retirement must finish before authority changes");
        require(appliedEnd==null || !appliedEnd.present() && !replayFiles.present() || !carriedVoteUntransferred(),
                "carried application staging must retire before another authority change");
    }
    private boolean carriedVoteUntransferred() {
        if(pendingAccept==null || pendingAccept.active()==null)return false;
        var vote=pendingAccept.active();return !Arrays.equals(vote.selector().bytes(),current.selector.bytes())
                && !vote.selected().digest().equals(current.manifest.value().get("selection"));
    }
    private void otherApplicationTransactionsIdle()throws IOException {
        contextTransactionIdle();otherAuthorityTransactionsIdle();
    }
    private void otherAuthorityTransactionsIdle()throws IOException {
        require(!capture.pending() && !sourceRetirement.pending() && !rotation.pending()
                && !floors.pending() && !floors.releasing() && !retirement.pending(),"pending ACCEPT conflicts with other authority transaction");
    }
    private void bindVoteCandidate(MembershipPendingAccept.Vote vote)throws IOException {
        verifyVote(vote);voteTransactionIdle();bindInstalledVote(vote);
    }
    private void bindInstalledVote(MembershipPendingAccept.Vote vote)throws IOException {
        require(vote.proof()==null || pendingAccept.active()!=null && vote.sameAcceptance(pendingAccept.active()),"PROOF candidate requires original active ACCEPT");
        require(vote.certificate()==null || pendingAccept.active()!=null && pendingAccept.active().proof()!=null && vote.sameProof(pendingAccept.active()),"certificate candidate requires original active PROOF");
        require(selection!=null && promise!=null && Arrays.equals(vote.promise().bytes(),promise.bytes())
                && Arrays.equals(vote.selected().bytes(),selection.bytes()) && Arrays.equals(vote.selector().bytes(),current.selector.bytes())
                && selection.digest().equals(current.manifest.value().get("selection")),"pending ACCEPT requires exact installed current selection");
        if(pendingAccept.active()!=null) {
            var prior=pendingAccept.active();int order=compareBallot(object(vote.accept().value().get("ballot")),object(prior.accept().value().get("ballot")));
            require(order>0 || order==0 && vote.sameAcceptance(prior)
                    && (prior.proof()==null || vote.proof()!=null && Arrays.equals(prior.proof().bytes(),vote.proof().bytes()))
                    && (prior.certificate()==null || vote.certificate()!=null && Arrays.equals(prior.certificate().bytes(),vote.certificate().bytes())),"pending ACCEPT conflict or obsolete ballot");
        }
        // The future original source must fit before this owner acknowledges a new vote.
        var packet=MembershipPendingAccept.packet(current,vote);verifiedPacket(packet);
        if(vote.certificate()==null) {
            // Preserve space for all remaining exact phased objects and their bounded index rows.
            int count=vote.proof()==null?2:1;
            int margin=MembershipPendingAccept.CERTIFICATE_MAXIMUM+128+(count==2?MembershipPendingAccept.PROOF_MAXIMUM+128:0);
            require(packet.objectNames().size()<=65536-count && packet.bytes().length<=MembershipSourcePacket.MAXIMUM-margin
                    && packet.capsule().bytes().length+MembershipSourcePacket.index(
                        packet.objectNames().stream().collect(java.util.stream.Collectors.toMap(h->h,packet::objectBytes)),packet.images()).length
                        <=MembershipSourcePacket.ENVELOPE-HEADER-8-count*128,"pending phased source completion capacity");
        }
        MembershipPendingAccept.accepted(current,vote);
    }
    private void recoverVote()throws IOException {
        verifyVote(pendingAccept.active());
        if(pendingAccept!=null && settledVoteCandidate(pendingAccept.active()))retireSettledVote();
        if(appliedEnd!=null && coveredVote(pendingAccept.active()))retireCoveredApplication();
        if(pendingAccept.pending()) {
            voteTransactionIdle();var complete=pendingAccept.completeCandidate();
            if(complete.isPresent()) {
                var vote=complete.get();bindVoteCandidate(vote);var bound=object(vote.accept().value().get("ballot"));
                cut.at(vote.phase()+"_RECOVERY_VALIDATED");checkOwner();fence(bound);
                pendingAccept.install(vote,()->{checkOwner();fence(bound);},cut);
            }
        }
        pendingAccept.sealActive(this::checkOwner,cut);
    }
    /** Actual local next-slot vote under the immutable original selection. No certificate, application publication or network ACK. */
    synchronized Owned acceptCurrent(Decoded proposed,byte[] payload)throws IOException {
        require(pendingAccept!=null,"pending ACCEPT storage owner required");checkOwner();voteTransactionIdle();
        require(promise!=null && selection!=null && selection.digest().equals(current.manifest.value().get("selection")),"ACCEPT requires installed current selection");
        var entry=decode(proposed.bytes(),"records","ENTRY");var bound=object(promise.value().get("ballot"));fence(bound);
        var value=new TreeMap<String,Object>();value.put("root",root.manifestDigest());value.put("authority",current.capsule.context.authority());
        value.put("ballot",bound);value.put("entry",entry.digest());value.put("index",entry.value().get("index"));
        var accepted=decode(encode("records","ACCEPT",value),"records","ACCEPT");
        var vote=new MembershipPendingAccept.Vote(current.selector,promise,selection,entry,accepted,payload);
        // Repeating ACCEPT cannot erase this owner's already forced proof.
        if(pendingAccept.active()!=null && vote.sameAcceptance(pendingAccept.active())) {
            require(!pendingAccept.pending(),"ACCEPT duplicate cannot replace pending PROOF transaction");vote=pendingAccept.active();
        }
        bindVoteCandidate(vote);pendingAccept.matches(vote);checkOwner();fence(bound);
        if(appliedEnd!=null && (appliedEnd.present() || replayFiles.present()))require(pendingAccept.active()!=null
                && Arrays.equals(pendingAccept.active().bytes(),vote.bytes()),"staged application requires original certificate or covering publication");
        if(appliedEnd!=null && (pendingAccept.active()==null || !vote.sameAcceptance(pendingAccept.active())))
            publicationCapacity(vote,pendingAccept.pending()?AutomaticReplicationException.Outcome.INDETERMINATE:AutomaticReplicationException.Outcome.NOT_SUBMITTED);
        reserveApplicationCompletion();
        if(pendingAccept.active()==null || !Arrays.equals(pendingAccept.active().bytes(),vote.bytes()) || pendingAccept.pending()) {
            int size=vote.bytes().length;
            long peak=Math.max((long)pendingAccept.activeLength()+size,2L*(size+MembershipPendingAccept.PROOF_MAXIMUM)+MembershipPendingAccept.CERTIFICATE_MAXIMUM);
            int remaining=Math.toIntExact(peak-pendingAccept.bytes());
            ensureJournalCapacity(Math.addExact(remaining,RESERVATION),"pending ACCEPT, proof completion and next grant exceed shared journal capacity");
            try {
                cut.at("ACCEPT_VALIDATED");checkOwner();fence(bound);
                pendingAccept.install(vote,()->{checkOwner();fence(bound);},cut);
            }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
        }
        cut.at("ACCEPT_BEFORE_RETURN");checkOwner();fence(bound);
        return new Owned(identity.nodeId().value(),identity.storageId(),accepted.digest(),cutDigest(current.capsule.context.cut));
    }

    /** Force the first exact ACCEPT-quorum proof under the same installed selection. */
    synchronized Owned proveCurrent(Decoded proposed,Set<Owned> accepts)throws IOException {
        require(pendingAccept!=null,"pending PROOF storage owner required");checkOwner();voteTransactionIdle();
        var prior=pendingAccept.active();require(prior!=null,"PROOF requires actual local ACCEPT");
        var proof=decode(proposed.bytes(),"records","PROOF");var vote=prior.withProof(proof);
        if(prior.proof()!=null)require(!pendingAccept.pending(),"PROOF duplicate cannot replace pending certificate transaction");
        bindVoteCandidate(vote);pendingAccept.matches(vote);var bound=object(vote.accept().value().get("ballot"));fence(bound);
        // A locally forced duplicate is already the durable attestation. First admission
        // (including an incomplete candidate) still requires the actual ACCEPT observations.
        if(prior.proof()==null)current.capsule.context.proof(proof,prior.accept(),accepts);
        if(prior.proof()==null || pendingAccept.pending()) {
            int size=vote.bytes().length;long peak=Math.max((long)pendingAccept.activeLength()+size,2L*size+MembershipPendingAccept.CERTIFICATE_MAXIMUM);
            int remaining=Math.toIntExact(peak-pendingAccept.bytes());
            ensureJournalCapacity(Math.addExact(remaining,RESERVATION),"pending PROOF, certificate completion and next grant exceed shared journal capacity");
            try {
                cut.at("PROOF_VALIDATED");checkOwner();fence(bound);
                pendingAccept.install(vote,()->{checkOwner();fence(bound);},cut);
            }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
        }
        cut.at("PROOF_BEFORE_RETURN");checkOwner();fence(bound);
        return new Owned(identity.nodeId().value(),identity.storageId(),proof.digest(),cutDigest(current.capsule.context.cut));
    }
    /** Local retained proof only; this accessor makes no new assertion about remote voters. */
    synchronized Optional<Owned> currentOwnedProof()throws IOException {
        require(pendingAccept!=null,"pending PROOF storage owner required");checkOwner();require(!pendingAccept.pending(),"pending PROOF is not complete");
        var vote=pendingAccept.active();return vote==null || vote.proof()==null?Optional.empty():Optional.of(
                new Owned(identity.nodeId().value(),identity.storageId(),vote.proof().digest(),cutDigest(current.capsule.context.cut)));
    }

    /** Persist a certificate over real exact phased observations; this does not apply/publish it. */
    synchronized Decoded certifyCurrent(Decoded proposed,Set<Owned> owned)throws IOException {
        require(pendingAccept!=null,"pending certificate storage owner required");checkOwner();voteTransactionIdle();
        var prior=pendingAccept.active();require(prior!=null && prior.proof()!=null,"certificate requires actual local PROOF");
        var certificate=decode(proposed.bytes(),"records","CERTIFICATE");var vote=prior.withCertificate(certificate);
        bindVoteCandidate(vote);pendingAccept.matches(vote);var bound=object(vote.accept().value().get("ballot"));fence(bound);
        if(prior.certificate()==null) {
            Objects.requireNonNull(owned,"owned phased observations");require(owned.size()<=12,"certificate observation count");
            verifiedPacket(MembershipPendingAccept.packet(current,vote)).context.certificate(certificate,Set.copyOf(owned));
        }
        if(prior.certificate()==null || pendingAccept.pending()) {
            int remaining=Math.toIntExact(vote.bytes().length-(pendingAccept.bytes()-pendingAccept.activeLength()));
            ensureJournalCapacity(Math.addExact(remaining,RESERVATION),"pending certificate and next grant exceed shared journal capacity");
            try {
                cut.at("CERTIFICATE_VALIDATED");checkOwner();fence(bound);
                pendingAccept.install(vote,()->{checkOwner();fence(bound);},cut);
            }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
        }
        cut.at("CERTIFICATE_BEFORE_RETURN");checkOwner();fence(bound);return certificate;
    }
    /** The actual local original certificate is not an applied cut or public result. */
    synchronized Optional<Decoded> currentCertificate()throws IOException {
        require(pendingAccept!=null,"pending certificate storage owner required");checkOwner();require(!pendingAccept.pending(),"pending certificate is not complete");
        return pendingAccept.active()==null?Optional.empty():Optional.ofNullable(pendingAccept.active().certificate());
    }

    private List<MembershipCapsule.Anchor> applicationParents(byte[] ancestry)throws IOException {
        return applicationParents(current.capsule,current.selectedSources().orElse(null),current.coverage().orElse(null),ancestry,promise,selection);
    }
    private List<MembershipCapsule.Anchor> applicationParents(MembershipCapsule original,byte[] selectedOriginals,byte[] coverage,
            byte[] ancestry,Decoded originalPromise,Decoded originalSelection)throws IOException {
        var parents=new ArrayList<>(selectedOriginals!=null?MembershipSelectedSources.parents(selectedOriginals,originalSelection,original,ancestry)
                :original.ancestryAnchors(ancestry).values());
        if(coverage!=null && originalSelection!=null && !originalSelection.value().get("cut").equals(original.context.cut)) {
            var first=MembershipRoundCoverage.first(original,coverage,ancestry,originalPromise,originalSelection);
            parents.add(first.parent());parents.add(first.end());
        }
        parents.add(original.terminal());addFloorParent(parents);
        for(var basis:bases.values()) {
            var cap=sources.original(basis).packet().capsule().value();
            parents.add(new MembershipCapsule.Anchor(object(cap.get("cut")),(String)cap.get("catalog"),(String)cap.get("application")));
        }
        original.verifyAncestry(ancestry,parents);return List.copyOf(parents);
    }
    /** Reserve every still-required endpoint, including the whole original selected set, before a new vote. */
    private void publicationCapacity(MembershipPendingAccept.Vote vote,AutomaticReplicationException.Outcome outcome)throws IOException {
        byte[] ancestry=current.ancestry();var parents=applicationParents(ancestry);String kind=(String)vote.entry().value().get("kind");
        var renewed=MembershipCheckpointPlan.renewalParents(current.capsule,kind,parents,ancestry);
        int groups=MembershipCheckpointPlan.requiredBridges(current.capsule,kind,parents).size();
        int bytes=renewed.size()>5?MembershipSelectionCoverage.MAXIMUM+1:current.coverage().isPresent()
                ?MembershipRoundCoverage.publicationBytes(current.capsule,current.coverage().orElseThrow(),ancestry,vote.promise(),vote.selected(),renewed)
                :MembershipSelectionCoverage.publicationBytes(vote.selected(),current.capsule.terminal(),renewed);
        if(groups>6 || renewed.size()>5 || bytes>MembershipSelectionCoverage.MAXIMUM)
            throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,outcome,Optional.empty(),
                    "next publication ancestry/coverage capacity; retain original authority and complete maintenance before new work",null);
    }

    record Applied(MembershipCheckpointPlan plan,MembershipAppliedEndFiles.Endorsement endorsement) {}
    /** Retire only derived work from a fenced certificate. The newer installed selection
     * must retain that exact logical entry at the identical parent; voting originals survive.
     * This method never forces or returns an old application ACK. A later volatile
     * observation still fences voting, but cannot revoke this exact cleanup authority. */
    synchronized <K,T> void retireSupersededApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations)throws IOException {
        require(appliedEnd!=null && replayFiles!=null,"application storage owner required");checkOwner();otherApplicationTransactionsIdle();
        require(!inactive.pending() && !pendingAccept.pending(),"staged retirement requires completed original authorities");
        var vote=pendingAccept.active();require(vote!=null && vote.certificate()!=null && voteReferencesInactive(vote),"staged retirement requires original carried certificate");
        verifyVote(vote);var originals=inactive.originalFiles();var old=originalGeneration(originals);
        require(promise!=null && basis!=null && selection!=null && promise.digest().equals(current.manifest.value().get("promise"))
                && basis.digest().equals(current.manifest.value().get("basis")) && selection.digest().equals(current.manifest.value().get("selection"))
                && compareBallot(object(promise.value().get("ballot")),object(vote.promise().value().get("ballot")))>0
                && current.capsule.terminal().equals(old.capsule.terminal()) && selection.value().get("cut").equals(old.capsule.context.cut)
                && vote.entry().digest().equals(selection.value().get("nextEntry")),"staged retirement requires newer installed exact carried selection");
        var local=originalSource();require(local.capsule.terminal().equals(old.capsule.terminal())
                && vote.accept().digest().equals(local.basis.value().get("accepted")),"staged retirement requires original local frozen tail");
        for(var frame:List.of(vote.entry(),vote.accept(),vote.proof(),vote.certificate()))
            require(Arrays.equals(frame.bytes(),local.capsule.packet.objectBytes(frame.digest())),"staged retirement lost original certified source");
        require(Arrays.equals(vote.payload(),local.capsule.packet.objectBytes((String)vote.entry().value().get("payload")))
                && Arrays.equals(vote.entry().bytes(),current.capsule.packet.objectBytes(vote.entry().digest()))
                && Arrays.equals(vote.payload(),current.capsule.packet.objectBytes((String)vote.entry().value().get("payload")))
                && current.accepted!=null && current.capsule.context.record(current.accepted,"ACCEPT").value().get("entry").equals(vote.entry().digest()),
                "staged retirement changed carried entry/payload");
        require(observations.size()<=12,"application phased observation count");var owned=Set.copyOf(observations);
        var packet=MembershipPendingAccept.packet(old.capsule.packet,vote);var images=new TreeMap<String,byte[]>();
        for(String h:old.capsule.packet.images().keySet())images.put(h,originals.get(h+".image"));
        var rootRecord=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var verified=Objects.requireNonNull(capsuleVerifier.verify(rootRecord,packet,images));
        require(Arrays.equals(verified.packet.bytes(),packet.bytes()),"staged retirement verifier substituted original packet");
        verified.context.certificate(vote.certificate(),owned);
        byte[] ancestry=originals.getOrDefault("ancestry.gsr",new byte[0]);
        var parents=applicationParents(old.capsule,originals.get(MembershipSelectedSources.FILE),originals.get(MembershipSelectionCoverage.FILE),ancestry,vote.promise(),vote.selected());
        var authority=new TreeMap<String,Object>();authority.put("pending",hash(vote.bytes()));authority.put("oldGeneration",old.generation.digest());
        authority.put("selector",current.selector.digest());authority.put("generation",current.manifest.digest());authority.put("promise",promise.digest());
        authority.put("selection",selection.digest());authority.put("basis",basis.digest());authority.put("source",hash(local.capsule.packet.bytes()));
        authority.put("ancestry",hash(ancestry));authority.put("coverage",hash(originals.getOrDefault(MembershipSelectionCoverage.FILE,new byte[0])));
        var parentSources=new ArrayList<Map<String,Object>>();for(var original:bases.values())parentSources.add(Map.of("basis",original.digest(),"packet",hash(sources.original(original).packet().bytes())));
        parentSources.sort(Comparator.comparing(v->(String)v.get("basis")));
        authority.put("parentSources",parentSources);authority.put("floor",floors.read().map(Decoded::digest).orElse(""));
        byte[] selector=current.selector.bytes(),installedPromise=promise.bytes(),installedBasis=basis.bytes(),installedSelection=selection.bytes();
        MembershipGenerationFiles.Guard guard=()->{
            // This is removal of derived work, not an acknowledgement under the
            // installed ballot. Preserve observed unchanged and bind every force
            // to the same owned durable originals even if a higher ballot arrives.
            checkOwner();otherApplicationTransactionsIdle();
            require(!pendingAccept.pending() && !inactive.pending() && pendingAccept.active()!=null && Arrays.equals(vote.bytes(),pendingAccept.active().bytes())
                    && Arrays.equals(selector,current.selector.bytes()) && Arrays.equals(installedPromise,promise.bytes())
                    && Arrays.equals(installedBasis,basis.bytes()) && Arrays.equals(installedSelection,selection.bytes()),"staged retirement original authority changed");
        };
        guard.check();AdmissionPaths.disjoint(List.of(directory,storage.directory()));
        if(!appliedEnd.present() && !replayFiles.present())return;
        reserveApplicationCompletion();
        try {
            cut.at("STAGED_RETIREMENT_AUTHORITY_VALIDATED");guard.check();
            var plan=replayFiles.executeRetained(vote.selector(),vote.certificate(),identity,work->MembershipCheckpointPlan.replay(configuration,storage,
                    old.capsule,packet,vote.certificate(),images,owned,work),guard,cut).renewAncestors(parents,ancestry);
            guard.check();appliedEnd.retireSuperseded(plan,vote.selector(),identity,authority,guard,cut);
            guard.check();replayFiles.releaseCompletion();cut.at("STAGED_RETIREMENT_BEFORE_RETURN");guard.check();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** Real local certificate + typed replay + forced end. This is not selector publication or public readiness. */
    synchronized <K,T> Applied applyCurrent(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations)throws IOException {
        require(appliedEnd!=null && replayFiles!=null,"application storage owner required");checkOwner();applicationTransactionIdle();
        require(!pendingAccept.pending(),"application requires completed original certificate");var vote=pendingAccept.active();
        require(vote!=null && vote.certificate()!=null,"application requires actual local certificate");
        require(observations.size()<=12,"application phased observation count");var owned=Set.copyOf(observations);
        var bound=object(vote.accept().value().get("ballot"));
        MembershipGenerationFiles.Guard guard=()->{
            checkOwner();fence(bound);require(promise!=null && selection!=null
                    && Arrays.equals(promise.bytes(),vote.promise().bytes()) && Arrays.equals(selection.bytes(),vote.selected().bytes())
                    && Arrays.equals(current.selector.bytes(),vote.selector().bytes()) && pendingAccept.active()!=null
                    && Arrays.equals(pendingAccept.active().bytes(),vote.bytes()) && !pendingAccept.pending(),"application original authority changed");
        };
        guard.check();var packet=votePacket();verifiedPacket(packet).context.certificate(vote.certificate(),owned);
        publicationCapacity(vote,AutomaticReplicationException.Outcome.INDETERMINATE);
        byte[] ancestry=current.ancestry();var parents=applicationParents(ancestry);
        AdmissionPaths.disjoint(List.of(directory,storage.directory()));reserveApplicationCompletion();
        try {
            cut.at("APPLICATION_AUTHORITY_VALIDATED");guard.check();
            var plan=replayFiles.executeRetained(vote.selector(),vote.certificate(),identity,work->MembershipCheckpointPlan.replay(configuration,storage,
                    current.capsule,packet,vote.certificate(),current.images(),owned,work),guard,cut);
            plan=plan.renewAncestors(parents,ancestry);
            guard.check();var endorsement=appliedEnd.force(plan,vote.selector(),identity,guard,cut);
            guard.check();return new Applied(plan,endorsement);
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }

    /** Force an exact complete checkpoint under the actual original vote/end owner, then retire only covered staging. */
    synchronized Decoded publishCurrent(Applied applied,List<Decoded> acknowledgements,Set<Owned> checkpoints,List<MembershipSelection.Bridge> bridges)throws IOException {
        require(appliedEnd!=null && replayFiles!=null,"publication storage owner required");checkOwner();applicationTransactionIdle();
        require(!pendingAccept.pending(),"publication requires complete original certificate");var vote=pendingAccept.active();
        boolean installed=current.publishedCertificate().filter(applied.plan().originalCertificate().digest()::equals).isPresent();
        Decoded originalPromise,originalBasis,originalSelection;
        if(installed) {
            var files=current.copyFiles();originalPromise=decode(files.get("promise.gsr"),"records","PROMISE");
            originalBasis=decode(files.get("basis.gsr"),"records","BASIS");originalSelection=decode(files.get("selected.gsr"),"records","SELECTED");
        }else {
            require(vote!=null && vote.certificate()!=null && Arrays.equals(vote.certificate().bytes(),applied.plan().originalCertificate().bytes())
                    && current.capsule.terminal().equals(applied.plan().originalParent()),"publication requires exact original applied certificate");
            require(promise!=null && basis!=null && selection!=null && Arrays.equals(promise.bytes(),vote.promise().bytes())
                    && Arrays.equals(selection.bytes(),vote.selected().bytes()) && Arrays.equals(current.selector.bytes(),vote.selector().bytes()),"publication original authority changed");
            originalPromise=promise;originalBasis=basis;originalSelection=selection;
            appliedEnd.completed(applied.plan(),vote.selector(),identity,applied.endorsement());require(!replayFiles.present(),"publication replay scratch must be removed");
        }
        var bound=object(originalPromise.value().get("ballot"));fence(bound);
        var plan=MembershipGenerationPlan.published(root,identity,installed?current.generation:inactive.slot(),originalPromise,originalBasis,originalSelection,
                applied.plan(),acknowledgements,checkpoints,bridges,current.selectedSources().orElse(null),current.capsule,current.coverage().orElse(null),current.ancestry());
        var parents=new ArrayList<MembershipCapsule.Anchor>();parents.add(applied.plan().originalParent());addFloorParent(parents);
        for(var original:bases.values()) {
            var cap=sources.original(original).packet().capsule().value();parents.add(new MembershipCapsule.Anchor(object(cap.get("cut")),(String)cap.get("catalog"),(String)cap.get("application")));
        }
        plan.verify(decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT"),identity,capsuleVerifier,parents);checkOwner();fence(bound);
        if(installed)require(Arrays.equals(current.manifest.bytes(),plan.manifest.bytes()) && !inactive.pending(),"publication differs from original completed representation");
        else inactive.checkPlan(plan);
        try {
            cut.at("PUBLICATION_VALIDATED");checkOwner();fence(bound);
            if(!installed) {
                // Transfer the reserved future slot to the actual candidate. Any failure
                // poisons this owner; reopen counts a written image or reserves the slot again.
                releasePublicationImage();
                inactive.install(plan,current.selector.bytes(),()->{checkBaseOwner();fence(bound);},current::check,cut);
                reloadGenerations();cut.at("PUBLICATION_SELECTOR_FORCED");checkOwner();fence(bound);
            }
            if(pendingAccept.active()!=null)retireCoveredApplication();
            cut.at("PUBLICATION_BEFORE_RETURN");checkOwner();fence(bound);return current.manifest;
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void retireCoveredApplication()throws IOException {
        applicationTransactionIdle();var original=pendingAccept.active();verifyCoveredVote(original);
        pendingAccept.checkCoveredCandidate(original);
        require(!replayFiles.present(),"covered application has unexpected replay scratch");
        MembershipGenerationFiles.Guard guard=()->{
            checkOwner();verifyCoveredVote(original);
            require(pendingAccept.active()==null || Arrays.equals(pendingAccept.active().bytes(),original.bytes()),"covered vote changed during retirement");
        };
        cut.at("PUBLICATION_COVERAGE_VALIDATED");guard.check();
        appliedEnd.retireCovered(current.capsule,current.images(),current.publishedParent(),current.publishedAncestors(),original,identity,guard,cut);
        pendingAccept.clearCovered(original,guard,cut);replayFiles.releaseCompletion();
        cut.at("PUBLICATION_RETIRED");checkOwner();
    }

    private Object key() throws IOException {
        Object key=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS).fileKey();
        require(key!=null,"grant file identity unavailable");return key;
    }
    private void live() {require(!closed && !failed,"grant journal closed or failed");}
    private void checkBaseOwner() throws IOException {
        live();allocator.checkOwner();require(fileKey.equals(key()),"grant journal inode changed");AdmissionPaths.exact(path,storedJournal());
        if(sources!=null)sources.check();
        if(rotation!=null)rotation.check();
        if(sourceRetirement!=null)sourceRetirement.check();
        if(capture!=null)capture.check();
        if(pendingAccept!=null)pendingAccept.check();
        if(pendingContext!=null)pendingContext.check();
        if(appliedEnd!=null)appliedEnd.check();
        if(replayFiles!=null)replayFiles.check();
    }
    private void checkWithoutFloor() throws IOException {
        checkBaseOwner();
        if(current!=null)current.check();
        if(inactive!=null)inactive.check();
    }
    private void checkWithoutRetirement() throws IOException {checkWithoutFloor();if(floors!=null)floors.check();}
    private void checkOwner() throws IOException {checkWithoutRetirement();if(retirement!=null)retirement.check();}
    private void sourceIdle(){contextTransactionIdle();applicationRetirementIdle();require(!carriedVoteUntransferred(),"carried vote must transfer before another authority change");if(pendingAccept!=null)require(!pendingAccept.pending(),"pending ACCEPT requires exact original completion");if(capture!=null)require(!capture.pending(),"pending source capture must finish before authority changes");if(sourceRetirement!=null)require(!sourceRetirement.pending(),"pending source retirement must finish before authority changes");}
    private void rotationIdle(){sourceIdle();if(floors!=null)require(!floors.releasing(),"pending floor release must finish before authority changes");if(rotation!=null)require(!rotation.pending(),"pending journal rotation must finish before authority changes");}
    private void floorIdle() throws IOException {
        rotationIdle();
        if(floors!=null)require(!floors.pending(),"pending floor must finish before authority changes");
        if(retirement!=null)require(!retirement.pending(),"pending retirement must finish before authority changes");
    }
    /** An interrupted application must reconstruct the same original endpoint plan. */
    private void applicationReferencesIdle()throws IOException {
        require(appliedEnd==null || !appliedEnd.present() && !replayFiles.present(),"staged application pins original source/floor references");
    }
    private void addFloorParent(Collection<MembershipCapsule.Anchor> parents) throws IOException {
        if(floors==null)return;var prior=floors.read();if(prior.isEmpty())return;
        var value=prior.get().value();var first=object(list(value.get("sources")).getFirst());
        parents.add(new MembershipCapsule.Anchor(object(value.get("cut")),(String)first.get("catalog"),(String)first.get("snapshot")));
    }
    synchronized Optional<Decoded> governingFloor() throws IOException {require(floors!=null,"floor storage owner required");checkOwner();return floors.read();}
    synchronized Decoded establishFloor(List<MembershipFloor.Copy> offered) throws IOException {
        require(floors!=null,"floor storage owner required");checkOwner();applicationReferencesIdle();rotationIdle();
        if(retirement!=null)require(!retirement.pending(),"pending retirement must finish before authority changes");var own=floorCopyCurrent();
        return establishFloor(own,offered);
    }
    synchronized MembershipFloor.Copy contextFloorCopy()throws IOException {
        contextMaintenanceIdle();require(!floors.pending() && !retirement.pending(),"context floor copy requires idle maintenance");
        return floorCopyChecked();
    }
    synchronized Decoded establishContextFloor(List<MembershipFloor.Copy> offered)throws IOException {
        contextMaintenanceIdle();require(!retirement.pending(),"pending retirement must finish before context floor establishment");
        return establishFloor(floorCopyChecked(),offered);
    }
    private Decoded establishFloor(MembershipFloor.Copy own,List<MembershipFloor.Copy> offered)throws IOException {
        // Validate and reserve before any persistent change; an interrupted transaction
        // may only resume with the same original full copies.
        try{
            // Empty replay scratch is disposable capacity. A floor needs real copies
            // before it may retire the old generation; it must not count those copies
            // on top of unused replay/end buffers. Existing application files pin them.
            if(replayFiles!=null && pendingAccept.active()!=null) {
                replayFiles.releaseCompletion();appliedEnd.releaseEmptyCompletion();
            }
            return floors.establish(own,offered,this::checkWithoutFloor,cut);
        }
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
        require(retirement!=null && floors!=null && inactive!=null,"retirement storage owner required");checkOwner();
        require(pendingAccept==null || !voteReferencesInactive(pendingAccept.active()),"original pending vote pins inactive generation until reacceptance");
        rotationIdle();
        return retireInactiveChecked();
    }
    synchronized Optional<Decoded> retireContextOriginal()throws IOException {
        contextMaintenanceIdle();return retireInactiveChecked();
    }
    private MembershipPendingContext.Reconstructed retirementContext()throws IOException {
        return pendingContext!=null && pendingContext.active().isPresent()?retainedContextOriginal():null;
    }
    private Optional<Decoded> retireInactiveChecked()throws IOException {
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
                var plan=MembershipRetirementPlan.create(root,identity,current,floor,original,retirementContext());
                inactive.forceOriginal(cut);checkOwner();retirement.prepare(plan,this::checkWithoutRetirement,cut);record=plan.record;
            }else {
                record=saved.get();bindRetirement(record,floor);retirement.checkSaved(record);
                if(inactive.exists()) {
                    var original=originalGeneration(retirement.original());var plan=MembershipRetirementPlan.create(root,identity,current,floor,original,retirementContext());
                    require(Arrays.equals(record.bytes(),plan.record.bytes()),"retirement differs from saved original generation");
                }
                retirement.sealAuthority(record,this::checkWithoutRetirement,cut);
            }
            bindRetirement(record,floor);retirement.checkSaved(record);checkOwner();
            inactive.deleteAuthorized(record,this::checkOwner,cut);
            require(!inactive.exists(),"retirement original still exists");
            if(appliedEnd!=null && pendingAccept.active()!=null)reservePublicationImage();
            retirement.clearAfterDeletion(record,this::checkWithoutRetirement,cut);
            cut.at("RETIREMENT_BEFORE_RETURN");checkOwner();return Optional.of(record);
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Relinquish a completed old floor only after every inactive generation is gone. */
    synchronized void releaseFloor() throws IOException {
        require(floorReleaseEnabled && floors!=null && retirement!=null && rotation!=null,"floor release storage owner required");checkOwner();applicationReferencesIdle();sourceIdle();
        require(!inactive.exists() && !inactive.pending() && !retirement.pending() && !rotation.pending(),"pending generation/retirement/rotation before floor release");
        require(promise==null || promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest()),"uninstalled adoption fence; prefix recovery required");
        try {
            if(!floors.exists())return;
            var successor=pendingAccept==null || pendingAccept.pending()?null:pendingAccept.active();
            if(successor!=null && Arrays.equals(successor.selector().bytes(),current.selector.bytes()))verifyVote(successor);else successor=null;
            floors.release(current,successor,this::checkOwner,cut);
            if(appliedEnd!=null && pendingAccept.active()!=null)reserveApplicationCompletion();
            cut.at("FLOOR_RELEASE_BEFORE_RETURN");checkOwner();
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Read-only decision for a completed original source; does not publish deletion authority. */
    synchronized MembershipSourceRetirementPlan planSourceRetirement(String id) throws IOException {
        require(floorReleaseEnabled && floors!=null && retirement!=null && rotation!=null,"source retirement maintenance owner required");
        checkOwner();
        if(pendingContext!=null && pendingContext.active().isPresent()) {
            contextMaintenanceIdle();require(!floors.pending() && !retirement.pending(),"context source planning requires completed floor/retirement");
            contextSourceRetirement(id);
        }else floorIdle();
        return sourceRetirementPlan(id);
    }
    private MembershipSourceRetirementPlan sourceRetirementPlan(String id)throws IOException {
        checkOwner();
        if(pendingAccept!=null && pendingAccept.protectsSource(id))contextSourceRetirement(id);
        require(!inactive.exists() && !inactive.pending(),"inactive generation must retire before source planning");
        require(promise!=null && (promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest())),"uninstalled adoption fence; prefix recovery required");
        var originalBasis=bases.get(id);require(promises.containsKey(id) && sources.retainedIdentities().contains(id),"source retirement requires complete original source");
        var retained=floors.retained().orElseThrow(()->new IllegalArgumentException("durable governing floor required before source retirement"));
        var original=sources.original(id,promises.get(id),originalBasis);var rootRecord=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var capsule=Objects.requireNonNull(capsuleVerifier.verify(rootRecord,original.packet(),original.images()));
        require(Arrays.equals(capsule.packet.bytes(),original.packet().bytes()),"source retirement verifier substituted source");
        var plan=MembershipSourceRetirementPlan.create(root,identity,current,retained,promise,promises.get(id),originalBasis,capsule,original.images(),retirementContext());
        checkOwner();return plan;
    }
    /** A forced context may cover the predecessor or a backing strictly between
     * the governing floor and latest backing. Floor/current grants stay pinned. */
    private void contextSourceRetirement(String id)throws IOException {
        require(pendingContext!=null && pendingContext.active().isPresent() && !pendingContext.pending(),
                "source still owns pending ACCEPT authority");
        var original=retainedContextOriginal();applicationReferencesIdle();var backing=retainedContextBasis();
        require(!id.equals(backing.value().get("basisId")),"context source retirement cannot remove backing");
        require(!inactive.exists() && !inactive.pending(),"context source retirement requires retired generation");
        if(id.equals(original.vote().promise().value().get("basisId")))return;
        // After the forced decision prunes the journal and begins deletion, the
        // original frames survive only in that exact retained decision. Never
        // reconstruct authority from a partially deleted source directory.
        var priorPromise=promises.get(id);var priorBasis=bases.get(id);
        if(priorPromise==null) {
            var decision=sourceRetirement.decision().orElseThrow(()->new IllegalArgumentException("context source retirement original decision absent"));
            require(id.equals(decision.id()),"context source retirement different decision");
            priorPromise=decision.promise();priorBasis=decision.basis();
        }
        var floor=contextRetirementFloor(original);
        var local=floor.copies().stream().filter(c->c.owner.equals(identity)).findFirst().orElseThrow();
        var floorBallot=object(decode(local.fileBytes("promise.gsr"),"records","PROMISE").value().get("ballot"));
        require(priorBasis!=null && id.equals(priorBasis.value().get("basisId"))
                && priorPromise.value().get("root").equals(backing.value().get("root"))
                && priorPromise.value().get("view").equals(backing.value().get("view"))
                && priorBasis.value().get("voter").equals(identity.nodeId().value())
                && priorBasis.value().get("accepted")!=null
                && !priorBasis.digest().equals(current.manifest.value().get("basis"))
                && compareBallot(object(priorPromise.value().get("ballot")),floorBallot)>0
                && compareBallot(object(priorPromise.value().get("ballot")),object(backing.value().get("ballot")))<0,
                "context source retirement requires covered intermediate backing");
        require(MembershipContextTail.retained(current,current.capsule.context.record((String)priorBasis.value().get("accepted"),"ACCEPT"),original),
                "context source retirement loses intermediate accepted tail");
        if(promises.containsKey(id)) {
            var packet=sources.original(id,priorPromise,priorBasis).packet();
            var vote=original.vote();var originals=new ArrayList<byte[]>(List.of(vote.entry().bytes(),vote.payload(),vote.accept().bytes()));
            if(vote.proof()!=null)originals.add(vote.proof().bytes());
            if(vote.certificate()!=null)originals.add(vote.certificate().bytes());
            for(var bytes:originals)require(Arrays.equals(bytes,packet.objectBytes(hash(bytes))),"context source retirement original bytes changed");
        }
    }
    /** Complete one exact source retirement; all other writer mutations remain blocked. */
    synchronized Decoded retireSource(String id)throws IOException {
        require(sourceRetirement!=null,"source retirement owner required");checkOwner();applicationReferencesIdle();require(pendingAccept==null || !pendingAccept.pending(),"pending ACCEPT requires exact original completion");
        if(pendingContext!=null && pendingContext.active().isPresent())contextSourceRetirement(id);
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
            decision.bind(root,identity,current,retained,promise,retirementContext());sourceRetirement.publish(decision,this::checkOwner,cut);
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
            decision.bind(root,identity,current,retained,promise,retirementContext());checkOwner();cut.at("SOURCE_RETIREMENT_JOURNAL_PRUNED");checkOwner();
            sources.deleteRetired(decision,this::checkOwner,cut);require(!sources.retainedIdentities().contains(id),"source retirement still owns original files");
            sources.releaseRetiredLeases(id);
            decision.bind(root,identity,current,retained,promise,retirementContext());sourceRetirement.clear(this::checkOwner,cut);cut.at("SOURCE_RETIREMENT_BEFORE_RETURN");checkOwner();return decision.record();
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
    private byte[] storedJournal() {
        if(tornBasis.length==0)return journal;
        byte[] stored=Arrays.copyOf(journal,journal.length+tornBasis.length);System.arraycopy(tornBasis,0,stored,journal.length,tornBasis.length);return stored;
    }
    private static int completePrefix(byte[] bytes) {
        int offset=0;
        while(offset<bytes.length) {
            if(bytes.length-offset<HEADER)return offset;
            byte[] head=Arrays.copyOfRange(bytes,offset,offset+HEADER);int kind=Short.toUnsignedInt(ByteBuffer.wrap(head).getShort(8));
            require(kind==3 || kind==4 || kind==5,"unknown grant journal record");String name=kind==3?"PROMISE":kind==4?"BASIS":"SELECTED";
            int length=HEADER+header(head,"records",name);
            if(length>bytes.length-offset){require(kind==4,"capture can only recover a torn BASIS");return offset;}
            offset+=length;
        }
        return offset;
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
        require(current!=null,"current generation required");checkOwner();
        if(pendingContext!=null && pendingContext.active().isPresent())return prepareContextCurrent(incoming);
        if(carriedVoteUntransferred() && promise!=null && basis!=null && promise.value().get("ballot").equals(incoming)) {
            // Replaying an already forced grant does not begin a new campaign or
            // mutate its source, including while derived staging is being retired.
            otherApplicationTransactionsIdle();require(!pendingAccept.pending() && !inactive.pending(),"original grant requires complete authorities");
            current.capsule.context.ballot(incoming,true);fence(incoming);originalSource();checkOwner();fence(incoming);return basis;
        }
        floorIdle();cut.at("CURRENT_BEFORE_CAPTURE");checkOwner();
        if(inactive!=null)require(!inactive.pending() && !(inactive.exists() && !current.adopted && current.manifest.value().get("selection")==null)
                && !inactive.incompleteOrSelected(selection==null?null:selection.digest(),number(current.capsule.context.cut.get("index"))),"pending generation installation must finish before another grant");
        require(promise==null || promise.value().get("basisId")!=null || current.manifest.value().get("promise").equals(promise.digest()),
                "uninstalled adoption fence; prefix recovery required");
        return prepareBound(voteCapsule(),incoming,voteAccepted(),current.images());
    }
    private Decoded prepareContextCurrent(Map<String,Object> incoming)throws IOException {
        contextCaptureIdle(false);var context=current.capsule.context;var next=ballot(context.ballot(incoming,true));
        observe(context,next);fence(next);
        if(promise.value().get("ballot").equals(next)) {
            require(basis!=null && Arrays.equals(basis.bytes(),retainedContextBasis().bytes()),"incomplete context capture; fresh ballot required");
            // This only acknowledges an already complete protected capture, never the
            // installed pre-transfer grant or an unmarked later PROMISE.
            require(!basis.digest().equals(current.manifest.value().get("basis")),"context capture duplicate requires transferred backing");
            originalSource();cut.at("GRANT_BEFORE_RETURN");checkOwner();fence(next);return basis;
        }
        int completion=RESERVATION+MembershipPendingContext.MAXIMUM;
        if(completion>maximum-journal.length-pendingBytes())throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,
                AutomaticReplicationException.Outcome.NOT_SUBMITTED,Optional.empty(),"protected capture journal completion capacity",null);
        var grant=decode(encode("records","PROMISE",Map.of("root",root.manifestDigest(),"view",context.authority(),
                "ballot",next,"basisId",UUID.randomUUID().toString())),"records","PROMISE");
        var plan=contextCapturePlan(grant,sources::original);checkBasis(plan.basis(),grant);
        var capsule=Objects.requireNonNull(capsuleVerifier.verify(decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT"),plan.packet(),plan.images()));
        require(Arrays.equals(capsule.packet.bytes(),plan.packet().bytes()),"context capture verifier substituted source");
        var reservation=sources.prepare(plan.basis(),capsule,plan.images());
        try(var retained=reservation) {
            append(grant,next);promise=grant;basis=null;selection=null;promises.put(plan.id(),grant);
            capture.write(plan,this::checkOwner,cut);retained.captureRecovering(this::checkOwner);fence(next);
            append(plan.basis(),next);basis=plan.basis();bases.put(plan.id(),basis);
            completeContextCapture(plan);checkOwner();fence(next);capture.clear(this::checkOwner,cut);
            cut.at("GRANT_BEFORE_RETURN");checkOwner();fence(next);return basis;
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    void observeCurrent(Map<String,Object> incoming) {live();require(current!=null,"current generation required");observe(current.capsule.context,incoming);}
    synchronized Optional<Owned> currentOwnedTail() throws IOException {
        require(current!=null,"current generation required");checkOwner();require(pendingAccept==null || !pendingAccept.pending(),"pending ACCEPT is not complete");String tail=voteAccepted();return tail==null?Optional.empty():Optional.of(new Owned(identity.nodeId().value(),identity.storageId(),tail,cutDigest(current.capsule.context.cut)));
    }
    /** Observation of the whole rechecked, locally forced selected generation; never a deletion permit. */
    synchronized MembershipFloor.Copy floorCopyCurrent() throws IOException {
        require(current!=null && inactive!=null,"generation owner required");checkOwner();rotationIdle();
        return floorCopyChecked();
    }
    private MembershipFloor.Copy floorCopyChecked()throws IOException {
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
        require(pendingAccept==null || pendingAccept.active()==null,"pending ACCEPT requires covered-prefix publication before adoption");
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
        require(pendingAccept==null || pendingAccept.active()==null,"pending ACCEPT requires covered-prefix publication before adoption");
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
        return retainedSource(basis);
    }
    /** Read an exact retained grant without substituting the latest promise/basis. */
    private MembershipSelection.Source retainedSource(Decoded retainedBasis)throws IOException {
        checkOwner();require(retainedBasis.value().get("view").equals(current.capsule.context.authority()),"obsolete original grant; fresh campaign required");
        var original=sources.original(retainedBasis);var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var capsule=Objects.requireNonNull(capsuleVerifier.verify(localRoot,original.packet(),original.images()));
        require(Arrays.equals(capsule.packet.bytes(),original.packet().bytes()),"original verifier substituted source");
        var reference=Map.<String,Object>of("voter",identity.nodeId().value(),"basisId",retainedBasis.value().get("basisId"),"basisDigest",retainedBasis.digest());
        var owned=new HashSet<Owned>();String parent=cutDigest(object(retainedBasis.value().get("cut")));
        owned.add(new Owned(identity.nodeId().value(),identity.storageId(),retainedBasis.digest(),parent));
        if(retainedBasis.value().get("accepted")!=null)owned.add(new Owned(identity.nodeId().value(),identity.storageId(),(String)retainedBasis.value().get("accepted"),parent));
        var result=MembershipSelection.Source.verify(capsule,retainedBasis,reference,identity,owned);checkOwner();return result;
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
        MembershipPendingContext.Reconstructed original=null;
        if(pendingContext!=null && pendingContext.active().isPresent()) {
            contextCaptureIdle(false);original=retainedContextOriginal();
            require(basis!=null && Arrays.equals(basis.bytes(),retainedContextBasis().bytes())
                    && !basis.digest().equals(current.manifest.value().get("basis")),"context selection requires latest protected capture");
        }else floorIdle();
        var selected=decision(offered,bridges).selected();var ballot=object(selected.value().get("ballot"));
        if(original!=null)require(selected.value().get("cut").equals(original.capsule().context.cut)
                && original.vote().entry().digest().equals(selected.value().get("nextEntry")),"context selection must carry exact original parent/entry");
        if(selection!=null) {require(Arrays.equals(selection.bytes(),selected.bytes()),"selection already fixed; fresh ballot required");return selection;}
        if(original!=null) {
            // The complete context/source remains pinned. Do not turn selection
            // admission into an implicit journal/source maintenance transaction.
            if(selected.bytes().length>maximum-storedJournal().length-pendingBytes())
                throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,
                        AutomaticReplicationException.Outcome.NOT_SUBMITTED,Optional.empty(),"context selection journal capacity",null);
        }else ensureJournalCapacity(selected.bytes().length,"selection journal rotation required");
        try {
            append(selected,ballot);selection=selected;selections.put(selected.digest(),selected);cut.at("SELECTED_BEFORE_RETURN");checkOwner();fence(ballot);return selected;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    /** Local installation receipt only after every materialized file and selector parent is forced. */
    synchronized Decoded installCurrent(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges,Map<String,byte[]> images) throws IOException {
        return installCurrent(offered,bridges,List.of(),images);
    }
    /** Selection ancestry fixes the vote; extra installation ancestry preserves local retained parents only. */
    synchronized Decoded installCurrent(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges,
            List<MembershipSelection.Bridge> retainedBridges,Map<String,byte[]> images) throws IOException {
        require(inactive!=null && selection!=null,"durable selection and generation owner required");
        boolean installed=selection.digest().equals(current.manifest.value().get("selection"));
        MembershipPendingContext.Reconstructed retainedOriginal=null;
        if(pendingContext!=null && pendingContext.active().isPresent()) {
            checkOwner();otherAuthorityTransactionsIdle();applicationReferencesIdle();retainedOriginal=retainedContextOriginal();
            require(!pendingAccept.pending() && !pendingContext.pending() && basis!=null
                    && Arrays.equals(basis.bytes(),retainedContextBasis().bytes())
                    && (installed || contextInstallationPending()),"context installation requires exact protected selection");
        }else if(installed && appliedEnd!=null && !appliedEnd.retirementPending()) {
            // A lost installation response may be retried while old derived work
            // awaits retirement. This branch still validates the entire exact plan
            // below and performs no write; a new installation remains excluded.
            checkOwner();otherApplicationTransactionsIdle();require(!pendingAccept.pending(),"pending ACCEPT requires exact original completion");
        }else floorIdle();
        var selected=decision(offered,bridges);require(Arrays.equals(selection.bytes(),selected.selected().bytes()),"installation differs from original selection");
        var ballot=object(selection.value().get("ballot"));
        boolean settles=pendingAccept!=null && pendingAccept.active()!=null
                && !selected.longest().capsule.context.cut.equals(current.capsule.context.cut);
        var ancestors=new ArrayList<MembershipCapsule.Anchor>();ancestors.add(current.capsule.terminal());addFloorParent(ancestors);
        // A completed receipt retains its original materialization even after safe source retirement.
        if(installed)ancestors.addAll(current.capsule.ancestryAnchors(current.ancestry()).values());
        for(var original:bases.values()) {
            var value=sources.original(original).packet().capsule().value();ancestors.add(new MembershipCapsule.Anchor(object(value.get("cut")),(String)value.get("catalog"),(String)value.get("application")));
        }
        var complete=MembershipGenerationPlan.installationBridges(selected,bridges,retainedBridges,ancestors);
        var plan=MembershipGenerationPlan.selected(root,identity,installed?current.generation:inactive.slot(),promise,basis,selected,complete,images);
        plan.verify(decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT"),identity,capsuleVerifier,ancestors);checkOwner();fence(ballot);
        if(settles)verifySettlement(pendingAccept.active(),current.copyFiles(),selected.longest().capsule,plan.files);
        if(retainedOriginal!=null) {
            require(retainedOriginal.capsule().context.cut.equals(selected.selected().value().get("cut"))
                    && retainedOriginal.vote().entry().digest().equals(selected.selected().value().get("nextEntry")),"context installation changed original tail");
            MembershipContextTail.selected(retainedOriginal,MembershipSourcePacket.decode(plan.files.get("source.gscp")),(String)plan.manifest.value().get("ownedTail"));
        }
        if(installed) {
            require(Arrays.equals(current.manifest.bytes(),plan.manifest.bytes()) && !inactive.pending(),"installed generation differs from original plan");checkOwner();fence(ballot);return current.manifest;
        }
        inactive.checkPlan(plan);
        try {
            // A carried vote already reserves the future generation image. Use that
            // slot for installation, as publication does, instead of counting it twice.
            // Any failure poisons this owner; reopen reconstructs all physical leases.
            releasePublicationImage();
            inactive.install(plan,current.selector.bytes(),()->{checkBaseOwner();fence(ballot);},current::check,cut);
            reloadGenerations();
            if(pendingAccept!=null && settledVoteCandidate(pendingAccept.active()))retireSettledVote();
            // The former active generation now occupies the future publication slot.
            // Keep its maximum completion reservation until authorized retirement.
            if(appliedEnd!=null && pendingAccept.active()!=null)reservePublicationImage();
            cut.at("INSTALL_BEFORE_RETURN");checkOwner();fence(ballot);return current.manifest;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    private Decoded prepareBound(MembershipCapsule source,Map<String,Object> incoming,String accepted,Map<String,byte[]> images) throws IOException {
        require((sources==null)==(images==null),"grant source mode mismatch");
        live();var context=source.context;
        require(context.root.equals(root.manifestDigest()) && identity.equals(context.identities.get(identity.nodeId().value()))
                && context.voters().contains(identity.nodeId().value()),"grant local eligible identity");
        var next=ballot(context.ballot(incoming,true));observe(current==null?context:current.capsule.context,next);fence(next);checkOwner();
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
            if(retained!=null){
                if(capture==null)retained.capture();
                else {
                    var plan=capturePlan(grant);
                    require(Arrays.equals(plan.basis().bytes(),frozen.bytes()),"capture differs from current original");
                    capture.write(plan,this::checkOwner,cut);retained.captureRecovering(this::checkOwner);
                }
                fence(next);
            }
            append(frozen,next);basis=frozen;bases.put((String)frozen.value().get("basisId"),frozen);
            if(capture!=null)capture.clear(this::checkOwner,cut);
            cut.at("GRANT_BEFORE_RETURN");checkOwner();fence(next);return frozen;
        } catch(IOException | RuntimeException | Error error) {failed=true;throw error;}
    }

    private void resumeCapture(MembershipCaptureFiles.Plan plan)throws IOException {
        var bound=object(plan.promise().value().get("ballot"));
        require(selection==null,"pending capture cannot already have a selection");
        if(tornBasis.length>0)completeTornBasis(plan,bound);
        else if(basis==null) {
            require(plan.basis().bytes().length<=maximum-journal.length-pendingBytes(),"capture recovery journal capacity");
            capture.write(plan,this::checkOwner,cut);
            sources.resumeCapture(plan,this::checkOwner);
            append(plan.basis(),bound);basis=plan.basis();bases.put(plan.id(),basis);
        }else require(Arrays.equals(basis.bytes(),plan.basis().bytes()),"completed capture basis changed");
        if(pendingContext!=null && pendingContext.active().isPresent())completeContextCapture(plan);
        checkOwner();fence(bound);capture.clear(this::checkOwner,cut);
    }

    private void completeTornBasis(MembershipCaptureFiles.Plan plan,Map<String,Object> bound)throws IOException {
        byte[] expected=plan.basis().bytes();checkOwner();fence(bound);
        require(basis==null && tornBasis.length<expected.length && Arrays.equals(tornBasis,Arrays.copyOf(expected,tornBasis.length)),"capture torn BASIS differs from original prefix");
        AdmissionPaths.exact(directory.resolve(MembershipCaptureFiles.FILE),plan.bytes());
        require(expected.length<=maximum-journal.length-pendingBytes(),"capture recovery journal capacity");
        // Once a BASIS append starts, every source member must already be complete.
        // Do not use the source-prefix writer to repair evidence lost after that boundary.
        var original=sources.original(plan.basis());require(Arrays.equals(original.packet().bytes(),plan.packet().bytes()),"capture torn BASIS original packet changed");
        for(var image:plan.images().entrySet())require(Arrays.equals(image.getValue(),original.images().get(image.getKey())),"capture torn BASIS original image changed");
        cut.at("BASIS_RECOVERY_VALIDATED");checkOwner();fence(bound);
        try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            require(channel.size()==journal.length+tornBasis.length,"capture recovery journal length changed");channel.position(channel.size());
            int middle=tornBasis.length+(expected.length-tornBasis.length)/2;
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,tornBasis.length,middle));tornBasis=Arrays.copyOf(expected,middle);
            cut.at("BASIS_RECOVERY_PREFIX_WRITTEN");checkOwner();fence(bound);
            AdmissionPaths.write(channel,Arrays.copyOfRange(expected,tornBasis.length,expected.length));tornBasis=expected;
            cut.at("BASIS_RECOVERY_WRITTEN");checkOwner();fence(bound);channel.force(true);
            cut.at("BASIS_RECOVERY_FORCED");checkOwner();fence(bound);
        }
        AdmissionPaths.forceDirectory(directory);cut.at("BASIS_RECOVERY_PARENT_FORCED");checkOwner();fence(bound);
        journal=storedJournal();tornBasis=new byte[0];basis=plan.basis();bases.put(plan.id(),basis);checkOwner();
    }

    private void ensureJournalCapacity(int bytes,String message) throws IOException {
        if(bytes<=maximum-journal.length-pendingBytes())return;
        // One bounded maintenance attempt. Never release sources, generations or
        // pending recovery work to admit a new operation at the byte ceiling.
        if(bytes<=maximum && rotation!=null && current!=null && floors!=null && retirement!=null
                && !inactive.exists() && !inactive.pending() && !floors.pending() && !retirement.pending())rotateJournal();
        if(bytes>maximum-journal.length-pendingBytes())throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,
                AutomaticReplicationException.Outcome.NOT_SUBMITTED,Optional.empty(),message,null);
    }
    private void append(Decoded record,Map<String,Object> expected) throws IOException {
        checkOwner();fence(expected);require(tornBasis.length==0,"pending torn BASIS must recover before append");byte[] bytes=record.bytes();require(bytes.length<=maximum-journal.length-pendingBytes(),"grant journal overflow");
        cut.at(record.kind()+"_BEFORE_WRITE");fence(expected);
        try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            require(channel.size()==journal.length,"grant journal length changed");channel.position(journal.length);
            if(capture!=null && record.kind().equals("BASIS")) {
                int half=bytes.length/2;AdmissionPaths.write(channel,Arrays.copyOf(bytes,half));cut.at("BASIS_PREFIX_WRITTEN");fence(expected);
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,half,bytes.length));
            }else AdmissionPaths.write(channel,bytes);
            cut.at(record.kind()+"_WRITTEN");fence(expected);
            channel.force(true);cut.at(record.kind()+"_FORCED");fence(expected);
        }
        int offset=journal.length;journal=Arrays.copyOf(journal,offset+bytes.length);System.arraycopy(bytes,0,journal,offset,bytes.length);
    }

    synchronized Optional<Decoded> promised() {live();return Optional.ofNullable(promise);}
    synchronized Optional<Decoded> originalBasis() {live();return Optional.ofNullable(basis);}
    synchronized Optional<Decoded> originalSelection() {live();return Optional.ofNullable(selection);}
    @Override public synchronized void close() throws IOException {
        if(!closed){closed=true;try{releasePublicationImage();if(pendingContext!=null)pendingContext.close();if(appliedEnd!=null)appliedEnd.close();if(replayFiles!=null)replayFiles.close();if(retirement!=null)retirement.close();if(floors!=null)floors.close();if(inactive!=null)inactive.close();if(current!=null)current.close();if(sources!=null)sources.close();}finally{allocator.close();}}
    }
}
