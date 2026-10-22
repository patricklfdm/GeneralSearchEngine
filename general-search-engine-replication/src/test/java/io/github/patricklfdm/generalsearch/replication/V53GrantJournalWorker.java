package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Metadata-only process probe. Fixture source ownership is conditional, never public grant evidence. */
public final class V53GrantJournalWorker {
    private static void print(Map<String,Object> value) {System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static void retain(Path path,byte[] bytes) throws Exception {
        if(Files.exists(path))AdmissionPaths.exact(path,bytes);else AdmissionPaths.write(path,bytes);
    }
    public static void main(String[] args) throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]);
        try {
            if(!Set.of("init","prepare","inspect").contains(command))throw new IllegalArgumentException("unknown grant probe command");
            if(command.equals("init")) {
                V53BallotAllocatorWorker.provision(path,size);AdmissionPaths.write(path.resolve(MembershipGrantJournal.FILE),new byte[0]);
                print(map("status","PASS","command",command));return;
            }
            long counter=args.length>3?Long.parseLong(args[3]):20;int through=args.length>4?Integer.parseInt(args[4]):0;
            String point=args.length>5?args[5]:"none",mode=args.length>6?args[6]:"none";
            var fixture=new V53CapsuleFixture(size,"REPLACE",through);var source=fixture.verify();
            retain(path.getParent().resolve("source-c"+through+".packet"),MembershipSourcePacket.encode(source.packet.capsule(),fixture.objects,fixture.images));
            for(var image:fixture.source.images.entrySet())retain(path.getParent().resolve("image-"+image.getKey()+".bin"),image.getValue());
            try(var store=MembershipGrantJournal.open(path,V53BallotAllocatorWorker.root(fixture.source),V53DeclarationsTest.node(1),MembershipGrantJournal.MAXIMUM,event->{
                print(map("event",event));
                if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",event));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                Decoded basis=command.equals("prepare")?store.prepare(source,fixture.source.ballot(counter),null):store.originalBasis().orElse(null);
                var promise=store.promised().orElse(null);
                print(map("status","PASS","command",command,"counter",promise==null?null:object(promise.value().get("ballot")).get("counter"),
                        "basis",basis==null?null:basis.digest(),"cut",basis==null?null:object(basis.value().get("cut")).get("index")));
            }
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
