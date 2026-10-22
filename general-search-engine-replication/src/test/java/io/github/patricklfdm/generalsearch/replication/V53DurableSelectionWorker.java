package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Real local grant/selection forces; remote source observations are conditional fixture inputs. */
public final class V53DurableSelectionWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static List<MembershipSelection.Source> offers(MembershipGrantJournal store,int size,long ballot,boolean alternate) throws Exception {
        var sources=new ArrayList<MembershipSelection.Source>();sources.add(store.originalSource());int from=alternate?3:2;
        for(int i=from;i<from+size/2;i++)sources.add(remote(new V53SelectionFixture(size,"REPLACE",1),i,ballot));
        return sources;
    }
    static MembershipSelection.Source remote(V53SelectionFixture fixture,int node,long ballot) {
        var source=fixture.source("node-"+node,ballot,node==2?"selected-tail":null,5);
        var value=new TreeMap<>(source.basis.value());value.put("basisId",new UUID(ballot,node).toString());
        var basis=decode(encode("records","BASIS",value),"records","BASIS");var owned=new HashSet<>(fixture.capsule.owned);
        String parent=MembershipContext.cutDigest(source.capsule.context.cut);
        owned.add(new MembershipContext.Owned(source.owner.nodeId().value(),source.owner.storageId(),basis.digest(),parent));
        if(source.accepted!=null)owned.add(new MembershipContext.Owned(source.owner.nodeId().value(),source.owner.storageId(),source.accepted.digest(),parent));
        return MembershipSelection.Source.verify(source.capsule,basis,V53SelectionFixture.reference(basis),source.owner,owned);
    }
    public static void main(String[] args) throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]);boolean tail=Boolean.parseBoolean(args[3]);
        try {
            if(!Set.of("init","select","conflict","advance").contains(command))throw new IllegalArgumentException("unknown selection command");
            var f=new V53CurrentGenerationFixture(size,1,tail);String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";
            if(command.equals("init"))f.provision(path);
            try(var store=MembershipGrantJournal.openCurrent(path,f.root(),V53DeclarationsTest.node(1),new MembershipResources(512*MembershipResources.MIB),f::verify,event->{
                if(!command.equals("init"))print(map("event",event));
                if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                if(command.equals("init")) {
                    store.prepareCurrent(f.fixture.source.ballot(20));Path inputs=path.getParent().resolve("inputs");Files.createDirectory(inputs);
                    for(long ballot:List.of(20L,21L))for(int i=2;i<=size;i++) {
                        var fixture=new V53SelectionFixture(size,"REPLACE",1);var source=remote(fixture,i,ballot);
                        String name="c"+ballot+"-node-"+i;Files.write(inputs.resolve(name+".basis"),source.basis.bytes());Files.write(inputs.resolve(name+".gscp"),source.capsule.packet.bytes());
                        for(var image:fixture.capsule.source.images.entrySet()) {
                            Path target=inputs.resolve(image.getKey()+".image");if(!Files.exists(target))Files.write(target,image.getValue());
                        }
                    }
                    print(map("status","PASS","command",command));return;
                }
                boolean next=command.equals("advance");long ballot=next?21:20;
                if(next)store.prepareCurrent(f.fixture.source.ballot(ballot));
                var sources=offers(store,size,ballot,next || command.equals("conflict"));
                var result=store.selectCurrent(sources,List.of());
                print(map("status","PASS","command",command,"selection",result.digest(),"counter",ballot,
                        "cut",result.value().get("cut"),"sources",result.value().get("sources"),"nextEntry",result.value().get("nextEntry"),"installationAck",false));
            }
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
