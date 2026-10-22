package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh-process physical retention probe; supplied semantic ownership remains a test fixture. */
public final class V53BasisSourcesWorker {
    private static void print(Map<String,Object> value) {System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args) throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]);
        try {
            if(!Set.of("init","prepare").contains(command))throw new IllegalArgumentException("unknown retained source command");
            if(command.equals("init")) {
                V53BallotAllocatorWorker.provision(path,size);AdmissionPaths.write(path.resolve(MembershipGrantJournal.FILE),new byte[0]);
                Files.createDirectory(path.resolve(MembershipBasisSources.DIRECTORY));AdmissionPaths.forceDirectory(path);
                print(map("status","PASS","command",command));return;
            }
            long counter=Long.parseLong(args[3]);int through=Integer.parseInt(args[4]);
            String point=args.length>5?args[5]:"none",mode=args.length>6?args[6]:"none";
            var fixture=new V53CapsuleFixture(size,"REPLACE",through);var source=fixture.verify();
            try(var store=MembershipGrantJournal.openRetained(path,V53BallotAllocatorWorker.root(fixture.source),V53DeclarationsTest.node(1),
                    new MembershipResources(512*MembershipResources.MIB),event->{
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
                Decoded basis=store.prepare(source,fixture.source.ballot(counter),null,fixture.source.images);
                print(map("status","PASS","command",command,"counter",counter,"basis",basis.digest(),"cut",object(basis.value().get("cut")).get("index")));
            }
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
