package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

/** Physical copies of compacted fixture history. No replica runtime or deletion is enabled. */
public final class V53CapsuleWorker {
    private static void force(Path root,String name,byte[] bytes,List<Map<String,Object>> events) throws Exception {
        Path path=root.resolve(name);Files.createDirectories(path.getParent());
        try(var channel=FileChannel.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
            var buffer=ByteBuffer.wrap(bytes);while(buffer.hasRemaining())channel.write(buffer);channel.force(true);
        }
        events.add(map("sequence",(long)events.size()+1,"path",name,"sha256",hash(bytes)));
    }
    public static void main(String[] args) throws Exception {
        Path output=Files.createDirectory(Path.of(args[0]));V53ContextWorker.main(new String[]{output.resolve("source").toString()});
        for(Object[] p:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}}) {
            String profile=p[0]+"-"+p[1];Path directory=Files.createDirectories(output.resolve("capsules").resolve(profile));
            for(int through=0;through<=9;through++) {
                Path root=Files.createDirectory(directory.resolve("cut-"+through));var f=new V53CapsuleFixture((int)p[0],(String)p[1],through);f.verify();
                var packet=f.packet();byte[] bytes=MembershipSourcePacket.encode(packet.capsule(),f.objects,f.images);
                Files.write(root.resolve("packet.bin"),bytes,StandardOpenOption.CREATE_NEW);Files.createDirectory(root.resolve("images"));
                for(var image:f.source.images.entrySet())Files.write(root.resolve("images").resolve(image.getKey()+".bin"),image.getValue(),StandardOpenOption.CREATE_NEW);
                var owned=new ArrayList<Map<String,Object>>();var events=new ArrayList<Map<String,Object>>();
                for(Object value:list(packet.capsule().value().get("items"))) {
                    var item=object(value);var statement=decode(f.objects.get(item.get("statement")),"records","CHECKPOINT").value();
                    for(Object hash:list(item.get("endorsements"))) {
                        byte[] ackBytes=f.objects.get(hash);var ack=decode(ackBytes,"records","CHECKPOINT_ACK").value();
                        String stem="owned/"+ack.get("voter")+"/"+ack.get("incarnation")+"/"+hash;
                        var applied=map("root",f.source.rootHash,"voter",ack.get("voter"),"storage",ack.get("incarnation"),
                                "cut",statement.get("end"),"catalog",statement.get("catalogAfter"),"application",statement.get("applicationAfter"));
                        force(root,stem+".applied",canonical(applied,16384),events);force(root,stem+".bin",ackBytes,events);
                        owned.add(map("voter",ack.get("voter"),"storage",ack.get("incarnation"),"ack",stem+".bin","applied",stem+".applied"));
                    }
                }
                Files.write(root.resolve("manifest.json"),canonical(map("schema","gse-v53-capsule-fixture-v1","profile",profile,"through",(long)through,
                        "packetSha256",hash(bytes),"runtimeEnabled",false,"authorityEvidence",false,"owned",owned,"forces",events),128*1024),StandardOpenOption.CREATE_NEW);
            }
        }
    }
}
