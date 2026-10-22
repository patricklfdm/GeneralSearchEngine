package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;
import static io.github.patricklfdm.generalsearch.replication.V53CapsuleWorker.force;

/** Source selection byte observations; these forces belong only to this fixture JVM. */
public final class V53SelectionWorker {
    public static void main(String[] args) throws Exception {
        Path output=Files.createDirectory(Path.of(args[0]));V53CapsuleWorker.main(new String[]{output.resolve("baseline").toString()});
        for(Object[] profile:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}}) {
            int size=(int)profile[0];String change=(String)profile[1],name=size+"-"+change;
            for(String scenario:List.of("heterogeneous","highest-tail","covered-tail","joint")) {
                Path root=Files.createDirectories(output.resolve("selections").resolve(name).resolve(scenario));
                var finalFixture=new V53SelectionFixture(size,change,scenario.equals("joint")?6:9);
                var voters=new TreeSet<>(finalFixture.capsule.verify().context.voters());var sources=new ArrayList<MembershipSelection.Source>();
                var forces=new ArrayList<Map<String,Object>>();int n=0;
                for(String voter:voters) {
                    int through=scenario.equals("joint")?6:scenario.equals("heterogeneous")?Math.min(7+n,9):scenario.equals("covered-tail")&&n==0?8:9;
                    var fixture=new V53SelectionFixture(size,change,through);
                    String tail=scenario.equals("highest-tail")&&n<2?"tail-"+n:scenario.equals("covered-tail")&&n==0?"minority":null;
                    var source=fixture.source(voter,20,tail,n==1?8:2);sources.add(source);
                    var packet=source.capsule.packet;var objects=new TreeMap<String,byte[]>();for(String h:packet.objectNames())objects.put(h,packet.objectBytes(h));
                    String directory="sources/"+voter+"/";Files.createDirectories(root.resolve(directory+"images"));
                    Files.write(root.resolve(directory+"packet.bin"),MembershipSourcePacket.encode(packet.capsule(),objects,packet.images()),StandardOpenOption.CREATE_NEW);
                    for(var image:fixture.capsule.source.images.entrySet())Files.write(root.resolve(directory+"images/"+image.getKey()+".bin"),image.getValue(),StandardOpenOption.CREATE_NEW);
                    var parent=map("root",source.capsule.context.root,"voter",voter,"storage",source.owner.storageId().toString(),"cut",source.capsule.context.cut,
                            "catalog",packet.capsule().value().get("catalog"),"application",packet.capsule().value().get("application"));
                    force(root,directory+"parent.json",canonical(parent,16384),forces);
                    if(source.accepted!=null)force(root,directory+"accepted.bin",source.accepted.bytes(),forces);
                    force(root,directory+"basis.bin",source.basis.bytes(),forces);n++;
                }
                var bridges=new ArrayList<MembershipSelection.Bridge>();
                if(scenario.equals("heterogeneous")||scenario.equals("covered-tail")) {
                    var bridge=finalFixture.bridge(8,9);bridges.add(bridge);Files.createDirectories(root.resolve("bridge"));
                    Files.write(root.resolve("bridge/statement.bin"),bridge.statement.bytes(),StandardOpenOption.CREATE_NEW);
                    for(var ack:bridge.acknowledgements) {
                        var value=ack.value();String voter=(String)value.get("voter");var s=bridge.statement.value();
                        var applied=map("root",s.get("root"),"voter",voter,"storage",value.get("incarnation"),"cut",s.get("end"),
                                "catalog",s.get("catalogAfter"),"application",s.get("applicationAfter"));
                        force(root,"bridge/"+voter+".applied",canonical(applied,16384),forces);force(root,"bridge/"+voter+".bin",ack.bytes(),forces);
                    }
                }
                var decision=new MembershipSelection.Campaign(sources.getFirst()).select(sources,bridges);
                Files.write(root.resolve("selected.bin"),decision.selected().bytes(),StandardOpenOption.CREATE_NEW);
                Files.write(root.resolve("manifest.json"),canonical(map("schema","gse-v53-selection-fixture-v1","profile",name,"case",scenario,
                        "runtimeEnabled",false,"authorityEvidence",false,"forces",forces),128*1024),StandardOpenOption.CREATE_NEW);
            }
        }
    }
}
