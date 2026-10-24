package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** The inherited immutable-result/storage tests enter through the real public API. */
class V53BootstrapPublicTest extends V53BootstrapResultReaderTest {
    private final Set<UUID> histories=new HashSet<>();
    @Override boolean publicBootstrap(){return true;}
    @Override MembershipBootstrapResult read(MembershipBootstrapPlanData p){return MembershipStorageOperations.readBootstrapResult(p.operation());}
    @Override MembershipBootstrapPlanData fixture(String name,int size,boolean backup)throws Exception {
        var helper=new V53BootstrapCoordinatorTest();helper.temp=temp;var request=helper.request(name,size,backup);
        var plan=MembershipStorageOperations.planBootstrap(builder(),request);
        assertEquals(plan,MembershipStorageOperations.planBootstrap(builder(),request));
        var result=MembershipStorageOperations.applyBootstrap(builder(),request,plan);
        var original=V53BootstrapCoordinatorTest.original(plan.operationDirectory(),false);
        assertEquals(new MembershipBootstrapCommitData(original).result(),result);
        assertEquals(4,result.root().historyId().version());assertTrue(histories.add(result.root().historyId()));
        assertEquals(result,MembershipStorageOperations.resumeBootstrap(builder(),request,plan));
        Files.move(MembershipBootstrapCoordinator.projection(plan.operationDirectory()),temp.resolve(name+"-saved-projection"));
        if(backup)Files.move(request.sourcePath().orElseThrow(),temp.resolve(name+"-saved-source"));
        assertEquals(result,MembershipStorageOperations.resumeBootstrap(builder(),request,plan));
        return original;
    }
    @Test void publicRecoveryCompletesTheExactPreparedAndCommittedPlanForAllSizesAndSources()throws Exception {
        var helper=new V53BootstrapCoordinatorTest();helper.temp=temp;
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true))for(String point:List.of("BOOTSTRAP_PREPARED_DURABLE","BOOTSTRAP_COMMITTING_DURABLE")) {
            var request=helper.request("resume-"+size+"-"+backup+"-"+point,size,backup);
            var plan=MembershipStorageOperations.planBootstrap(builder(),request);
            assertThrows(IOException.class,()->MembershipBootstrapCoordinator.apply(builder().configuration(),request,plan,false,e->{if(e.equals(point))throw new IOException(e);}));
            var original=V53BootstrapCoordinatorTest.original(plan.operationDirectory(),false);
            if(point.equals("BOOTSTRAP_COMMITTING_DURABLE")) {
                Files.move(MembershipBootstrapCoordinator.projection(plan.operationDirectory()),temp.resolve("projection-"+size+"-"+backup));
                if(backup)Files.move(request.sourcePath().orElseThrow(),temp.resolve("source-"+size));
            }
            var wrong=V53BootstrapCoordinatorTest.budget(request,request.maxOperationBytes()+1);
            var before=V53BootstrapRevalidationTest.authority(original);
            assertThrows(IllegalArgumentException.class,()->MembershipStorageOperations.resumeBootstrap(builder(),wrong,plan));
            assertEquals(before,V53BootstrapRevalidationTest.authority(original));
            assertEquals(new MembershipBootstrapCommitData(original).result(),MembershipStorageOperations.resumeBootstrap(builder(),request,plan));
            assertEquals(new MembershipBootstrapCommitData(original).result(),read(original));
        }
    }
    @Test void publicEntryRefusesNullsMissingResultsAndInvalidBudgetBeforeInventingAuthority()throws Exception {
        var helper=new V53BootstrapCoordinatorTest();helper.temp=temp;var request=helper.request("invalid",3,false);
        assertThrows(NullPointerException.class,()->MembershipStorageOperations.planBootstrap(null,request));
        assertThrows(NullPointerException.class,()->MembershipStorageOperations.planBootstrap(builder(),null));
        assertThrows(NullPointerException.class,()->MembershipStorageOperations.applyBootstrap(builder(),request,null));
        assertThrows(NullPointerException.class,()->MembershipStorageOperations.resumeBootstrap(builder(),request,null));
        assertThrows(NullPointerException.class,()->MembershipStorageOperations.readBootstrapResult(null));
        var missing=temp.resolve("missing");
        assertEquals("bootstrap result directory absent",assertThrows(IllegalArgumentException.class,()->MembershipStorageOperations.readBootstrapResult(missing)).getMessage());
        assertFalse(Files.exists(missing));
        var io=new IOException("injected offline I/O");
        var mapped=assertThrows(ReplicationException.class,()->AdmissionBootstrap.guarded(()->{throw io;}));
        assertEquals(ReplicationException.Reason.STORAGE_FAILURE,mapped.reason());assertSame(io,mapped.getCause());
        assertThrows(RuntimeException.class,()->MembershipStorageOperations.planBootstrap(builder(),V53BootstrapCoordinatorTest.budget(request,1)));
        V53BootstrapSeedTest.absent(request);assertFalse(Files.exists(MembershipBootstrapCoordinator.projection(request.operationDirectory())));
    }
}
