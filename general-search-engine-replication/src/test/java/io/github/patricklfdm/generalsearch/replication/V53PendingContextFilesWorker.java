package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Component process worker: real exclusive lock/forces; context authority is a supplied original fixture. */
public final class V53PendingContextFilesWorker {
    private static void print(Map<String,Object> value) {
        System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();
    }
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),inputs=Path.of(args[1]);String point=args[2],mode=args[3];
        var record=decode(Files.readAllBytes(inputs.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)record.value().get("groupId"))),
                UUID.fromString((String)record.value().get("historyId")),record.rootDigest());
        var local=MembershipContext.identity(object(list(record.value().get("initial")).getFirst()));
        byte[] expected=Files.readAllBytes(inputs.resolve("expected.gspc"));
        byte[] prior=Files.exists(inputs.resolve("prior.gspc"))?Files.readAllBytes(inputs.resolve("prior.gspc")):null;
        var resources=new MembershipResources(512*MembershipResources.MIB);Path lock=path.resolve("owner.lock");
        Object lockKey=MembershipBasisSources.key(lock);
        try(var owner=AdmissionPaths.own(lock,false);
                var lease=resources.reserve(MembershipResources.Unit.JOURNAL,"context-process",MembershipResources.Unit.JOURNAL.bytes);
                var files=new MembershipPendingContextFiles(path,root,local,resources,2L*MembershipPendingContext.MAXIMUM)) {
            byte[] result=files.install(MembershipPendingContext.decode(expected),prior,()->{
                if(!owner.lock().isValid() || !lockKey.equals(MembershipBasisSources.key(lock)))throw new java.io.IOException("lost exclusive context owner");
            },event->{
                print(Map.of("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(Map.of("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(30_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            });
            if(!Arrays.equals(result,expected))throw new IllegalArgumentException("different durable context");
            print(Map.of("status","PASS","context",hash(result),"bytes",(long)result.length));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("context process lease leak");
    }
}
