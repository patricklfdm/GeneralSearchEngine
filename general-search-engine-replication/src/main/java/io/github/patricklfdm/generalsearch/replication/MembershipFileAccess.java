package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** V5.3 descriptor custody. Closing another descriptor for an inode can release
 * this process's POSIX locks. Ordinary views therefore borrow an owned channel,
 * keep their own cursor, and never close/unlock it. Unowned opens are counted so
 * an owner cannot acquire a lock while a read/write descriptor can still close. */
final class MembershipFileAccess {
    private static final Set<OpenOption> OPTIONS=Set.of(StandardOpenOption.READ,StandardOpenOption.WRITE,
            StandardOpenOption.CREATE,StandardOpenOption.CREATE_NEW,LinkOption.NOFOLLOW_LINKS);
    private static final Map<Object,Owned> OWNED=new HashMap<>();
    private static final Map<Object,Integer> OPEN=new HashMap<>();
    private MembershipFileAccess(){}
    static synchronized Owned own(Path requested,boolean create,boolean force,Consumer<FileChannel> opened)throws IOException {
        Path path=AdmissionPaths.safe(requested);
        if(!create){AdmissionPaths.regular(path);available(MembershipBasisSources.key(path));}
        FileChannel channel=FileChannel.open(path,create?Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.READ,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS):
                Set.of(StandardOpenOption.READ,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));
        try {
            opened.accept(channel);
            Object key=MembershipBasisSources.key(path);available(key);
            var lock=channel.tryLock();if(lock==null)throw new ReplicationException(ReplicationException.Reason.STORAGE_FAILURE,"membership file already owned");
            if(channel.size()!=0)throw new ReplicationException(ReplicationException.Reason.INTEGRITY_FAILURE,"membership lock file is not empty");
            if(force && create){channel.force(true);AdmissionPaths.forceDirectory(path.getParent());}
            var result=new Owned(key,new AdmissionPaths.Owner(channel,lock));OWNED.put(key,result);return result;
        }catch(IOException|RuntimeException|Error error){try{channel.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private static void available(Object key) {
        if(OWNED.containsKey(key) || OPEN.containsKey(key))throw new ReplicationException(ReplicationException.Reason.STORAGE_FAILURE,"membership file has an existing owner or open view");
    }
    static final class Owned implements AutoCloseable {
        private final Object key;private final AdmissionPaths.Owner owner;private boolean transferred;
        private Owned(Object key,AdmissionPaths.Owner owner){this.key=key;this.owner=owner;}
        FileChannel channel(){synchronized(MembershipFileAccess.class){require(!transferred,"file custody transferred");return owner.channel();}}
        FileLock lock(){synchronized(MembershipFileAccess.class){require(!transferred,"file custody transferred");return owner.lock();}}
        Owned transfer() {
            synchronized(MembershipFileAccess.class) {
                require(!transferred && OWNED.get(key)==this && owner.channel().isOpen() && owner.lock().isValid(),"file custody unavailable");
                var next=new Owned(key,owner);OWNED.put(key,next);transferred=true;return next;
            }
        }
        @Override public void close()throws IOException {
            synchronized(MembershipFileAccess.class) {
                if(transferred)return;
                try{owner.close();}finally{if(!owner.channel().isOpen())OWNED.remove(key,this);}
            }
        }
    }
    static FileChannel open(Path path,OpenOption... options)throws IOException {return open(path,Set.of(options));}
    static synchronized FileChannel open(Path requested,Set<? extends OpenOption> options)throws IOException {
        Path path=AdmissionPaths.safe(requested);
        require(OPTIONS.containsAll(options),"unsupported membership file open options");
        var requestedOptions=new HashSet<OpenOption>(options);requestedOptions.add(LinkOption.NOFOLLOW_LINKS);
        boolean write=requestedOptions.contains(StandardOpenOption.WRITE),read=requestedOptions.contains(StandardOpenOption.READ) || !write;
        Object before=null;
        if(Files.exists(path,LinkOption.NOFOLLOW_LINKS)) {
            AdmissionPaths.regular(path);before=MembershipBasisSources.key(path);var owner=OWNED.get(before);
            if(owner!=null) {
                if(requestedOptions.contains(StandardOpenOption.CREATE_NEW))throw new FileAlreadyExistsException(path.toString());
                require(Set.<OpenOption>of(StandardOpenOption.READ,StandardOpenOption.WRITE,StandardOpenOption.CREATE,LinkOption.NOFOLLOW_LINKS).containsAll(requestedOptions),
                        "unsupported operation on an owned membership file");
                require(owner.channel().isOpen() && owner.lock().isValid(),"membership file owner unavailable");
                return new View(before,owner.channel(),owner,read,write);
            }
        }
        var channel=FileChannel.open(path,requestedOptions);
        try {
            Object key=MembershipBasisSources.key(path);require(before==null || before.equals(key),"membership file replaced during open");
            require(!OWNED.containsKey(key),"membership file became owned during open");
            OPEN.merge(key,1,Integer::sum);return new View(key,channel,null,read,write);
        }catch(IOException|RuntimeException|Error error){try{channel.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private static final class View extends FileChannel {
        private final Object key;private final FileChannel channel;private final Owned owner;
        private final boolean readable,writable;private long cursor;
        private View(Object key,FileChannel channel,Owned owner,boolean readable,boolean writable) {
            this.key=key;this.channel=channel;this.owner=owner;this.readable=readable;this.writable=writable;
        }
        private void check()throws IOException {
            if(!isOpen() || !channel.isOpen())throw new ClosedChannelException();
            if(owner!=null)synchronized(MembershipFileAccess.class){require(OWNED.get(key)==owner && owner.lock().isValid(),"membership borrowed owner revoked");}
            // Renames are checked by the owning transaction. Existing views keep
            // their original descriptor; a new path must resolve that same inode.
        }
        private void reading()throws IOException {check();if(!readable)throw new NonReadableChannelException();}
        private void writing()throws IOException {check();if(!writable)throw new NonWritableChannelException();}
        @Override public synchronized int read(ByteBuffer dst)throws IOException {reading();int n=channel.read(dst,cursor);if(n>0)cursor+=n;return n;}
        @Override public synchronized int write(ByteBuffer src)throws IOException {writing();int n=channel.write(src,cursor);cursor+=n;return n;}
        @Override public int read(ByteBuffer dst,long position)throws IOException {reading();return channel.read(dst,position);}
        @Override public int write(ByteBuffer src,long position)throws IOException {writing();return channel.write(src,position);}
        @Override public synchronized long read(ByteBuffer[] dst,int offset,int length)throws IOException {
            Objects.checkFromIndexSize(offset,length,dst.length);reading();long total=0;
            for(int n=offset;n<offset+length;n++){int count=read(dst[n]);if(count<0)return total==0?-1:total;total+=count;if(dst[n].hasRemaining())break;}return total;
        }
        @Override public synchronized long write(ByteBuffer[] src,int offset,int length)throws IOException {
            Objects.checkFromIndexSize(offset,length,src.length);writing();long total=0;
            for(int n=offset;n<offset+length;n++){total+=write(src[n]);if(src[n].hasRemaining())break;}return total;
        }
        @Override public synchronized long position()throws IOException {check();return cursor;}
        @Override public synchronized FileChannel position(long position)throws IOException {check();if(position<0)throw new IllegalArgumentException("negative position");cursor=position;return this;}
        @Override public long size()throws IOException {check();return channel.size();}
        @Override public synchronized FileChannel truncate(long size)throws IOException {writing();channel.truncate(size);if(cursor>size)cursor=size;return this;}
        @Override public void force(boolean metadata)throws IOException {check();channel.force(metadata);}
        @Override public long transferTo(long position,long count,WritableByteChannel target)throws IOException {reading();return channel.transferTo(position,count,target);}
        @Override public long transferFrom(ReadableByteChannel source,long position,long count)throws IOException {writing();return channel.transferFrom(source,position,count);}
        @Override public MappedByteBuffer map(MapMode mode,long position,long size)throws IOException {check();throw new UnsupportedOperationException("membership file views cannot escape through mappings");}
        @Override public FileLock lock(long position,long size,boolean shared)throws IOException {check();throw new UnsupportedOperationException("membership file views do not grant ownership");}
        @Override public FileLock tryLock(long position,long size,boolean shared)throws IOException {return lock(position,size,shared);}
        @Override protected void implCloseChannel()throws IOException {
            if(owner!=null)return;
            synchronized(MembershipFileAccess.class) {
                try{channel.close();}finally{if(!channel.isOpen())OPEN.compute(key,(k,n)->n==null || n==1?null:n-1);}
            }
        }
    }
}
