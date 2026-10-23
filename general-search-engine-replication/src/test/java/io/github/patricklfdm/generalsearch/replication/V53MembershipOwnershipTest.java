package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53MembershipOwnershipTest {
    @TempDir Path temp;
    void probe(Path... locks)throws Exception {
        var command=new ArrayList<String>(List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),V53BootstrapTransactionTest.LockProbe.class.getName()));
        for(Path p:locks)command.add(p.toString());var child=new ProcessBuilder(command).redirectErrorStream(true).start();
        try{assertTrue(child.waitFor(20,TimeUnit.SECONDS));assertEquals(0,child.exitValue(),new String(child.getInputStream().readAllBytes()));}finally{if(child.isAlive())child.destroyForcibly();}
    }
    @Test void duplicateAllocatorOpenDoesNotReleaseTheExternalLockAndCloseAllowsReopen()throws Exception {
        var helper=new V53BallotAllocatorTest();helper.temp=temp;Path root=helper.create("allocator",3);
        try(var owner=helper.open(root,3)) {
            assertThrows(ReplicationException.class,()->helper.open(root,3));assertEquals(1,owner.reserve(0));
            try(var pool=java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor()) {
                assertTrue(pool.submit(()->{try(var ignored=helper.open(root,3)){return false;}catch(ReplicationException expected){return true;}}).get(20,TimeUnit.SECONDS));
            }
            probe(root.resolve("replica.lock"));
        }
        try(var owner=helper.open(root,3)){assertEquals(2,owner.reserve(0));probe(root.resolve("replica.lock"));}
    }
    @Test void duplicatePlanOpenDoesNotReleaseTheExternalLock()throws Exception {
        var helper=new V53BootstrapPlanTest();helper.temp=temp;var plan=helper.fixture("plan",3,false).plan();
        try(var owner=MembershipBootstrapPlanFiles.create(plan,e->{})) {
            assertThrows(ReplicationException.class,()->MembershipBootstrapPlanFiles.open(plan.operation(),plan.summary(),e->{}));
            assertEquals(plan.summary(),owner.summary());probe(plan.operation().resolve("operation.lock"));
        }
    }
    @Test void renamedInodeAndRepeatedRequestsDoNotOpenAnotherChannel()throws Exception {
        Path lock=temp.resolve("owned.lock"),moved=temp.resolve("moved.lock");
        try(var owner=MembershipOwnership.own(lock,true)) {
            Files.move(lock,moved);assertThrows(ReplicationException.class,()->MembershipOwnership.own(moved,false));probe(moved);
            Files.createFile(lock);assertThrows(ReplicationException.class,()->MembershipOwnership.own(lock,false));probe(moved);
        }
        try(var owner=MembershipOwnership.own(moved,false)){probe(moved);}
    }
    @Test void failedOpenDoesNotLeaveARegistrationAndDifferentInodesCanBeOwned()throws Exception {
        Path invalid=temp.resolve("invalid.lock");Files.writeString(invalid,"not empty");assertThrows(ReplicationException.class,()->MembershipOwnership.own(invalid,false));
        Files.write(invalid,new byte[0]);try(var a=MembershipOwnership.own(invalid,false);var b=MembershipOwnership.own(temp.resolve("b.lock"),true)){probe(invalid,temp.resolve("b.lock"));}
        var again=MembershipOwnership.own(invalid,false);again.close();again.close();try(var next=MembershipOwnership.own(invalid,false)){probe(invalid);}
    }
}
