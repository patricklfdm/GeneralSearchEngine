package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.function.BiConsumer;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test observations only: append exact canonical rows without retaining their payloads.
 * Reads materialize one row. No force, protocol action, retry or resource authority is issued.
 * A failed append poisons the history; close cannot turn a dropped row into valid evidence. */
final class V53EvidenceSpool extends AbstractList<Map<String,Object>> implements AutoCloseable {
    private static final int ROW_BYTES=16*1024*1024;
    private record Row(long offset,int bytes,byte[] digest) {}
    private final Path path;
    private final long maximum;
    private final FileChannel file;
    private final Object identity;
    private final BiConsumer<Integer,Map<String,Object>> beforeAppend;
    private final List<Row> rows=new ArrayList<>();
    private MessageDigest expected=digest();
    private long end;
    private boolean closed;
    private boolean observing;
    private String sealedDigest;
    private Throwable failure;

    V53EvidenceSpool(Path path,long maximum)throws IOException {
        this(path,maximum,(index,row)->{});
    }
    V53EvidenceSpool(Path path,long maximum,BiConsumer<Integer,Map<String,Object>> beforeAppend)throws IOException {
        require(maximum>=2,"evidence spool byte capacity");
        this.beforeAppend=Objects.requireNonNull(beforeAppend);
        this.path=path;this.maximum=maximum;
        file=FileChannel.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.READ,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
        try {
            var attributes=attributes();identity=attributes.fileKey();
            require(identity!=null && attributes.size()==0,"evidence spool initial identity");
            write(new byte[]{'['});end=1;
        } catch(IOException|RuntimeException|Error error) {try{file.close();}catch(IOException close){error.addSuppressed(close);}throw error;}
    }
    private BasicFileAttributes attributes()throws IOException {
        var value=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
        require(value.isRegularFile() && !value.isSymbolicLink(),"evidence spool regular file");return value;
    }
    private void unchanged()throws IOException {
        var value=attributes();
        require(identity.equals(value.fileKey()) && value.size()==end && file.size()==end,"evidence spool file changed");
    }
    private void active() {
        require(!closed,"evidence spool closed");
        if(failure!=null)throw new IllegalStateException("evidence spool failed",failure);
    }
    private void write(byte[] bytes)throws IOException {
        var buffer=ByteBuffer.wrap(bytes);while(buffer.hasRemaining())file.write(buffer);expected.update(bytes);
    }
    private static MessageDigest digest() {
        try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException error){throw new AssertionError(error);}
    }
    private void copyPrefix(FileChannel target,boolean retainDigest)throws IOException {
        byte[] wanted=expected.digest();var observed=digest();var continuing=retainDigest?digest():null;
        var buffer=ByteBuffer.allocate(64*1024);long position=0;
        while(position<end) {
            buffer.clear();buffer.limit((int)Math.min(buffer.capacity(),end-position));
            int count=file.read(buffer,position);if(count<0)throw new EOFException("evidence snapshot truncated source");
            position+=count;buffer.flip();observed.update(buffer.asReadOnlyBuffer());
            if(continuing!=null)continuing.update(buffer.asReadOnlyBuffer());
            if(target!=null)while(buffer.hasRemaining())target.write(buffer);
        }
        unchanged();require(MessageDigest.isEqual(wanted,observed.digest()),"evidence spool content changed");
        if(continuing!=null)expected=continuing;
    }
    private RuntimeException poison(Exception error) {
        if(failure==null)failure=error instanceof IOException io?new UncheckedIOException(io):(RuntimeException)error;
        return failure instanceof RuntimeException runtime?runtime:new IllegalStateException("evidence spool failed",failure);
    }
    @Override public synchronized boolean add(Map<String,Object> row) {
        active();
        try {
            require(!observing,"evidence spool recursive append");
            unchanged();require(rows.size()<V53EvidenceArray.HISTORY_ROWS,"evidence spool row capacity");
            byte[] bytes=canonical(Objects.requireNonNull(row),(int)Math.min(maximum,ROW_BYTES));int comma=rows.isEmpty()?0:1;
            require(bytes.length<=maximum-end-comma-1,"evidence spool byte capacity");
            observing=true;
            try{beforeAppend.accept(rows.size(),row);}finally{observing=false;}
            active(); // A callback cannot catch a nested failure and restore eligibility.
            if(comma!=0)write(new byte[]{','});long offset=end+comma;write(bytes);
            end=offset+bytes.length;rows.add(new Row(offset,bytes.length,sha(bytes)));modCount++;return true;
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
    }
    @Override public synchronized Map<String,Object> get(int index) {
        active();var row=rows.get(index);
        try {
            unchanged();var bytes=ByteBuffer.allocate(row.bytes());long position=row.offset();
            while(bytes.hasRemaining()) {
                int count=file.read(bytes,position);if(count<0)throw new EOFException("evidence spool truncated row");position+=count;
            }
            unchanged();require(MessageDigest.isEqual(row.digest(),sha(bytes.array())),"evidence spool content changed");
            return object(parse(bytes.array(),ROW_BYTES));
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
    }
    @Override public synchronized int size(){return rows.size();}
    long maximum(){return maximum;}
    /** Digest of the bytes checked and sealed by close, bound to the admitted
     * output path. Independent replay still checks those bytes against the index. */
    synchronized String sealedSha256(Path expectedPath) {
        require(closed && failure==null && sealedDigest!=null,"evidence spool not sealed");
        require(path.toAbsolutePath().normalize().equals(expectedPath.toAbsolutePath().normalize()),"evidence spool seal path");
        return sealedDigest;
    }
    /** Copy this exact prefix with fixed-size buffers. Later callbacks may append
     * to this spool but cannot change the exclusively created snapshot. */
    synchronized void snapshot(Path destination) {
        active();
        try {
            require(!observing,"evidence spool recursive snapshot");
            unchanged();
            try(var target=FileChannel.open(destination,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                var before=Files.readAttributes(destination,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
                require(before.isRegularFile() && before.fileKey()!=null,"evidence snapshot regular file");
                copyPrefix(target,true);
                var copied=Files.readAttributes(destination,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
                require(copied.isRegularFile() && before.fileKey().equals(copied.fileKey()) && copied.size()==end && target.size()==end,
                        "evidence snapshot file changed");
                var delimiter=ByteBuffer.wrap(new byte[]{']'});while(delimiter.hasRemaining())target.write(delimiter);
                var after=Files.readAttributes(destination,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
                require(after.isRegularFile() && before.fileKey().equals(after.fileKey()) && after.size()==end+1 && target.size()==end+1,
                        "evidence snapshot file changed");
            }
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
    }
    @Override public synchronized void close()throws IOException {
        if(closed)return;
        if(failure!=null) {
            // A try-with-resources body may be unwinding this very failure.
            // Rethrowing that same object from close would self-suppress it.
            try(file){throw new IllegalStateException("evidence spool failed",failure);}
            finally{closed=true;}
        }
        try(file) {
            active();require(!observing,"evidence spool recursive close");
            unchanged();copyPrefix(null,true);write(new byte[]{']'});end++;unchanged();
            sealedDigest=HexFormat.of().formatHex(expected.digest());
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
        finally {closed=true;}
    }
}
