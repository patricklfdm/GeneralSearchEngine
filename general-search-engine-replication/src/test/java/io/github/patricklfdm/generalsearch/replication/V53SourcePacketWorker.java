package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;

/** Internal packet fixture, not a public runtime or a recovery-authority receipt. */
public final class V53SourcePacketWorker {
    public static void main(String[] args) throws Exception {
        Path base=Files.createDirectory(Path.of(args[0]));
        for(boolean tail:new boolean[]{false,true}) {
            Path output=Files.createDirectory(base.resolve(tail?"accepted-tail":"initial"));var f=new V53SourcePacketTest.Fixture(tail);
            Files.write(output.resolve("packet.bin"),f.bytes(),StandardOpenOption.CREATE_NEW);
            Files.write(output.resolve("basis.bin"),f.basis().bytes(),StandardOpenOption.CREATE_NEW);
            Path images=Files.createDirectory(output.resolve("images"));
            for(var row:f.f.images.entrySet())Files.write(images.resolve(row.getKey()+".bin"),row.getValue(),StandardOpenOption.CREATE_NEW);
        }
    }
}
