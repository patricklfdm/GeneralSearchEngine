package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Derived receiving workspace only. Its marker is neither protocol authority nor
 * permission to retire any generation, proof or selected source. The owner must
 * exclude its durable authority paths before opening this scope. */
final class MembershipScratch implements AutoCloseable {
    enum Role { OUTGOING, INCOMING }
    interface Events { void at(String event)throws IOException; }
    record Discarded(String path,boolean directory,long bytes) {}
    private static final String MARKER="owner.json", LOCK="scope.lock";
    private static final int MAXIMUM_MARKER=32768;
    private static final String UUID_TEXT="[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
    private final Path directory;
    private final Map<String,Object> parent;
    private final Object directoryKey;
    private final byte[] marker;
    private final Role role;
    private final MembershipResources resources;
    private final MembershipSourcePull.Guard guard;
    private final Events events;
    private final List<Discarded> discarded=new ArrayList<>();
    private MembershipOwnership lock;
    private MembershipResources.Lease metadata;
    private Object markerKey,lockKey;
    private boolean closed;

    static MembershipScratch open(Path path,String root,MembershipIdentity local,Role role,
            MembershipResources resources,MembershipSourcePull.Guard guard,Events events)throws IOException {
        return new MembershipScratch(path,root,local,role,resources,guard,events);
    }
    private MembershipScratch(Path path,String root,MembershipIdentity local,Role role,
            MembershipResources resources,MembershipSourcePull.Guard guard,Events events)throws IOException {
        MembershipValidation.digest(root);Objects.requireNonNull(local);this.role=Objects.requireNonNull(role);this.resources=Objects.requireNonNull(resources);
        this.guard=Objects.requireNonNull(guard);this.events=Objects.requireNonNull(events);guard.check();
        directory=AdmissionPaths.safe(path);parent=AdmissionPaths.binding(directory);
        try {
            metadata=resources.reserve(MembershipResources.Unit.CONTROL,"scratch-owner-"+UUID.randomUUID(),MAXIMUM_MARKER);
            if(!Files.exists(directory,LinkOption.NOFOLLOW_LINKS))Files.createDirectory(directory);
            require(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"scratch root must be directory");
            directoryKey=MembershipBasisSources.key(directory);
            marker=canonical(Map.of("schema","gse-v53-derived-scratch-v1","root",root,"identity",MembershipBootstrapSeed.identity(local),
                    "role",role.name(),"parent",parent,"directoryKey",directoryKey.toString()),MAXIMUM_MARKER);
            var names=MembershipBasisSources.children(directory,8);
            if(!names.contains(MARKER))require(names.isEmpty() || names.equals(Set.of(LOCK)),"unowned scratch directory");
            require(names.isEmpty() || names.contains(LOCK),"scratch lock missing");
            lock=MembershipOwnership.own(directory.resolve(LOCK),!names.contains(LOCK));lockKey=MembershipBasisSources.key(directory.resolve(LOCK));
            initialize();check();recover();check();
        }catch(IOException|RuntimeException|Error error) {
            try{release();}catch(IOException close){error.addSuppressed(close);}throw error;
        }
    }
    private void initialize()throws IOException {
        Path path=directory.resolve(MARKER);byte[] prior=new byte[0];boolean exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);
        if(exists)prior=AdmissionPaths.read(path,MAXIMUM_MARKER);
        require(prior.length<=marker.length && Arrays.equals(prior,Arrays.copyOf(marker,prior.length)),"scratch root/identity/role/path changed");
        if(prior.length!=marker.length) {
            var names=MembershipBasisSources.children(directory,8);
            require(names.equals(exists?Set.of(LOCK,MARKER):Set.of(LOCK)),"incomplete scratch marker has data");
            try(var file=MembershipFileAccess.open(path,exists?Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                    Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS))) {
                file.position(prior.length);AdmissionPaths.write(file,Arrays.copyOfRange(marker,prior.length,marker.length));
                events.at("MARKER_WRITTEN");file.force(true);events.at("MARKER_FORCED");
            }
        }
        markerKey=MembershipBasisSources.key(path);AdmissionPaths.forceDirectory(directory);AdmissionPaths.forceDirectory(directory.getParent());events.at("OWNER_FORCED");
    }
    synchronized void check()throws IOException {
        require(!closed && lock!=null && lock.lock().isValid(),"scratch owner closed");AdmissionPaths.recheck(parent);AdmissionPaths.safe(directory);
        require(directoryKey.equals(MembershipBasisSources.key(directory)),"scratch directory replaced");
        AdmissionPaths.regular(directory.resolve(LOCK));AdmissionPaths.regular(directory.resolve(MARKER));
        require(lockKey.equals(MembershipBasisSources.key(directory.resolve(LOCK))) && Files.size(directory.resolve(LOCK))==0
                && markerKey.equals(MembershipBasisSources.key(directory.resolve(MARKER)))
                && Arrays.equals(marker,AdmissionPaths.read(directory.resolve(MARKER),MAXIMUM_MARKER)),"scratch owner metadata changed");
    }
    synchronized Path directory()throws IOException {check();return directory;}
    synchronized List<Discarded> recovered()throws IOException {check();return List.copyOf(discarded);}

    private final class Tree implements AutoCloseable {
        final Map<Path,Object> directories=new LinkedHashMap<>();
        final Map<Path,BasicFileAttributes> files=new LinkedHashMap<>();
        final Map<Path,MembershipResources.Unit> kinds=new HashMap<>();
        final Map<Path,MembershipResources.Lease> leases=new HashMap<>();
        int sources,images;
        void directory(Path path)throws IOException {
            AdmissionPaths.safe(path);require(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"scratch member directory");
            directories.put(path,MembershipBasisSources.key(path));
        }
        void source(Path path)throws IOException {
            require(++sources<=6,"scratch source count");directory(path);
            for(String name:new TreeSet<>(MembershipBasisSources.children(path,8))) {
                MembershipResources.Unit kind;
                if(name.equals("source.gscp"))kind=MembershipResources.Unit.SOURCE;
                else {require(name.matches("[0-9a-f]{64}\\.image") && ++images<=7,"scratch image name/count");kind=MembershipResources.Unit.APPLICATION;}
                Path file=path.resolve(name);AdmissionPaths.regular(file);var attributes=Files.readAttributes(file,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
                require(attributes.size()<=kind.bytes,"scratch file extent");files.put(file,attributes);kinds.put(file,kind);
            }
        }
        void reserve() {
            for(var row:files.entrySet())leases.put(row.getKey(),resources.reserve(kinds.get(row.getKey()),"scratch-recovery-"+UUID.randomUUID(),Math.max(1,row.getValue().size())));
        }
        void check()throws IOException {
            guard.check();MembershipScratch.this.check();var parents=new ArrayList<Path>();parents.add(directory);parents.addAll(directories.keySet());
            for(Path path:parents) {
                if(!path.equals(directory))require(directories.get(path).equals(MembershipBasisSources.key(path)),"scratch child directory replaced");
                var expected=new HashSet<String>();if(path.equals(directory))expected.addAll(Set.of(LOCK,MARKER));
                for(Path child:directories.keySet())if(child.getParent().equals(path))expected.add(child.getFileName().toString());
                for(Path child:files.keySet())if(child.getParent().equals(path))expected.add(child.getFileName().toString());
                require(expected.equals(MembershipBasisSources.children(path,8)),"scratch child inventory changed");
            }
            for(var row:files.entrySet()) {
                AdmissionPaths.regular(row.getKey());var now=Files.readAttributes(row.getKey(),BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);var before=row.getValue();
                require(now.fileKey().equals(before.fileKey()) && now.size()==before.size() && now.lastModifiedTime().equals(before.lastModifiedTime()),"scratch child file changed");
            }
        }
        @Override public void close(){for(var lease:leases.values())lease.close();leases.clear();}
    }
    private void recover()throws IOException {
        try(var tree=new Tree()) {
            var names=new TreeSet<>(MembershipBasisSources.children(directory,8));names.removeAll(Set.of(MARKER,LOCK));
            boolean selected=role==Role.INCOMING && names.size()==1 && names.first().matches("selected-"+UUID_TEXT);
            // Incoming maintenance pulls original floor copies directly into
            // source-UUID, whereas SELECTED receives one nested source set.
            // The single control worker drains one layout before the other;
            // mixed layouts are not an abandoned scope we can safely adopt.
            if(role==Role.INCOMING)require(selected || names.stream().allMatch(name->name.matches("source-"+UUID_TEXT)),"incoming scratch name/count");
            for(String name:names) {
                Path path=directory.resolve(name);
                if(!selected){require(name.matches("source-"+UUID_TEXT),"outgoing scratch name");tree.source(path);}
                else {
                    tree.directory(path);
                    for(String child:new TreeSet<>(MembershipBasisSources.children(path,6))) {
                        require(child.matches("source-[0-5]"),"selected scratch source name");tree.source(path.resolve(child));
                    }
                }
            }
            tree.reserve();tree.check();events.at("RECOVERY_VALIDATED");
            for(var row:List.copyOf(tree.files.entrySet())) {
                tree.check();Files.delete(row.getKey());tree.files.remove(row.getKey());tree.leases.remove(row.getKey()).close();
                discarded.add(new Discarded(directory.relativize(row.getKey()).toString(),false,row.getValue().size()));
                events.at("FILE_REMOVED");AdmissionPaths.forceDirectory(row.getKey().getParent());events.at("FILE_REMOVAL_FORCED");
            }
            var paths=new ArrayList<>(tree.directories.keySet());Collections.reverse(paths);
            for(Path path:paths) {
                tree.check();Files.delete(path);tree.directories.remove(path);discarded.add(new Discarded(directory.relativize(path).toString(),true,0));
                events.at("DIRECTORY_REMOVED");AdmissionPaths.forceDirectory(path.getParent());events.at("DIRECTORY_REMOVAL_FORCED");
            }
            tree.check();events.at("RECOVERY_COMPLETE");
        }
    }
    private void release()throws IOException {
        if(lock!=null){lock.close();lock=null;}if(metadata!=null){metadata.close();metadata=null;}closed=true;
    }
    /** Components drain/delete their own live children before releasing this scope.
     * Persist the tiny owner marker/lock for exact restart recovery. */
    @Override public synchronized void close()throws IOException {
        if(closed)return;check();require(MembershipBasisSources.children(directory,8).equals(Set.of(MARKER,LOCK)),"live scratch children remain");
        AdmissionPaths.forceDirectory(directory);release();
    }
}
