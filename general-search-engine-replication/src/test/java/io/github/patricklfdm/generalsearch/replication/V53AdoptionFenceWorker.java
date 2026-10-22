package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Durable promise-fence probe only. It does not install the incoming prefix or issue a vote. */
public final class V53AdoptionFenceWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args) throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        try {
            if(!Set.of("init","adopt","same","old").contains(command))throw new IllegalArgumentException("unknown adoption command");
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
                if(command.equals("same") || command.equals("old")) {
                    store.prepareCurrent(f.initial.fixture.source.ballot(command.equals("same")?24+through:20));
                    print(map("command",command,"status","PASS","unexpectedGrant",true));return;
                }
                var fence=store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of());
                print(map("command",command,"status","PASS","promise",fence.digest(),"view",fence.value().get("view"),
                        "ballot",fence.value().get("ballot"),"hasBasis",store.originalBasis().isPresent(),"prefixInstalled",false,"networkAck",false));
            }
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
