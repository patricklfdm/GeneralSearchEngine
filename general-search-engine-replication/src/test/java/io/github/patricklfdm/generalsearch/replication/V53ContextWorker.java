package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

/** Single-process byte fixture producer. Force events describe fixture files, never a live consensus execution. */
public final class V53ContextWorker {
    private final Path output;
    private final List<Map<String,Object>> files=new ArrayList<>();
    private final List<Map<String,Object>> forces=new ArrayList<>();
    private V53ContextWorker(Path output) throws Exception {this.output=Files.createDirectory(output);}
    private void write(String name,byte[] bytes,boolean force) throws Exception {
        Path path=output.resolve(name);Files.createDirectories(path.getParent());
        try(var channel=FileChannel.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
            var buffer=ByteBuffer.wrap(bytes);while(buffer.hasRemaining())channel.write(buffer);
            if(force)channel.force(true);
        }
        files.add(map("path",name,"sha256",hash(bytes),"size",(long)bytes.length));
        if(force)forces.add(map("path",name,"sequence",(long)forces.size()+1,"sha256",hash(bytes)));
    }
    private void profile(int size,String change) throws Exception {
        var f=new V53ContextFixture(size,change);f.transition(change);String prefix=size+"-"+change+"/";
        for(var row:f.inventory.entrySet())write(prefix+"objects/"+row.getKey()+".bin",row.getValue(),false);
        for(var row:f.images.entrySet())write(prefix+"images/"+row.getKey()+".bin",row.getValue(),false);
        var observations=new ArrayList<Map<String,Object>>();
        for(var own:f.owned) {
            String stem=prefix+"owned/"+own.voter()+"/"+own.storage()+"/"+own.record();
            String parent=stem+".parent",record=stem+".bin";
            write(parent,canonical(f.parents.get(own.parent()),16384),true);
            write(record,f.inventory.get(own.record()),true);
            observations.add(map("parent",parent,"record",record,"storage",own.storage().toString(),"voter",own.voter()));
        }
        write(prefix+"history.json",canonical(map("root",f.root.digest(),"profile",size+"-"+change,
                "steps",f.steps,"owned",observations),1024*1024),false);
    }
    public static void main(String[] args) throws Exception {
        var writer=new V53ContextWorker(Path.of(args[0]));
        for(Object[] p:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}})
            writer.profile((int)p[0],(String)p[1]);
        var manifest=map("schema","gse-v53-context-fixture-v1","runtimeEnabled",false,"authorityEvidence",false,
                "execution","single-jvm-byte-fixture","files",writer.files,"forces",writer.forces);
        Files.write(writer.output.resolve("manifest.json"),canonical(manifest,2*1024*1024),StandardOpenOption.CREATE_NEW);
    }
}
