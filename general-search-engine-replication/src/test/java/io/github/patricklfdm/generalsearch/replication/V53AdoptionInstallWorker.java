package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh-process adoption transaction probe. Historical remote forces remain fixture observations. */
public final class V53AdoptionInstallWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args) throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        try {
            if(!Set.of("init","adopt","advance","same").contains(command))throw new IllegalArgumentException("unknown adoption install command");
            var f=new V53AdoptionFenceFixture(size,through);String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";
            if(command.equals("init")) {
                f.provision(path);Path inputs=path.getParent().resolve("inputs");Files.createDirectory(inputs);
                Files.write(inputs.resolve("source.gscp"),f.remote.packet().bytes());
                for(var image:f.remote.source.images.entrySet())Files.write(inputs.resolve(image.getKey()+".image"),image.getValue());
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
                if(command.equals("advance") || command.equals("same")) {
                    var basis=store.prepareCurrent(f.initial.fixture.source.ballot(command.equals("same")?24+through:50));
                    print(map("command",command,"status","PASS","basis",basis.digest(),"cut",basis.value().get("cut")));return;
                }
                var manifest=store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
                print(map("command",command,"status","PASS","manifest",manifest.digest(),"cut",manifest.value().get("cut"),
                        "selection",manifest.value().get("selection"),"ownedTail",manifest.value().get("ownedTail"),"localInstallation",true,"networkAck",false));
            }
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
