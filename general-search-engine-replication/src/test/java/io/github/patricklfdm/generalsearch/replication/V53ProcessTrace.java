package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.Map;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.canonical;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test observation order only. Does not force storage, grant authority or retry work. */
final class V53ProcessTrace {
    private static final Object LOCAL=new Object();
    private static final long MAXIMUM=64L*1024*1024;
    private final Path path;
    private final String origin;
    V53ProcessTrace(Path path,String origin,boolean create)throws IOException {
        require(origin.equals("parent") || origin.equals("halt") || origin.equals("kill") || origin.equals("resume"),"process trace origin");
        this.path=path;this.origin=origin;
        if(create)Files.createFile(path);
        require(Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(path),"process trace regular file");
    }
    void add(Map<String,Object> value) {
        byte[] row=canonical(Map.of("origin",origin,"value",value),16*1024*1024);
        // JVM file locks overlap rather than block inside one process. The
        // local monitor handles that case; the OS lock orders different JVMs.
        synchronized(LOCAL) {
            try(var file=FileChannel.open(path,StandardOpenOption.READ,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
                var lock=file.lock()) {
                long end=file.size();require(end+row.length+1<=MAXIMUM,"process trace capacity");
                file.position(end);var bytes=ByteBuffer.allocate(row.length+1).put(row).put((byte)'\n');bytes.flip();
                while(bytes.hasRemaining())file.write(bytes);
            }catch(IOException error){throw new UncheckedIOException(error);}
        }
    }
}
