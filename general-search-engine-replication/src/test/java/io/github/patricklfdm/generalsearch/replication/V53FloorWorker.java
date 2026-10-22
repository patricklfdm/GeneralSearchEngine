package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Real per-owner force observations; the certified historical edges remain fixture evidence. */
public final class V53FloorWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static void provision(Path path,int size,int through,int node)throws Exception {
        var f=new V53CurrentGenerationFixture(size,through,false);f.provision(path);String name="node-"+node;
        Files.write(path.resolve("node.gsr"),encode("records","NODE",map("identity",V53ContextFixture.member(node),"root",f.root().manifestDigest())));
        Files.write(path.resolve(MembershipBallotAllocator.CURRENT),encode("records","ALLOCATOR",map("counter",0L,"node",name,"root",f.root().manifestDigest())));
        var manifest=new TreeMap<>(decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value());manifest.put("node",name);
        byte[] raw=encode("records","GENERATION",manifest);Files.write(path.resolve("generations/a/generation.gsr"),raw);
        Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",map("root",f.root().manifestDigest(),"node",name,"generation","a","digest",hash(raw))));
    }
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";var f=new V53CurrentGenerationFixture(size,through,false);
        try {
            if(!Set.of("init","floor","inspect").contains(command))throw new IllegalArgumentException("unknown floor command");
            Path inputs=path.getParent().resolve("inputs");
            if(command.equals("init")) {
                provision(path,size,through,1);Files.createDirectory(inputs);
                for(int node=2;node<=size/2+1;node++)provision(inputs.resolve("node-"+node),size,through,node);
                print(map("command",command,"status","PASS"));return;
            }
            var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=MembershipGrantJournal.openFloors(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,event->{
                print(map("event",event,"node","node-1"));
                if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                Decoded floor;
                if(command.equals("inspect"))floor=store.governingFloor().orElseThrow();
                else {
                    var copies=new ArrayList<MembershipFloor.Copy>();copies.add(store.floorCopyCurrent());
                    for(int node=2;node<=size/2+1;node++) {
                        String name="node-"+node;var peerResources=new MembershipResources(512*MembershipResources.MIB);
                        try(var peer=MembershipGrantJournal.openFloors(inputs.resolve(name),f.root(),V53DeclarationsTest.node(node),peerResources,f::verify,event->print(map("event",event,"node",name)))) {
                            copies.add(peer.floorCopyCurrent());
                        }
                        if(peerResources.usage().leases()!=0)throw new IllegalStateException("peer floor lease leaked");
                    }
                    floor=store.establishFloor(copies);
                }
                print(map("command",command,"status","PASS","floor",floor.digest(),"cut",floor.value().get("cut"),"networkAck",false,"deletion",false));
            }
            if(resources.usage().leases()!=0)throw new IllegalStateException("floor lease leaked");
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
