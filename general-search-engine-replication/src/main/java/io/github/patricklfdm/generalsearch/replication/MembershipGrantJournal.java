package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.LongSupplier;
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
    private volatile MembershipCurrentGeneration current;
    private MembershipCurrentGeneration.Verifier capsuleVerifier;
    private boolean ownedHistory;
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
    private MembershipPeerRetentionFiles peerRetention;
    private MembershipLearnerRetentionFiles learnerRetention;
    private MembershipFutureRetentionFiles futureRetention;
    private Applied nativeApplied;
    private String retentionSelector;
    private MembershipSelectedRetention selectedRetention;
    private MembershipReplayFiles replayFiles;
    private MembershipAppliedEndFiles appliedEnd;
    private int applicationMetadata;
    private MembershipResources.Lease publicationImage;
    private final Set<MembershipSourceExport> sourceExports=new HashSet<>();
    private final Set<MembershipRecordExport> recordExports=new HashSet<>();
    private final Set<MembershipVoteExport> voteExports=new HashSet<>();
    private final Set<MembershipPrefixExport> prefixExports=new HashSet<>();
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

    /** The original journal is parsed by this owner, never supplied as caller-side grant lists.
     * This scope reads only selected history; it does not recover pending transactions or admit voting. */
    static RetainedHistory readRetainedHistory(Path requested,Path materialization,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(resources);Objects.requireNonNull(cut);Path path=AdmissionPaths.safe(requested);
        var owner=MembershipBallotAllocator.openBootstrapped(path,Objects.requireNonNull(materialization),root,identity,cut);
        MembershipGrantJournal journal=null;MembershipCurrentGeneration selected=null;
        try {
            journal=new MembershipGrantJournal(path,root,identity,owner,MAXIMUM,cut);
            journal.resources=resources;
            journal.sources=new MembershipBasisSources(path,resources,cut,journal.promises,journal.bases);
            journal.loadPeerRetention();
            journal.loadLearnerRetention();
            selected=MembershipCurrentGeneration.readOwned(new HistoryRead(journal),resources,cut);
            if(journal.peerRetention!=null)journal.peerRetention.state().plan().required(selected.capsule,selected.ancestry());
            if(journal.learnerRetention!=null)journal.learnerRetention.state().plan().required(selected.capsule,selected.ancestry());
            return new RetainedHistory(journal,selected);
        }catch(IOException|RuntimeException|Error error) {
            if(selected!=null)selected.close();
            try {if(journal==null)owner.close();else journal.close();}catch(IOException close){error.addSuppressed(close);}throw error;
        }
    }
    /** Private minting binds the complete selected copy to this exact replayed live journal. */
    static final class HistoryRead {
        private final MembershipGrantJournal owner;
        private final MembershipBasisSources.Originals originals;
        private HistoryRead(MembershipGrantJournal owner){this(owner,null);}
        private HistoryRead(MembershipGrantJournal owner,MembershipBasisSources.Originals originals){this.owner=owner;this.originals=originals;}
        void check()throws IOException{owner.checkBaseOwner();}
        Path directory(){return owner.directory;}
        MembershipRoot root(){return owner.root;}
        MembershipIdentity identity(){return owner.identity;}
        Collection<Decoded> promises(){return List.copyOf(owner.promises.values());}
        Collection<Decoded> bases(){return List.copyOf(owner.bases.values());}
        Collection<Decoded> selections(){return List.copyOf(owner.selections.values());}
        void basis(Decoded basis)throws IOException {
            check();var retained=owner.bases.get((String)basis.value().get("basisId"));
            require(retained!=null && Arrays.equals(retained.bytes(),basis.bytes()),"original history requires journal-owned BASIS");
        }
        void grant(Decoded promise,Decoded basis)throws IOException {
            basis(basis);var retained=owner.promises.get((String)basis.value().get("basisId"));
            require(retained!=null && Arrays.equals(retained.bytes(),promise.bytes()),"original history requires journal-owned PROMISE");
        }
        MembershipBasisSources.Original original(Decoded basis)throws IOException {
            basis(basis);var result=originals==null?Objects.requireNonNull(owner.sources,"original history sources unavailable").original(basis):originals.read(basis);
            check();return result;
        }
        void generation(Decoded manifest)throws IOException {
            check();var value=manifest.value();
            require(owner.promises.values().stream().anyMatch(p->p.digest().equals(value.get("promise"))),"history original promise absent");
            if(value.get("basis")!=null)require(owner.bases.values().stream().anyMatch(p->p.digest().equals(value.get("basis"))),"history original basis absent");
            if(value.get("selection")!=null)require(owner.selections.containsKey(value.get("selection")),"history original selection absent");
        }
    }
    static final class RetainedHistory implements AutoCloseable {
        private final MembershipGrantJournal owner;
        private final MembershipCurrentGeneration selected;
        private RetainedHistory(MembershipGrantJournal owner,MembershipCurrentGeneration selected){this.owner=owner;this.selected=selected;}
        synchronized MembershipCapsule capsule()throws IOException{selected.check();return selected.capsule;}
        synchronized Map<String,byte[]> images()throws IOException{var images=selected.images();selected.check();return images;}
        synchronized Decoded manifest()throws IOException{selected.check();return selected.manifest;}
        synchronized byte[] ancestry()throws IOException {
            var bytes=selected.ancestry();selected.check();return bytes;
        }
        @Override public synchronized void close()throws IOException{try{selected.close();}finally{owner.close();}}
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
        return openGenerations(requested,root,identity,resources,verifier,cut,withFloors,withRetirement,withRotation,withFloorRelease,maximum,
                withSourceRetirement,withCapture,withVotes,withApplication,withContext,materialization,false);
    }
    /** Native original-history storage open. No historical observation set is supplied by the caller. */
    static MembershipGrantJournal openBootstrapped(Path requested,Path materialization,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        return openGenerations(requested,root,identity,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,Set.of()),cut,
                true,true,true,true,maximum,true,true,true,true,true,Objects.requireNonNull(materialization),true);
    }
    /** Required-retention entry for the future automatic owner. Legacy component
     * opens remain usable, but cannot silently replace this entry after initialization. */
    static MembershipGrantJournal openRetainingPeers(Path requested,Path materialization,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        var owner=openBootstrapped(requested,materialization,root,identity,resources,maximum,cut);
        try{owner.initializePeerRetention();return owner;}
        catch(IOException|RuntimeException|Error error){try{owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    /** Required future-intent entry. Missing state cannot be recreated from a
     * later tip; legacy component opens do not replace this automatic-owner entry. */
    static MembershipGrantJournal openRetainingFuturePeers(Path requested,Path materialization,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        var owner=openRetainingPeers(requested,materialization,root,identity,resources,maximum,cut);
        try{owner.initializeFutureRetention();return owner;}
        catch(IOException|RuntimeException|Error error){try{owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private static MembershipGrantJournal openGenerations(Path requested,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,MembershipCurrentGeneration.Verifier verifier,MembershipBallotAllocator.Cut cut,
            boolean withFloors,boolean withRetirement,boolean withRotation,boolean withFloorRelease,int maximum,boolean withSourceRetirement,
            boolean withCapture,boolean withVotes,boolean withApplication,boolean withContext,Path materialization,boolean ownedHistory)throws IOException {
        require(maximum>=RESERVATION && maximum<=MAXIMUM,"grant journal capacity");
        Objects.requireNonNull(resources);Objects.requireNonNull(verifier);Objects.requireNonNull(cut);Path path=AdmissionPaths.safe(requested);
        var owner=materialization!=null?MembershipBallotAllocator.openBootstrapped(path,materialization,root,identity,cut):withContext?MembershipBallotAllocator.openWithPendingContext(path,root,identity,cut):withApplication?MembershipBallotAllocator.openWithAppliedEnd(path,root,identity,cut):withVotes?MembershipBallotAllocator.openWithPendingAccept(path,root,identity,cut):withCapture?MembershipBallotAllocator.openWithCaptureRecovery(path,root,identity,cut):withSourceRetirement?MembershipBallotAllocator.openWithSourceRetirement(path,root,identity,cut):withRotation?MembershipBallotAllocator.openWithJournalRotation(path,root,identity,cut):withRetirement?MembershipBallotAllocator.openWithRetirement(path,root,identity,cut):withFloors?MembershipBallotAllocator.openWithFloorCopies(path,root,identity,cut):MembershipBallotAllocator.openWithGenerationInstall(path,root,identity,cut);MembershipGrantJournal journal=null;
        try {
            journal=new MembershipGrantJournal(path,root,identity,owner,maximum,cut,withCapture);journal.resources=resources;journal.ownedHistory=ownedHistory;journal.capsuleVerifier=ownedHistory?journal::verifyKnownHistory:verifier;journal.floorReleaseEnabled=withFloorRelease;
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
            if(materialization!=null)journal.loadPeerRetention();
            if(materialization!=null)journal.loadFutureRetention();
            if(materialization!=null)journal.loadLearnerRetention();
            if(journal.current==null)journal.reloadGenerations();
            if(journal.peerRetention!=null)journal.recoverPeerRetention();
            if(journal.learnerRetention!=null)journal.recoverLearnerRetention();
            if(withFloors) {
                journal.floors=ownedHistory?new MembershipFloorFiles(path,root,identity,resources,new HistoryRead(journal),withFloorRelease):
                        new MembershipFloorFiles(path,root,identity,resources,verifier,withFloorRelease);
                var parents=new ArrayList<MembershipCapsule.Anchor>();journal.addFloorParent(parents);journal.current.verifyParents(parents);
            }
            if(withRetirement)journal.retirement=new MembershipRetirementFiles(path,resources,journal.floors,journal.sources);
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
            if(journal.futureRetention!=null)journal.recoverFutureRetention();
            journal.checkOwner();
            if(protectedCapture) {
                journal.contextCaptureIdle(true);journal.retainedContextOriginal(false,true);
                journal.resumeCapture(pending);pending=null;
            }
            if(withContext && (journal.pendingContext.active().isPresent() || journal.pendingContext.pending())) {
                if(!journal.recoverCoveredContext() && !journal.recoverContextAcceptance())journal.retainPendingContext();
            }
            if(withVotes)journal.recoverVote();
            journal.completeFutureRetention();
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
        current=ownedHistory?MembershipCurrentGeneration.readOwned(new HistoryRead(this),resources,cut):
                new MembershipCurrentGeneration(directory,root,identity,resources,promises.values(),bases.values(),selections.values(),capsuleVerifier,cut,true);
        inactive=new MembershipGenerationFiles(directory,current.generation,resources);
    }

    private void loadLearnerRetention()throws IOException {
        if(Files.exists(directory.resolve(MembershipLearnerRetentionFiles.FILE),LinkOption.NOFOLLOW_LINKS)
                || Files.exists(directory.resolve(MembershipLearnerRetentionFiles.NEXT),LinkOption.NOFOLLOW_LINKS))
            learnerRetention=new MembershipLearnerRetentionFiles(new HistoryRead(this),resources,maximum-storedJournal().length-pendingBytes());
    }
    private void recoverLearnerRetention()throws IOException {
        if(learnerRetention.initialized())learnerRetention.state().plan().required(current.capsule,current.ancestry());
        else requireRetentionGenesis();
        learnerRetention.discardUnexposed(cut);
        if(!learnerRetention.initialized())learnerRetention.install(MembershipLearnerRetentionPlan.genesis(current.capsule),maximum-storedJournal().length-pendingBytes(),cut);
        else learnerRetention.reseal(cut);
    }
    /** Private local component only. Missing obligations cannot be reconstructed
     * from a later tip; the required open must be used after opting in. */
    synchronized MembershipLearnerRetentionFiles.State initializeLearnerRetention()throws IOException {
        require(ownedHistory,"learner retention requires native history owner");checkOwner();
        if(learnerRetention!=null){require(!learnerRetention.pending(),"learner retention recovery required");return learnerRetention.state();}
        requireRetentionGenesis();
        learnerRetention=new MembershipLearnerRetentionFiles(new HistoryRead(this),resources,maximum-storedJournal().length-pendingBytes());
        try{return learnerRetention.install(MembershipLearnerRetentionPlan.genesis(current.capsule),maximum-storedJournal().length-pendingBytes(),cut);}
        catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    synchronized MembershipLearnerRetentionFiles.State learnerRetentionState()throws IOException {
        checkOwner();require(learnerRetention!=null && !learnerRetention.pending(),"learner retention not initialized/recovered");
        learnerRetention.state().plan().required(current.capsule,current.ancestry());return learnerRetention.state();
    }
    /** Exact local obligation only, never an export permit or learner ACK. */
    synchronized MembershipLearnerRetentionFiles.State retainLearnerOffer(MembershipIdentity joining)throws IOException {
        var before=learnerRetentionState();floorIdle();applicationReferencesIdle();
        require(pendingAccept.active()==null,"learner retention cannot change a pending slot");
        var plan=before.plan().offer(current.capsule,current.ancestry(),joining);
        if(Arrays.equals(plan.bytes(),before.plan().bytes()))return before;
        require(promise==null || basis!=null || current.manifest.value().get("promise").equals(promise.digest()),
                "learner retention cannot change an incomplete grant");
        try{return learnerRetention.install(plan,maximum-storedJournal().length-pendingBytes(),cut);}
        catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** Quorum replication/frozen-source propagation must be connected before
     * enabling source exposure in this mode. Local files cannot stand in for it. */
    synchronized void checkLearnerRetentionExport()throws IOException {
        checkOwner();require(learnerRetention==null,"learner source export requires replicated retention permit");
    }

    private void loadPeerRetention()throws IOException {
        if(Files.exists(directory.resolve(MembershipPeerRetentionFiles.FILE),LinkOption.NOFOLLOW_LINKS)
                || Files.exists(directory.resolve(MembershipPeerRetentionFiles.NEXT),LinkOption.NOFOLLOW_LINKS))
            peerRetention=new MembershipPeerRetentionFiles(new HistoryRead(this),resources,maximum-storedJournal().length-pendingBytes());
    }
    /** Opt-in local learner-retention component. Not yet a public/automatic mode. */
    static MembershipGrantJournal openRetainingLearners(Path requested,Path materialization,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,int maximum,MembershipBallotAllocator.Cut cut)throws IOException {
        var owner=openBootstrapped(requested,materialization,root,identity,resources,maximum,cut);
        try{owner.initializeLearnerRetention();return owner;}
        catch(IOException|RuntimeException|Error error){try{owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private void loadFutureRetention()throws IOException {
        if(Files.exists(directory.resolve(MembershipFutureRetentionFiles.FILE),LinkOption.NOFOLLOW_LINKS)
                || Files.exists(directory.resolve(MembershipFutureRetentionFiles.NEXT),LinkOption.NOFOLLOW_LINKS)) {
            require(ownedHistory && peerRetention!=null,"future retention requires native peer ledger");
            futureRetention=new MembershipFutureRetentionFiles(new HistoryRead(this),resources,maximum-storedJournal().length-pendingBytes());
            require(pendingBytes()<=maximum-storedJournal().length,"future retention shared completion capacity");
        }
    }
    private void recoverFutureRetention()throws IOException {
        if(futureRetention.initialized())verifyFutureRetention();else requireRetentionGenesis();
        futureRetention.recover(cut);
    }
    synchronized MembershipFutureRetentionFiles.State initializeFutureRetention()throws IOException {
        checkOwner();require(ownedHistory && peerRetention!=null,"future retention requires initialized native peers");
        if(futureRetention!=null && futureRetention.initialized())return futureRetention.state();
        requireRetentionGenesis();require(peerRetention.state().revision()==0,"future retention initialization requires unused peer ledger");
        if(futureRetention==null)futureRetention=new MembershipFutureRetentionFiles(new HistoryRead(this),resources,maximum-storedJournal().length-pendingBytes());
        try {
            futureRetention.install(futureRetention.proposal(null,List.of(),Map.of()),maximum-storedJournal().length-pendingBytes(),this::checkOwner,cut);
            return futureRetention.state();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private boolean futurePending(){return futureRetention!=null && futureRetention.initialized() && futureRetention.state().pending();}
    private void verifyFutureRetention()throws IOException {
        if(!futurePending())return;var state=futureRetention.state();var currentIndex=number(current.capsule.context.cut.get("index"));
        var parents=new ArrayList<MembershipCapsule.Anchor>();
        for(var peer:state.peers) {
            require(peer.identity().equals(current.capsule.context.identities.get(peer.identity().nodeId().value())),"future retention permanent peer changed");
            peerRetention.state().plan().possible(peer.identity());parents.add(peer.lower());
        }
        if(currentIndex>=number(state.target().cut().get("index")))parents.add(state.target());
        else {
            require(current.capsule.terminal().equals(state.parent),"future retention lost original parent");
            var selected=selectedRetentionIntent();
            boolean inherited=selected!=null && selected.futureObjects().containsKey(state.digest);
            if(!inherited) {
                state.matches(pendingAccept.active());verifyVote(pendingAccept.active());
                // Covering installation retires derived application files before
                // switching the selector. Its original vote and frozen GSFT must
                // remain owned by the exact local source of the newer selection.
                boolean coveredCapture=selection!=null && basis!=null && sources!=null
                        && !selection.digest().equals(current.manifest.value().get("selection"))
                        && number(object(selection.value().get("cut")).get("index"))>=number(state.target().cut().get("index"))
                        && list(selection.value().get("sources")).stream().map(MembershipFormat::object)
                            .anyMatch(row->row.get("voter").equals(identity.nodeId().value()) && row.get("basisDigest").equals(basis.digest()))
                        && MembershipPeerRetentionSource.read(sources.original(basis).packet(),basis,identity).proofs().stream()
                            .anyMatch(proof->hash(proof.bytes()).equals(state.digest));
                if(!coveredCapture){require(appliedEnd!=null,"future retention application owner unavailable");appliedEnd.retainedTarget(state);}
            }
        }
        current.capsule.verifyAncestry(current.ancestry(),parents);
        checkFutureEndpointCapacity(peerRetention.state().plan());
    }
    private void checkFutureEndpointCapacity(MembershipPeerRetentionPlan plan) {
        if(!futurePending())return;var target=futureRetention.state().target();
        for(var peer:futureRetention.state().peers) {
            var points=plan.possible(peer.identity());
            require(number(points.getFirst().cut().get("index"))>=number(target.cut().get("index"))
                    || points.size()==1 || points.getLast().equals(target),"future retention unresolved endpoint capacity");
        }
    }
    synchronized MembershipFutureRetentionFiles.State futureRetentionState()throws IOException {
        checkOwner();require(futureRetention!=null && futureRetention.initialized() && !futureRetention.candidate(),"future retention not initialized/recovered");return futureRetention.state();
    }
    /** Persist one peer's possible future endpoint from this owner's real applied
     * end. No transport or governing quorum is implied by this local return. */
    synchronized MembershipFutureRetentionFiles.State retainFutureDispatch(MembershipIdentity peer,PendingPublication target)throws IOException {
        require(!peer.equals(identity),"future retention self dispatch");return retainFutureTarget(peer,target);
    }
    // Incoming quorum recording may name this voter as the intended recipient.
    // That records another proposer's uncertainty; it does not send to ourselves.
    private MembershipFutureRetentionFiles.State retainFutureTarget(MembershipIdentity peer,PendingPublication target)throws IOException {
        var state=futureRetentionState();target.check();require(target.owner==this,"future retention foreign live capability");
        var plan=peerRetentionState().plan();
        var originals=new TreeMap<>(target.originals());var vote=target.vote;
        originals.put("entry.gsr",vote.entry().bytes());originals.put("accept.gsr",vote.accept().bytes());originals.put("proof.gsr",vote.proof().bytes());
        var peers=new TreeMap<String,MembershipFutureRetentionFiles.Peer>();
        if(state.pending()) {
            require(state.parent.equals(target.parent()) && state.target().equals(target.target()),"future retention different unresolved target");
            state.matchesOriginals(originals);
            state.peers.forEach(p->peers.put(p.identity().nodeId().value(),p));
        }
        if(peers.containsKey(peer.nodeId().value())) {
            require(peers.get(peer.nodeId().value()).identity().equals(peer),"future retention changed target identity");return state;
        }
        var possible=plan.possible(peer);require(possible.size()==1,"future retention earlier dispatch unresolved");
        peers.put(peer.nodeId().value(),new MembershipFutureRetentionFiles.Peer(peer,possible.getFirst()));
        byte[] proposed=futureRetention.proposal(target.parent(),List.copyOf(peers.values()),originals);
        try {
            long completion=state.pending()?0:MembershipPeerRetentionFiles.MAXIMUM+futureRetention.clearMaximum();
            futureRetention.install(proposed,maximum-storedJournal().length-pendingBytes()-completion,target::check,cut);
            cut.at("FUTURE_RETENTION_BEFORE_RETURN");target.check();return futureRetention.state();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** Make covered uncertainty durable in the ordinary ledger before clearing
     * its original future proof. Replaying this merge never removes an endpoint. */
    private void completeFutureRetention()throws IOException {
        if(!futurePending())return;var state=futureRetention.state();
        if(number(current.capsule.context.cut.get("index"))<number(state.target().cut().get("index")))return;
        verifyFutureRetention();var plan=peerRetention.state().plan();
        for(var peer:state.peers)plan=plan.recordCoveredDispatch(current.capsule,current.ancestry(),peer.identity(),peer.lower(),state.target());
        try {
            if(!Arrays.equals(plan.bytes(),peerRetention.state().plan().bytes()))retainPeerPlan(plan,MembershipPeerRetentionFiles.MAXIMUM);
            cut.at("FUTURE_RETENTION_PROMOTED");checkOwner();
            futureRetention.install(futureRetention.proposal(null,List.of(),Map.of()),maximum-storedJournal().length-pendingBytes()+futureRetention.clearMaximum(),this::checkOwner,cut);
            cut.at("FUTURE_RETENTION_CLEARED");checkOwner();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void recoverPeerRetention()throws IOException {
        if(peerRetention.initialized())peerRetention.state().plan().required(current.capsule,current.ancestry());
        else requireRetentionGenesis();
        peerRetention.discardUnexposed(cut);
        if(!peerRetention.initialized())peerRetention.install(MembershipPeerRetentionPlan.genesis(current.capsule),maximum-storedJournal().length-pendingBytes(),cut);
        else peerRetention.reseal(cut);
        completeSelectedRetention();
        completeInheritedFutureRetention();
    }
    /** The immutable selected generation carries the recovery intent. Its exact
     * revision boundary prevents a later observation from being merged twice. */
    private MembershipSelectedRetention selectedRetentionIntent()throws IOException {
        if(peerRetention==null || current==null)return null;
        if(!current.selector.digest().equals(retentionSelector)) {
            selectedRetention=null;importedFuturePending=false;
            if(current.manifest.value().get("selection")!=null && current.coverage().isEmpty()) {
                var selected=current.selectedRecord().orElseThrow();
                selectedRetention=MembershipSelectedRetention.find(current.capsule,selected,identity)
                        .orElseThrow(()->new IllegalArgumentException("selected generation missing peer retention intent"));
                selectedRetention.plan.required(current.capsule,current.ancestry());
                current.capsule.verifyAncestry(current.ancestry(),selectedRetention.requiredParents());
                importedFuturePending=selectedRetention.hasPendingFutures();
            }else if(current.coverage().isPresent() || current.adopted) {
                var completion=inheritedFutureCompletion();
                importedFuturePending=completion!=null && completion.needsCompletion(peerRetention.state());
            }
            retentionSelector=current.selector.digest();
        }
        return selectedRetention;
    }
    private void completeSelectedRetention()throws IOException {
        var intent=selectedRetentionIntent();
        if(intent!=null && intent.needsCompletion(peerRetention.state())) {
            peerRetention.install(intent.plan,maximum-storedJournal().length-pendingBytes(),cut);
            require(!intent.needsCompletion(peerRetention.state()),"selected retention completion changed");
            cut.at("SELECTED_RETENTION_COMPLETED");
        }
    }
    private MembershipFutureRetentionCompletion inheritedFutureCompletion()throws IOException {
        if(peerRetention==null || current==null)return null;
        if(current.adopted)return MembershipFutureRetentionCompletion.find(current.capsule,null,identity,current.ancestry()).orElse(null);
        if(current.coverage().isEmpty())return null;
        var selected=current.selectedRecord().orElseThrow();
        var retention=MembershipSelectedRetention.find(current.capsule,selected,identity);
        if(retention.isEmpty() || retention.get().futures().isEmpty())return null;
        return MembershipFutureRetentionCompletion.find(current.capsule,selected,identity,current.ancestry())
                .orElseThrow(()->new IllegalArgumentException("published future completion missing"));
    }
    private void completeInheritedFutureRetention()throws IOException {
        var completion=inheritedFutureCompletion();
        if(completion!=null && completion.needsCompletion(peerRetention.state())) {
            peerRetention.install(completion.plan,maximum-storedJournal().length-pendingBytes()+MembershipPeerRetentionFiles.MAXIMUM,cut);
            require(!completion.needsCompletion(peerRetention.state()),"inherited future promotion changed");
            importedFuturePending=false;
            cut.at("INHERITED_FUTURE_RETENTION_PROMOTED");
        }
    }
    /** Explicit private opt-in before the first campaign. A non-genesis history
     * cannot reconstruct lost peer uncertainty from its own latest selector. */
    synchronized MembershipPeerRetentionFiles.State initializePeerRetention()throws IOException {
        require(ownedHistory,"peer retention requires native history owner");checkOwner();
        if(peerRetention!=null){require(!peerRetention.pending(),"peer retention recovery required");return peerRetention.state();}
        requireRetentionGenesis();
        peerRetention=new MembershipPeerRetentionFiles(new HistoryRead(this),resources,maximum-storedJournal().length-pendingBytes());
        try{return peerRetention.install(MembershipPeerRetentionPlan.genesis(current.capsule),maximum-storedJournal().length-pendingBytes(),cut);}
        catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void requireRetentionGenesis()throws IOException {
        require(number(current.capsule.context.cut.get("index"))==0,"peer retention initialization requires unused genesis");
        var rootRecord=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var genesis=decode(AdmissionPaths.read(directory.resolve("genesis.gsr"),65536),"records","GENESIS");
        var layout=new MembershipBootstrapLayout(rootRecord,genesis,current.capsule.packet.images().get((String)genesis.value().get("application")));
        var metadata=layout.metadata(identity);
        require(Arrays.equals(storedJournal(),metadata.get(FILE)) && Arrays.equals(current.selector.bytes(),metadata.get(MembershipCurrentGeneration.SELECTOR))
                && Arrays.equals(current.manifest.bytes(),metadata.get("generations/a/generation.gsr")),"peer retention initialization changed bootstrap authority");
        AdmissionPaths.exact(directory.resolve(MembershipBallotAllocator.CURRENT),metadata.get(MembershipBallotAllocator.CURRENT));
        AdmissionPaths.exact(directory.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());
    }
    synchronized MembershipPeerRetentionFiles.State peerRetentionState()throws IOException {
        checkOwner();require(peerRetention!=null && !peerRetention.pending(),"peer retention not initialized/recovered");
        peerRetention.state().plan().required(current.capsule,current.ancestry());return peerRetention.state();
    }
    private MembershipPeerRetentionFiles.State retainPeerPlan(MembershipPeerRetentionPlan plan)throws IOException {
        return retainPeerPlan(plan,0);
    }
    private MembershipPeerRetentionFiles.State retainPeerPlan(MembershipPeerRetentionPlan plan,long completingFuture)throws IOException {
        require(ownedHistory,"peer retention requires native history owner");plan.required(current.capsule,current.ancestry());
        checkFutureEndpointCapacity(plan);
        require(capture==null || !capture.pending(),"peer retention cannot change an unfinished frozen capture");
        require(promise==null || basis!=null || current.manifest.value().get("promise").equals(promise.digest()),"peer retention cannot change an incomplete grant");
        try{return peerRetention.install(plan,maximum-storedJournal().length-pendingBytes()+completingFuture,cut);}catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    synchronized MembershipPeerRetentionFiles.State retainPeerDispatch(MembershipIdentity peer)throws IOException {
        var plan=peerRetentionState().plan();return retainPeerPlan(plan.dispatch(current.capsule,current.ancestry(),peer));
    }
    synchronized MembershipPeerRetentionFiles.State retainPeerObservation(MembershipFloor.Copy copy)throws IOException {
        var plan=peerRetentionState().plan();return retainPeerPlan(plan.observe(current.capsule,current.ancestry(),copy));
    }
    synchronized MembershipPeerRetentionFiles.State reconcilePeerRetention(List<MembershipFloor.Copy> joining)throws IOException {
        var plan=peerRetentionState().plan();return retainPeerPlan(plan.reconcile(current.capsule,current.ancestry(),joining));
    }
    /** A native grant captures the current governing view, not the preceding
     * publication's view. Preserve every remaining peer endpoint and force the
     * existing reconciliation transaction before freezing that new source.
     * A newly added voter still requires its actual complete joining copy;
     * this path cannot infer learner readiness from a configuration alone. */
    private void reconcileKnownPeerConfiguration()throws IOException {
        if(peerRetention==null)return;
        var previous=peerRetentionState().plan();
        var next=previous.reconcile(current.capsule,current.ancestry(),List.of());
        if(!Arrays.equals(previous.bytes(),next.bytes()))retainPeerPlan(next);
    }
    synchronized void checkRetentionResources(MembershipResources budget)throws IOException {
        require(resources==budget,"retention requires actual storage resource owner");peerRetentionState();
    }
    /** No dispatch permission: construct a bounded request under the actual
     * installed round. A pending identical target can be resumed after lost ACKs. */
    synchronized MembershipRetentionIntent peerRetentionIntent(MembershipIdentity peer,Map<String,Object> ballot)throws IOException {
        var state=peerRetentionState();checkRetentionRound(ballot,null);
        require(!peer.equals(identity),"retention intent self dispatch");var possible=state.plan().possible(peer);
        require(possible.size()==1 || possible.getLast().equals(current.capsule.terminal()),"retention intent different unresolved target");
        return new MembershipRetentionIntent(Map.of("selection",current.manifest.value().get("selection"),
                "peer",MembershipPeerRetentionPlan.identity(peer),"lower",MembershipRetentionIntent.anchor(possible.getFirst()),
                "upper",MembershipRetentionIntent.anchor(current.capsule.terminal())));
    }
    private void checkRetentionRound(Map<String,Object> ballot,MembershipRetentionIntent intent)throws IOException {
        checkActivationBallot(current.capsule.context.authority(),ballot);
        var selected=current.selectedRecord().orElseThrow(()->new IllegalArgumentException("retention intent installed selection required"));
        require(selected.value().get("ballot").equals(ballot) && promise!=null && promise.value().get("ballot").equals(ballot)
                && promise.digest().equals(current.manifest.value().get("promise")),"retention intent inactive round");
        if(intent!=null)require(intent.payload.get("selection").equals(selected.digest()) && intent.upper.equals(current.capsule.terminal()),"retention intent changed selected target");
    }
    /** Atomic force under the original native fence. The ACK is not a vote or a
     * completed peer installation. A higher observed PREPARE fences the reply. */
    synchronized Decoded recordPeerRetention(MembershipIdentity sender,Decoded request)throws IOException {
        require(request.kind().equals("RETENTION_INTENT"),"retention request kind");peerRetentionState();
        var value=request.value();var ballot=object(value.get("ballot"));
        current.capsule.context.wire(request,sender,identity,ballot,UUID.fromString((String)value.get("trace")),number(value.get("sequence")));
        require(sender.nodeId().value().equals(ballot.get("proposer")),"retention intent requires current proposer");
        var intent=new MembershipRetentionIntent(object(value.get("payload")));checkRetentionRound(ballot,intent);
        var plan=peerRetention.state().plan().recordDispatch(current.capsule,current.ancestry(),intent.peer,intent.lower,intent.upper);
        if(!Arrays.equals(plan.bytes(),peerRetention.state().plan().bytes()))retainPeerPlan(plan);
        checkRetentionRound(ballot,intent);cut.at("RETENTION_ACK_BEFORE_RETURN");checkRetentionRound(ballot,intent);
        var response=new TreeMap<>(value);response.put("sender",value.get("recipient"));response.put("recipient",value.get("sender"));
        var state=peerRetention.state();response.put("payload",Map.of("intent",intent.digest,"revision",state.revision(),"ledger",state.digest()));
        return decode(encode("wire","RETENTION_ACK",response),"wire","RETENTION_ACK");
    }
    synchronized void checkPeerRetentionDispatch(MembershipRetentionIntent intent,Map<String,Object> ballot)throws IOException {
        peerRetentionState();checkRetentionRound(ballot,intent);
        var points=peerRetention.state().plan().possible(intent.peer);
        require(points.stream().anyMatch(intent.upper::equals),"retention intent target no longer retained");
    }

    /** Snapshot only: this does not record intent or authorize a network send. */
    synchronized MembershipFutureRetentionIntent futureRetentionIntent(MembershipIdentity peer,Map<String,Object> ballot,PendingPublication target)throws IOException {
        require(target.owner==this,"future intent foreign native owner");target.check();checkRetentionRound(ballot,null);
        require(!peer.equals(identity),"future intent self dispatch");var points=peerRetentionState().plan().possible(peer);
        require(points.size()==1,"future intent earlier dispatch unresolved");
        return new MembershipFutureRetentionIntent(Map.of("selection",target.vote.selected().digest(),"certificate",target.vote.certificate().digest(),
                "peer",MembershipPeerRetentionPlan.identity(peer),"lower",MembershipRetentionIntent.anchor(points.getFirst()),
                "parent",MembershipRetentionIntent.anchor(target.parent()),"upper",MembershipRetentionIntent.anchor(target.target())));
    }
    private void checkFutureIntent(MembershipFutureRetentionIntent intent,Map<String,Object> ballot)throws IOException {
        checkRetentionRound(ballot,null);
        require(intent.selection.equals(current.selectedRecord().orElseThrow().digest()),"future intent changed selection");
        require(intent.peer.equals(current.capsule.context.identities.get(intent.peer.nodeId().value()))
                && current.capsule.context.voters().contains(intent.peer.nodeId().value()),"future intent non-governing identity");
    }
    synchronized void checkFutureRetentionRecording(MembershipFutureRetentionIntent intent,Map<String,Object> ballot,PendingPublication target)throws IOException {
        require(target.owner==this,"future intent foreign native owner");target.check();checkFutureIntent(intent,ballot);
        require(target.parent().equals(intent.parent) && target.target().equals(intent.upper)
                && target.vote.certificate().digest().equals(intent.certificate),"future intent changed native application");
        var state=futureRetentionState();
        require(state.pending() && state.target().equals(intent.upper) && state.peers.stream().anyMatch(p->p.identity().equals(intent.peer)
                && p.lower().equals(intent.lower)),"future intent not durably recorded locally");
    }
    private Decoded futureRetentionRejection(Decoded request,String reason) {
        var response=new TreeMap<>(request.value());response.put("sender",request.value().get("recipient"));response.put("recipient",request.value().get("sender"));
        response.put("payload",Map.of("reason",reason,"promised",object(promise.value().get("ballot"))));
        return decode(encode("wire","REJECT",response),"wire","REJECT");
    }
    /** Forces this voter's own proof before acknowledging an unpublished target.
     * The sender's digest cannot create nativeApplied, votes, or remote progress. */
    synchronized Decoded recordFutureRetention(MembershipIdentity sender,Decoded request)throws IOException {
        require(request.kind().equals("FUTURE_RETENTION_INTENT"),"future retention request kind");checkOwner();peerRetentionState();
        var value=request.value();var ballot=object(value.get("ballot"));
        current.capsule.context.wire(request,sender,identity,ballot,UUID.fromString((String)value.get("trace")),number(value.get("sequence")));
        require(sender.nodeId().value().equals(ballot.get("proposer")),"future intent requires current proposer");
        var intent=new MembershipFutureRetentionIntent(object(value.get("payload")));checkFutureIntent(intent,ballot);
        String storage,digest;long revision;
        if(current.capsule.terminal().equals(intent.upper)) {
            require(current.publishedCertificate().filter(intent.certificate::equals).isPresent(),"future intent changed published certificate");
            current.capsule.verifyAncestry(current.ancestry(),List.of(intent.parent,intent.lower));
            var plan=peerRetention.state().plan().recordCoveredDispatch(current.capsule,current.ancestry(),intent.peer,intent.lower,intent.upper);
            if(!Arrays.equals(plan.bytes(),peerRetention.state().plan().bytes()))retainPeerPlan(plan);
            storage="CURRENT";digest=peerRetention.state().digest();revision=peerRetention.state().revision();
        } else {
            if(nativeApplied==null)return futureRetentionRejection(request,"NOT_READY");var target=pendingPublication(nativeApplied);
            require(target.parent().equals(intent.parent) && target.target().equals(intent.upper)
                    && target.vote.certificate().digest().equals(intent.certificate),"future intent changed native application");
            current.capsule.verifyAncestry(current.ancestry(),List.of(intent.lower));
            var points=peerRetention.state().plan().possible(intent.peer);
            // Distinct old endpoints would require a third possible cut. Obtain
            // a verified complete peer copy before retrying; never choose one.
            if(points.size()!=1 || !points.getFirst().equals(intent.lower))return futureRetentionRejection(request,"CAPACITY_EXCEEDED");
            var state=retainFutureTarget(intent.peer,target);storage="FUTURE";digest=state.digest;revision=state.revision;
        }
        checkFutureIntent(intent,ballot);cut.at("FUTURE_RETENTION_ACK_BEFORE_RETURN");checkFutureIntent(intent,ballot);
        var response=new TreeMap<>(value);response.put("sender",value.get("recipient"));response.put("recipient",value.get("sender"));
        response.put("payload",Map.of("intent",intent.digest,"storage",storage,"revision",revision,"digest",digest));
        return decode(encode("wire","FUTURE_RETENTION_ACK",response),"wire","FUTURE_RETENTION_ACK");
    }

    /** Resolve only an already retained proven prefix. Raw incoming or newly published
     * prefixes require their own typed proof path; no catch-and-trust fallback exists. */
    private MembershipCapsule verifyKnownHistory(Decoded rootRecord,MembershipSourcePacket packet,Map<String,byte[]> images) {
        try {
            checkBaseOwner();require(rootRecord.rootDigest().equals(root.manifestDigest()),"owned history foreign root");
            if(current!=null && current.capsule.sameProvenPrefix(packet)) {
                current.check();var result=current.capsule.materialization(packet,images,current.capsule.verifiedAncestry(current.ancestry()));current.check();return result;
            }
            if(inactive!=null && inactive.exists() && !inactive.pending()) {
                var originals=inactive.originalFiles();
                if(originals.containsKey("source.gscp") && originals.containsKey("generation.gsr")) {
                    var original=MembershipSourcePacket.decode(originals.get("source.gscp"));
                    var a=new TreeMap<>(original.capsule().value());var b=new TreeMap<>(packet.capsule().value());a.remove("inventory");b.remove("inventory");
                    if(a.equals(b) && original.images().equals(packet.images())) {
                        var capsule=inactive.verifiedOriginal(new HistoryRead(this));return capsule.materialization(packet,images,
                                capsule.verifiedAncestry(originals.getOrDefault("ancestry.gsr",new byte[0])));
                    }
                }
            }
            if(sources!=null)for(var basis:bases.values())if(sources.retainedIdentities().contains(basis.value().get("basisId"))) {
                var original=sources.original(basis);
                // Decode and verify only the exact selected candidate. All source files are
                // already bounded and owned; no unbounded trust cache is retained.
                var a=new TreeMap<>(original.packet().capsule().value());var b=new TreeMap<>(packet.capsule().value());a.remove("inventory");b.remove("inventory");
                if(a.equals(b) && original.packet().images().equals(packet.images())) {
                    var capsule=sources.verifiedOriginal(basis,new HistoryRead(this));return capsule.materialization(packet,images,List.of());
                }
            }
            if(floors!=null)for(var copy:floors.retained().map(MembershipFloorFiles.Retained::copies).orElse(List.of()))
                if(copy.capsule.sameProvenPrefix(packet))return copy.capsule.materialization(packet,images,
                        copy.capsule.verifiedAncestry(copy.fileNames().contains("ancestry.gsr")?copy.fileBytes("ancestry.gsr"):new byte[0]));
            throw new IllegalArgumentException("original historical prefix not retained by owner");
        }catch(IOException error){throw new java.io.UncheckedIOException(error);}
    }
    private void verifyPlan(MembershipGenerationPlan plan,Collection<MembershipCapsule.Anchor> parents)throws IOException {
        var original=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        if(ownedHistory)plan.verifyOwned(original,identity,parents);else plan.verify(original,identity,capsuleVerifier,parents);
    }
    /** A context owns a specific old generation, not merely another copy at the same
     * cut. Preserve that generation's original first/latest coverage and ancestry. */
    private MembershipCurrentGeneration.Verifier contextVerifier() {
        return contextVerifier(new HistoryRead(this));
    }
    private MembershipCurrentGeneration.Verifier contextVerifier(HistoryRead read) {
        if(!ownedHistory)return capsuleVerifier;
        return (rootRecord,packet,images)->{
            try {
                read.check();require(rootRecord.rootDigest().equals(root.manifestDigest()),"context history foreign root");
                MembershipCapsule original;
                if(pendingContext!=null && pendingContext.active().isPresent())original=pendingContext.verifiedOriginal(read);
                else {
                    require(inactive!=null && inactive.exists() && !inactive.pending(),"context original generation unavailable");
                    original=inactive.verifiedOriginal(read);
                }
                require(Arrays.equals(original.packet.bytes(),packet.bytes()),"context verifier substituted original packet");
                packet.verifyImages(images);read.check();return original;
            }catch(IOException failure){throw new java.io.UncheckedIOException(failure);}
        };
    }
    private long pendingBytes(){return (pendingAccept==null?0:pendingAccept.bytes()+(applicationMetadata>0?pendingAccept.clearAllowance():0))+applicationMetadata+(pendingContext==null?0:pendingContext.bytes())+(peerRetention==null?0:peerRetention.bytes())+(learnerRetention==null?0:learnerRetention.bytes())+(futureRetention==null?0:futureRetention.bytes())+futureCompletionBytes();}
    private boolean importedFuturePending;
    private long futureCompletionBytes() {
        if(!futurePending() && !importedFuturePending)return 0;
        return Math.max(0,MembershipPeerRetentionFiles.MAXIMUM-peerRetention.candidateBytes())
                +(futurePending()?Math.max(0,futureRetention.clearMaximum()-futureRetention.candidateBytes()):0);
    }

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
        var expected=MembershipPendingContext.create(root,identity,vote.selector(),originals,vote,promise,local,source.images(),contextVerifier());
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
            return MembershipPendingContext.reconstruct(pendingContext.active().orElseThrow(),root,identity,promise,local,source.images(),contextVerifier());
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
                promises.get((String)backing.value().get("basisId")),retainedSource(backing),sources.original(backing).images(),contextVerifier());
        if(contextCoveredBy(original,current.capsule)) {
            require(!installing && !inactive.pending() && inactive.exists()
                    && promise.digest().equals(current.manifest.value().get("promise"))
                    && basis!=null && basis.digest().equals(current.manifest.value().get("basis"))
                    && selection!=null && selection.digest().equals(current.manifest.value().get("selection")),
                    "covered context requires exact completed installed decision");
            require(pendingAccept.active()==null?replacingVote && !pendingAccept.pending()
                    :Arrays.equals(pendingAccept.active().bytes(),original.vote().bytes()),"covered context original vote changed");
            verifyContextCoverage(original,current.capsule,current.ancestry(),selection);
            contextRetirementFloor(original);contextIntermediate(original,inactive.originalFiles());return original;
        }
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
                && (selection.value().get("cut").equals(current.capsule.context.cut)
                    && Objects.equals(selection.value().get("nextEntry"),installed.value().get("nextEntry"))
                    || number(object(selection.value().get("cut")).get("index"))>number(current.capsule.context.cut.get("index")))
                && compareBallot(object(selection.value().get("ballot")),object(installed.value().get("ballot")))>0;
    }
    private boolean contextCoveredBy(MembershipPendingContext.Reconstructed original,MembershipCapsule capsule) {
        return number(capsule.context.cut.get("index"))>=number(original.vote().entry().value().get("index"));
    }
    /** Selection may settle the old slot, but never discard its protected originals.
     * The exact backing can retain a higher selected ACCEPT for the same entry. */
    private void verifyContextCoverage(MembershipPendingContext.Reconstructed original,MembershipCapsule next,byte[] ancestry,Decoded chosen)throws IOException {
        checkOwner();applicationReferencesIdle();var backing=retainedContextBasis();var source=retainedSource(backing);
        require(contextCoveredBy(original,next) && next.context.view.get("operation")==null
                && next.context.authority().equals(original.capsule().context.authority()),"covered context requires advanced stable prefix");
        next.verifyAncestry(ancestry,List.of(original.capsule().terminal(),source.capsule.terminal()));
        require(basis!=null && Arrays.equals(basis.bytes(),backing.bytes()) && chosen.value().get("ballot").equals(promise.value().get("ballot"))
                && chosen.value().get("view").equals(next.context.authority()) && chosen.value().get("cut").equals(next.context.cut)
                && compareBallot(object(promise.value().get("ballot")),object(original.vote().promise().value().get("ballot")))>0
                && list(chosen.value().get("sources")).stream().map(MembershipFormat::object).anyMatch(row->row.equals(source.reference())),
                "covered context missing exact selected backing");
        MembershipContextTail.selected(original,source.capsule.packet,(String)backing.value().get("accepted"));
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
    /** A forced covering selector can finish an exact empty vote/context cleanup.
     * No ACK is emitted; governing floor release remains explicit maintenance. */
    private boolean recoverCoveredContext()throws IOException {
        if(pendingContext.active().isEmpty() || pendingContext.pending())return false;
        var original=retainedContextOriginal(true);
        if(!contextCoveredBy(original,current.capsule))return false;
        completeCoveredContext(original);return true;
    }
    private void completeCoveredContext(MembershipPendingContext.Reconstructed original)throws IOException {
        byte[] context=pendingContext.activeBytes().orElseThrow(),selector=current.selector.bytes();
        byte[] boundPromise=promise.bytes(),boundBasis=basis.bytes(),boundSelection=selection.bytes();
        MembershipGenerationFiles.Guard guard=()->{
            checkOwner();otherAuthorityTransactionsIdle();applicationReferencesIdle();
            require(Arrays.equals(selector,current.selector.bytes()) && Arrays.equals(boundPromise,promise.bytes())
                    && Arrays.equals(boundBasis,basis.bytes()) && Arrays.equals(boundSelection,selection.bytes()),"covered context installed authority changed");
            if(pendingContext.active().isPresent()) {
                require(Arrays.equals(context,pendingContext.activeBytes().orElseThrow()),"covered context metadata changed");
                require(Arrays.equals(original.vote().bytes(),retainedContextOriginal(true).vote().bytes()),"covered context reconstructed vote changed");
            }else require(pendingAccept.active()==null && !pendingAccept.pending(),"covered context removed before empty vote");
        };
        try {
            cut.at("CONTEXT_SETTLEMENT_VALIDATED");guard.check();
            if(pendingAccept.active()!=null)pendingAccept.clearSettled(original.vote(),guard,cut);
            else require(!pendingAccept.pending(),"covered context unexpected empty-vote candidate");
            pendingAccept.sealActive(guard,cut);cut.at("CONTEXT_SETTLEMENT_EMPTY_FORCED");guard.check();
            pendingContext.clearRedundant(context,guard,cut);cut.at("CONTEXT_SETTLEMENT_CLEARED");guard.check();
            replayFiles.releaseCompletion();appliedEnd.releaseEmptyCompletion();releasePublicationImage();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
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
    /** The exact original unpublished source stays pinned after clearing the vote.
     * It is reclaimed later only by the normal independently forced floor path. */
    private void verifySettlement(MembershipPendingAccept.Vote vote,Map<String,byte[]> originals,
            MembershipCapsule next,Map<String,byte[]> installed)throws IOException {
        require(vote!=null,"settlement requires original vote");
        require(appliedEnd!=null && replayFiles!=null && !appliedEnd.present() && !replayFiles.present()
                && (pendingContext==null || pendingContext.active().isEmpty() && !pendingContext.pending()),"settlement conflicts with derived or protected authority");
        verifySettlementAuthority(vote,originals,next,installed);
    }
    private void verifySettlementAuthority(MembershipPendingAccept.Vote vote,Map<String,byte[]> originals,
            MembershipCapsule next,Map<String,byte[]> installed)throws IOException {
        var old=originalGeneration(originals);var selector=vote.selector().value();
        require(selector.get("root").equals(root.manifestDigest()) && selector.get("node").equals(identity.nodeId().value())
                && selector.get("generation").equals(old.generation.value().get("generation")) && selector.get("digest").equals(old.generation.digest()),"settlement original selector changed");
        require(Arrays.equals(originals.get("promise.gsr"),vote.promise().bytes()) && Arrays.equals(originals.get("selected.gsr"),vote.selected().bytes()),"settlement original decision changed");
        // Recheck any original forced PROOF/certificate too. These remain original
        // local attestations, not new peer observations or an application ACK.
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
        if(peerRetention!=null) {
            // Reconstruct the exact frozen source, including its original ledger
            // and future obligations. The live ledger may already have advanced;
            // it is not evidence of what this earlier PROMISE captured.
            var frozen=MembershipPeerRetentionSource.read(retainedSource(b));
            expected=frozen.projection()==null?
                    MembershipPeerRetentionSource.freeze(expected,frozen.promise(),identity,frozen.localBytes(),frozen.futureBytes()):
                    MembershipPeerRetentionSource.freezeInherited(expected,frozen.promise(),identity,frozen.localBytes(),frozen.proofs());
        }
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
        return MembershipCaptureFiles.plan(current,grant,identity,retentionPacket(votePacket(),grant),voteAccepted());
    }
    private MembershipSourcePacket retentionPacket(MembershipSourcePacket original,Decoded grant)throws IOException {
        byte[] future=null;
        if(futureRetention!=null)future=futureRetention.activeBytes();
        else if(Files.exists(directory.resolve(MembershipFutureRetentionFiles.FILE),LinkOption.NOFOLLOW_LINKS))
            future=AdmissionPaths.read(directory.resolve(MembershipFutureRetentionFiles.FILE),MembershipFutureRetentionFiles.MAXIMUM);
        if(future!=null && !MembershipFutureRetentionFiles.decodeOwned(future,root.manifestDigest(),identity).pending())future=null;
        byte[] bytes;
        if(peerRetention!=null)bytes=peerRetention.activeBytes();
        else if(Files.exists(directory.resolve(MembershipPeerRetentionFiles.FILE),LinkOption.NOFOLLOW_LINKS))
            // Capture recovery precedes opening all shared-journal users. Read only
            // exact bounded active bytes under this owner; normal open rechecks them
            // before any response and does not select an unexposed next candidate.
            bytes=AdmissionPaths.read(directory.resolve(MembershipPeerRetentionFiles.FILE),MembershipPeerRetentionFiles.MAXIMUM);
        else {require(future==null,"future source requires original peer ledger");return original;}
        var state=MembershipPeerRetentionFiles.decodeOwned(bytes,root.manifestDigest(),identity);
        state.plan().capture(current.capsule,current.ancestry());
        var retention=selectedRetentionIntent();
        // Interrupted capture is reconstructed before the mutable journal users
        // open. Read the exact installed intent, not an empty inferred snapshot.
        if(retention==null && peerRetention==null && current.coverage().isEmpty() && current.selectedRecord().isPresent())
            retention=MembershipSelectedRetention.find(current.capsule,current.selectedRecord().orElseThrow(),identity).orElseThrow();
        if(retention!=null && !retention.futures().isEmpty()) {
            var proofs=new TreeMap<String,MembershipFutureRetentionSet.Proof>();
            for(var proof:retention.futures())if(number(proof.state().target().cut().get("index"))>number(current.capsule.context.cut.get("index")))proofs.put(hash(proof.bytes()),proof);
            if(future!=null)proofs.put(hash(future),new MembershipFutureRetentionSet.Proof(future,MembershipFutureRetentionFiles.decodeOwned(future,root.manifestDigest(),identity)));
            return MembershipPeerRetentionSource.freezeInherited(original,grant,identity,bytes,proofs.values());
        }
        return MembershipPeerRetentionSource.freeze(original,grant,identity,bytes,future);
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
        var contextVerifier=contextVerifier(new HistoryRead(this,originals));
        var original=MembershipPendingContext.reconstructStored(context,root,identity,backingPromise,backingBasis,backing,stored.images(),contextVerifier);
        require(pendingAccept.active()!=null && Arrays.equals(original.vote().bytes(),pendingAccept.active().bytes()),"context capture original vote changed");
        var protectedSource=MembershipPendingTransfer.capture(original,current.capsule,current.images(),capsuleVerifier);
        var packet=retentionPacket(protectedSource.capsule().packet,grant);
        var captured=packet==protectedSource.capsule().packet?protectedSource.capsule():protectedSource.capsule().materialization(packet,protectedSource.images(),current.capsule.verifiedAncestry(current.ancestry()));
        var plan=MembershipCaptureFiles.plan(current,grant,identity,packet,MembershipPendingAccept.accepted(current,original.vote()),protectedSource.images());
        MembershipPendingContext.Context expected=context;
        if(!Arrays.equals(backingBasis.bytes(),plan.basis().bytes()))expected=MembershipPendingContext.rebindStored(context,root,identity,
                backingPromise,backingBasis,backing,stored.images(),grant,plan.basis(),captured,plan.images(),contextVerifier);
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
                    plan.promise(),retainedSource(plan.basis()),sources.original(plan.basis()).images(),contextVerifier());
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
    /** Native installed-voting lifetime. Caller record hashes cannot construct it. */
    final class Voting {
        final MembershipCapsule before;
        final Map<String,Object> ballot;
        private final String selected,selector;
        private Voting()throws IOException {
            require(ownedHistory && current!=null && pendingAccept!=null && promise!=null && selection!=null,"native installed voting owner required");
            before=current.capsule;ballot=Map.copyOf(object(promise.value().get("ballot")));
            selected=selection.digest();selector=current.selector.digest();check();
        }
        void check()throws IOException {
            synchronized(MembershipGrantJournal.this){checkOwner();
                require(ownedHistory && current.selector.digest().equals(selector) && current.capsule.context.cut.equals(before.context.cut)
                        && promise!=null && promise.value().get("ballot").equals(ballot) && selection!=null && selection.digest().equals(selected)
                        && selected.equals(current.manifest.value().get("selection")),"native voting selection changed/uninstalled");
                fence(ballot);}
        }
        void request(MembershipIdentity sender,Decoded request)throws IOException {
            check();require(Set.of("ACCEPT","PROOF","APPLY").contains(request.kind()),"native voting request kind");
            MembershipActivation.incoming(before.context,identity,sender,request,request.kind());
            require(request.value().get("ballot").equals(ballot),"native voting request ballot");
            if(request.kind().equals("APPLY"))require(selected.equals(object(request.value().get("payload")).get("selection")),"native application selected binding");check();
        }
        /** The first selected slot can retain an older logical entry. Its new
         * ACCEPT must precede a floor that would retire the old vote's owner. */
        boolean carriedSlot()throws IOException {
            synchronized(MembershipGrantJournal.this){check();return selection.value().get("nextEntry")!=null
                    && selection.value().get("cut").equals(before.context.cut);}
        }
        private MembershipPendingAccept.Vote vote()throws IOException {
            check();require(!pendingAccept.pending(),"incomplete pending vote cannot attest");return pendingAccept.active();
        }
        Optional<Decoded> record(String phase)throws IOException {
            synchronized(MembershipGrantJournal.this){require(Set.of("ACCEPT","PROOF").contains(phase),"original vote phase");
                var vote=vote();
                // A carried prior-ballot vote remains original recovery evidence,
                // but cannot acknowledge this newly installed voting round.
                if(vote==null || !vote.accept().value().get("ballot").equals(ballot) || !vote.selected().digest().equals(selected)
                        || !vote.selector().digest().equals(selector))return Optional.empty();
                return Optional.ofNullable(phase.equals("ACCEPT")?vote.accept():vote.proof());}
        }
        Owned observation(Decoded record)throws IOException {
            synchronized(MembershipGrantJournal.this){require(record(record.kind()).map(r->r.digest().equals(record.digest())).orElse(false),"original own vote missing");
                MembershipVoteReceipt.bytes(before.context,identity,record);check();
                return new Owned(identity.nodeId().value(),identity.storageId(),record.digest(),cutDigest(before.context.cut));}
        }
        Optional<Decoded> acknowledge(MembershipIdentity sender,Decoded request)throws IOException {
            synchronized(MembershipGrantJournal.this){request(sender,request);String phase=request.kind();
                if(phase.equals("APPLY"))return applicationAcknowledgement(request);
                var held=record(phase);String reference=(String)object(request.value().get("payload")).get(phase.equals("ACCEPT")?"acceptance":"proof");
                if(held.isEmpty() || !held.get().digest().equals(reference))return Optional.empty();
                var record=held.get();observation(record);
                var response=MembershipActivation.frame(phase+"_ACK",before.context,identity,sender,ballot,
                        UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")),
                        Map.of("entry",record.value().get("entry"),"receipt",hash(MembershipVoteReceipt.bytes(before.context,identity,record))));
                cut.at(phase+"_ACK_BEFORE_RETURN");check();return Optional.of(response);}
        }
        /** Only this live owner's completed native end; no selector publication. */
        Optional<Applied> application()throws IOException {
            synchronized(MembershipGrantJournal.this){check();
                var held=vote();
                if(nativeApplied==null || held==null || held.certificate()==null || record("PROOF").isEmpty()
                        || !held.certificate().digest().equals(nativeApplied.plan().originalCertificate().digest()))return Optional.empty();
                pendingPublication(nativeApplied).check();check();return Optional.of(nativeApplied);}
        }
        private Optional<Decoded> applicationAcknowledgement(Decoded request)throws IOException {
            var applied=application();if(applied.isEmpty())return Optional.empty();var actual=applied.get();
            String certificate=(String)object(request.value().get("payload")).get("certificate");
            require(actual.plan().originalCertificate().digest().equals(certificate),"native application acknowledgement certificate");
            var response=new TreeMap<>(request.value());response.put("sender",request.value().get("recipient"));response.put("recipient",request.value().get("sender"));
            var payload=new TreeMap<String,Object>();payload.put("certificate",certificate);payload.put("selection",selected);
            payload.put("statement",actual.plan().statement.digest());
            payload.put("acknowledgement",actual.votingEnd().map(end->end.acknowledgement().digest()).orElse(null));
            response.put("payload",payload);
            var ack=decode(encode("wire","APPLY_ACK",response),"wire","APPLY_ACK");
            cut.at("APPLICATION_ACK_BEFORE_RETURN");check();pendingPublication(actual).check();return Optional.of(ack);
        }
    }
    synchronized Voting voting(MembershipResources budget)throws IOException {
        require(resources==budget,"native voting resource owner");return new Voting();
    }

    /** Native typed reacceptance may retire only this owner's old derived work,
     * after matching the exact entry and payload in the installed selection.
     * The durable old vote survives until acceptCurrent forces its replacement. */
    synchronized <K,T> Owned acceptCurrent(Decoded proposed,byte[] payload,
            io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage)throws IOException {
        require(ownedHistory,"native acceptance requires original history owner");checkOwner();
        if(carriedVoteUntransferred() && appliedEnd!=null && (appliedEnd.present() || replayFiles.present() || appliedEnd.retirementPending())) {
            var entry=decode(proposed.bytes(),"records","ENTRY");
            require(selection!=null && entry.digest().equals(selection.value().get("nextEntry"))
                    && selection.value().get("cut").equals(current.capsule.context.cut)
                    && Arrays.equals(entry.bytes(),current.capsule.packet.objectBytes(entry.digest()))
                    && Arrays.equals(payload,current.capsule.packet.objectBytes((String)entry.value().get("payload"))),
                    "native carried acceptance exact entry/payload before cleanup");
            fence(object(promise.value().get("ballot")));
            retireSupersededApplication(configuration,storage);
        }
        return acceptCurrent(proposed,payload);
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
        if(peerRetention!=null)parents.addAll(peerRetention.state().plan().required(original,ancestry));
        if(learnerRetention!=null)parents.addAll(learnerRetention.state().plan().required(original,ancestry));
        for(var basis:bases.values()) {
            var cap=sources.original(basis).packet().capsule().value();
            parents.add(new MembershipCapsule.Anchor(object(cap.get("cut")),(String)cap.get("catalog"),(String)cap.get("application")));
        }
        original.verifyAncestry(ancestry,parents);return List.copyOf(parents);
    }
    /** Reserve every still-required endpoint, including the whole original selected set, before a new vote. */
    private void publicationCapacity(MembershipPendingAccept.Vote vote,AutomaticReplicationException.Outcome outcome)throws IOException {
        byte[] ancestry=current.ancestry();var parents=applicationParents(ancestry);String kind=(String)vote.entry().value().get("kind");
        if(learnerRetention!=null && learnerRetention.state().plan().preventsRetirement(kind,vote.payload()))
            throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,outcome,Optional.empty(),
                    "retained learner obligation prevents operation retirement",null);
        var renewed=MembershipCheckpointPlan.renewalParents(current.capsule,kind,parents,ancestry);
        int groups=MembershipCheckpointPlan.requiredBridges(current.capsule,kind,parents).size();
        int bytes=renewed.size()>5?MembershipSelectionCoverage.MAXIMUM+1:current.coverage().isPresent()
                ?MembershipRoundCoverage.publicationBytes(current.capsule,current.coverage().orElseThrow(),ancestry,vote.promise(),vote.selected(),renewed)
                :MembershipSelectionCoverage.publicationBytes(vote.selected(),current.capsule.terminal(),renewed);
        if(groups>6 || renewed.size()>5 || bytes>MembershipSelectionCoverage.MAXIMUM)
            throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,outcome,Optional.empty(),
                    "next publication ancestry/coverage capacity; retain original authority and complete maintenance before new work",null);
        if(!MembershipPublicationCapacity.admits(current.capsule,current.coverage().orElse(null),kind,vote.payload().length,groups))
            throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,outcome,Optional.empty(),
                    "next publication packet/envelope/generation capacity; retain original authority",null);
    }

    record Applied(MembershipCheckpointPlan plan,MembershipAppliedEndFiles.Completion completion) {
        MembershipAppliedEndFiles.Endorsement endorsement() {
            require(completion instanceof MembershipAppliedEndFiles.Endorsement,"nonvoting application has no endorsement");
            return (MembershipAppliedEndFiles.Endorsement)completion;
        }
        Optional<MembershipAppliedEndFiles.Endorsement> votingEnd() {
            return completion instanceof MembershipAppliedEndFiles.Endorsement end?Optional.of(end):Optional.empty();
        }
    }
    /** An exact native applied end, still distinct from a published generation.
     * The capability is local to this live owner. Its original records are inputs
     * for future durable retention, not a voting/installation receipt or dispatch
     * permission. Every access rechecks the original authority and complete end. */
    static final class PendingPublication {
        private final MembershipGrantJournal owner;
        private final Applied applied;
        private final MembershipPendingAccept.Vote vote;
        private final MembershipCapsule before;
        private PendingPublication(MembershipGrantJournal owner,Applied applied,MembershipPendingAccept.Vote vote) {
            this.owner=owner;this.applied=applied;this.vote=vote;this.before=owner.current.capsule;
        }
        private void check()throws IOException {
            owner.checkOwner();owner.applicationTransactionIdle();
            require(owner.ownedHistory && owner.current.capsule==before && owner.pendingAccept!=null && !owner.pendingAccept.pending()
                    && owner.pendingAccept.active()!=null && Arrays.equals(owner.pendingAccept.active().bytes(),vote.bytes()),
                    "pending publication original owner changed");
            require(owner.promise!=null && owner.selection!=null && Arrays.equals(owner.promise.bytes(),vote.promise().bytes())
                    && Arrays.equals(owner.selection.bytes(),vote.selected().bytes()) && Arrays.equals(owner.current.selector.bytes(),vote.selector().bytes()),
                    "pending publication original authority changed");
            owner.fence(object(vote.accept().value().get("ballot")));owner.verifyVote(vote);
            require(vote.certificate()!=null && Arrays.equals(vote.certificate().bytes(),applied.plan().originalCertificate().bytes())
                    && before.terminal().equals(applied.plan().originalParent()),"pending publication original application changed");
            require(owner.appliedEnd!=null && owner.replayFiles!=null && !owner.replayFiles.present(),"pending publication incomplete replay");
            owner.appliedEnd.completed(applied.plan(),vote.selector(),owner.identity,applied.completion());
        }
        MembershipCapsule.Anchor target()throws IOException {
            synchronized(owner) {
                check();var catalog=applied.plan().catalog;
                return new MembershipCapsule.Anchor(object(catalog.value().get("cut")),catalog.digest(),(String)catalog.value().get("application"));
            }
        }
        MembershipCapsule.Anchor parent()throws IOException {synchronized(owner){check();return before.terminal();}}
        MembershipIdentity owner()throws IOException {synchronized(owner){check();return owner.identity;}}
        /** Exact original records only, without an additional application image.
         * A caller cannot reconstruct this capability from these bytes. They do
         * not prove any peer received or installed the target. */
        Map<String,byte[]> originals()throws IOException {
            synchronized(owner) {
                check();var records=new TreeMap<String,byte[]>();
                records.put("selector.gsr",vote.selector().bytes());records.put("promise.gsr",vote.promise().bytes());
                records.put("selected.gsr",vote.selected().bytes());records.put("certificate.gsr",vote.certificate().bytes());
                records.put("catalog.gsr",applied.plan().catalog.bytes());records.put("statement.gsr",applied.plan().statement.bytes());
                applied.votingEnd().ifPresent(end->records.put("ack.gsr",end.acknowledgement().bytes()));return Collections.unmodifiableMap(records);
            }
        }
    }
    /** Only an actual completed native application can identify a future endpoint.
     * Taking this snapshot does not change any durable state or force a retention
     * ledger. Publication still requires its complete checkpoint quorum. */
    synchronized PendingPublication pendingPublication(Applied applied)throws IOException {
        checkOwner();applicationTransactionIdle();require(ownedHistory,"pending publication requires native owner");
        require(applied!=null && applied==nativeApplied,"pending publication requires this owner's completed native application");
        require(pendingAccept!=null && !pendingAccept.pending() && pendingAccept.active()!=null
                && pendingAccept.active().certificate()!=null,"pending publication requires complete original certificate");
        var target=new PendingPublication(this,Objects.requireNonNull(applied),pendingAccept.active());target.check();return target;
    }
    /** One original native application through exact publication. Unlike the
     * pending-only capability, this permits idempotent acknowledgement after the
     * selector changes, but never after another certificate/selection takes over. */
    final class Publication {
        private final MembershipGrantJournal owningJournal=MembershipGrantJournal.this;
        final Applied applied;
        final MembershipCapsule before;
        final MembershipCapsule.Anchor target;
        final Map<String,Object> ballot;
        final String selection,certificate;
        private final String requestView;
        private final Set<String> requestVoters;
        private final PendingPublication pending;
        private Publication(PendingPublication pending)throws IOException {
            this.pending=pending;applied=pending.applied;before=pending.before;target=pending.target();
            ballot=object(pending.vote.accept().value().get("ballot"));selection=pending.vote.selected().digest();
            certificate=pending.vote.certificate().digest();
            requestView=before.context.authority();requestVoters=Set.copyOf(before.context.voters());
        }
        private Publication()throws IOException {
            checkOwner();applicationTransactionIdle();require(ownedHistory,"published acknowledgement requires native history owner");
            certificate=current.publishedCertificate().orElseThrow(()->new IllegalArgumentException("no native completed publication"));
            var selected=current.selectedRecord().orElseThrow(()->new IllegalArgumentException("published original selection unavailable"));
            pending=null;applied=null;before=current.capsule;target=before.terminal();selection=selected.digest();
            ballot=object(selected.value().get("ballot"));requestView=(String)selected.value().get("view");
            var view=object(current.publishedParent().cut().get("view"));
            require(requestView.equals(MembershipContext.viewDigest(before.context.root,view)),"published original authority mismatch");
            var voters=new TreeSet<>(MembershipContext.nodes(view,"old"));voters.addAll(MembershipContext.nodes(view,"new"));requestVoters=Set.copyOf(voters);
            require(published(),"native publication no longer current");
        }
        boolean published()throws IOException {
            synchronized(MembershipGrantJournal.this) {
                checkOwner();fence(ballot);
                require(promise!=null && promise.value().get("ballot").equals(ballot)
                        && current.manifest.value().get("selection").equals(selection)
                        && current.manifest.value().get("promise").equals(promise.digest()),"publication scope authority changed");
                if(current.publishedCertificate().filter(certificate::equals).isPresent()) {
                    require(current.capsule.terminal().equals(target),"publication scope target changed");return true;
                }
                require(pending!=null,"published acknowledgement generation changed");pending.check();return false;
            }
        }
        void check()throws IOException {published();}
        List<MembershipSelection.Bridge> retainedBridges()throws IOException {
            synchronized(MembershipGrantJournal.this) {
                require(!published() && applied!=null,"retained publication ancestry requires pending original");
                var result=applied.plan().retainedBridges(current.ancestry());
                check();return result;
            }
        }
        void request(MembershipIdentity sender,Decoded request)throws IOException {
            synchronized(MembershipGrantJournal.this) {
                check();require(request.kind().equals("PUBLISH"),"publication request kind");var value=request.value();
                MembershipWire.envelope(request,before.context.root,sender,identity);
                require(value.get("view").equals(requestView) && value.get("ballot").equals(ballot)
                        && sender.equals(before.context.identities.get(sender.nodeId().value()))
                        && requestVoters.contains(sender.nodeId().value()) && requestVoters.contains(identity.nodeId().value()),
                        "publication request original authority/identities");
                require(sender.nodeId().value().equals(ballot.get("proposer"))
                        && object(value.get("payload")).get("certificate").equals(certificate),"publication request original proposer/certificate");
            }
        }
        Decoded acknowledge(MembershipIdentity sender,Decoded request)throws IOException {
            synchronized(MembershipGrantJournal.this) {
                request(sender,request);require(published(),"publication acknowledgement before selector");
                cut.at("PUBLICATION_ACK_BEFORE_RETURN");request(sender,request);require(published(),"publication acknowledgement lost selector");
                var response=new TreeMap<>(request.value());response.put("sender",request.value().get("recipient"));response.put("recipient",request.value().get("sender"));
                response.put("payload",Map.of("certificate",certificate,"selection",selection,
                        "published",MembershipRetentionIntent.anchor(target),"generation",current.manifest.digest()));
                return decode(encode("wire","PUBLISH_ACK",response),"wire","PUBLISH_ACK");
            }
        }
    }
    synchronized Publication publication(Applied applied)throws IOException {return new Publication(pendingPublication(applied));}
    /** No new application, vote or publication. Reopen must first finish native
     * covered staging/retention recovery; only the exact current original can ACK. */
    synchronized Decoded acknowledgePublished(MembershipIdentity sender,Decoded request)throws IOException {
        return new Publication().acknowledge(sender,request);
    }
    /** A capability for one complete, re-forced native certificate. It carries no
     * fresh remote observations and never advances the published cut. */
    static final class CertifiedCurrent {
        private final MembershipGrantJournal owner;
        private final MembershipPendingAccept.Vote vote;
        private CertifiedCurrent(MembershipGrantJournal owner,MembershipPendingAccept.Vote vote){this.owner=owner;this.vote=vote;}
        Decoded certificate(){return vote.certificate();}
        void check(MembershipCapsule before,MembershipSourcePacket packet)throws IOException {
            synchronized(owner) {
                owner.checkOwner();owner.applicationTransactionIdle();
                require(owner.ownedHistory && owner.pendingAccept!=null && !owner.pendingAccept.pending()
                        && owner.pendingAccept.active()!=null && Arrays.equals(owner.pendingAccept.active().bytes(),vote.bytes()),
                        "native application certificate no longer owned");
                require(owner.promise!=null && owner.selection!=null && Arrays.equals(owner.promise.bytes(),vote.promise().bytes())
                        && Arrays.equals(owner.selection.bytes(),vote.selected().bytes()) && Arrays.equals(owner.current.selector.bytes(),vote.selector().bytes()),
                        "native application original authority changed");
                owner.fence(object(vote.accept().value().get("ballot")));owner.verifyVote(vote);
                require(before==owner.current.capsule && Arrays.equals(packet.bytes(),owner.votePacket().bytes()),
                        "native application substituted original history");
            }
        }
    }
    private CertifiedCurrent currentApplicationProof()throws IOException {
        require(ownedHistory,"native application requires original history owner");
        var vote=pendingAccept.active();require(vote!=null && vote.certificate()!=null,"native application requires complete certificate");
        var proof=new CertifiedCurrent(this,vote);var before=current.capsule;var packet=votePacket();
        MembershipGenerationFiles.Guard guard=()->proof.check(before,packet);
        guard.check();pendingAccept.sealActive(guard,cut);cut.at("NATIVE_CERTIFICATE_RETAINED");guard.check();return proof;
    }
    /** A cleanup-only original certificate, scoped to this owner and exact
     * retained generation. It does not revive the original ballot's authority. */
    static final class CertifiedRetirement {
        private final MembershipGrantJournal owner;
        private final MembershipPendingAccept.Vote vote;
        private final MembershipFloor.Copy original;
        private final MembershipSourcePacket packet;
        private final MembershipGenerationFiles.Guard guard;
        private CertifiedRetirement(MembershipGrantJournal owner,MembershipPendingAccept.Vote vote,
                MembershipFloor.Copy original,MembershipSourcePacket packet,MembershipGenerationFiles.Guard guard) {
            this.owner=owner;this.vote=vote;this.original=original;this.packet=packet;this.guard=guard;
        }
        Decoded certificate(){return vote.certificate();}
        void check(MembershipCapsule before,MembershipSourcePacket supplied)throws IOException {
            synchronized(owner) {
                require(owner.ownedHistory,"native retirement requires original history owner");guard.check();
                require(owner.pendingAccept.active()!=null && Arrays.equals(owner.pendingAccept.active().bytes(),vote.bytes()),
                        "native retirement certificate no longer owned");
                owner.verifyVote(vote);original.check();
                require(before==original.capsule && Arrays.equals(supplied.bytes(),packet.bytes()),"native retirement substituted original history");
            }
        }
    }
    /** Retire only derived work from a fenced certificate. The newer installed selection
     * must retain that exact logical entry at the identical parent; voting originals survive.
     * This method never forces or returns an old application ACK. A later volatile
     * observation still fences voting, but cannot revoke this exact cleanup authority. */
    synchronized <K,T> void retireSupersededApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations)throws IOException {
        retireSupersededApplication(configuration,storage,observations,false);
    }
    synchronized <K,T> void retireSupersededApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage)throws IOException {
        require(ownedHistory,"native retirement requires original history owner");retireSupersededApplication(configuration,storage,Set.of(),true);
    }
    private <K,T> void retireSupersededApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations,boolean nativeOriginal)throws IOException {
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
        retireApplication(configuration,storage,observations,vote,originals,old,local,Map.of(),null,new byte[0],nativeOriginal);
    }
    /** Retire only old derived staging before installing an authenticated covering
     * prefix. The current selector and original certified vote remain unchanged;
     * typed replay must match an authenticated endpoint of the selected prefix. */
    synchronized <K,T> void retireCoveredApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations,
            List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges,
            List<MembershipSelection.Bridge> retainedBridges,Map<String,byte[]> images)throws IOException {
        retireCoveredApplication(configuration,storage,observations,offered,bridges,retainedBridges,images,List.of());
    }
    /** A hidden applied endpoint may have one additional authenticated RANGE proof.
     * This proof authorizes derived cleanup only, never selection or installation.
     * The retirement marker pins its exact bytes across repeated interruptions. */
    synchronized <K,T> void retireCoveredApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations,
            List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges,
            List<MembershipSelection.Bridge> retainedBridges,Map<String,byte[]> images,List<MembershipSelection.Bridge> appliedBridges)throws IOException {
        retireCoveredApplication(configuration,storage,observations,offered,bridges,retainedBridges,images,appliedBridges,false);
    }
    synchronized <K,T> void retireCoveredApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,
            List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges,
            List<MembershipSelection.Bridge> retainedBridges,Map<String,byte[]> images,List<MembershipSelection.Bridge> appliedBridges)throws IOException {
        require(ownedHistory,"native retirement requires original history owner");
        retireCoveredApplication(configuration,storage,Set.of(),offered,bridges,retainedBridges,images,appliedBridges,true);
    }
    private <K,T> void retireCoveredApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations,
            List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges,
            List<MembershipSelection.Bridge> retainedBridges,Map<String,byte[]> images,List<MembershipSelection.Bridge> appliedBridges,boolean nativeOriginal)throws IOException {
        require(appliedBridges.size()<=1,"covered staging applied ancestry count");
        require(appliedEnd!=null && replayFiles!=null,"application storage owner required");checkOwner();otherApplicationTransactionsIdle();
        require(selection!=null && !inactive.pending() && !pendingAccept.pending(),"covered staging requires completed original authorities");
        var vote=pendingAccept.active();require(vote!=null && vote.certificate()!=null
                && Arrays.equals(vote.selector().bytes(),current.selector.bytes()),"covered staging requires current original certificate");
        require(pendingContext==null || pendingContext.active().isEmpty() && !pendingContext.pending(),"covered staging conflicts with protected context");
        verifyVote(vote);var originals=current.copyFiles();var old=originalGeneration(originals);
        var selected=verifyDecision(offered,bridges);require(Arrays.equals(selection.bytes(),selected.selected().bytes()),"installation differs from original selection");
        var plan=installationPlan(selected,bridges,retainedBridges,images,false);
        verifySettlementAuthority(vote,originals,plan.verifiedMaterialization(),plan.files);
        var authority=new TreeMap<String,Object>(Map.of("mode","covered-prefix","coveringGeneration",plan.manifest.digest(),"coveringSelector",plan.selector.digest()));
        byte[] ancestry=plan.files.getOrDefault("ancestry.gsr",new byte[0]);
        if(!appliedBridges.isEmpty()) {
            var proof=appliedBridges.getFirst();var statement=proof.statement.value();var start=object(statement.get("start"));
            var covering=selected.longest().capsule;
            require(start.get("index").equals(vote.entry().value().get("index")) && start.get("entry").equals(vote.entry().digest())
                    && covering.anchor(number(start.get("index")))==null && !covering.ancestryAnchors(ancestry).containsKey(start),
                    "covered staging unused or changed applied endpoint");
            proof.verify(covering,new MembershipCapsule.Anchor(start,(String)statement.get("catalogBefore"),(String)statement.get("applicationBefore")));
            byte[] extra=MembershipGenerationPlan.ancestry(appliedBridges);var combined=new java.io.ByteArrayOutputStream();combined.writeBytes(ancestry);combined.writeBytes(extra);
            ancestry=combined.toByteArray();covering.ancestryAnchors(ancestry); // unchanged total count, bytes and ownership bounds
            authority.put("appliedAncestry",hash(extra));
        }
        retireApplication(configuration,storage,observations,vote,originals,old,originalSource(),authority,
                selected.longest().capsule,ancestry,nativeOriginal);
    }
    private <K,T> void retireApplication(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations,
            MembershipPendingAccept.Vote vote,Map<String,byte[]> originals,MembershipFloor.Copy old,MembershipSelection.Source local,
            Map<String,Object> extraAuthority,MembershipCapsule covering,byte[] coveringAncestry,boolean nativeOriginal)throws IOException {
        require(observations.size()<=12,"application phased observation count");var owned=Set.copyOf(observations);
        var packet=MembershipPendingAccept.packet(old.capsule.packet,vote);var images=new TreeMap<String,byte[]>();
        for(String h:old.capsule.packet.images().keySet())images.put(h,originals.get(h+".image"));
        var rootRecord=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        if(!nativeOriginal) {
            var verified=Objects.requireNonNull(capsuleVerifier.verify(rootRecord,packet,images));
            require(Arrays.equals(verified.packet.bytes(),packet.bytes()),"staged retirement verifier substituted original packet");
            verified.context.certificate(vote.certificate(),owned);
        }
        byte[] ancestry=originals.getOrDefault("ancestry.gsr",new byte[0]);
        var parents=applicationParents(old.capsule,originals.get(MembershipSelectedSources.FILE),originals.get(MembershipSelectionCoverage.FILE),ancestry,vote.promise(),vote.selected());
        var authority=new TreeMap<String,Object>(extraAuthority);authority.put("pending",hash(vote.bytes()));authority.put("oldGeneration",old.generation.digest());
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
            var proof=nativeOriginal?new CertifiedRetirement(this,vote,old,packet,guard):null;
            if(proof!=null) {
                proof.check(old.capsule,packet);pendingAccept.sealActive(guard,cut);
                cut.at("NATIVE_RETIREMENT_CERTIFICATE_RETAINED");proof.check(old.capsule,packet);
            }
            cut.at("STAGED_RETIREMENT_AUTHORITY_VALIDATED");guard.check();
            var plan=replayFiles.executeRetained(vote.selector(),vote.certificate(),identity,work->nativeOriginal?
                    MembershipCheckpointPlan.replayRetirement(configuration,storage,old.capsule,packet,images,proof,work):
                    MembershipCheckpointPlan.replay(configuration,storage,old.capsule,packet,vote.certificate(),images,owned,work),guard,cut).renewAncestors(parents,ancestry);
            if(proof!=null)proof.check(old.capsule,packet);
            if(covering!=null) {
                var statement=plan.statement.value();covering.verifyAncestry(coveringAncestry,List.of(new MembershipCapsule.Anchor(
                        object(statement.get("end")),(String)statement.get("catalogAfter"),(String)statement.get("applicationAfter"))));
            }
            guard.check();appliedEnd.retireSuperseded(plan,vote.selector(),identity,authority,guard,cut);
            guard.check();replayFiles.releaseCompletion();cut.at("STAGED_RETIREMENT_BEFORE_RETURN");guard.check();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    /** Real local certificate + typed replay + forced end. This is not selector publication or public readiness. */
    synchronized <K,T> Applied applyCurrent(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations)throws IOException {
        return applyCurrent(configuration,storage,observations,false);
    }
    /** Recover from the exact native forced certificate, including after process
     * restart. Only the newly forced local applied end creates a new observation. */
    synchronized <K,T> Applied applyCurrent(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage)throws IOException {
        require(ownedHistory,"native application requires original history owner");
        return applyCurrent(configuration,storage,Set.of(),true);
    }
    private <K,T> Applied applyCurrent(io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Set<Owned> observations,boolean nativeOriginal)throws IOException {
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
        guard.check();var packet=votePacket();
        if(!nativeOriginal)verifiedPacket(packet).context.certificate(vote.certificate(),owned);
        publicationCapacity(vote,AutomaticReplicationException.Outcome.INDETERMINATE);
        byte[] ancestry=current.ancestry();var parents=applicationParents(ancestry);
        AdmissionPaths.disjoint(List.of(directory,storage.directory()));reserveApplicationCompletion();
        try {
            var proof=nativeOriginal?currentApplicationProof():null;
            cut.at("APPLICATION_AUTHORITY_VALIDATED");guard.check();
            var plan=replayFiles.executeRetained(vote.selector(),vote.certificate(),identity,work->nativeOriginal?
                    MembershipCheckpointPlan.replayStored(configuration,storage,current.capsule,packet,current.images(),proof,work):
                    MembershipCheckpointPlan.replay(configuration,storage,current.capsule,packet,vote.certificate(),current.images(),owned,work),guard,cut);
            if(proof!=null)proof.check(current.capsule,packet);
            plan=plan.renewAncestors(parents,ancestry);
            guard.check();var endorsement=appliedEnd.forceCompletion(plan,vote.selector(),identity,guard,cut);
            guard.check();var applied=new Applied(plan,endorsement);if(nativeOriginal)nativeApplied=applied;return applied;
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
            appliedEnd.completed(applied.plan(),vote.selector(),identity,applied.completion());require(!replayFiles.present(),"publication replay scratch must be removed");
        }
        var bound=object(originalPromise.value().get("ballot"));fence(bound);
        var plan=MembershipGenerationPlan.published(root,identity,installed?current.generation:inactive.slot(),originalPromise,originalBasis,originalSelection,
                applied.plan(),acknowledgements,checkpoints,bridges,current.selectedSources().orElse(null),current.capsule,current.coverage().orElse(null),current.ancestry());
        if(peerRetention!=null) {
            MembershipFutureRetentionCompletion completion=installed?inheritedFutureCompletion():null;
            if(!installed) {
                var retained=selectedRetentionIntent();
                if(retained!=null && !retained.futures().isEmpty())completion=MembershipFutureRetentionCompletion.create(retained,peerRetention.activeBytes(),plan.verifiedMaterialization(),plan.files.getOrDefault("ancestry.gsr",new byte[0]),identity);
            }
            if(completion!=null)plan=plan.retainingFutureCompletion(completion);
        }
        var parents=new ArrayList<MembershipCapsule.Anchor>();parents.add(applied.plan().originalParent());addFloorParent(parents);
        for(var original:bases.values()) {
            var cap=sources.original(original).packet().capsule().value();parents.add(new MembershipCapsule.Anchor(object(cap.get("cut")),(String)cap.get("catalog"),(String)cap.get("application")));
        }
        verifyPlan(plan,parents);checkOwner();fence(bound);
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
            completeInheritedFutureRetention();
            completeFutureRetention();
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
        if(peerRetention!=null)peerRetention.check();
        if(learnerRetention!=null)learnerRetention.check();
        if(futureRetention!=null)futureRetention.check();
        if(appliedEnd!=null)appliedEnd.check();
        if(replayFiles!=null)replayFiles.check();
    }
    private void checkWithoutFloor() throws IOException {
        checkBaseOwner();
        if(current!=null)current.check();
        if(inactive!=null)inactive.check();
        if(current!=null && peerRetention!=null && peerRetention.initialized()) {
            peerRetention.state().plan().required(current.capsule,current.ancestry());
            var intent=selectedRetentionIntent();
            require(intent==null || !intent.needsCompletion(peerRetention.state()),"selected retention completion required");
        }
        if(current!=null && learnerRetention!=null && learnerRetention.initialized())
            learnerRetention.state().plan().required(current.capsule,current.ancestry());
        if(current!=null && futureRetention!=null && futureRetention.initialized())verifyFutureRetention();
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
    /** Read-only admission hint; deletion still requires complete governing copies. */
    synchronized boolean nativeGenerationMaintenanceRequired()throws IOException {
        require(ownedHistory && inactive!=null && retirement!=null && floors!=null,"native generation maintenance owner required");
        checkOwner();require(!inactive.pending() && !retirement.pending() && !floors.pending(),"native maintenance requires recovered storage");
        return inactive.exists() || floors.exists();
    }
    /** A completed publication can require retirement before another grant adds
     * a source or installs a generation. Pending votes/applications retain their
     * existing carried-entry path; they cannot borrow this permission. */
    synchronized boolean publishedMaintenanceRequired()throws IOException {
        if(!nativeGenerationMaintenanceRequired())return false;
        return (pendingAccept==null || !pendingAccept.pending() && pendingAccept.active()==null)
                && (pendingContext==null || !pendingContext.pending() && pendingContext.active().isEmpty())
                && (appliedEnd==null || !appliedEnd.present() && !replayFiles.present());
    }
    final class PublishedMaintenance {
        private final MembershipGrantJournal owningJournal=MembershipGrantJournal.this;
        private final MembershipCurrentGeneration generation=current;
        private final String originalPromise=promise==null?null:promise.digest(),originalSelection=selection==null?null:selection.digest();
        final MembershipContext context=current.capsule.context;
        final Map<String,Object> ballot=Map.copyOf(observed.get());
        private PublishedMaintenance() { }
        void check()throws IOException {
            synchronized(MembershipGrantJournal.this) {
                checkOwner();applicationReferencesIdle();contextTransactionIdle();
                require(current==generation && Objects.equals(originalPromise,promise==null?null:promise.digest())
                        && Objects.equals(originalSelection,selection==null?null:selection.digest()),
                        "published maintenance authority changed");
                require(pendingAccept==null || !pendingAccept.pending() && pendingAccept.active()==null,
                        "published maintenance cannot retire pending vote");
                fence(ballot);
            }
        }
    }
    synchronized PublishedMaintenance publishedMaintenance(MembershipResources budget)throws IOException {
        require(resources==budget && publishedMaintenanceRequired(),"published maintenance requires clean owned generation");
        rotationIdle();applicationReferencesIdle();reconcileKnownPeerConfiguration();
        var permit=new PublishedMaintenance();permit.check();return permit;
    }
    /** Candidates are only older durable promises that neither the current
     * generation nor its governing floor references. The existing retirement
     * planner must still prove exact ancestry/tail preservation for each one. */
    synchronized List<String> supersededPublishedSources(PublishedMaintenance permit)throws IOException {
        require(permit.owningJournal==this,"published maintenance foreign owner");
        permit.check();require(!inactive.exists() && !inactive.pending(),"published sources require retired inactive generation");
        var floor=floors.retained().orElseThrow(()->new IllegalArgumentException("published sources require governing floor"));
        var local=floor.copies().stream().filter(c->c.owner.equals(identity)).findFirst().orElseThrow();
        var result=new ArrayList<String>();
        for(String id:new TreeSet<>(sources.retainedIdentities())) {
            var original=promises.get(id);require(original!=null,"published source original promise missing");
            var originalBasis=bases.get(id);
            if(compareBallot(object(promise.value().get("ballot")),object(original.value().get("ballot")))<=0)continue;
            if(original.digest().equals(current.manifest.value().get("promise")) || original.digest().equals(local.generation.value().get("promise")))continue;
            if(originalBasis!=null && (originalBasis.digest().equals(current.manifest.value().get("basis"))
                    || originalBasis.digest().equals(local.generation.value().get("basis"))))continue;
            planSourceRetirement(id);result.add(id);
        }
        permit.check();return List.copyOf(result);
    }
    synchronized Decoded establishFloor(List<MembershipFloor.Copy> offered) throws IOException {
        return establishFloor(offered,null);
    }
    synchronized Decoded establishFloor(List<MembershipFloor.Copy> offered,MembershipFloorFiles.Handoff handoff) throws IOException {
        require(floors!=null,"floor storage owner required");checkOwner();applicationReferencesIdle();rotationIdle();
        if(retirement!=null)require(!retirement.pending(),"pending retirement must finish before authority changes");var own=floorCopyCurrent();
        return establishFloor(own,offered,handoff);
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
        return establishFloor(own,offered,null);
    }
    private Decoded establishFloor(MembershipFloor.Copy own,List<MembershipFloor.Copy> offered,MembershipFloorFiles.Handoff handoff)throws IOException {
        // Validate and reserve before any persistent change; an interrupted transaction
        // may only resume with the same original full copies.
        try{
            // Empty replay scratch is disposable capacity. A floor needs real copies
            // before it may retire the old generation; it must not count those copies
            // on top of unused replay/end buffers. Existing application files pin them.
            if(replayFiles!=null && pendingAccept.active()!=null) {
                replayFiles.releaseCompletion();appliedEnd.releaseEmptyCompletion();
            }
            return floors.establish(own,offered,this::checkWithoutFloor,cut,handoff);
        }
        catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    private MembershipFloor.Copy originalGeneration(Map<String,byte[]> files) throws IOException {
        require(files.containsKey("generation.gsr") && files.containsKey("source.gscp"),"complete retirement source required");
        var manifest=decode(files.get("generation.gsr"),"records","GENERATION");var packet=MembershipSourcePacket.decode(files.get("source.gscp"));
        var images=new TreeMap<String,byte[]>();packet.images().keySet().forEach(h->images.put(h,files.get(h+".image")));
        var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        MembershipCapsule capsule;
        if(ownedHistory && retirement!=null && retirement.authority().isPresent()
                && Arrays.equals(retirement.original().get("generation.gsr"),manifest.bytes())) {
            var original=retirement.original();require(original.keySet().equals(files.keySet())
                    && original.entrySet().stream().allMatch(e->Arrays.equals(e.getValue(),files.get(e.getKey()))),"retirement original bytes substituted");
            capsule=retirement.verifiedOriginal(new HistoryRead(this));
        }else if(ownedHistory && inactive!=null && inactive.exists() && !inactive.pending()
                && Arrays.equals(inactive.originalFiles().get("generation.gsr"),manifest.bytes())) {
            // Two generations may share the same proven cut but retain different original
            // coverage/ancestry. Resolve the exact owning generation before prefix reuse.
            var original=inactive.originalFiles();require(original.keySet().equals(files.keySet())
                    && original.entrySet().stream().allMatch(e->Arrays.equals(e.getValue(),files.get(e.getKey()))),"inactive original bytes substituted");
            capsule=inactive.verifiedOriginal(new HistoryRead(this));
        }else capsule=Objects.requireNonNull(capsuleVerifier.verify(localRoot,packet,images));
        require(Arrays.equals(capsule.packet.bytes(),packet.bytes()),"retirement verifier substituted source");
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
    private MembershipPendingAccept.Vote retirementSuccessor()throws IOException {
        var vote=pendingAccept==null?null:pendingAccept.active();
        if(vote!=null) {require(!pendingAccept.pending(),"retirement successor must be complete");verifyVote(vote);}
        return vote;
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
                var plan=MembershipRetirementPlan.create(root,identity,current,floor,original,retirementContext(),retirementSuccessor());
                inactive.forceOriginal(cut);checkOwner();retirement.prepare(plan,this::checkWithoutRetirement,cut);record=plan.record;
            }else {
                record=saved.get();bindRetirement(record,floor);retirement.checkSaved(record);
                if(inactive.exists()) {
                    var original=originalGeneration(retirement.original());var plan=MembershipRetirementPlan.create(root,identity,current,floor,original,retirementContext(),retirementSuccessor());
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
    /** A proposed/unforced successor cannot authorize deletion. Every plan and
     * resumed decision rechecks the same physically loaded current vote. */
    private MembershipPendingAccept.Vote sourceRetirementSuccessor()throws IOException {
        var vote=pendingAccept==null || pendingAccept.pending()?null:pendingAccept.active();
        if(vote==null || !Arrays.equals(vote.selector().bytes(),current.selector.bytes()))return null;
        verifyVote(vote);return vote;
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
        var plan=MembershipSourceRetirementPlan.create(root,identity,current,retained,promise,promises.get(id),originalBasis,capsule,original.images(),retirementContext(),sourceRetirementSuccessor());
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
        expireSourceExports();require(sourceExports.stream().noneMatch(export->export.pinsSource(id)),"source export pins original files");
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
            decision.bind(root,identity,current,retained,promise,retirementContext(),sourceRetirementSuccessor());sourceRetirement.publish(decision,this::checkOwner,cut);
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
            decision.bind(root,identity,current,retained,promise,retirementContext(),sourceRetirementSuccessor());checkOwner();cut.at("SOURCE_RETIREMENT_JOURNAL_PRUNED");checkOwner();
            sources.deleteRetired(decision,this::checkOwner,cut);require(!sources.retainedIdentities().contains(id),"source retirement still owns original files");
            sources.releaseRetiredLeases(id);
            decision.bind(root,identity,current,retained,promise,retirementContext(),sourceRetirementSuccessor());sourceRetirement.clear(this::checkOwner,cut);cut.at("SOURCE_RETIREMENT_BEFORE_RETURN");checkOwner();return decision.record();
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
        require(learnerRetention==null || learnerRetention.state().plan().empty(),"learner retention frozen-source propagation unavailable");
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
        current.capsule.context.ballot(incoming,true);reconcileKnownPeerConfiguration();
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
    /** Phase 3's private controller shares this writer; no caller-assigned ballot or source. */
    synchronized MembershipSelection.Source beginActivation() throws IOException {
        require(current!=null,"current generation required");checkOwner();
        require(identity.equals(current.capsule.context.identities.get(identity.nodeId().value()))
                && current.capsule.context.voters().contains(identity.nodeId().value()),"activation requires current voter");
        long counter=reserveCounter();
        prepareCurrent(Map.of("counter",counter,"proposer",identity.nodeId().value(),"incarnation",identity.storageId().toString()));
        return originalSource();
    }
    MembershipIdentity activationIdentity() {return identity;}
    synchronized MembershipScratch openScratch(Path path,MembershipScratch.Role role,MembershipResources budget,MembershipScratch.Events events)throws IOException {
        require(current!=null && resources==budget,"scratch requires actual storage resource owner");checkOwner();allocator.checkScratchPath(path);
        return MembershipScratch.open(path,root.manifestDigest(),identity,role,budget,()->{synchronized(this){checkOwner();allocator.checkScratchPath(path);}},events);
    }
    synchronized MembershipContext activationContext() throws IOException {
        require(current!=null,"current generation required");checkOwner();return current.capsule.context;
    }
    record DiscoveryState(MembershipContext context,Map<String,Object> ballot) {}
    /** Reuse the actual observed root fence for correlation; discovery must not
     * allocate a new ballot or require its own PREPARE before finding a newer view. */
    synchronized DiscoveryState discoveryState(MembershipResources budget)throws IOException {
        require(current!=null && resources==budget,"discovery requires actual storage resource owner");checkOwner();
        var bound=observed.get();require(bound!=null,"discovery requires initialized root fence");
        return new DiscoveryState(current.capsule.context,Map.copyOf(bound));
    }
    /** Read the actual forced current cut without allocating a ballot or granting a
     * vote. Cross-view discovery must not use current-voter wire admission. */
    synchronized Decoded discoveryStatus(MembershipIdentity sender,Decoded request)throws IOException {
        require(current!=null,"current generation required");checkOwner();
        var reply=MembershipDiscovery.answer(current.capsule.context,identity,sender,request);checkOwner();return reply;
    }
    synchronized MembershipCapsule activationCapsule() throws IOException {
        require(current!=null,"current generation required");checkOwner();return current.capsule;
    }
    /** Authenticate a current-view proposer before observing its ballot. This does
     * not wait for the writer monitor and cannot grant or install anything. */
    void observeActivation(MembershipIdentity sender,Decoded request) {
        live();var generation=current;require(generation!=null,"current generation required");
        var context=MembershipActivation.incoming(generation.capsule.context,identity,sender,request,"PREPARE");
        observe(context,object(request.value().get("ballot")));
    }
    synchronized void checkActivationBallot(String view,Map<String,Object> ballot)throws IOException {
        require(current!=null && current.capsule.context.authority().equals(view),"activation view changed");checkOwner();fence(ballot);
    }
    /** Volatile replies cannot outlive the exact live owner, grant, view or installed selection. */
    synchronized void checkActivation(Decoded original,Decoded selected,boolean installed) throws IOException {
        require(current!=null && promise!=null && basis!=null,"activation grant unavailable");checkOwner();
        require(Arrays.equals(original.bytes(),basis.bytes()) && original.value().get("ballot").equals(promise.value().get("ballot"))
                && original.value().get("view").equals(current.capsule.context.authority()),"activation grant/view changed");
        fence(object(original.value().get("ballot")));
        if(selected!=null)require(selection!=null && Arrays.equals(selected.bytes(),selection.bytes()),"activation selection changed");
        if(installed)require(selected!=null && selected.digest().equals(current.manifest.value().get("selection"))
                && selected.value().get("cut").equals(current.manifest.value().get("cut")),"activation not locally installed");
    }
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
        require(current!=null && inactive!=null,"generation owner required");checkOwner();
        var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var incoming=Objects.requireNonNull(capsuleVerifier.verify(localRoot,packet,images));
        require(Arrays.equals(incoming.packet.bytes(),packet.bytes()),"adoption verifier substituted source");
        return fenceMembershipPrefix(incoming,images,bridges);
    }
    /** Accept only an already authenticated complete history; raw incoming bytes still
     * require the original verifier. Historical proof never supplies a fresh vote. */
    synchronized Decoded fenceMembershipPrefix(MembershipCapsule incoming,Map<String,byte[]> images,List<MembershipSelection.Bridge> bridges) throws IOException {
        require(pendingAccept==null || pendingAccept.active()==null,"pending ACCEPT requires covered-prefix publication before adoption");
        require(current!=null && inactive!=null,"generation owner required");checkOwner();rotationIdle();
        require(!inactive.pending() && !(inactive.exists() && !current.adopted && current.manifest.value().get("selection")==null)
                && !inactive.incompleteOrSelected(selection==null?null:selection.digest(),number(current.capsule.context.cut.get("index"))),"pending generation installation must finish before adoption");floorIdle();
        checkIncomingHistory(incoming,images);
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
        require(current!=null && inactive!=null,"generation owner required");checkOwner();
        var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var incoming=Objects.requireNonNull(capsuleVerifier.verify(localRoot,packet,images));
        require(Arrays.equals(incoming.packet.bytes(),packet.bytes()),"adoption verifier substituted source");
        return adoptCurrent(incoming,images,bridges);
    }
    /** Native adoption receives a typed proof from complete verified local or network
     * history. It preserves all local ancestry, tail, fence and install obligations. */
    synchronized Decoded adoptCurrent(MembershipCapsule incoming,Map<String,byte[]> images,List<MembershipSelection.Bridge> bridges) throws IOException {
        require(pendingAccept==null || pendingAccept.active()==null,"pending ACCEPT requires covered-prefix publication before adoption");
        require(current!=null && inactive!=null,"generation owner required");checkOwner();floorIdle();
        checkIncomingHistory(incoming,images);var packet=incoming.packet;
        var ancestors=new ArrayList<MembershipCapsule.Anchor>();ancestors.add(current.capsule.terminal());addFloorParent(ancestors);
        if(peerRetention!=null)ancestors.addAll(peerRetention.state().plan().required(current.capsule,current.ancestry()));
        if(learnerRetention!=null)ancestors.addAll(learnerRetention.state().plan().required(current.capsule,current.ancestry()));
        for(var original:bases.values()) {
            var cap=sources.original(original).packet().capsule().value();
            ancestors.add(new MembershipCapsule.Anchor(object(cap.get("cut")),(String)cap.get("catalog"),(String)cap.get("application")));
        }
        if(futurePending()) {
            ancestors.add(futureRetention.state().target());
            futureRetention.state().peers.forEach(peer->ancestors.add(peer.lower()));
        }
        incoming.verifyAncestry(MembershipGenerationPlan.ancestry(bridges),ancestors);
        if(learnerRetention!=null)learnerRetention.state().plan().required(incoming,MembershipGenerationPlan.ancestry(bridges));
        var certificate=incoming.membershipCertificateFence().orElseThrow(()->new IllegalArgumentException("no authenticated membership certificate fence"));
        if(current.adopted && current.capsule.sameProvenPrefix(packet)) {
            var saved=decode(AdmissionPaths.read(directory.resolve("generations").resolve(current.generation).resolve("promise.gsr"),8192),"records","PROMISE");
            var duplicate=MembershipGenerationPlan.adopted(root,identity,current.generation,saved,incoming,bridges,images);
            var completion=inheritedFutureCompletion();if(completion!=null)duplicate=duplicate.retainingFutureCompletion(completion);
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
        var retained=selectedRetentionIntent();
        if(retained!=null && !retained.futures().isEmpty())plan=plan.retainingFutureCompletion(
                MembershipFutureRetentionCompletion.create(retained,peerRetention.activeBytes(),incoming,MembershipGenerationPlan.ancestry(bridges),identity));
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
            reloadGenerations();completeInheritedFutureRetention();completeFutureRetention();cut.at("ADOPTION_INSTALL_BEFORE_RETURN");checkOwner();fence(bound);return current.manifest;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    private void checkIncomingHistory(MembershipCapsule incoming,Map<String,byte[]> images)throws IOException {
        Objects.requireNonNull(incoming);
        var localRoot=AdmissionPaths.read(directory.resolve("root.gsr"),16384);
        require(incoming.context.root.equals(root.manifestDigest())
                && Arrays.equals(localRoot,incoming.packet.objectBytes(incoming.context.recordRootDigest())),"adoption historical root differs");
        incoming.packet.verifyImages(images);
    }
    /** Observation of this owner's forced original grant, not an assertion of remote force. */
    synchronized MembershipSelection.Source originalSource() throws IOException {
        require(current!=null && basis!=null,"complete current grant required");checkOwner();
        return retainedSource(basis);
    }
    /** The active original grant may reuse only its actual selected prefix's ancestry. */
    synchronized List<MembershipSelection.Bridge> activationAncestry(Decoded original)throws IOException {
        checkActivation(original,null,false);var source=originalSource();current.check();
        require(current.capsule.sameProvenPrefix(source.capsule.packet),"activation ancestry original prefix changed");
        var bridges=current.capsule.verifiedAncestry(current.ancestry());
        // The native source reader must have retained the exact original historical keys.
        source.capsule.retainingVerifiedAncestry(bridges);current.check();checkActivation(original,null,false);
        return List.copyOf(bridges);
    }
    /** Read-only transfer authority for an exact forced retained BASIS. A higher grant may
     * coexist with this borrow; it cannot change these originals or renew its deadline. */
    synchronized MembershipSourceExport exportSource(Decoded original,long budget)throws IOException {
        return exportSource(original,System::nanoTime,budget);
    }
    synchronized MembershipSourceExport exportSource(Decoded original,LongSupplier clock,long budget)throws IOException {
        return exportSource(original,clock,Objects.requireNonNull(clock).getAsLong(),budget);
    }
    private MembershipSourceExport exportSource(Decoded original,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"source export time budget");
        require(current!=null && sources!=null && resources!=null,"source export storage owner required");
        checkOwner();sourceIdle();expireSourceExports();require(sourceExports.size()<6,"source export owner capacity");
        require(original.family().equals("records") && original.kind().equals("BASIS"),"source export requires BASIS");
        String id=(String)original.value().get("basisId");var exact=bases.get(id);var granted=promises.get(id);
        require(exact!=null && granted!=null && Arrays.equals(exact.bytes(),original.bytes()),"source export original basis absent/changed");
        var source=retainedSource(exact);
        var export=new MembershipSourceExport(this,directory.resolve(MembershipBasisSources.DIRECTORY).resolve(id),source,granted,resources,clock,started,budget);
        sourceExports.add(export);
        try {checkSourceExport(export);return export;}
        catch(IOException|RuntimeException|Error error){releaseSourceExport(export);throw error;}
    }
    private void expireSourceExports(){for(var export:List.copyOf(sourceExports))if(export.expired())releaseSourceExport(export);}
    synchronized void checkSourceExport(MembershipSourceExport export)throws IOException {
        expireSourceExports();require(sourceExports.contains(export),"source export closed/expired");checkOwner();
        expireSourceExports();require(sourceExports.contains(export),"source export closed/expired");
    }
    synchronized void releaseSourceExport(MembershipSourceExport export){sourceExports.remove(export);export.revoke();}
    /** Reuse exact already-accounted local images without exporting their old authority.
     * The existing borrow pins each backing original against retirement until expiry/close. */
    synchronized boolean pinSourceImage(MembershipSourceExport export,String digest,long bytes)throws IOException {
        checkSourceExport(export);sourceIdle();
        for(String id:new TreeSet<>(sources.retainedIdentities())) {
            var original=bases.get(id);if(original==null)continue; // no partial PROMISE-only capture
            var copy=sources.original(original);Long size=copy.packet().images().get(digest);
            if(size!=null && size==bytes) {
                export.pinImage(id,directory.resolve(MembershipBasisSources.DIRECTORY).resolve(id).resolve(digest+".image"),digest,bytes);
                checkSourceExport(export);return true;
            }
        }
        checkSourceExport(export);return false;
    }
    /** Read-only current generation, requiring neither PREPARE nor a frozen BASIS. */
    synchronized MembershipPrefixExport exportPrefix(String cut,Map<String,Object> ballot,String view,
            MembershipResources budget,LongSupplier clock,long started,long limit)throws IOException {
        require(current!=null && resources==budget,"prefix export actual shared owner required");checkOwner();
        for(var old:List.copyOf(prefixExports))if(old.expired() || old.generation!=current)releasePrefixExport(old);
        require(MembershipPrefixExport.reference(current.capsule.context,cut),"prefix cut changed");
        require(prefixExports.size()<6,"prefix export owner capacity");
        var export=new MembershipPrefixExport(this,current,ballot,view,resources,clock,started,limit,cut.equals(MembershipPrefixExport.ancestryReference(current.capsule.context)),cut.equals(MembershipPrefixExport.generationReference(current.capsule.context)));prefixExports.add(export);
        try{checkPrefixExport(export);return export;}
        catch(IOException|RuntimeException|Error error){releasePrefixExport(export);throw error;}
    }
    synchronized void checkPrefixExport(MembershipPrefixExport export)throws IOException {
        try {
            require(prefixExports.contains(export) && !export.expired() && current==export.generation,"prefix export closed/expired/replaced");
            checkOwner();require(!export.expired(),"prefix export deadline after owner check");
        }catch(IOException|RuntimeException error){releasePrefixExport(export);throw error;}
    }
    synchronized void releasePrefixExport(MembershipPrefixExport export){prefixExports.remove(export);export.revoke();}
    /** A bounded live borrow from forced storage; never accepts caller-supplied record bytes. */
    synchronized MembershipRecordExport exportRecord(String digest,String kind,Map<String,Object> exchangeBallot,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"record export time budget");Objects.requireNonNull(clock);
        require(current!=null && resources!=null,"record export storage owner required");checkOwner();
        expireRecordExports();current.capsule.context.ballot(exchangeBallot,true);
        require(kind!=null && MembershipRecordExport.KINDS.contains(kind),"record export reference/kind");var record=retainedRecord(digest,kind);
        var export=new MembershipRecordExport(this,current.capsule.context,identity,exchangeBallot,record,resources,clock,started,budget);
        recordExports.add(export);
        try{checkRecordExport(export);return export;}
        catch(IOException|RuntimeException|Error error){releaseRecordExport(export);throw error;}
    }
    /** Lookup retained journal, complete active vote, verified current packet or
     * this live owner's completed native application, never a candidate file. */
    private Decoded retainedRecord(String digest,String kind)throws IOException {
        require(digest!=null && digest.matches("[0-9a-f]{64}") && (kind==null || MembershipRecordExport.KINDS.contains(kind)),"record export reference/kind");
        for(var values:List.of(promises.values(),bases.values(),selections.values()))for(var value:values)
            if((kind==null || value.kind().equals(kind)) && value.digest().equals(digest))return value;
        if(pendingAccept!=null && !pendingAccept.pending() && pendingAccept.active()!=null) {
            var vote=pendingAccept.active();
            for(var value:Arrays.asList(vote.promise(),vote.selected(),vote.entry(),vote.accept(),vote.proof(),vote.certificate()))
                if(value!=null && (kind==null || value.kind().equals(kind)) && value.digest().equals(digest))return value;
        }
        if(current.capsule.packet.objectNames().contains(digest)) {
            if(kind==null) {
                long maximum=MembershipRecordExport.KINDS.stream().mapToLong(k->number(object(object(CATALOG.get("records")).get(k)).get("maximum"))).max().orElseThrow();
                require(current.capsule.packet.objectSize(digest)>=HEADER && current.capsule.packet.objectSize(digest)<=maximum,"record export typed extent");
                byte[] header=current.capsule.packet.objectBytes(digest);int id=Short.toUnsignedInt(ByteBuffer.wrap(header).getShort(8));
                kind=MembershipRecordExport.KINDS.stream().filter(k->number(object(object(CATALOG.get("records")).get(k)).get("id"))==id).findFirst()
                        .orElseThrow(()->new IllegalArgumentException("original forced record kind unavailable"));
            }
            require(current.capsule.packet.objectSize(digest)<=number(object(object(CATALOG.get("records")).get(kind)).get("maximum")),"record export typed extent");
            if(!kind.equals("CHECKPOINT") && !kind.equals("CHECKPOINT_ACK"))return current.capsule.context.record(digest,kind);
        }
        // A packet inventory can contain unused records. Possession of an extra ACK
        // is not an authenticated checkpoint, even if its voter happens to be local.
        if(kind==null || kind.equals("CHECKPOINT") || kind.equals("CHECKPOINT_ACK")) {
            for(Object value:list(current.capsule.packet.capsule().value().get("items"))) {
                var item=object(value);
                if((kind==null || kind.equals("CHECKPOINT")) && digest.equals(item.get("statement")))
                    return current.capsule.context.record(digest,"CHECKPOINT");
                if((kind==null || kind.equals("CHECKPOINT_ACK")) && list(item.get("endorsements")).contains(digest))
                    return current.capsule.context.record(digest,"CHECKPOINT_ACK");
            }
            for(var bridge:current.capsule.verifiedAncestry(current.ancestry())) {
                if((kind==null || kind.equals("CHECKPOINT")) && digest.equals(bridge.statement.digest()))return bridge.statement;
                for(var ack:bridge.acknowledgements)if((kind==null || kind.equals("CHECKPOINT_ACK")) && digest.equals(ack.digest()))return ack;
            }
        }
        // An unpublished application has already forced its own checkpoint ACK,
        // but it is not part of the published capsule. Only the live native
        // capability can expose that record; a copied on-disk end or a hash
        // supplied by a remote proposer cannot manufacture it. Each borrow read
        // repeats this lookup, so fencing/replacement revokes pending records.
        if(nativeApplied!=null && (kind==null || kind.equals("CHECKPOINT") || kind.equals("CHECKPOINT_ACK"))) {
            var candidates=new ArrayList<Decoded>();
            candidates.add(nativeApplied.plan().statement);
            nativeApplied.votingEnd().ifPresent(end->{
                candidates.add(end.acknowledgement());var renewed=new ArrayList<>(end.ancestors());end.parent().ifPresent(renewed::add);
                for(var parent:renewed){candidates.add(parent.statement());candidates.add(parent.acknowledgement());}
            });
            for(var candidate:candidates)if(candidate.digest().equals(digest) && (kind==null || candidate.kind().equals(kind))) {
                pendingPublication(nativeApplied).check();return candidate;
            }
        }
        throw new IllegalArgumentException("original forced record unavailable");
    }
    /** Resolve the initial content reference from actual storage. A BASIS starts the complete
     * frozen source; all other supported record references retain only that exact record. */
    synchronized MembershipTransferExport exportTransfer(String reference,String authority,Map<String,Object> exchangeBallot,
            LongSupplier clock,long started,long budget)throws IOException {
        require(current!=null && resources!=null,"transfer storage owner required");checkOwner();
        require(authority.equals(current.capsule.context.authority()),"transfer view changed");current.capsule.context.ballot(exchangeBallot,true);
        var vote=exportVote(reference,exchangeBallot,clock,started,budget);if(vote!=null)return vote;
        var record=retainedRecord(reference,null);
        if(record.kind().equals("BASIS")) {
            require(record.value().get("ballot").equals(exchangeBallot),"transfer original basis ballot");
            return exportSource(record,clock,started,budget);
        }
        return exportRecord(reference,record.kind(),exchangeBallot,clock,started,budget);
    }
    private MembershipVoteExport exportVote(String reference,Map<String,Object> exchangeBallot,LongSupplier clock,long started,long budget)throws IOException {
        for(var export:List.copyOf(voteExports))if(export.expired())releaseVoteExport(export);
        if(!ownedHistory || pendingAccept==null || pendingAccept.pending() || pendingAccept.active()==null)return null;
        var vote=pendingAccept.active();String phase=null,record=null;byte[] receipt=null;
        boolean payload=vote.payloadSize()>0 && reference.equals(vote.entry().value().get("payload"));
        if(payload){phase="ACCEPT";record=vote.accept().digest();}
        else for(var candidate:new Decoded[]{vote.accept(),vote.proof()})if(candidate!=null) {
            // Generic historical record export must remain usable while a prior
            // vote is retained; only current-next-slot receipts are attested.
            if(!candidate.value().get("authority").equals(current.capsule.context.authority())
                    || number(candidate.value().get("index"))!=number(current.capsule.context.cut.get("index"))+1)continue;
            byte[] bytes=MembershipVoteReceipt.bytes(current.capsule.context,identity,candidate);
            if(reference.equals(MembershipVoteReceipt.reference(bytes))){phase=candidate.kind();record=candidate.digest();receipt=bytes;break;}
        }
        if(phase==null)return null;
        require(budget>0 && budget<Long.MAX_VALUE/2,"vote export time budget");var scope=voting(resources);
        require(scope.ballot.equals(exchangeBallot),"vote export ballot changed");byte[] fixed=receipt;
        var export=new MembershipVoteExport(this,scope,reference,phase,record,payload?vote.payloadSize():fixed.length,
                payload?vote::payload:()->fixed,resources,Objects.requireNonNull(clock),started,budget);
        voteExports.add(export);try{checkVoteExport(export);return export;}
        catch(IOException|RuntimeException|Error error){releaseVoteExport(export);throw error;}
    }
    synchronized void checkVoteExport(MembershipVoteExport export)throws IOException {
        try{require(voteExports.contains(export) && !export.expired(),"vote export closed/expired");
            export.voting.check();require(export.voting.record(export.phase).map(r->r.digest().equals(export.record)).orElse(false),"original vote export changed");
            require(!export.expired(),"vote export deadline");}
        catch(IOException|RuntimeException error){releaseVoteExport(export);throw error;}
    }
    synchronized void releaseVoteExport(MembershipVoteExport export){voteExports.remove(export);export.revoke();}
    /** Only this owner's retained checkpoint from its exact completed publication
     * may cross the changed view. No old grant, vote receipt or payload export. */
    private Decoded publishedCheckpoint(Publication publication,String digest)throws IOException {
        require(publication.owningJournal==this && publication.published(),"checkpoint export requires own completed publication");
        var record=retainedRecord(digest,null);
        require(record.kind().equals("CHECKPOINT") || record.kind().equals("CHECKPOINT_ACK"),"completed publication checkpoint only");
        var value=record.value();
        if(record.kind().equals("CHECKPOINT_ACK"))require(value.get("voter").equals(identity.nodeId().value())
                && value.get("incarnation").equals(identity.storageId().toString())
                && value.get("cut").equals(publication.target.cut()),"completed publication original local checkpoint");
        else require(value.get("end").equals(publication.target.cut()),"completed publication original checkpoint end");
        return record;
    }
    synchronized MembershipRecordExport exportPublishedCheckpoint(Publication publication,String digest,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"record export time budget");Objects.requireNonNull(clock);
        var record=publishedCheckpoint(publication,digest);expireRecordExports();
        var export=new MembershipRecordExport(this,publication.before.context,identity,publication.ballot,record,resources,clock,started,budget,publication);
        recordExports.add(export);
        try{checkRecordExport(export);return export;}
        catch(IOException|RuntimeException|Error error){releaseRecordExport(export);throw error;}
    }
    private void expireRecordExports(){for(var export:List.copyOf(recordExports))if(export.expired())releaseRecordExport(export);}
    synchronized void checkRecordExport(MembershipRecordExport export)throws IOException {
        expireRecordExports();require(recordExports.contains(export),"record export closed/expired");
        try {
            checkOwner();
            if(export.publication==null) {
                require(current.capsule.context.authority().equals(export.context().authority()),"record export view changed");
                retainedRecord(export.digest(),export.kind());
            } else require(publishedCheckpoint(export.publication,export.digest()).kind().equals(export.kind()),"completed checkpoint export kind changed");
            expireRecordExports();require(recordExports.contains(export),"record export closed/expired");
        }catch(IOException|RuntimeException error){releaseRecordExport(export);throw error;}
    }
    synchronized void releaseRecordExport(MembershipRecordExport export){recordExports.remove(export);export.revoke();}
    /** Read an exact retained grant without substituting the latest promise/basis. */
    private MembershipSelection.Source retainedSource(Decoded retainedBasis)throws IOException {
        checkOwner();require(retainedBasis.value().get("view").equals(current.capsule.context.authority()),"obsolete original grant; fresh campaign required");
        var original=sources.original(retainedBasis);var localRoot=decode(AdmissionPaths.read(directory.resolve("root.gsr"),16384),"records","ROOT");
        var capsule=ownedHistory?sources.verifiedOriginal(retainedBasis,new HistoryRead(this)):
                Objects.requireNonNull(capsuleVerifier.verify(localRoot,original.packet(),original.images()));
        if(ownedHistory && current.capsule.sameProvenPrefix(original.packet())) {
            current.check();byte[] ancestry=current.ancestry();
            if(ancestry.length!=0) {
                // A BASIS copy retains the exact source packet, not a generation's
                // supplemental file. Project only the actual owner's authenticated
                // same-prefix history; do not turn copied ACKs into fresh votes.
                capsule=current.capsule.materialization(original.packet(),original.images(),current.capsule.verifiedAncestry(ancestry));
            }
            current.check();
        }
        require(Arrays.equals(capsule.packet.bytes(),original.packet().bytes()),"original verifier substituted source");
        var reference=Map.<String,Object>of("voter",identity.nodeId().value(),"basisId",retainedBasis.value().get("basisId"),"basisDigest",retainedBasis.digest());
        var owned=new HashSet<Owned>();String parent=cutDigest(object(retainedBasis.value().get("cut")));
        owned.add(new Owned(identity.nodeId().value(),identity.storageId(),retainedBasis.digest(),parent));
        if(retainedBasis.value().get("accepted")!=null)owned.add(new Owned(identity.nodeId().value(),identity.storageId(),(String)retainedBasis.value().get("accepted"),parent));
        var result=MembershipSelection.Source.verify(capsule,retainedBasis,reference,identity,owned);checkOwner();return result;
    }
    private MembershipSelection.Decision decision(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges) throws IOException {
        require(current!=null && promise!=null && basis!=null,"complete current grant required");checkOwner();
        var ballot=object(promise.value().get("ballot"));fence(ballot);
        var result=verifyDecision(offered,bridges);
        if(!ownedHistory || peerRetention==null || futureRetention==null)
            for(var source:result.sources())MembershipPeerRetentionSource.requireSelectable(source);
        fence(ballot);return result;
    }
    /** Pure original-decision verification also supports exact derived cleanup.
     * Selection/installation callers separately retain their live voting fence. */
    private MembershipSelection.Decision verifyDecision(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges) throws IOException {
        require(current!=null && promise!=null && basis!=null,"complete current grant required");checkOwner();
        var ballot=object(promise.value().get("ballot"));var local=originalSource();
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
        var result=new MembershipSelection.Campaign(proposer).select(verified,bridges);checkSelection(result.selected());checkOwner();return result;
    }
    /** Records the immutable selection only. No installation, ACCEPT or installation ACK is authorized. */
    synchronized Decoded selectCurrent(List<MembershipSelection.Source> offered,List<MembershipSelection.Bridge> bridges) throws IOException {
        MembershipPendingContext.Reconstructed original=null;
        if(pendingContext!=null && pendingContext.active().isPresent()) {
            contextCaptureIdle(false);original=retainedContextOriginal();
            require(basis!=null && Arrays.equals(basis.bytes(),retainedContextBasis().bytes())
                    && !basis.digest().equals(current.manifest.value().get("basis")),"context selection requires latest protected capture");
        }else floorIdle();
        var calculated=decision(offered,bridges);var selected=calculated.selected();var ballot=object(selected.value().get("ballot"));
        if(original!=null) {
            if(contextCoveredBy(original,calculated.longest().capsule))verifyContextCoverage(original,calculated.longest().capsule.retainingVerifiedAncestry(bridges),MembershipGenerationPlan.ancestry(bridges),selected);
            else require(selected.value().get("cut").equals(original.capsule().context.cut)
                    && original.vote().entry().digest().equals(selected.value().get("nextEntry")),"context selection must carry exact original parent/entry");
        }
        if(selection!=null) {require(Arrays.equals(selection.bytes(),selected.bytes()),"selection already fixed; fresh ballot required");return selection;}
        if(peerRetention!=null) {
            var retention=MembershipSelectedRetention.capture(calculated,identity,peerRetention.activeBytes());
            require(retention.completionBytes()+selected.bytes().length+(retention.hasPendingFutures() && !futurePending() && !importedFuturePending?MembershipPeerRetentionFiles.MAXIMUM:0)<=maximum-storedJournal().length-pendingBytes(),"selected retention completion journal capacity");
        }
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
        var plan=installationPlan(selected,bridges,retainedBridges,images,installed);checkOwner();fence(ballot);
        if(settles) {
            if(retainedOriginal!=null)verifyContextCoverage(retainedOriginal,plan.verifiedMaterialization(),plan.files.getOrDefault("ancestry.gsr",new byte[0]),selection);
            else verifySettlement(pendingAccept.active(),current.copyFiles(),plan.verifiedMaterialization(),plan.files);
        }
        if(retainedOriginal!=null && !settles) {
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
            completeSelectedRetention();
            if(retainedOriginal!=null && settles)completeCoveredContext(retainedOriginal);
            else if(pendingAccept!=null && settledVoteCandidate(pendingAccept.active()))retireSettledVote();
            completeFutureRetention();
            // The former active generation now occupies the future publication slot.
            // Keep its maximum completion reservation until authorized retirement.
            if(appliedEnd!=null && pendingAccept.active()!=null)reservePublicationImage();
            cut.at("INSTALL_BEFORE_RETURN");checkOwner();fence(ballot);return current.manifest;
        }catch(IOException | RuntimeException | Error error){failed=true;throw error;}
    }
    private MembershipGenerationPlan installationPlan(MembershipSelection.Decision selected,List<MembershipSelection.Bridge> bridges,
            List<MembershipSelection.Bridge> retainedBridges,Map<String,byte[]> images,boolean installed)throws IOException {
        require(learnerRetention==null || learnerRetention.state().plan().empty(),"learner retention selected-source propagation unavailable");
        var ancestors=new ArrayList<MembershipCapsule.Anchor>();ancestors.add(current.capsule.terminal());addFloorParent(ancestors);
        if(peerRetention!=null)ancestors.addAll(peerRetention.state().plan().required(current.capsule,current.ancestry()));
        if(learnerRetention!=null)ancestors.addAll(learnerRetention.state().plan().required(current.capsule,current.ancestry()));
        MembershipSelectedRetention retention=null;
        if(peerRetention!=null) {
            retention=installed?selectedRetentionIntent():MembershipSelectedRetention.capture(selected,identity,peerRetention.activeBytes());
            require(retention!=null,"selected retention installation intent absent");ancestors.addAll(retention.requiredParents());
            require(installed || retention.completionBytes()<=maximum-storedJournal().length-pendingBytes(),"selected retention completion journal capacity");
        }
        // A completed receipt retains its original materialization even after safe source retirement.
        if(installed)ancestors.addAll(current.capsule.ancestryAnchors(current.ancestry()).values());
        for(var original:bases.values()) {
            var value=sources.original(original).packet().capsule().value();ancestors.add(new MembershipCapsule.Anchor(object(value.get("cut")),(String)value.get("catalog"),(String)value.get("application")));
        }
        var installation=MembershipGenerationPlan.installation(selected,bridges,retainedBridges,ancestors,current.capsule,current.ancestry());
        selected=installation.decision();var complete=installation.bridges();
        var retained=new TreeMap<String,byte[]>();
        if(installed) {
            // An exact retry can follow explicit floor/source maintenance. Keep
            // the already forced extra objects, rechecked against the immutable
            // local source below; neither the choice nor owned tail can change.
            var base=MembershipGenerationPlan.selected(root,identity,current.generation,promise,basis,selected,complete,images,Map.of(),retention);
            var ordinary=MembershipSourcePacket.decode(base.files.get("source.gscp"));
            for(String h:current.capsule.packet.objectNames())if(!ordinary.objectNames().contains(h))retained.put(h,current.capsule.packet.objectBytes(h));
        }else if(pendingContext!=null && pendingContext.active().isPresent()) {
            var original=retainedContextOriginal();
            if(contextCoveredBy(original,selected.longest().capsule)) {
                retainInstallationVote(retained,original.vote().accept(),original.capsule().packet,original.vote());
                if(current.accepted!=null)retainInstallationVote(retained,decode(current.capsule.packet.objectBytes(current.accepted),"records","ACCEPT"),current.capsule.packet,null);
            }
        }
        // The previous generation's owned tail is an independent retirement
        // obligation even after the live vote reaccepts at a newer ballot.
        // Preserve its exact bytes in the new generation until the existing
        // governing-floor gate can delete that now-inactive original. Do not
        // preserve every older ballot: the next installation roots only its
        // then-current owned tail and any separately protected pending context.
        if(!installed && current.accepted!=null)
            retainInstallationVote(retained,decode(current.capsule.packet.objectBytes(current.accepted),"records","ACCEPT"),current.capsule.packet,null);
        var plan=MembershipGenerationPlan.selected(root,identity,installed?current.generation:inactive.slot(),promise,basis,selected,complete,images,retained,retention);
        verifyPlan(plan,ancestors);return plan;
    }
    private static void retainInstallationVote(Map<String,byte[]> objects,Decoded accept,MembershipSourcePacket packet,MembershipPendingAccept.Vote original) {
        var entry=original==null?decode(packet.objectBytes((String)accept.value().get("entry")),"records","ENTRY"):original.entry();
        byte[] payload=original==null?packet.objectBytes((String)entry.value().get("payload")):original.payload();
        objects.put(accept.digest(),accept.bytes());objects.put(entry.digest(),entry.bytes());objects.put(hash(payload),payload);
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
        if(current!=null) {
            var packet=retentionPacket(source.packet,grant);
            if(packet!=source.packet)source=source.materialization(packet,images,current.capsule.verifiedAncestry(current.ancestry()));
        }
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
        for(var export:List.copyOf(prefixExports))releasePrefixExport(export);
        for(var export:List.copyOf(voteExports))releaseVoteExport(export);
        for(var export:List.copyOf(recordExports))releaseRecordExport(export);
        for(var export:List.copyOf(sourceExports))releaseSourceExport(export);
        if(!closed){closed=true;try{releasePublicationImage();if(futureRetention!=null)futureRetention.close();if(peerRetention!=null)peerRetention.close();if(learnerRetention!=null)learnerRetention.close();if(pendingContext!=null)pendingContext.close();if(appliedEnd!=null)appliedEnd.close();if(replayFiles!=null)replayFiles.close();if(retirement!=null)retirement.close();if(floors!=null)floors.close();if(inactive!=null)inactive.close();if(current!=null)current.close();if(sources!=null)sources.close();}finally{allocator.close();}}
    }
}
