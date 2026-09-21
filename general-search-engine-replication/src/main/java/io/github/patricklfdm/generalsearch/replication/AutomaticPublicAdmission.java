package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import java.util.Arrays;

/** Local sealed configuration verification while the runtime already holds authority ownership. */
final class AutomaticPublicAdmission {
    private AutomaticPublicAdmission() { }
    static <K,T> void verify(AutomaticReplicationGroupConfig<K,T> config,SearchEngineConfiguration<K,T> captured) {
        AutomaticBootstrap.guarded(() -> {
            var root=AdmissionPaths.safe(config.replicaDirectory());
            var seal=decode(AdmissionPaths.read(root.resolve("bootstrap-seal.gsr"),META),"SEAL");
            var receipt=decode(unbase(seal.value().get("receipt")),"RECEIPT");
            var plan=new AutomaticBootstrapPlan(decode(unbase(receipt.value().get("plan")),"PLAN"),
                    AdmissionPaths.read(root.resolve(AutomaticBootstrapPlan.BINDING),META));
            int ordinal=nodes(plan.manifest().value()).indexOf(config.localNodeId().value());
            need(ordinal>=0,"local voter not sealed");
            var local=object(list(plan.descriptor().get("replicas")).get(ordinal));
            var projection=AdmissionConfiguration.local(new ReplicationGroupConfig<>(config.groupId(),config.configurationId(),config.localNodeId(),
                    config.members().getFirst().nodeId(),config.members(),config.replicaDirectory(),config.materialization(),config.bounds()));
            need(Arrays.equals(canonical(local),canonical(projection)),"local configuration differs from sealed bootstrap");
            need(Arrays.equals(canonical(plan.descriptor().get("application")),canonical(AdmissionConfiguration.application(captured))),"application configuration differs from seal");
            // The coordinator, source backup and other voters' directories need not be mounted here.
            AdmissionPaths.recheck(object(local.get("target")));
            AdmissionPaths.recheck(object(object(local.get("materialization")).get("directory")));
            return null;
        });
    }
}
