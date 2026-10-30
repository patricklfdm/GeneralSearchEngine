package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Failed scratch cleanup retains the exact receiving owner until a later drain.
 * Foreign bytes deliberately block deletion; removing them does not authorize a vote. */
class V53MaintenanceDrainTest {
    @TempDir Path temp;
    private void run(String mode,boolean higher)throws Exception {
        boolean endpointOwned=mode.equals("endpoint"),driverOwned=mode.equals("driver");
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network()) {
            var owner=n.owners.getFirst();var pool=n.resources.getFirst();
            try(var first=new MembershipActivation(owner,pool,System::nanoTime,V53NativeDispatchTest.BUDGET)) {
                assertNotNull(first.ownSource());
            }
            try(var campaign=new MembershipActivation(owner,pool,System::nanoTime,V53NativeDispatchTest.BUDGET)) {
                var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
                var usage=pool.usage();Path scratch=temp.resolve("drain-scratch");
                if(!endpointOwned && !driverOwned)Files.createDirectory(scratch);
                var foreign=new AtomicReference<Path>();var injected=new AtomicBoolean();
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                    try(var paths=Files.walk(scratch)) {
                        var file=paths.filter(p->p.getFileName().toString().equals("source.gscp")).findFirst();
                        if(file.isPresent() && injected.compareAndSet(false,true)) {
                            foreign.set(Files.writeString(file.orElseThrow().resolveSibling("foreign"),"operator data"));
                            return CompletableFuture.failedFuture(new IOException("held source interrupted"));
                        }
                    }catch(IOException error){return CompletableFuture.failedFuture(error);}
                    return n.transports.getFirst().exchange(peer,request,kind,deadline);
                };
                if(driverOwned) {
                    var driver=new MembershipActivationDriver(owner,n.endpoints.getFirst(),pool,n.bounds,link,List.of(),List.of(),scratch,
                            System::nanoTime,V53NativeDispatchTest.BUDGET,2);
                    try {
                        assertThrows(Exception.class,driver::run);assertTrue(injected.get());assertEquals(0,driver.campaigns());
                        assertThrows(Exception.class,driver::close);
                        assertEquals("operator data",Files.readString(foreign.get()));Files.delete(foreign.get());
                        driver.close();assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scratch,8));
                    }finally{if(foreign.get()!=null)Files.deleteIfExists(foreign.get());driver.close();}
                }else if(endpointOwned) {
                    var endpoint=new MembershipActivationEndpoint(owner,pool,n.bounds,link,List.of(),List.of(),scratch,
                            System::nanoTime,V53NativeDispatchTest.BUDGET);
                    try {
                        assertThrows(Exception.class,()->endpoint.serve(campaign));assertTrue(injected.get());
                        if(higher)try(var next=new MembershipActivation(owner,pool,System::nanoTime,V53NativeDispatchTest.BUDGET)) {
                            assertThrows(Exception.class,()->endpoint.serve(next));
                        }
                        assertThrows(Exception.class,endpoint::close);
                        assertEquals("operator data",Files.readString(foreign.get()));Files.delete(foreign.get());
                        endpoint.close();
                        assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scratch,8));
                    }finally{if(foreign.get()!=null)Files.deleteIfExists(foreign.get());endpoint.close();}
                }else {
                    var work=MembershipGenerationMaintenance.beforeGrant(owner,pool,n.bounds,link,()->{},scratch,
                            System::nanoTime,System.nanoTime(),V53NativeDispatchTest.BUDGET);
                    try {
                        assertThrows(Exception.class,work::run);assertTrue(injected.get());
                        assertThrows(Exception.class,work::close);
                        assertEquals("operator data",Files.readString(foreign.get()));Files.delete(foreign.get());
                        work.close();assertEquals(Set.of(),MembershipBasisSources.children(scratch,8));
                    }finally{if(foreign.get()!=null)Files.deleteIfExists(foreign.get());work.close();}
                }
                if(!higher){assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));assertEquals(usage,pool.usage());}
            }
        }
    }
    @Test void maintenanceRetriesOnlyItsOriginalFailedReceiveCleanup()throws Exception {run("maintenance",false);}
    @Test void endpointRetainsFailedMaintenanceForLaterClose()throws Exception {run("endpoint",false);}
    @Test void higherScopeCannotDiscardUndrainedMaintenance()throws Exception {run("endpoint",true);}
    @Test void driverRetainsFailedPreGrantMaintenanceForLaterClose()throws Exception {run("driver",false);}
}
