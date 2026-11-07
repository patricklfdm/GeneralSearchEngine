package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Separate large-history test format, never selected by an ordinary EMPTY gate.
 * Payloads live in sealed segments; only offsets and hashes remain in memory.
 * Snapshots seal a prefix and rotate before subsequent observations. No protocol
 * action, force, retry, or runtime-resource claim is made by this collector. */
final class V53SegmentedEvidence extends AbstractList<Map<String,Object>> implements AutoCloseable {
    static final int ROW_BYTES=16*1024*1024,SEGMENT_BYTES=64*1024*1024,SEGMENTS=4096,CUTS=16;
    static final long MAXIMUM=128L*1024*1024*1024;
    static final String SCHEMA="gse-v53-segmented-evidence-v1";
    /** Shared capture-file accounting, distinct from production resource pools.
     * Failed reservations remain failed and cannot be reused by another history. */
    static final class Budget {
        private final long maximum;
        private long used;
        private boolean failed;
        Budget(long maximum){require(maximum>=0 && maximum<=MAXIMUM,"segmented evidence shared limit");this.maximum=maximum;}
        synchronized void reserve(long bytes) {
            require(!failed,"segmented evidence shared budget failed");
            if(bytes<0 || bytes>maximum-used){failed=true;throw new IllegalArgumentException("segmented evidence shared byte capacity");}
            used+=bytes;
        }
        synchronized long used(){return used;}
    }
    private record Row(int segment,long offset,int bytes,byte[] digest) {}
    private record Segment(Path path,Object identity,long bytes,int rows,String hash) {
        Map<String,Object> descriptor(){return Map.of("path",path.getFileName().toString(),"bytes",bytes,"rows",rows,"sha256",hash);}
    }
    private final Path root,segmentsPath,cutsPath;
    private final Object rootIdentity,segmentsIdentity,cutsIdentity;
    private final long maximum;
    private final Budget aggregate;
    private final List<Row> rows=new ArrayList<>();
    private final List<Segment> segments=new ArrayList<>();
    private final Set<String> cuts=new HashSet<>();
    private final List<Segment> cutFiles=new ArrayList<>();
    private FileChannel file;
    private Path path;
    private Object identity;
    private MessageDigest expected;
    private long total,end;
    private int segmentRows;
    private boolean closed;
    private Throwable failure;

    V53SegmentedEvidence(Path root,long maximum)throws IOException {
        this(root,maximum,null);
    }
    V53SegmentedEvidence(Path root,long maximum,Budget aggregate)throws IOException {
        require(maximum>=0 && maximum<=MAXIMUM,"segmented evidence byte limit");
        this.root=root;this.maximum=maximum;this.aggregate=aggregate;
        Files.createDirectory(root);segmentsPath=Files.createDirectory(root.resolve("segments"));cutsPath=Files.createDirectory(root.resolve("cuts"));
        rootIdentity=directory(root);segmentsIdentity=directory(segmentsPath);cutsIdentity=directory(cutsPath);
    }
    private static Object directory(Path path)throws IOException {
        var a=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
        require(a.isDirectory() && !a.isSymbolicLink() && a.fileKey()!=null,"segmented evidence directory");return a.fileKey();
    }
    private void directories()throws IOException {
        require(rootIdentity.equals(directory(root)) && segmentsIdentity.equals(directory(segmentsPath)) &&
                cutsIdentity.equals(directory(cutsPath)),"segmented evidence directory changed");
    }
    private static BasicFileAttributes regular(Path path)throws IOException {
        var a=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
        require(a.isRegularFile() && !a.isSymbolicLink() && a.fileKey()!=null,"segmented evidence regular file");return a;
    }
    private static MessageDigest digest() {
        try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}
    }
    private static String hex(byte[] bytes){return HexFormat.of().formatHex(bytes);}
    private void active() {
        require(!closed,"segmented evidence closed");
        if(failure!=null)throw new IllegalStateException("segmented evidence failed",failure);
    }
    private RuntimeException poison(Exception error) {
        if(failure==null)failure=error instanceof IOException io?new UncheckedIOException(io):(RuntimeException)error;
        return failure instanceof RuntimeException e?e:new IllegalStateException("segmented evidence failed",failure);
    }
    private void unchanged(Path path,Object identity,long length)throws IOException {
        directories();var a=regular(path);
        require(identity.equals(a.fileKey()) && a.size()==length,"segmented evidence file changed");
    }
    private void openSegment()throws IOException {
        require(segments.size()<SEGMENTS,"segmented evidence segment capacity");
        path=segmentsPath.resolve(String.format(Locale.ROOT,"segment-%04d.jsonl",segments.size()));
        file=FileChannel.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
        identity=regular(path).fileKey();expected=digest();end=0;segmentRows=0;
    }
    private void write(byte[] bytes)throws IOException {
        var b=ByteBuffer.wrap(bytes);while(b.hasRemaining())file.write(b);expected.update(bytes);
    }
    private void verify(Segment segment)throws IOException {
        unchanged(segment.path,segment.identity,segment.bytes);var observed=digest();
        try(var input=FileChannel.open(segment.path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
            var buffer=ByteBuffer.allocate(64*1024);long count=0;
            while(count<segment.bytes) {
                buffer.clear();buffer.limit((int)Math.min(buffer.capacity(),segment.bytes-count));
                int n=input.read(buffer);if(n<=0)throw new EOFException("segmented evidence truncated file");
                count+=n;buffer.flip();observed.update(buffer);
            }
            require(input.size()==segment.bytes,"segmented evidence file changed");
        }
        unchanged(segment.path,segment.identity,segment.bytes);
        require(hex(observed.digest()).equals(segment.hash),"segmented evidence content changed");
    }
    private void sealSegment()throws IOException {
        if(file==null)return;
        var segment=new Segment(path,identity,end,segmentRows,hex(expected.digest()));
        try{verify(segment);}finally{file.close();file=null;}
        segments.add(segment);
    }
    private Map<String,Object> index() {
        return Map.of("schema",SCHEMA,"rows",rows.size(),"bytes",total,
                "segments",segments.stream().map(Segment::descriptor).toList());
    }
    private Segment index(Path destination)throws IOException {
        byte[] bytes=canonical(index(),ROW_BYTES);
        if(aggregate!=null)aggregate.reserve(bytes.length);
        Files.write(destination,bytes,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
        return new Segment(destination,regular(destination).fileKey(),bytes.length,0,hex(sha(bytes)));
    }
    @Override public synchronized boolean add(Map<String,Object> row) {
        active();
        try {
            directories();require(rows.size()<V53EvidenceArray.HISTORY_ROWS,"segmented evidence row capacity");
            byte[] bytes=canonical(Objects.requireNonNull(row),ROW_BYTES);
            require(bytes.length+1L<=maximum-total,"segmented evidence byte capacity");
            if(aggregate!=null)aggregate.reserve(bytes.length+1L);
            if(file!=null){unchanged(path,identity,end);if(bytes.length+1L>SEGMENT_BYTES-end)sealSegment();}
            if(file==null)openSegment();
            long offset=end;write(bytes);write(new byte[]{'\n'});end+=bytes.length+1L;total+=bytes.length+1L;segmentRows++;
            rows.add(new Row(segments.size(),offset,bytes.length,sha(bytes)));modCount++;return true;
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
    }
    @Override public synchronized Map<String,Object> get(int index) {
        active();var row=rows.get(index);
        try {
            Path source;Object key;long length;
            if(row.segment<segments.size()){var s=segments.get(row.segment);source=s.path;key=s.identity;length=s.bytes;}
            else{source=path;key=identity;length=end;}
            unchanged(source,key,length);var buffer=ByteBuffer.allocate(row.bytes);
            try(var input=FileChannel.open(source,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
                long position=row.offset;
                while(buffer.hasRemaining()) {int n=input.read(buffer,position);if(n<=0)throw new EOFException("segmented evidence truncated row");position+=n;}
            }
            unchanged(source,key,length);require(MessageDigest.isEqual(sha(buffer.array()),row.digest),"segmented evidence content changed");
            return object(parse(buffer.array(),ROW_BYTES));
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
    }
    @Override public synchronized int size(){return rows.size();}
    synchronized void snapshot(String name) {
        active();
        try {
            directories();require(name!=null && name.matches("[a-z][a-z0-9-]{0,63}") && cuts.size()<CUTS && !cuts.contains(name),"segmented evidence cut");
            sealSegment();for(var segment:segments)verify(segment);
            for(var cut:cutFiles)verify(cut);
            cutFiles.add(index(cutsPath.resolve(name+".json")));cuts.add(name);
        }catch(IOException|RuntimeException error){throw poison(error);}
        catch(Error error){failure=error;throw error;}
    }
    @Override public synchronized void close()throws IOException {
        if(closed)return;
        try {
            if(failure!=null)throw new IllegalStateException("segmented evidence failed",failure);
            directories();sealSegment();for(var segment:segments)verify(segment);
            for(var cut:cutFiles)verify(cut);
            index(root.resolve("complete.json"));
        }catch(IOException|RuntimeException error){if(failure==null)failure=error;throw error;}
        catch(Error error){failure=error;throw error;}
        finally {
            closed=true;
            if(file!=null)try{file.close();}catch(IOException error){if(failure==null)throw error;failure.addSuppressed(error);}finally{file=null;}
        }
    }
}
