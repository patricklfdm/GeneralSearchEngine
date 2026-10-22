package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Local install crash probe. Historical remote ownership remains explicitly conditional. */
public final class V53GenerationInstallWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args) throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]);boolean tail=Boolean.parseBoolean(args[3]);
        try {
            if(!Set.of("init","install","advance").contains(command))throw new IllegalArgumentException("unknown install command");
            var f=new V53GenerationInstallFixture(size,0,1,tail);String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";
            if(command.equals("init")) {
                f.provision(path);Path inputs=path.getParent().resolve("inputs");Files.createDirectory(inputs);
                for(int node=2;node<=1+size/2;node++) {
                    var source=f.remote(node,20,tail && node==2);String name="node-"+node;
                    Files.write(inputs.resolve(name+".basis"),source.basis.bytes());Files.write(inputs.resolve(name+".gscp"),source.capsule.packet.bytes());
                }
                for(var image:f.images().entrySet())Files.write(inputs.resolve(image.getKey()+".image"),image.getValue());
                print(map("command",command,"status","PASS"));return;
            }
            try(var store=f.open(path,new MembershipResources(512*MembershipResources.MIB),event->{
                print(map("event",event));
                if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                if(command.equals("advance")) {
                    var basis=store.prepareCurrent(f.initial.fixture.source.ballot(21));
                    print(map("command",command,"status","PASS","basis",basis.digest(),"cut",basis.value().get("cut")));return;
                }
                var installed=store.installCurrent(f.offers(store,20),f.bridges,f.images());
                print(map("command",command,"status","PASS","manifest",installed.digest(),"cut",installed.value().get("cut"),
                          "selection",installed.value().get("selection"),"ownedTail",installed.value().get("ownedTail"),"localInstallation",true,"networkAck",false));
            }
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
