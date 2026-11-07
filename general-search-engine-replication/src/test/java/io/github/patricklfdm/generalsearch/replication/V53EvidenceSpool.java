package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test observations only: append exact canonical rows without retaining their payloads.
 * Reads materialize one row. No force, protocol action, retry or resource authority is issued.
 * A failed append poisons the history; close cannot turn a dropped row into valid evidence. */
final class V53EvidenceSpool extends AbstractList<Map<String,Object>> implements AutoCloseable {
    private static final int ROW_BYTES=16*1024*1024;
    private record Row(long offset,int bytes) {}
    private final Path path;
    private final long maximum;
    private final FileChannel file;
    private final Object identity;
    private final List<Row> rows=new ArrayList<>();
    private long end;
    private boolean closed;
    private Throwable failure;

    V53EvidenceSpool(Path path,long maximum)throws IOException {
        require(maximum>=2,"evidence spool byte capacity");
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
        var buffer=ByteBuffer.wrap(bytes);while(buffer.hasRemaining())file.write(buffer);
    }
    private RuntimeException poison(Exception error) {
        if(failure==null)failure=error instanceof IOException io?new UncheckedIOException(io):(RuntimeException)error;
        return failure instanceof RuntimeException runtime?runtime:new IllegalStateException("evidence spool failed",failure);
    }
    @Override public synchronized boolean add(Map<String,Object> row) {
        active();
        try {
            unchanged();require(rows.size()<V53EvidenceArray.HISTORY_ROWS,"evidence spool row capacity");
            byte[] bytes=canonical(Objects.requireNonNull(row),(int)Math.min(maximum,ROW_BYTES));int comma=rows.isEmpty()?0:1;
            require(bytes.length<=maximum-end-comma-1,"evidence spool byte capacity");
            if(comma!=0)write(new byte[]{','});long offset=end+comma;write(bytes);
            end=offset+bytes.length;rows.add(new Row(offset,bytes.length));modCount++;return true;
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
            unchanged();return object(parse(bytes.array(),ROW_BYTES));
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
    }
    @Override public synchronized int size(){return rows.size();}
    long maximum(){return maximum;}
    @Override public synchronized void close()throws IOException {
        if(closed)return;
        try(file) {
            active();unchanged();write(new byte[]{']'});end++;unchanged();
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
        finally {closed=true;}
    }
}
