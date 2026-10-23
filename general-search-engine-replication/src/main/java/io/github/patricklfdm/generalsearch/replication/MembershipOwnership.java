package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.Set;

/** V5.3 process-local exclusion precedes opening a POSIX lock inode. Closing a
 * second channel after an overlapping-lock failure can release the original
 * process lock even when its Java FileLock still reports valid. */
final class MembershipOwnership implements AutoCloseable {
    private static final Set<Path> PATHS=new HashSet<>();
    private static final Set<Object> INODES=new HashSet<>();
    private final Path path;
    private final Object inode;
    private final AdmissionPaths.Owner owner;
    private boolean closed;
    private MembershipOwnership(Path path,Object inode,AdmissionPaths.Owner owner){this.path=path;this.inode=inode;this.owner=owner;}
    static synchronized MembershipOwnership own(Path requested,boolean create)throws IOException {
        Path path=AdmissionPaths.safe(requested);
        if(PATHS.contains(path))throw occupied();
        Object before=null;if(!create){AdmissionPaths.regular(path);before=MembershipBasisSources.key(path);if(INODES.contains(before))throw occupied();}
        var owner=AdmissionPaths.own(path,create);
        try {
            Object inode=MembershipBasisSources.key(path);MembershipValidation.require(before==null || before.equals(inode),"membership owner inode changed during open");if(INODES.contains(inode))throw occupied();
            PATHS.add(path);INODES.add(inode);return new MembershipOwnership(path,inode,owner);
        }catch(IOException|RuntimeException|Error error){try{owner.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private static ReplicationException occupied(){return new ReplicationException(ReplicationException.Reason.STORAGE_FAILURE,"membership authority already owned in this process");}
    FileChannel channel(){return owner.channel();}
    FileLock lock(){return owner.lock();}
    @Override public void close()throws IOException {
        synchronized(MembershipOwnership.class) {
            if(closed)return;
            try{owner.close();}finally{
                if(!owner.channel().isOpen()){closed=true;PATHS.remove(path);INODES.remove(inode);}
            }
        }
    }
}
