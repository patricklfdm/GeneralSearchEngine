package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Local owned directories and real deletion; historical membership edges remain fixture observations. */
public final class V53RetirementWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static void provision(Path path,int size,int through)throws Exception {
        var f=new V53CurrentGenerationFixture(size,through,false);V53FloorWorker.provision(path,size,through,1);
        Path inputs=path.getParent().resolve("inputs");Files.createDirectory(inputs);var copies=new ArrayList<MembershipFloor.Copy>();var offers=new ArrayList<MembershipSelection.Source>();
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var store=MembershipGrantJournal.openRetirement(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,e->{})) {
            copies.add(store.floorCopyCurrent());
            for(int node=2;node<=size/2+1;node++) {
                Path peer=inputs.resolve("node-"+node);V53FloorWorker.provision(peer,size,through,node);var used=new MembershipResources(512*MembershipResources.MIB);
                try(var other=MembershipGrantJournal.openRetirement(peer,f.root(),V53DeclarationsTest.node(node),used,f::verify,e->{})) {
                    copies.add(other.floorCopyCurrent());other.prepareCurrent(f.fixture.source.ballot(100));offers.add(other.originalSource());
                }
                if(used.usage().leases()!=0)throw new IllegalStateException("peer retirement lease leaked");
            }
            store.establishFloor(copies);store.prepareCurrent(f.fixture.source.ballot(100));offers.addFirst(store.originalSource());
            store.selectCurrent(offers,List.of());store.installCurrent(offers,List.of(),f.fixture.source.images);
        }
        if(resources.usage().leases()!=0)throw new IllegalStateException("retirement setup lease leaked");
    }
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";var fixture=new V53CurrentGenerationFixture(size,through,false);
        String eventName=point.split("@")[0];int occurrence=point.contains("@")?Integer.parseInt(point.split("@")[1]):1;int[] seen={0};
        try {
            if(!Set.of("init","retire","inspect").contains(command))throw new IllegalArgumentException("unknown retirement command");
            if(command.equals("init")){provision(path,size,through);print(map("command",command,"status","PASS"));return;}
            var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=MembershipGrantJournal.openRetirement(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,event->{
                print(map("event",event));
                if(event.equals(eventName) && ++seen[0]==occurrence) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                var result=command.equals("retire")?store.retireInactive():Optional.<Decoded>empty();
                var floor=store.governingFloor().orElseThrow();String selector=hash(Files.readAllBytes(path.resolve("selector.gsr")));
                print(map("command",command,"status","PASS","retirement",result.map(Decoded::digest).orElse(null),"floor",floor.digest(),"selector",selector,"networkAck",false));
            }
            if(resources.usage().leases()!=0)throw new IllegalStateException("retirement lease leaked");
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
