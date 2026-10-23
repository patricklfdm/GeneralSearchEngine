package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact private context persistence under the caller's exclusive owner and shared JOURNAL lease.
 * This component neither authorizes a context transition nor pins/deletes source or generation authority.
 * The caller must retain and verify the exact prior context even after a replacement rename, revalidate
 * backing evidence, and supply an allowance deducted from all other shared-journal users. Only a
 * successful install returns durably sealed local metadata, never an Owned observation or a
 * publication acknowledgement; snapshot getters perform no force and confer no authority. */
final class MembershipPendingContextFiles implements AutoCloseable {
    static final String FILE="pending.context",NEXT="pending.context.next";
    static final long MAXIMUM_METADATA=2L*MembershipPendingContext.MAXIMUM;
    private final Path directory;
    private final Map<String,Object> binding;
    private final Object directoryKey;
    private final MembershipRoot root;
    private final MembershipIdentity identity;
    private final MembershipResources resources;
    private final long maximumMetadata;
    private FileIdentity activeIdentity,nextIdentity;
    private byte[] activeBytes,nextBytes;
    private MembershipPendingContext.Context active;
    private boolean failed,closed;

    MembershipPendingContextFiles(Path existingOwnerRoot,MembershipRoot root,MembershipIdentity identity,
            MembershipResources resources,long maximumMetadata)throws IOException {
        directory=AdmissionPaths.safe(existingOwnerRoot);binding=AdmissionPaths.binding(directory);
        require(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"pending context owner directory absent");
        directoryKey=key(directory);this.root=Objects.requireNonNull(root);this.identity=Objects.requireNonNull(identity);
        this.resources=Objects.requireNonNull(resources);
        require(maximumMetadata>=0 && maximumMetadata<=MAXIMUM_METADATA
                && maximumMetadata<=MembershipResources.Unit.JOURNAL.bytes,"pending context journal allowance");
        this.maximumMetadata=maximumMetadata;sharedJournal();
        if(Files.exists(directory.resolve(FILE),LinkOption.NOFOLLOW_LINKS)) {
            activeBytes=AdmissionPaths.read(directory.resolve(FILE),MembershipPendingContext.MAXIMUM);
            active=decodeOwned(activeBytes);activeIdentity=inspect(directory.resolve(FILE),activeBytes.length,hash(activeBytes));
        }
        if(Files.exists(directory.resolve(NEXT),LinkOption.NOFOLLOW_LINKS)) {
            nextBytes=AdmissionPaths.read(directory.resolve(NEXT),MembershipPendingContext.MAXIMUM);candidate(nextBytes);
            nextIdentity=inspect(directory.resolve(NEXT),nextBytes.length,hash(nextBytes));
        }
        require(storedBytes()<=maximumMetadata,"pending context retained journal capacity");verify();
        // Constructor deliberately does not force, fill, rename, remove, or reconstruct either file.
    }

    Optional<MembershipPendingContext.Context> active(){live();return Optional.ofNullable(active);}
    Optional<byte[]> activeBytes(){live();return activeBytes==null?Optional.empty():Optional.of(activeBytes.clone());}
    boolean pending(){live();return nextIdentity!=null;}
    long bytes(){live();return storedBytes();}
    private long storedBytes(){return (activeBytes==null?0L:activeBytes.length)+(nextBytes==null?0L:nextBytes.length);}
    private void live(){require(!closed && !failed,"pending context files closed or failed; reopen required");}
    private void sharedJournal() {
        require(resources.usage().counts().getOrDefault(MembershipResources.Unit.JOURNAL,0)==1,
                "pending context requires shared journal reservation");
    }
    private MembershipPendingContext.Context decodeOwned(byte[] bytes) {
        var context=MembershipPendingContext.decode(bytes);MembershipPendingContext.checkOwner(context,root,identity);return context;
    }
    private byte[] expectedBytes(MembershipPendingContext.Context expected) {
        MembershipPendingContext.checkOwner(Objects.requireNonNull(expected),root,identity);
        return MembershipPendingContext.encode(expected);
    }
    /** Extra candidate bytes needed, in addition to bytes() (which already includes the active and
     * any candidate prefix). A fully installed context with no candidate requires only re-forcing. */
    long completionAllowance(MembershipPendingContext.Context expected) {
        live();byte[] bytes=expectedBytes(expected);matches(bytes);
        return Arrays.equals(activeBytes,bytes) && nextBytes==null?0:bytes.length-(nextBytes==null?0:nextBytes.length);
    }
    private void matches(byte[] expected) {
        require(nextBytes==null || nextBytes.length<=expected.length
                && Arrays.equals(nextBytes,Arrays.copyOf(expected,nextBytes.length)),"pending context candidate differs from exact request");
    }
    /** A surviving prefix is not authority. Validate every header byte available and decode only a
     * complete candidate; the absent suffix may only come from a fully verified exact caller request. */
    private void candidate(byte[] bytes) {
        require(bytes.length<=MembershipPendingContext.MAXIMUM,"pending context candidate capacity");
        byte[] fixed=ByteBuffer.allocate(12).putInt(MembershipPendingContext.MAGIC).putShort((short)1).putShort((short)3)
                .putShort((short)0).putShort((short)0).array();
        for(int i=0;i<Math.min(bytes.length,fixed.length);i++)require(bytes[i]==fixed[i],"pending context candidate protocol/kind/flags");
        if(bytes.length<16)return;
        long declared=HEADER+Integer.toUnsignedLong(ByteBuffer.wrap(bytes).getInt(12));
        require(declared>=HEADER+24 && declared<=MembershipPendingContext.MAXIMUM && bytes.length<=declared,
                "pending context candidate declared length");
        if(bytes.length==declared)decodeOwned(bytes);
    }

    void check()throws IOException {
        try {live();verify();}catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void verify()throws IOException {
        AdmissionPaths.recheck(binding);sharedJournal();
        require(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS) && directoryKey.equals(key(directory)),
                "pending context owner directory changed");
        require((activeIdentity!=null)==Files.exists(directory.resolve(FILE),LinkOption.NOFOLLOW_LINKS),
                "pending context active presence changed");
        require((nextIdentity!=null)==Files.exists(directory.resolve(NEXT),LinkOption.NOFOLLOW_LINKS),
                "pending context candidate presence changed");
        if(activeIdentity!=null)require(activeIdentity.equals(inspect(directory.resolve(FILE),activeIdentity.bytes(),activeIdentity.digest())),
                "pending context active inode changed");
        if(nextIdentity!=null)require(nextIdentity.equals(inspect(directory.resolve(NEXT),nextIdentity.bytes(),nextIdentity.digest())),
                "pending context candidate inode changed");
        require(storedBytes()<=maximumMetadata,"pending context retained journal capacity");
    }
    private void guarded(MembershipGenerationFiles.Guard guard)throws IOException {
        check();guard.check();check();
    }
    private void event(String event,MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        cut.at(event);guarded(guard);
    }

    /** First install requires null prior. Replacement requires all original prior bytes, not merely
     * a digest. Active==expected is recognized first so a retry after atomic rename can re-seal with
     * the original prior still supplied. Such a retry is not evidence of how that active file arose;
     * the caller's guard remains responsible for authorizing the exact requested transition. */
    byte[] install(MembershipPendingContext.Context expected,byte[] exactPrior,
            MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        try {
            Objects.requireNonNull(guard);Objects.requireNonNull(cut);guarded(guard);
            byte[] bytes=expectedBytes(expected);
            require(exactPrior==null || exactPrior.length>=HEADER && exactPrior.length<=MembershipPendingContext.MAXIMUM,
                    "pending context prior capacity");
            byte[] prior=exactPrior==null?null:exactPrior.clone();
            if(prior!=null)decodeOwned(prior);
            matches(bytes);boolean installed=Arrays.equals(activeBytes,bytes);
            if(!installed)require(prior==null?activeBytes==null:Arrays.equals(activeBytes,prior),"pending context exact prior changed");
            if(installed && nextBytes==null) {
                sealActive(guard,cut);return bytes.clone();
            }
            long peak=(activeBytes==null?0L:activeBytes.length)+bytes.length;
            require(peak<=maximumMetadata && peak<=MAXIMUM_METADATA,"pending context completion journal capacity");
            var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));
            boolean create=nextIdentity==null;if(create)options.add(StandardOpenOption.CREATE_NEW);
            guarded(guard);
            try(var channel=FileChannel.open(directory.resolve(NEXT),options)) {
                if(create) {snapshotNext(new byte[0]);event("CONTEXT_CANDIDATE_CREATED",guard,cut);}
                Object inode=nextIdentity.key();int offset=nextBytes.length,middle=offset+(bytes.length-offset)/2;
                require(channel.size()==offset,"pending context candidate length changed");channel.position(offset);
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,offset,middle));snapshotNext(Arrays.copyOf(bytes,middle));
                require(inode.equals(nextIdentity.key()),"pending context candidate inode changed");
                event("CONTEXT_PREFIX_WRITTEN",guard,cut);
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,middle,bytes.length));snapshotNext(bytes);
                require(inode.equals(nextIdentity.key()),"pending context candidate inode changed");
                event("CONTEXT_CANDIDATE_WRITTEN",guard,cut);channel.force(true);
                event("CONTEXT_CANDIDATE_FORCED",guard,cut);
            }
            AdmissionPaths.forceDirectory(directory);event("CONTEXT_CANDIDATE_PARENT_FORCED",guard,cut);
            Files.move(directory.resolve(NEXT),directory.resolve(FILE),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            activeIdentity=nextIdentity;activeBytes=bytes.clone();active=decodeOwned(activeBytes);nextIdentity=null;nextBytes=null;
            event("CONTEXT_RENAMED",guard,cut);AdmissionPaths.forceDirectory(directory);
            event("CONTEXT_PARENT_FORCED",guard,cut);return activeBytes.clone();
        }catch(IOException|RuntimeException|Error error){failed=true;throw error;}
    }
    private void snapshotNext(byte[] bytes)throws IOException {
        nextIdentity=inspect(directory.resolve(NEXT),bytes.length,hash(bytes));nextBytes=bytes.clone();
    }
    private void sealActive(MembershipGenerationFiles.Guard guard,MembershipBallotAllocator.Cut cut)throws IOException {
        guarded(guard);
        try(var channel=FileChannel.open(directory.resolve(FILE),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
        event("CONTEXT_ACTIVE_FORCED",guard,cut);AdmissionPaths.forceDirectory(directory);
        event("CONTEXT_ACTIVE_PARENT_FORCED",guard,cut);
    }
    /** Borrowed JOURNAL reservation and all authority bytes remain the caller's responsibility. */
    @Override public void close(){closed=true;}
}
