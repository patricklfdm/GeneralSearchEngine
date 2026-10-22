package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh-process filesystem probe; fixture provisioning is not public bootstrap acceptance. */
public final class V53BallotAllocatorWorker {
    static MembershipRoot root(V53ContextFixture fixture) {
        return new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)fixture.root.value().get("groupId"))),
                UUID.fromString((String)fixture.root.value().get("historyId")),fixture.rootHash);
    }
    static void provision(Path path,int size) throws Exception {
        provision(path,new V53ContextFixture(size,"REPLACE"));
    }
    static void provision(Path path,V53ContextFixture fixture) throws Exception {
        Files.createDirectory(path); AdmissionPaths.forceDirectory(path.getParent());
        AdmissionPaths.write(path.resolve("replica.lock"),new byte[0]);
        AdmissionPaths.write(path.resolve("root.gsr"),fixture.root.bytes());
        AdmissionPaths.write(path.resolve("genesis.gsr"),fixture.inventory.get(fixture.root.value().get("genesis")));
        AdmissionPaths.write(path.resolve("node.gsr"),encode("records","NODE",map("identity",V53ContextFixture.member(1),"root",fixture.rootHash)));
        AdmissionPaths.write(path.resolve(MembershipBallotAllocator.CURRENT),encode("records","ALLOCATOR",map("counter",0L,"node","node-1","root",fixture.rootHash)));
    }
    private static void print(Map<String,Object> value) { System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII)); System.out.flush(); }
    public static void main(String[] args) throws Exception {
        String command=args[0]; Path path=Path.of(args[1]); int size=Integer.parseInt(args[2]);
        try {
            if(!Set.of("init","reserve","inspect","hold").contains(command))throw new IllegalArgumentException("unknown probe command");
            if(command.equals("init")) { provision(path,size); print(map("status","PASS","command",command)); return; }
            String fault=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";
            var fixture=new V53ContextFixture(size,"REPLACE");
            try(var allocator=MembershipBallotAllocator.open(path,root(fixture),V53DeclarationsTest.node(1),point->{
                print(map("event",point));
                if(point.equals(fault)) {
                    if(mode.equals("halt")) Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(map("event","AWAITING_KILL","cut",point));
                        try { Thread.sleep(120_000); } catch(InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            })) {
                if(command.equals("hold")) { print(map("event","HELD")); System.in.read(); }
                long counter=command.equals("reserve")?allocator.reserve(Long.parseLong(args[3])):allocator.counter();
                print(map("status","PASS","command",command,"counter",counter));
            }
        } catch(Exception error) { print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage()))); System.exit(2); }
    }
}
