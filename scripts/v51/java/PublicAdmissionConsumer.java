package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.replication.*;
import java.net.ServerSocket;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** External public bootstrap/start probes; no product decoder or authority repair. */
public final class PublicAdmissionConsumer {
    private static ReplicationGroupConfig<Integer,Doc> configured(AutomaticReplicationGroupConfig<Integer,Doc> c) {
        return new ReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),c.members().getFirst().nodeId(),
                c.members(),c.replicaDirectory(),c.materialization(),c.bounds());
    }
    private static void failure(Map<String,Object> result,Throwable cause) {
        while((cause instanceof CompletionException||cause instanceof ExecutionException)&&cause.getCause()!=null)cause=cause.getCause();
        result.put("errorType",cause.getClass().getName());result.put("reason",cause.toString());
        if(cause instanceof AutomaticReplicationException automatic) {
            result.put("outcome",automatic.outcome().name());result.put("reasonCode",automatic.reason().name());
        } else if(cause instanceof ReplicationException configured) {
            result.put("outcome","NOT_APPLICABLE");result.put("reasonCode",configured.reason().name());
        } else result.put("outcome","VALIDATION_FAILURE");
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);String action=args[1];
        if(action.equals("setup-configured")) {
            var sockets=new ArrayList<ServerSocket>();
            try {for(int i=0;i<3;i++)sockets.add(new ServerSocket(0));Files.write(root.resolve("ports.txt"),sockets.stream().map(s->""+s.getLocalPort()).toList());}
            finally {for(var socket:sockets)socket.close();}
            var request=new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY,null,configs(root).stream().map(PublicAdmissionConsumer::configured).toList(),root.resolve("operation"),1L<<30,1L<<30);
            ReplicationStorageOperations.applyBootstrap(builder(),request,ReplicationStorageOperations.planBootstrap(builder(),request));
            System.out.println(AdmissionJson.canonical(Map.of("status","SETUP","mode","CONFIGURED")));return;
        }
        var c=configs(root).getFirst();var bounds=c.bounds();var materialization=c.materialization();
        if(action.equals("bounds-mismatch"))bounds=new ReplicationBounds(bounds.maxFrameBytes(),100,8,17,2,1200,25,65536,64L<<20,64L<<20);
        if(action.equals("schema-mismatch"))materialization=DurableStorageConfig.builder(materialization.directory(),new Codec())
                .storageIdentity("public-runtime-store").schemaIdentity("different-schema").maxDocuments(1000).maxBulkElements(100).build();
        c=new AutomaticReplicationGroupConfig<>(action.equals("group-mismatch")?new ReplicationGroupId(UUID.fromString("22222222-2222-2222-2222-222222222222")):c.groupId(),
                action.equals("configuration-mismatch")?"different-configuration":c.configurationId(),c.localNodeId(),c.members(),c.replicaDirectory(),materialization,bounds,c.leadershipPolicy());
        var result=new LinkedHashMap<String,Object>();result.put("pid",ProcessHandle.current().pid());result.put("case",action);
        if(action.equals("configured-on-automatic")||action.equals("configured-control")) {
            try(var engine=ReplicatedSearchEngines.builder(builder(),configured(c)).build()) {
                try {engine.start().get(20,TimeUnit.SECONDS);result.put("outcome","SUCCESS");}catch(Exception error){failure(result,error);}
                result.put("state",engine.replicationStatus().state().name());
            }
        } else {
            try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),c).build()) {
                try {engine.start().get(20,TimeUnit.SECONDS);result.put("outcome","SUCCESS");}catch(Exception error){failure(result,error);}
                result.put("state",engine.leadershipStatus().state().name());
            }
        }
        System.out.println(AdmissionJson.canonical(result));
    }
}
