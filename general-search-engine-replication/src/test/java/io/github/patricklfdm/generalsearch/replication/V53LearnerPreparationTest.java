package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Conditional historical sources exercise the real retained-store boundary.
 * This does not qualify typed readiness, remote freshness or joint eligibility. */
class V53LearnerPreparationTest {
    @TempDir Path temp;
    V53LearnerStoreTest.Fixture source(int size,String kind,int index)throws Exception {
        var helper=new V53LearnerStoreTest();helper.temp=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
        return helper.new Fixture(size,kind,index);
    }
    @Test void allFiveJoiningShapesRequireTheExactCertifiedPreparation()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            try(var f=source(size,kind,3);var store=f.install(e->{})) {
                f.disconnect();var before=V53ReplayFilesTest.files(f.replica());var usage=f.source.client.usage();
                var prepared=MembershipLearnerPreparation.from(store,1);
                var operation=object(list(store.capsule().context.catalog.get("results")).getFirst());
                assertEquals(operation.get("prepared"),prepared.prepared());
                String digest=(String)prepared.prepared().get("application");byte[] image=prepared.image();
                assertArrayEquals(Files.readAllBytes(f.source.path.resolve("generations/a/"+digest+".image")),image);image[0]^=1;
                assertEquals(digest,hash(prepared.image()));assertEquals(usage,f.source.client.usage());
                assertEquals(before,V53ReplayFilesTest.files(f.replica()));
                for(long revision:List.of(0L,2L,64L,65L,Long.MAX_VALUE))
                    assertThrows(IllegalArgumentException.class,()->MembershipLearnerPreparation.from(store,revision));
            }
        }
    }
    @Test void reserveReadyAndSealedSourcesCannotCreateANewPreparation()throws Exception {
        for(int index:List.of(2,4,5))try(var f=source(3,"ADD",index);var store=f.install(e->{})) {
            var before=V53ReplayFilesTest.files(f.replica());
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerPreparation.from(store,1));
            assertEquals(before,V53ReplayFilesTest.files(f.replica()));
        }
    }
    @Test void closedOrReplacedSourceInvalidatesPreviouslyCapturedPreparation()throws Exception {
        try(var f=source(3,"ADD",3)) {
            var store=f.install(e->{});var prepared=MembershipLearnerPreparation.from(store,1);f.disconnect();store.close();
            assertThrows(IllegalArgumentException.class,prepared::prepared);assertThrows(IllegalArgumentException.class,prepared::image);
            try(var reopened=f.resume(e->{})) {
                var next=MembershipLearnerPreparation.from(reopened,1);String digest=(String)next.prepared().get("application");
                Path image=f.destination().resolve(digest+".image"),old=f.destination().resolveSibling("original-image");
                Files.move(image,old);Files.copy(old,image);
                try{assertThrows(IllegalArgumentException.class,next::image);assertThrows(IllegalArgumentException.class,next::prepared);}
                finally{Files.delete(image);Files.move(old,image);}
            }
        }
    }
    @Test void localIdentityPathsAndOperationOverlapRefuseBeforeAnyMaterialization()throws Exception {
        try(var f=source(3,"ADD",3);var store=f.install(e->{})) {
            var prepared=MembershipLearnerPreparation.from(store,1);var request=f.plan.request;var bounds=ReplicationBounds.defaults();
            Path anchor=temp.resolve("unused");var timing=AutomaticLeadershipPolicy.forBounds(bounds);
            var wrongIdentity=new MembershipReplicaConfig<>(request.root(),V53DeclarationsTest.node(1),List.of(),request.replicaDirectory(),storage(anchor,2),bounds,timing);
            assertThrows(IllegalArgumentException.class,()->prepared.configuration(builder().configuration(),wrongIdentity));
            var wrongPath=new MembershipReplicaConfig<>(request.root(),request.identity(),List.of(),temp.resolve("other"),storage(anchor,2),bounds,timing);
            assertThrows(IllegalArgumentException.class,()->prepared.configuration(builder().configuration(),wrongPath));
            var overlap=new MembershipReplicaConfig<>(request.root(),request.identity(),List.of(),request.replicaDirectory(),storage(request.operationDirectory().resolve("nested"),2),bounds,timing);
            assertThrows(ReplicationException.class,()->prepared.configuration(builder().configuration(),overlap));
            assertFalse(Files.exists(anchor));assertFalse(Files.exists(request.operationDirectory().resolve("nested")));
        }
    }
    @Test void actualBootstrapRootRequiresItsCapturedSchemaCodecAndStartupIndexes()throws Exception {
        var helper=new V53BootstrapSeedTest();helper.temp=temp;
        var request=helper.request(temp.resolve("bootstrap"),3,null);var seed=helper.project(request,temp.resolve("seed"));
        var config=builder().configuration();var storage=request.targets().getFirst().materialization();
        MembershipLearnerPreparation.configuration(seed.rootRecord,config,storage);
        for(String field:List.of("schema","indexes","codecId","codecVersion")) {
            var value=new TreeMap<>(seed.rootRecord.value());value.put(field,field.equals("codecVersion")?2L:field.equals("codecId")?"foreign":"00".repeat(32));
            var root=decode(encode("records","ROOT",value),"records","ROOT");
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerPreparation.configuration(root,config,storage));
        }
        var changed=io.github.patricklfdm.generalsearch.engine.SearchEngine.builder(Doc.class,ID)
                .index(io.github.patricklfdm.generalsearch.index.IndexDefinition.prefix(VALUE)).configuration();
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerPreparation.configuration(seed.rootRecord,changed,storage));
        V53BootstrapSeedTest.absent(request);
    }
}
