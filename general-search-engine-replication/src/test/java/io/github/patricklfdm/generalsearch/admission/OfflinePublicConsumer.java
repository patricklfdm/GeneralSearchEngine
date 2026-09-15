package io.github.patricklfdm.generalsearch.admission;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import io.github.patricklfdm.generalsearch.replication.*;

/** Runs all actual offline operations from outside the implementation package. */
public final class OfflinePublicConsumer {
    private OfflinePublicConsumer() { }
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]).toAbsolutePath().normalize(); String command = args[1];
        Path source = args[2].equals("-") ? null : Path.of(args[2]);
        var request = OfflineApplication.request(root, source); var builder = OfflineApplication.builder();
        Object output;
        switch (command) {
            case "semantic" -> {
                var application = AdmissionSemanticModel.builder();
                var materialization = AdmissionSemanticModel.storage(root.resolve("semantic-anchor"), 2);
                var imported = application.readDurableBackup(source, new io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig<>(
                        materialization.storageIdentity(), materialization.schemaIdentity(), materialization.codec(), 1,
                        materialization.maxEncodedKeyBytes(), materialization.maxEncodedDocumentBytes(), materialization.maxDocuments()), 1 << 20);
                var configs = request.replicas().stream().map(local -> new ReplicationGroupConfig<>(local.groupId(), local.configurationId(), local.localNodeId(),
                        local.configuredLeaderId(), local.members(), local.replicaDirectory(),
                        AdmissionSemanticModel.storage(local.materialization().directory(), 2), local.bounds())).toList();
                var importedRequest = new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP, source, configs,
                        request.operationDirectory(), 1 << 30, 1 << 30);
                var importedPlan = ReplicationStorageOperations.planBootstrap(application, importedRequest);
                var result = ReplicationStorageOperations.applyBootstrap(application, importedRequest, importedPlan);
                try (var engine = application.configuration().newBuilder().build()) {
                    engine.addAll(imported.documents()).join();
                    output = Map.of("sequence", imported.sequence(), "semantics", AdmissionSemanticModel.report(engine),
                            "applicationHistory", result.applicationHistory().toString());
                }
                for (int minor = 0; minor < 3; minor++) application.writeDurableBackup(imported,
                        AdmissionSemanticModel.storage(root.resolve("export-anchor-" + minor), minor),
                        new io.github.patricklfdm.generalsearch.durability.DurableBackupRequest(root.resolve("export-" + minor), 1 << 20));
            }
            case "plan" -> output = Map.of("planDigest", ReplicationStorageOperations.planBootstrap(builder, request).planDigest());
            case "apply", "resume" -> {
                var plan = new ReplicationBootstrapPlan(request.replicas().getFirst().groupId(), "config-v1", request.source(), source,
                        request.replicas().stream().map(ReplicationGroupConfig::replicaDirectory).toList(), args[3]);
                var result = command.equals("apply") ? ReplicationStorageOperations.applyBootstrap(builder, request, plan)
                        : ReplicationStorageOperations.resumeBootstrap(builder, request, plan);
                output = Map.of("planDigest", result.plan().planDigest(), "receiptDigest", result.receiptDigest(),
                        "manifestDigest", result.manifestDigest(), "genesisDigest", result.genesisDigest(),
                        "applicationHistory", result.applicationHistory().toString(), "applicationSequence", result.applicationSequence());
            }
            case "read" -> {
                var result = ReplicationStorageOperations.readBootstrapResult(request.operationDirectory());
                output = Map.of("receiptDigest", result.receiptDigest(), "applicationSequence", result.applicationSequence());
            }
            case "inspect" -> {
                var result = ReplicationStorageOperations.inspect(root.resolve(args[3]));
                output = Map.of("valid", result.structurallyValid(), "minor", result.formatMinor(), "node", result.nodeId().orElseThrow().value());
            }
            case "cleanup-plan" -> {
                var plan = ReplicationStorageOperations.planCleanup(request.operationDirectory());
                output = Map.of("operationDirectory", plan.operationDirectory().toString(), "operationDigest", plan.operationDigest(),
                        "deletePaths", plan.deletePaths().stream().map(Path::toString).toList(), "inventoryDigest", plan.inventoryDigest(), "planDigest", plan.planDigest());
            }
            case "cleanup-apply" -> {
                Map<String, Object> value = (Map<String, Object>) AdmissionJson.parse(Files.readString(Path.of(args[3])));
                ReplicationStorageOperations.applyCleanup(new ReplicationCleanupPlan(Path.of((String) value.get("operationDirectory")),
                        (String) value.get("operationDigest"), ((List<String>) value.get("deletePaths")).stream().map(Path::of).toList(),
                        (String) value.get("inventoryDigest"), (String) value.get("planDigest")));
                output = Map.of("cleaned", true);
            }
            case "replacement-plan", "replacement-apply", "replacement-resume" -> {
                var old = request.replicas().get(2);
                var config = new ReplicationGroupConfig<>(old.groupId(), old.configurationId(), old.localNodeId(), old.configuredLeaderId(), old.members(),
                        root.resolve("replacement"), old.materialization(), old.bounds());
                if (command.equals("replacement-plan")) {
                    var plan = ReplicationStorageOperations.planReplacement(config, root.resolve("node-1"), root.resolve("replacement-operation"));
                    output = Map.of("planDigest", plan.planDigest(), "sourceInventoryDigest", plan.sourceInventoryDigest(), "manifestDigest", plan.manifestDigest());
                } else {
                    Map<String, Object> value = (Map<String, Object>) AdmissionJson.parse(Files.readString(Path.of(args[3])));
                    var plan = new ReplicationReplacementPlan(root.resolve("replacement-operation"), root.resolve("node-1"), old.localNodeId(), config.replicaDirectory(),
                            (String) value.get("manifestDigest"), (String) value.get("sourceInventoryDigest"), (String) value.get("planDigest"));
                    if (command.equals("replacement-apply")) ReplicationStorageOperations.applyReplacement(config, plan);
                    else ReplicationStorageOperations.resumeReplacement(config, plan);
                    output = Map.of("replacementPrepared", true);
                }
            }
            default -> throw new IllegalArgumentException("unknown offline command");
        }
        System.out.println(AdmissionJson.canonical(output));
    }
}
