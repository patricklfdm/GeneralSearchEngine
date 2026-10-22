package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh-process bounded floor release; no runtime service or historical remote force claim. */
public final class V53FloorReleaseWorker {
    static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    static void copy(Path from,Path to)throws Exception {
        try(var paths=Files.walk(from)) {for(Path path:paths.sorted().toList()) {
            Path output=to.resolve(from.relativize(path));if(Files.isDirectory(path))Files.createDirectory(output);else Files.copy(path,output);
        }}
    }
    static void provision(Path path,int size,int through)throws Exception {
        V53RetirementWorker.provision(path,size,through);copy(path,path.getParent().resolve("seed"));
        var fixture=new V53CurrentGenerationFixture(size,through,false);var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var store=MembershipGrantJournal.openMaintenance(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,e->{})){store.retireInactive();}
        if(resources.usage().leases()!=0)throw new IllegalStateException("floor release setup lease leaked");
    }
    public static void main(String[] args)throws Exception {
        String command=args[0];Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";String[] parts=point.split("@");
        int occurrence=parts.length==2?Integer.parseInt(parts[1]):1;int[] seen={0};var fixture=new V53CurrentGenerationFixture(size,through,false);
        try {
            if(!Set.of("init","release","inspect").contains(command))throw new IllegalArgumentException("unknown floor release command");
            if(command.equals("init")){provision(path,size,through);print(map("command",command,"status","PASS"));return;}
            var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=MembershipGrantJournal.openMaintenance(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,event->{
                print(map("event",event));if(event.equals(parts[0]) && ++seen[0]==occurrence) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                if(command.equals("release"))store.releaseFloor();
                print(map("command",command,"status","PASS","journal",hash(Files.readAllBytes(path.resolve("grants.gsr"))),
                        "selector",hash(Files.readAllBytes(path.resolve("selector.gsr"))),"floor",store.governingFloor().map(Decoded::digest).orElse(null),"networkAck",false));
            }
            if(resources.usage().leases()!=0)throw new IllegalStateException("floor release lease leaked");
        }catch(Exception error){print(map("command",command,"status","FAIL","type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
