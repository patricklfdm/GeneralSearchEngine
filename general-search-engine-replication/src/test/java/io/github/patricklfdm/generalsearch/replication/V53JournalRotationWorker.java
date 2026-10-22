package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh-process exact journal rotation; no runtime service or historical remote force claim. */
public final class V53JournalRotationWorker {
    static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static void copy(Path from,Path to)throws Exception {
        try(var paths=Files.walk(from)) {for(Path path:paths.sorted().toList()) {
            Path output=to.resolve(from.relativize(path));if(Files.isDirectory(path))Files.createDirectory(output);else Files.copy(path,output);
        }}
    }
    static void provision(Path path,int size,int through)throws Exception {
        V53RetirementWorker.provision(path,size,through);copy(path,path.getParent().resolve("seed"));
        var fixture=new V53CurrentGenerationFixture(size,through,false);var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var store=MembershipGrantJournal.openRotating(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,e->{})){store.retireInactive();}
        for(int counter=101;counter<=106;counter++) {
            try(var store=MembershipGrantJournal.openRotating(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,e->{if(e.equals("PROMISE_FORCED"))throw new java.io.IOException("injected incomplete grant");})) {
                try{store.prepareCurrent(fixture.fixture.source.ballot(counter));throw new IllegalStateException("missing initialization cut");}
                catch(java.io.IOException expected){if(!expected.getMessage().equals("injected incomplete grant"))throw expected;}
            }
        }
        if(resources.usage().leases()!=0)throw new IllegalStateException("rotation setup lease leaked");
    }
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";var fixture=new V53CurrentGenerationFixture(size,through,false);
        try {
            if(!Set.of("init","rotate","inspect").contains(command))throw new IllegalArgumentException("unknown rotation command");
            if(command.equals("init")){provision(path,size,through);print(map("command",command,"status","PASS"));return;}
            var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=MembershipGrantJournal.openRotating(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,event->{
                print(map("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                if(command.equals("rotate"))store.rotateJournal();
                print(map("command",command,"status","PASS","journal",hash(Files.readAllBytes(path.resolve("grants.gsr"))),
                        "promise",store.promised().orElseThrow().digest(),"networkAck",false));
            }
            if(resources.usage().leases()!=0)throw new IllegalStateException("rotation lease leaked");
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
