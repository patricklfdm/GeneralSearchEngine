package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;

/** Synchronous all-three offline bootstrap. No runtime, transport or node writer is opened. */
final class AutomaticBootstrap {
    static final Set<String> OPERATION_FILES = Set.of("operation.lock", "plan.gsr", "operation.gsr",
            "receipt.pending.gsr", "receipt.gsr", "cleanup.gsr", AutomaticBootstrapPlan.BINDING);
    private AutomaticBootstrap() { }

    static <K,T> AutomaticBootstrapPlan project(SearchEngineBuilder<K,T> builder,
            AutomaticReplicationBootstrapRequest<K,T> request, boolean absent) throws IOException {
        Objects.requireNonNull(builder,"builder"); Objects.requireNonNull(request,"request");
        var captured = builder.configuration(); var first = request.replicas().getFirst(); var core = first.materialization();
        var paths = new ArrayList<Path>(); paths.add(request.operationDirectory());
        if (request.sourcePath()!=null) paths.add(request.sourcePath());
        for (var local : request.replicas()) { paths.add(local.replicaDirectory()); paths.add(local.materialization().directory()); }
        AdmissionPaths.disjoint(paths);
        if (absent) AdmissionPaths.absent(request.operationDirectory());
        for (var local : request.replicas()) {
            if (absent) AdmissionPaths.absent(local.replicaDirectory());
            AdmissionPaths.absent(local.materialization().directory());
        }
        var descriptor = descriptor(captured,request); List<T> documents = List.of(); long sequence=0; var importedConfig=captured;
        UUID sourceHistory = new UUID(0,0); Object sourceInventory = List.of();
        if (request.source()!=ReplicationBootstrapSource.EMPTY) {
            var before = AdmissionPaths.inventory(AdmissionPaths.safe(request.sourcePath()),request.maxSourceBytes());
            var imported = captured.newBuilder().readDurableBackup(request.sourcePath(),new DurableVerificationConfig<>(
                    core.storageIdentity(),core.schemaIdentity(),core.codec(),core.codec().codecVersion(),
                    core.maxEncodedKeyBytes(),core.maxEncodedDocumentBytes(),core.maxDocuments()),request.maxSourceBytes());
            need(before.equals(AdmissionPaths.inventory(request.sourcePath(),request.maxSourceBytes())),"source changed during planning");
            documents=imported.documents(); sequence=imported.sequence(); sourceHistory=imported.history();
            importedConfig=new SearchEngineConfiguration<>(captured.schema(),imported.indexes(),captured.config(),captured.plannerConfig());
            sourceInventory=before.stream().map(m -> Map.of("path",m.name(),"kind",m.kind(),"size",m.size(),"sha256",m.digest())).toList();
        }
        descriptor.put("sourceInventory",sourceInventory);
        byte[] binding=encode("BOOTSTRAP_BINDING",Map.of("descriptor",b64(ReplicaJson.encode(descriptor,META))));
        UUID history=AdmissionFormat.history(first.groupId().value());
        need(!sourceHistory.equals(history),"source history cannot be reused");
        int maximum=IMAGE;
        for (var local:request.replicas()) maximum=(int)Math.min(maximum,local.bounds().maxSnapshotStagingBytes());
        byte[] application=AdmissionBootstrap.application(importedConfig,documents,core,maximum);
        String schemaDigest=AutomaticApplication.schemaDigest(captured,core);
        String indexesDigest=sha(canonical(captured.indexes().stream().map(ReplicaApplication::descriptor).sorted().toList()));
        for (var local:request.replicas()) {
            var other=local.materialization();
            need(core.storageIdentity().equals(other.storageIdentity()) && core.schemaIdentity().equals(other.schemaIdentity())
                    && core.codec().codecId().equals(other.codec().codecId()) && core.codec().codecVersion()==other.codec().codecVersion(),"local codec/storage identity mismatch");
            need(Arrays.equals(application,AdmissionBootstrap.application(importedConfig,documents,other,maximum)),"local codec bytes disagree");
        }
        var g=new LinkedHashMap<String,Object>(); g.put("groupId",first.groupId().value().toString()); g.put("historyId",history.toString());
        g.put("baseSequence",sequence); g.put("schemaDigest",schemaDigest); g.put("indexesDigest",indexesDigest);
        g.put("source",request.source().name()); g.put("sourceDigest",request.sourcePath()==null ? null : sha(canonical(sourceInventory)));
        g.put("application",b64(application)); byte[] genesis=encode("GENESIS",g);
        var m=new LinkedHashMap<String,Object>();
        for (String key:List.of("groupId","historyId","baseSequence","schemaDigest","indexesDigest")) m.put(key,g.get(key));
        m.put("mode","AUTOMATIC"); m.put("protocol","gse-replication/1.2"); m.put("storageMajor",1); m.put("storageMinor",2);
        m.put("genesisEpoch",1); m.put("configurationId",first.configurationId()); m.put("genesisDigest",digest(genesis));
        m.put("codecId",core.codec().codecId()); m.put("codecVersion",core.codec().codecVersion());
        m.put("members",first.members().stream().map(v -> Map.of("node",v.nodeId().value(),"host",v.endpoint().host(),"port",v.endpoint().port())).toList());
        var manifest=decode(encode("MANIFEST",m),"MANIFEST");
        var p=new LinkedHashMap<String,Object>(); p.put("manifest",b64(manifest.bytes())); p.put("genesis",b64(genesis));
        p.put("operationPath",AdmissionPaths.safe(request.operationDirectory()).toString());
        p.put("sourcePath",request.sourcePath()==null ? null : AdmissionPaths.safe(request.sourcePath()).toString());
        p.put("maxSourceBytes",request.maxSourceBytes()); p.put("maxOperationBytes",request.maxOperationBytes());
        var targets=new ArrayList<Map<String,Object>>();
        for (int i=0;i<3;i++) {
            var local=request.replicas().get(i); var policy=local.leadershipPolicy(); var d=object(list(descriptor.get("replicas")).get(i));
            targets.add(Map.of("node",local.localNodeId().value(),"authorityPath",AdmissionPaths.safe(local.replicaDirectory()).toString(),
                    "materializationPath",AdmissionPaths.safe(local.materialization().directory()).toString(),"bounds",d.get("replicationBounds"),
                    "policy",Map.of("heartbeatIntervalMillis",policy.heartbeatIntervalMillis(),"minElectionTimeoutMillis",policy.minElectionTimeoutMillis(),
                            "maxElectionTimeoutMillis",policy.maxElectionTimeoutMillis(),"operationTimeoutMillis",policy.operationTimeoutMillis()),
                    "files",AutomaticBootstrapPlan.inventory(AutomaticBootstrapPlan.payloads(manifest,genesis,binding,local.localNodeId().value()))));
        }
        p.put("targets",targets); var plan=new AutomaticBootstrapPlan(decode(encode("PLAN",p),"PLAN"),binding); plan.checkBudget();
        return plan;
    }
    private static Map<String,Object> descriptor(SearchEngineConfiguration<?,?> captured, AutomaticReplicationBootstrapRequest<?,?> request) throws IOException {
        var result=new LinkedHashMap<String,Object>(); result.put("operation",AdmissionPaths.binding(request.operationDirectory()));
        result.put("source",request.sourcePath()==null ? null : AdmissionPaths.binding(request.sourcePath()));
        result.put("application",AdmissionConfiguration.application(captured));
        var locals=new ArrayList<Map<String,Object>>();
        for (var local:request.replicas()) locals.add(localDescriptor(local));
        result.put("replicas",locals); return result;
    }
    private static <K,T> Map<String,Object> localDescriptor(AutomaticReplicationGroupConfig<K,T> local) throws IOException {
        // Reuse the pure local descriptor codec; the configured leader is never persisted or activated.
        return AdmissionConfiguration.local(new ReplicationGroupConfig<>(local.groupId(),local.configurationId(),local.localNodeId(),
                local.members().getFirst().nodeId(),local.members(),local.replicaDirectory(),local.materialization(),local.bounds()));
    }
    static <K,T> ReplicationBootstrapResult apply(SearchEngineBuilder<K,T> builder, AutomaticReplicationBootstrapRequest<K,T> request,
            ReplicationBootstrapPlan summary, boolean resume) {
        return guarded(() -> {
            Objects.requireNonNull(summary,"plan"); Objects.requireNonNull(request,"request");
            Path operation=AdmissionPaths.safe(request.operationDirectory());
            // A completed decision uses the retained canonical application; the backup may have been archived.
            AutomaticBootstrapPlan projected;
            if(resume && Files.exists(operation.resolve(AutomaticBootstrapPlan.BINDING),LinkOption.NOFOLLOW_LINKS)) {
                try(var owner=AdmissionPaths.own(operation.resolve("operation.lock"),false)) {
                    var retained=readPlan(operation);
                    int phase=phase(retained,false);
                    if(phase>=3) {
                        need(retained.summary().equals(summary),"committed summary differs");
                        verifyCommitted(builder,request,retained);
                        need(!Files.exists(operation.resolve("cleanup.gsr"),LinkOption.NOFOLLOW_LINKS),"cleanup intent forbids resume");
                        return complete(retained,phase,() -> {});
                    }
                } catch(AutomaticReplicationException error) {
                    // Only a partial deterministic decision tail may proceed through the exact-request repair path.
                    if(!error.getMessage().equals("ambiguous decision tail")) throw error;
                }
            }
            projected=project(builder,request,!resume);
            need(projected.summary().equals(summary),"caller summary differs from complete request");
            if (!resume) { Files.createDirectory(operation); AdmissionPaths.forceDirectory(operation.getParent()); }
            try (var owner=AdmissionPaths.own(operation.resolve("operation.lock"),!resume)) {
                operationInventory(operation,projected.maximum());
                need(!Files.exists(operation.resolve("cleanup.gsr"),LinkOption.NOFOLLOW_LINKS),"cleanup intent forbids bootstrap resume");
                if (!resume) {
                    AdmissionPaths.write(operation.resolve("plan.gsr"),projected.record().bytes()); at("PLAN");
                    AdmissionPaths.write(operation.resolve(AutomaticBootstrapPlan.BINDING),projected.binding()); at("BINDING");
                } else {
                    AdmissionPaths.exact(operation.resolve("plan.gsr"),projected.record().bytes());
                    AdmissionBootstrap.completeFile(operation.resolve(AutomaticBootstrapPlan.BINDING),projected.binding(),true);
                }
                need(!Files.exists(operation.resolve("cleanup.gsr"),LinkOption.NOFOLLOW_LINKS),"cleanup intent forbids bootstrap resume");
                int phase=phase(projected,true);
                if (phase==0) { for(int i=0;i<3;i++) AdmissionPaths.absent(projected.target(i)); advance(projected,1); phase=1; }
                return complete(projected,phase,() -> need(Arrays.equals(projected.record().bytes(),project(builder,request,false).record().bytes()),"request/source changed before decision"));
            }
        });
    }
    private static <K,T> void verifyCommitted(SearchEngineBuilder<K,T> builder,AutomaticReplicationBootstrapRequest<K,T> request,AutomaticBootstrapPlan plan) throws IOException {
        var actual=descriptor(builder.configuration(),request); var retained=new LinkedHashMap<>(plan.descriptor()); retained.remove("sourceInventory");
        need(Arrays.equals(canonical(actual),canonical(retained)),"committed application/path configuration changed");
        need(request.maxSourceBytes()==number(plan.record().value(),"maxSourceBytes") && request.maxOperationBytes()==plan.maximum()
                && request.source()==plan.summary().source(),"committed source/budget changed");
        var m=plan.manifest().value();
        for(int i=0;i<3;i++) {
            var c=request.replicas().get(i); var p=c.leadershipPolicy();
            need(c.groupId().value().toString().equals(m.get("groupId")) && c.configurationId().equals(m.get("configurationId"))
                    && Arrays.equals(canonical(c.members().stream().map(v -> Map.of("node",v.nodeId().value(),"host",v.endpoint().host(),"port",v.endpoint().port())).toList()),canonical(m.get("members"))),"committed group changed");
            need(Arrays.equals(canonical(plan.targetValue(i).get("policy")),canonical(Map.of("heartbeatIntervalMillis",p.heartbeatIntervalMillis(),
                    "minElectionTimeoutMillis",p.minElectionTimeoutMillis(),"maxElectionTimeoutMillis",p.maxElectionTimeoutMillis(),"operationTimeoutMillis",p.operationTimeoutMillis()))),"committed policy changed");
            // Decode/re-encode with each current callback set, without touching a durable materialization directory.
            try(var app=new ReplicaApplication<>(builder.configuration(),c.materialization(),c.bounds());
                var rebuilt=app.rebuildApplication(unbase(decode(plan.genesis(),"GENESIS").value().get("application")),0,number(m,"baseSequence"))) {
                need(Arrays.equals(rebuilt.snapshot(),unbase(decode(plan.genesis(),"GENESIS").value().get("application"))),"committed codec changed");
            }
        }
    }
    @FunctionalInterface interface Recheck { void run() throws IOException; }
    private static ReplicationBootstrapResult complete(AutomaticBootstrapPlan plan,int phase,Recheck recheck) throws IOException {
        var owners=new ArrayList<AdmissionPaths.Owner>(); var payloads=plan.payloads(); plan.recheckPaths();
        need(phase>=3 || !Files.exists(plan.operation().resolve("receipt.gsr"),LinkOption.NOFOLLOW_LINKS)
                && !Files.exists(plan.operation().resolve("receipt.pending.gsr"),LinkOption.NOFOLLOW_LINKS),"receipt precedes global decision");
        try {
            for(int i=0;i<3;i++) {
                Path target=plan.target(i); boolean created=!Files.exists(target,LinkOption.NOFOLLOW_LINKS);
                need(!created || phase==1,"prepared authority lost");
                if(created) { Files.createDirectory(target); AdmissionPaths.forceDirectory(target.getParent()); }
                boolean newLock=!Files.exists(target.resolve("replica.lock"),LinkOption.NOFOLLOW_LINKS);
                need(!newLock || phase==1,"prepared ownership lost"); owners.add(AdmissionPaths.own(target.resolve("replica.lock"),newLock));
                verifyPartial(plan,i,phase); at("TARGET_"+i);
            }
            if(phase==1) {
                for(int i=0;i<3;i++) {
                    for(var file:payloads.get(i).entrySet()) { AdmissionBootstrap.completeFile(plan.target(i).resolve(file.getKey()),file.getValue(),true); at("FILE_"+i+"_"+file.getKey()); }
                    AdmissionBootstrap.completeFile(plan.target(i).resolve("bootstrap-prepared.gsr"),plan.preparation(i),true); at("PREPARATION_"+i);
                }
                advance(plan,2); phase=2;
            }
            for(int i=0;i<3;i++) {
                for(var file:payloads.get(i).entrySet()) AdmissionPaths.exact(plan.target(i).resolve(file.getKey()),file.getValue());
                AdmissionPaths.exact(plan.target(i).resolve("bootstrap-prepared.gsr"),plan.preparation(i));
            }
            if(phase==2) { recheck.run(); advance(plan,3); phase=3; }
            if(phase==3) {
                AdmissionPaths.publish(plan.operation().resolve("receipt.pending.gsr"),plan.operation().resolve("receipt.gsr"),plan.receipt(),"AUTO_RECEIPT");
                advance(plan,4);
            }
            AdmissionPaths.exact(plan.operation().resolve("receipt.gsr"),plan.receipt());
            for(int i=0;i<3;i++) {
                AdmissionPaths.publish(plan.target(i).resolve("bootstrap-seal.pending.gsr"),plan.target(i).resolve("bootstrap-seal.gsr"),plan.seal(i),"AUTO_SEAL_"+i);
                at("SEALED_"+i);
            }
            return plan.result();
        } finally { close(owners); }
    }
    static void verifyPartial(AutomaticBootstrapPlan plan,int i,int phase) throws IOException {
        var expected=new TreeMap<>(plan.payloads().get(i)); expected.put("bootstrap-prepared.gsr",plan.preparation(i));
        if(phase==4) { expected.put("bootstrap-seal.gsr",plan.seal(i)); expected.put("bootstrap-seal.pending.gsr",plan.seal(i)); }
        for(var file:AdmissionPaths.inventory(plan.target(i),plan.maximum())) {
            byte[] bytes=expected.get(file.name()); need(file.kind()==1 && bytes!=null,"unknown bootstrap member");
            byte[] actual=AdmissionPaths.read(plan.target(i).resolve(file.name()),bytes.length);
            need(Arrays.equals(actual,Arrays.copyOf(bytes,actual.length)) && (actual.length==bytes.length || phase==1
                    || phase==4 && file.name().equals("bootstrap-seal.pending.gsr")),"changed bootstrap payload");
        }
    }
    /** Strict cleanup/read mode rejects even a checksum-valid prefix of an undecided row. */
    static int phase(AutomaticBootstrapPlan plan,boolean repair) throws IOException {
        Path path=plan.operation().resolve("operation.gsr");
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS)) return 0;
        byte[] actual=AdmissionPaths.read(path,4*META); int offset=0,phase=0;
        for(int i=1;i<=4 && offset<actual.length;i++) {
            byte[] row=plan.row(i); int remaining=actual.length-offset;
            if(remaining<row.length) {
                need(repair && Arrays.equals(Arrays.copyOfRange(actual,offset,actual.length),Arrays.copyOf(row,remaining)),"ambiguous decision tail");
                try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                    channel.position(actual.length); AdmissionPaths.write(channel,Arrays.copyOfRange(row,remaining,row.length)); channel.force(true);
                }
                AdmissionPaths.forceDirectory(path.getParent()); return i;
            }
            need(Arrays.equals(Arrays.copyOfRange(actual,offset,offset+row.length),row),"decision chain mismatch");
            offset+=row.length; phase=i;
        }
        need(offset==actual.length,"trailing decision bytes"); return phase;
    }
    static void advance(AutomaticBootstrapPlan plan,int phase) throws IOException { AdmissionBootstrap.append(plan.operation(),plan.row(phase)); at(AutomaticBootstrapPlan.STATES.get(phase-1)); }
    static void at(String point) throws IOException { AdmissionIo.at("AUTO_BOOTSTRAP_"+point); }
    static void operationInventory(Path operation,long maximum) throws IOException {
        for(var member:AdmissionPaths.inventory(operation,maximum)) need(member.kind()==1 && OPERATION_FILES.contains(member.name()),"unknown automatic coordinator member");
    }
    static AutomaticBootstrapPlan readPlan(Path operation) throws IOException {
        var plan=new AutomaticBootstrapPlan(decode(AdmissionPaths.read(operation.resolve("plan.gsr"),META),"PLAN"),
                AdmissionPaths.read(operation.resolve(AutomaticBootstrapPlan.BINDING),META));
        need(plan.operation().equals(operation),"copied coordinator path"); plan.checkBudget(); plan.recheckPaths(); operationInventory(operation,plan.maximum()); return plan;
    }
    static ReplicationBootstrapResult readResult(Path requested) {
        return guarded(() -> {
            Path operation=AdmissionPaths.safe(requested);
            try(var owner=AdmissionPaths.own(operation.resolve("operation.lock"),false)) {
                var plan=readPlan(operation); need(phase(plan,false)==4,"bootstrap is not committed");
                need(!Files.exists(operation.resolve("cleanup.gsr"),LinkOption.NOFOLLOW_LINKS),"committed cleanup intent");
                AdmissionPaths.exact(operation.resolve("receipt.gsr"),plan.receipt()); return plan.result();
            }
        });
    }
    static void close(List<AdmissionPaths.Owner> owners) throws IOException {
        IOException failed=null;
        for(int i=owners.size()-1;i>=0;i--) try { owners.get(i).close(); } catch(IOException e) { if(failed==null) failed=e; else failed.addSuppressed(e); }
        if(failed!=null) throw failed;
    }
    @FunctionalInterface interface Action<T> { T run() throws IOException; }
    static <T> T guarded(Action<T> action) {
        try { return AdmissionBootstrap.guarded(action::run); }
        catch(ReplicationException e) {
            var reason=switch(e.reason()) {
                case CAPACITY_EXCEEDED -> AutomaticReplicationException.Reason.CAPACITY_EXCEEDED;
                case PROTOCOL_MISMATCH -> AutomaticReplicationException.Reason.PROTOCOL_MISMATCH;
                case STORAGE_FAILURE -> AutomaticReplicationException.Reason.STORAGE_FAILURE;
                default -> AutomaticReplicationException.Reason.INTEGRITY_FAILURE;
            };
            throw failure(reason,"automatic offline operation rejected: "+e.getMessage(),e);
        }
    }
}
