package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private offline orchestration. The public entry remains gated on complete-store
 * seal admission and result inspection after mutable runtime progress. */
final class MembershipBootstrapCoordinator {
    private MembershipBootstrapCoordinator(){}
    static Path projection(Path operation) {
        Path path=AdmissionPaths.safe(operation);require(path.getParent()!=null,"bootstrap operation has no parent");
        return path.resolveSibling(".gse-v53-bootstrap-"+hash(path.toString().getBytes(StandardCharsets.UTF_8))+".projection");
    }
    static <K,T> MembershipBootstrapPlan plan(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(captured);Objects.requireNonNull(request);Objects.requireNonNull(cut);
        Path operation=AdmissionPaths.safe(request.operationDirectory()),scratch=projection(operation);
        if(Files.exists(operation,LinkOption.NOFOLLOW_LINKS)) {
            // Complete original candidate plans can be resealed. Missing/torn plans
            // never acquire a replacement history from this request.
            var original=retained(operation,true);metadata(captured,request,original);
            try(var owner=MembershipBootstrapPlanFiles.open(operation,original.summary(),cut,p->verify(captured,request,p,cut))) {
                return owner.summary();
            }
        }
        AdmissionPaths.absent(scratch);
        var seed=MembershipBootstrapSeed.project(captured,request,UUID.randomUUID(),scratch);
        var original=MembershipBootstrapPlanData.create(seed,request);
        verify(captured,request,original,cut); // full completion plus retained projection, before coordinator writes
        try(var owner=MembershipBootstrapPlanFiles.create(original,cut)){return owner.summary();}
    }
    static <K,T> MembershipBootstrapResult apply(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            MembershipBootstrapPlan reviewed,boolean resume,MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(captured);Objects.requireNonNull(request);Objects.requireNonNull(reviewed);Objects.requireNonNull(cut);
        return MembershipBootstrapTransaction.applyAdmitted(reviewed,resume,p->metadata(captured,request,p),p->verify(captured,request,p,cut),cut);
    }
    /** Initial committed result only. Future public result reading must tolerate
     * legitimate runtime mutations without treating them as bootstrap corruption. */
    static MembershipBootstrapResult readInitialResult(Path operation)throws IOException {
        return MembershipBootstrapTransaction.readAdmitted(retained(AdmissionPaths.safe(operation),false).summary());
    }
    private static MembershipBootstrapPlanData retained(Path operation,boolean candidate)throws IOException {
        AdmissionPaths.safe(operation);Path active=operation.resolve(MembershipBootstrapPlanFiles.FILE);
        Path path=Files.exists(active,LinkOption.NOFOLLOW_LINKS)?active:candidate?operation.resolve(MembershipBootstrapPlanFiles.NEXT):active;
        var plan=MembershipBootstrapPlanData.decode(AdmissionPaths.read(path,MembershipBootstrapPlanData.MAXIMUM),
                AdmissionPaths.read(operation.resolve(MembershipBootstrapPlanFiles.IMAGE),MembershipApplicationImage.MAXIMUM));
        require(plan.operation().equals(operation),"bootstrap retained coordinator location");return plan;
    }
    private static void metadata(SearchEngineConfiguration<?,?> captured,MembershipBootstrapRequest<?,?> request,MembershipBootstrapPlanData plan) {
        require(Arrays.equals(MembershipBootstrapPlanData.create(plan.seed,request).bytes(),plan.bytes()),"bootstrap coordinator request drift");
        require(Arrays.equals(canonical(AdmissionConfiguration.application(captured),1024*1024),canonical(plan.seed.descriptor().get("application"),1024*1024)),"bootstrap coordinator application drift");
    }
    private static <K,T> void verify(SearchEngineConfiguration<K,T> captured,MembershipBootstrapRequest<K,T> request,
            MembershipBootstrapPlanData plan,MembershipBallotAllocator.Cut cut)throws IOException {
        metadata(captured,request,plan);MembershipBootstrapRecheck.verifyAdmitted(captured,request,plan,projection(plan.operation()));
        cut.at("BOOTSTRAP_TYPED_RECHECKED");
    }
}
