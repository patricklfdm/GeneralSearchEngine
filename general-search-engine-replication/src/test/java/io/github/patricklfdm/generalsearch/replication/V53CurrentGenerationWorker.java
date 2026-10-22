package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Real selected-generation files; remote certificate observations remain test fixtures. */
public final class V53CurrentGenerationWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args) throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]);boolean tail=Boolean.parseBoolean(args[3]);
        try {
            if(!Set.of("init","prepare").contains(command))throw new IllegalArgumentException("unknown current generation command");
            var f=new V53CurrentGenerationFixture(size,1,tail);
            if(command.equals("init")){f.provision(path);print(map("status","PASS","command",command));return;}
            long counter=Long.parseLong(args[4]);String point=args.length>5?args[5]:"none",mode=args.length>6?args[6]:"none";
            try(var store=MembershipGrantJournal.openCurrent(path,f.root(),V53DeclarationsTest.node(1),new MembershipResources(512*MembershipResources.MIB),f::verify,event->{
                print(map("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                var basis=store.prepareCurrent(f.fixture.source.ballot(counter));var owned=store.currentOwnedTail().orElse(null);
                print(map("status","PASS","command",command,"basis",basis.digest(),"counter",counter,"cut",object(basis.value().get("cut")).get("index"),
                        "accepted",basis.value().get("accepted"),"ownedTail",owned==null?null:map("voter",owned.voter(),"storage",owned.storage().toString(),"record",owned.record(),"parent",owned.parent())));
            }
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
