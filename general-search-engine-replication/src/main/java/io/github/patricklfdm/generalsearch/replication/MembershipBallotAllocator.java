package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Internal durable allocation only. Opening this component does not admit a voter or start service. */
final class MembershipBallotAllocator implements AutoCloseable {
    static final long MAX = Long.MAX_VALUE - 1;
    static final String CURRENT = "allocator.gsr", PENDING = "allocator.pending.gsr";
    private static final Set<String> FILES = Set.of("replica.lock", "root.gsr", "genesis.gsr", "node.gsr", CURRENT, PENDING);
    @FunctionalInterface interface Cut { void at(String point) throws IOException; }
    private final Path directory;
    private final MembershipRoot root;
    private final MembershipIdentity identity;
    private final AdmissionPaths.Owner owner;
    private final Map<String,Object> pathBinding;
    private final Object directoryKey, lockKey;
    private final Map<String,byte[]> immutable;
    private final Cut cut;
    private final Set<String> additional;
    private byte[] current;
    private long counter;
    private boolean failed, closed;

    private MembershipBallotAllocator(Path directory, MembershipRoot root, MembershipIdentity identity,
            AdmissionPaths.Owner owner, Cut cut, Set<String> additional) throws IOException {
        this.directory=directory; this.root=root; this.identity=identity; this.owner=owner; this.cut=cut;
        this.additional=additional;
        pathBinding=AdmissionPaths.binding(directory); directoryKey=key(directory); lockKey=key(directory.resolve("replica.lock"));
        immutable=Map.of("root.gsr",AdmissionPaths.read(directory.resolve("root.gsr"),16384),
                "genesis.gsr",AdmissionPaths.read(directory.resolve("genesis.gsr"),65536),
                "node.gsr",AdmissionPaths.read(directory.resolve("node.gsr"),4096));
        var header=decode(immutable.get("root.gsr"),"records","ROOT");
        require(header.rootDigest().equals(root.manifestDigest())
                && header.value().get("groupId").equals(root.groupId().value().toString())
                && header.value().get("historyId").equals(root.historyId().toString()),"allocator root identity");
        var genesis=decode(immutable.get("genesis.gsr"),"records","GENESIS");
        require(genesis.digest().equals(header.value().get("genesis")),"allocator original genesis");
        for(String field:List.of("groupId","historyId","baseSequence","schema","indexes"))
            require(genesis.value().get(field).equals(header.value().get(field)),"allocator root/genesis "+field);
        require(genesis.value().get("source").equals("EMPTY")== (genesis.value().get("sourceDigest")==null),"genesis source binding");
        require(header.value().get("limits").equals(hash(canonical(CATALOG.get("resources"),16384))),"allocator resource contract");
        var initial=new ArrayList<MembershipIdentity>();
        for(Object member:list(header.value().get("initial"))) initial.add(MembershipContext.identity(object(member)));
        MembershipValidation.identities(initial,3,5);
        var node=decode(immutable.get("node.gsr"),"records","NODE").value();
        require(node.get("root").equals(root.manifestDigest()) && MembershipContext.identity(object(node.get("identity"))).equals(identity),"allocator node identity");
        current=AdmissionPaths.read(directory.resolve(CURRENT),4096); counter=decodeCounter(current);
    }

    static MembershipBallotAllocator open(Path requested, MembershipRoot root, MembershipIdentity identity) throws IOException {
        return open(requested,root,identity,point->{});
    }

    static MembershipBallotAllocator open(Path requested, MembershipRoot root, MembershipIdentity identity, Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of());
    }

    static MembershipBallotAllocator openWithGrantJournal(Path requested, MembershipRoot root, MembershipIdentity identity, Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr"));
    }

    static MembershipBallotAllocator openWithRetainedGrants(Path requested, MembershipRoot root, MembershipIdentity identity, Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY));
    }

    static MembershipBallotAllocator openWithCurrentGeneration(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR));
    }
    static MembershipBallotAllocator openWithGenerationInstall(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR,MembershipGenerationFiles.PENDING));
    }

    static MembershipBallotAllocator openWithFloorCopies(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR,MembershipGenerationFiles.PENDING,MembershipFloorFiles.DIRECTORY));
    }

    static MembershipBallotAllocator openWithRetirement(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR,MembershipGenerationFiles.PENDING,
                MembershipFloorFiles.DIRECTORY,MembershipRetirementFiles.DIRECTORY));
    }

    static MembershipBallotAllocator openWithJournalRotation(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR,MembershipGenerationFiles.PENDING,
                MembershipFloorFiles.DIRECTORY,MembershipRetirementFiles.DIRECTORY,MembershipJournalRotation.PENDING));
    }

    static MembershipBallotAllocator openWithSourceRetirement(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR,MembershipGenerationFiles.PENDING,
                MembershipFloorFiles.DIRECTORY,MembershipRetirementFiles.DIRECTORY,MembershipJournalRotation.PENDING,MembershipSourceRetirementFiles.FILE));
    }

    static MembershipBallotAllocator openWithCaptureRecovery(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return open(requested,root,identity,cut,Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR,MembershipGenerationFiles.PENDING,
                MembershipFloorFiles.DIRECTORY,MembershipRetirementFiles.DIRECTORY,MembershipJournalRotation.PENDING,
                MembershipSourceRetirementFiles.FILE,MembershipCaptureFiles.FILE));
    }

    static MembershipBallotAllocator openWithPendingAccept(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return openWithPendingAccept(requested,root,identity,cut,false);
    }
    static MembershipBallotAllocator openWithAppliedEnd(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return openWithPendingAccept(requested,root,identity,cut,true);
    }
    static MembershipBallotAllocator openWithPendingContext(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut) throws IOException {
        return openWithPendingAccept(requested,root,identity,cut,true,true);
    }
    private static MembershipBallotAllocator openWithPendingAccept(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut,boolean applying) throws IOException {
        return openWithPendingAccept(requested,root,identity,cut,applying,false);
    }
    private static MembershipBallotAllocator openWithPendingAccept(Path requested,MembershipRoot root,MembershipIdentity identity,Cut cut,boolean applying,boolean context) throws IOException {
        var names=new HashSet<>(Set.of("grants.gsr",MembershipBasisSources.DIRECTORY,
                MembershipCurrentGeneration.DIRECTORY,MembershipCurrentGeneration.SELECTOR,MembershipGenerationFiles.PENDING,
                MembershipFloorFiles.DIRECTORY,MembershipRetirementFiles.DIRECTORY,MembershipJournalRotation.PENDING,
                MembershipSourceRetirementFiles.FILE,MembershipCaptureFiles.FILE,MembershipPendingAccept.FILE,MembershipPendingAccept.NEXT));
        if(applying){names.add(MembershipAppliedEndFiles.DIRECTORY);names.add(MembershipReplayFiles.DIRECTORY);}
        if(context){names.add(MembershipPendingContextFiles.FILE);names.add(MembershipPendingContextFiles.NEXT);}
        return open(requested,root,identity,cut,names);
    }

    private static MembershipBallotAllocator open(Path requested, MembershipRoot root, MembershipIdentity identity, Cut cut, Set<String> additional) throws IOException {
        Objects.requireNonNull(root); Objects.requireNonNull(identity); Objects.requireNonNull(cut);
        Path directory=AdmissionPaths.safe(requested);
        require(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"allocator directory absent");
        // No CREATE and no repair from arguments: a missing root/lock/counter is lost authority.
        inventory(directory,additional);
        var owner=AdmissionPaths.own(directory.resolve("replica.lock"),false);
        try {
            var allocator=new MembershipBallotAllocator(directory,root,identity,owner,cut,additional);
            allocator.recover(); return allocator;
        } catch(IOException | RuntimeException | Error error) {
            try { owner.close(); } catch(IOException close) { error.addSuppressed(close); }
            throw error;
        }
    }

    private static Object key(Path path) throws IOException {
        Object key=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS).fileKey();
        require(key!=null,"allocator file identity unavailable"); return key;
    }

    private static void inventory(Path directory,Set<String> additional) throws IOException {
        Set<String> seen=new HashSet<>();
        try(var stream=Files.newDirectoryStream(directory)) {
            for(Path path:stream) {
                require(seen.size()<FILES.size()+additional.size() && (FILES.contains(path.getFileName().toString())
                        || additional.contains(path.getFileName().toString())),"unknown allocator authority file");
                if(additional.contains(path.getFileName().toString()) && Set.of(MembershipBasisSources.DIRECTORY,MembershipCurrentGeneration.DIRECTORY,MembershipFloorFiles.DIRECTORY,MembershipRetirementFiles.DIRECTORY,MembershipAppliedEndFiles.DIRECTORY,MembershipReplayFiles.DIRECTORY).contains(path.getFileName().toString())) {
                    AdmissionPaths.safe(path);require(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"missing basis source directory");
                } else AdmissionPaths.regular(path);
                seen.add(path.getFileName().toString());
            }
        }
        require(seen.containsAll(Set.of("replica.lock","root.gsr","genesis.gsr","node.gsr",CURRENT)),"incomplete allocator authority");
        var required=new HashSet<>(additional);required.remove(MembershipGenerationFiles.PENDING);required.remove(MembershipFloorFiles.DIRECTORY);required.remove(MembershipRetirementFiles.DIRECTORY);required.remove(MembershipJournalRotation.PENDING);required.remove(MembershipSourceRetirementFiles.FILE);required.remove(MembershipCaptureFiles.FILE);required.remove(MembershipPendingAccept.NEXT);
        required.remove(MembershipAppliedEndFiles.DIRECTORY);required.remove(MembershipReplayFiles.DIRECTORY);
        required.remove(MembershipPendingContextFiles.FILE);required.remove(MembershipPendingContextFiles.NEXT);
        require(seen.containsAll(required),"incomplete grant authority");
    }

    private long decodeCounter(byte[] bytes) {
        var value=decode(bytes,"records","ALLOCATOR").value();
        require(value.get("root").equals(root.manifestDigest()) && value.get("node").equals(identity.nodeId().value()),"foreign allocator record");
        long valueCounter=number(value.get("counter")); require(valueCounter>=0 && valueCounter<=MAX,"allocator counter capacity"); return valueCounter;
    }

    synchronized void checkOwner() throws IOException {
        require(!closed && !failed && owner.lock().isValid(),"allocator closed or failed");
        AdmissionPaths.recheck(pathBinding);
        require(key(directory).equals(directoryKey) && key(directory.resolve("replica.lock")).equals(lockKey),"allocator owner path changed");
        inventory(directory,additional);
        for(var entry:immutable.entrySet()) AdmissionPaths.exact(directory.resolve(entry.getKey()),entry.getValue());
        AdmissionPaths.exact(directory.resolve(CURRENT),current);
    }

    private void forceFile(Path path) throws IOException {
        AdmissionPaths.regular(path);
        try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) { channel.force(true); }
    }

    private void recover() throws IOException {
        checkOwner(); Path pending=directory.resolve(PENDING);
        if(Files.exists(pending,LinkOption.NOFOLLOW_LINKS)) {
            byte[] bytes=AdmissionPaths.read(pending,4096); long next=decodeCounter(bytes);
            require(next>counter,"stale allocator pending record");
            // A complete unreturned reservation is burned, even if its old process never sent a ballot.
            forceFile(pending); cut.at("RECOVERY_PENDING_FORCED");
            checkOwner(); Files.move(pending,directory.resolve(CURRENT),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            cut.at("RECOVERY_RENAMED"); AdmissionPaths.forceDirectory(directory); cut.at("RECOVERY_DIRECTORY_FORCED");
            current=bytes; counter=next;
        } else {
            // Seal an atomic rename that was visible when its previous process died before directory force.
            forceFile(directory.resolve(CURRENT)); AdmissionPaths.forceDirectory(directory);
        }
    }

    synchronized long counter() { require(!closed && !failed,"allocator closed or failed"); return counter; }

    synchronized long reserve(long observedCounter) throws IOException {
        require(observedCounter>=0 && observedCounter<=MAX,"observed ballot counter capacity");
        require(!closed && !failed,"allocator closed or failed");
        if(Math.max(counter,observedCounter)==MAX)
            throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,
                    AutomaticReplicationException.Outcome.NOT_SUBMITTED,Optional.empty(),"membership ballot counter exhausted",null);
        long next=Math.max(counter,observedCounter)+1;
        byte[] bytes=encode("records","ALLOCATOR",Map.of("root",root.manifestDigest(),"node",identity.nodeId().value(),"counter",next));
        try {
            checkOwner(); Path pending=directory.resolve(PENDING); AdmissionPaths.absent(pending); cut.at("ALLOCATOR_BEFORE_WRITE");
            try(var channel=FileChannel.open(pending,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                cut.at("ALLOCATOR_CREATED"); AdmissionPaths.write(channel,bytes); cut.at("ALLOCATOR_WRITTEN");
                channel.force(true); cut.at("ALLOCATOR_FORCED");
            }
            checkOwner(); AdmissionPaths.exact(pending,bytes);
            Files.move(pending,directory.resolve(CURRENT),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            cut.at("ALLOCATOR_RENAMED"); AdmissionPaths.forceDirectory(directory); cut.at("ALLOCATOR_DIRECTORY_FORCED");
            current=bytes; counter=next; cut.at("ALLOCATOR_BEFORE_RETURN"); return next;
        } catch(IOException | RuntimeException | Error error) {
            failed=true; throw error;
        }
    }

    @Override public synchronized void close() throws IOException {
        if(!closed) { closed=true; owner.close(); }
    }
}
