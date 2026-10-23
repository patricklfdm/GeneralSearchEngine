package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Typed read-only recheck of the original retained planning exports. Repeated
 * recovery uses one bounded projection; it creates no new scratch or authority. */
final class MembershipBootstrapRecheck {
    private MembershipBootstrapRecheck(){}
    private record Snapshot(List<AdmissionFormat.Member> members,Map<String,Object> keys) {
        long bytes(){long bytes=0;for(var member:members)bytes=Math.addExact(bytes,member.size());return bytes;}
    }
    static <K,T> long verify(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            MembershipBootstrapPlanData plan,Path requestedProjection)throws IOException {
        return verify(captured,request,plan,requestedProjection,false);
    }
    static <K,T> long verifyAdmitted(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            MembershipBootstrapPlanData plan,Path requestedProjection)throws IOException {
        return verify(captured,request,plan,requestedProjection,true);
    }
    private static <K,T> long verify(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            MembershipBootstrapPlanData plan,Path requestedProjection,boolean admitted)throws IOException {
        Objects.requireNonNull(captured);Objects.requireNonNull(request);Objects.requireNonNull(plan);
        require(Arrays.equals(MembershipBootstrapPlanData.create(plan.seed,request).bytes(),plan.bytes()),"bootstrap retained recheck request drift");
        Path projection=AdmissionPaths.safe(requestedProjection);var paths=new ArrayList<Path>();paths.add(projection);
        for(var binding:plan.bindings()){AdmissionPaths.recheck(binding);paths.add(AdmissionConfiguration.path(binding));}
        AdmissionPaths.disjoint(paths);var binding=AdmissionPaths.binding(projection);var descriptor=plan.seed.descriptor();
        configuration(captured,request,descriptor);absentCore(request);
        var wanted=new TreeMap<String,Integer>();for(int n=0;n<request.targets().size();n++) {
            String directory="application-"+n;wanted.put(directory,0);
            for(String name:MembershipApplicationImage.MEMBERS)wanted.put(directory+"/"+name,1);
        }
        var original=snapshot(projection,(long)request.targets().size()*MembershipApplicationImage.MAXIMUM);
        require(original.members().size()==wanted.size() && original.members().stream().allMatch(m->Objects.equals(wanted.get(m.name()),m.kind())),"bootstrap retained projection inventory");
        var commit=new MembershipBootstrapCommitData(plan);
        long completion=admitted?MembershipBootstrapAdmissionData.completionBytes(commit.metadata):commit.completionBytes;
        require(original.bytes()<=request.maxOperationBytes()-completion,"bootstrap retained projection completion capacity");
        Path source=request.sourcePath().orElse(null);Snapshot sourceBefore=null;long sourceLimit=Math.min(request.maxSourceBytes(),MembershipApplicationImage.MAXIMUM-MembershipApplicationImage.OVERHEAD);
        if(source!=null) {
            sourceBefore=snapshot(source,sourceLimit);
            var inventory=sourceBefore.members().stream().map(v->Map.of("path",v.name(),"kind",v.kind(),"size",v.size(),"sha256",v.digest())).toList();
            require(Arrays.equals(canonical(inventory,65536),canonical(descriptor.get("sourceInventory"),65536)),"bootstrap retained source inventory drift");
        }
        for(int n=0;n<request.targets().size();n++) {
            var storage=request.targets().get(n).materialization();
            if(source!=null) {
                var imported=captured.newBuilder().readDurableBackup(source,new DurableVerificationConfig<>(storage.storageIdentity(),storage.schemaIdentity(),storage.codec(),
                        storage.codec().codecVersion(),storage.maxEncodedKeyBytes(),storage.maxEncodedDocumentBytes(),storage.maxDocuments()),request.maxSourceBytes());
                require(!plan.seed.root.historyId().equals(imported.history()) && imported.sequence()==plan.seed.sequence
                        && imported.indexes().stream().map(ReplicaApplication::descriptor).toList().equals(captured.indexes().stream().map(ReplicaApplication::descriptor).toList()),"bootstrap retained imported state drift");
            }
            // The core reader checks canonical key/document round trips with this
            // target's actual codec. No equality of Java document objects is trusted.
            byte[] image=MembershipApplicationImage.fromBackup(captured,storage,projection.resolve("application-"+n));
            require(Arrays.equals(image,plan.seed.application()),"bootstrap retained projection image drift");
            require(original.equals(snapshot(projection,(long)request.targets().size()*MembershipApplicationImage.MAXIMUM)),"bootstrap retained projection changed during recheck");
            if(source!=null)require(sourceBefore.equals(snapshot(source,sourceLimit)),"bootstrap retained source changed during recheck");
        }
        AdmissionPaths.recheck(binding);for(var b:plan.bindings())AdmissionPaths.recheck(b);
        configuration(captured,request,descriptor);absentCore(request);
        require(original.equals(snapshot(projection,(long)request.targets().size()*MembershipApplicationImage.MAXIMUM)),"bootstrap retained projection changed before return");
        if(source!=null)require(sourceBefore.equals(snapshot(source,sourceLimit)),"bootstrap retained source changed before return");
        return original.bytes();
    }
    private static Snapshot snapshot(Path path,long maximum)throws IOException {
        var members=AdmissionPaths.inventory(path,maximum);require(members.size()<=20,"bootstrap retained projection member count");
        var keys=new TreeMap<String,Object>();keys.put("",MembershipBasisSources.key(path));
        for(var member:members)keys.put(member.name(),MembershipBasisSources.key(path.resolve(member.name())));
        return new Snapshot(members,keys);
    }
    private static void configuration(SearchEngineConfiguration<?,?> captured,MembershipBootstrapRequest<?,?> request,Map<String,Object> descriptor) {
        require(Arrays.equals(canonical(AdmissionConfiguration.application(captured),1024*1024),canonical(descriptor.get("application"),1024*1024)),"bootstrap retained application configuration drift");
        for(var target:request.targets())require(Arrays.equals(canonical(MembershipBootstrapSeed.core(target.materialization()),65536),canonical(descriptor.get("core"),65536)),"bootstrap retained codec configuration drift");
    }
    private static void absentCore(MembershipBootstrapRequest<?,?> request){for(var target:request.targets())AdmissionPaths.absent(target.materialization().directory());}
}
