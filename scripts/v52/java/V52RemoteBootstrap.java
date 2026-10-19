package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.replication.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Prepare only local authority from a verified source; never start a voter. */
public final class V52RemoteBootstrap {
    private static String sha(Path path) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=2||!Set.of("node-1","node-2","node-3").contains(args[1]))
            throw new IllegalArgumentException("remote bootstrap arguments");
        Path root=Path.of(args[0]).toAbsolutePath();String node=args[1];
        var topology=V52RemoteTopology.read(root);
        for(String name:List.of("node-1","node-2","node-3","operation","unstarted-bootstrap"))
            if(Files.exists(root.resolve(name),LinkOption.NOFOLLOW_LINKS))throw new IllegalArgumentException("remote bootstrap consumed destination");
        var builder=V52MeasurementQueries.measurementBuilder();
        var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
            root.resolve("control/seed"),topology.configs(root),root.resolve("operation"),1L<<30,1L<<30);
        AutomaticReplicationStorageOperations.applyBootstrap(builder,request,
            AutomaticReplicationStorageOperations.planBootstrap(builder,request));
        Path archive=Files.createDirectory(root.resolve("unstarted-bootstrap"));
        for(String name:List.of("node-1","node-2","node-3","operation"))
            if(!name.equals(node))Files.move(root.resolve(name),archive.resolve(name),StandardCopyOption.ATOMIC_MOVE);
        Path authority=root.resolve(node);
        System.out.println(AdmissionJson.canonical(Map.of("status","PREPARED_NOT_STARTED","node",node,
            "originalRoot",root.toString(),"topology",topology.value(),
            "manifestSha256",sha(authority.resolve("manifest.gsr")),"genesisSha256",sha(authority.resolve("genesis.gsr")),
            "coreSource",Path.of(io.github.patricklfdm.generalsearch.engine.SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString(),
            "replicationSource",Path.of(AutomaticReplicatedSearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString())));
    }
}
