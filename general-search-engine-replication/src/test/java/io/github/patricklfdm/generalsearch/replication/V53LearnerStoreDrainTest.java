package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53PendingListenerDrainTest.storage;

/** Conditional retained authority; actual TCP, resource mutations and independent
 * JVM probes of the original POSIX operation/replica/preparation locks. */
class V53LearnerStoreDrainTest {
    @TempDir Path temp;
    public static final class LockProbe {
        public static void main(String[] args)throws Exception {
            var result=new ArrayList<Map<String,Object>>();
            for(int i=0;i<args.length;i+=2) {
                Path path=Path.of(args[i+1]);Object key=MembershipBasisSources.key(path);
                try(var channel=FileChannel.open(path,StandardOpenOption.READ,StandardOpenOption.WRITE);var lock=channel.tryLock()) {
                    result.add(Map.of("scope",args[i],"path",path.toString(),"key",key.toString(),"held",lock==null));
                }
            }
            System.out.write(canonical(result,16384));
        }
    }
    static List<Map<String,Object>> locks(Map<String,Path> paths)throws Exception {
        var command=new ArrayList<String>(List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData",
                "-cp",System.getProperty("java.class.path"),LockProbe.class.getName()));
        paths.forEach((name,path)->{command.add(name);command.add(path.toString());});
        var child=new ProcessBuilder(command).redirectErrorStream(true).start();
        try {
            assertTrue(child.waitFor(15,TimeUnit.SECONDS),"store lock probe deadline");byte[] bytes=child.getInputStream().readAllBytes();
            assertEquals(0,child.exitValue(),new String(bytes,java.nio.charset.StandardCharsets.UTF_8));
            return list(parse(bytes,16384)).stream().map(MembershipFormat::object).toList();
        }finally{if(child.isAlive())child.destroyForcibly();child.waitFor();}
    }
    static List<Map<String,String>> files(Map<String,Path> paths)throws IOException {
        var result=new ArrayList<Map<String,String>>();
        for(var root:paths.entrySet())for(var file:V53ReplayFilesTest.files(root.getValue()).entrySet())
            result.add(Map.of("path",root.getKey()+"/"+file.getKey(),"sha256",file.getValue()));
        return result;
    }
    @ParameterizedTest @ValueSource(strings={"checkpoint","head"})
    void callbackCloseKeepsStoreResourcesAndLocksUntilExternalRetry(String listener)throws Exception {run(listener,true);}
    @ParameterizedTest @ValueSource(strings={"checkpoint","head"})
    void interruptedCloseKeepsStoreResourcesAndLocksUntilExternalRetry(String listener)throws Exception {run(listener,false);}
    private void run(String listener,boolean callback)throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;
        V53PendingListenerDrainTest.Capture capture=null;Throwable failure=null;
        var inventories=new TreeMap<String,Object>();var lockObservations=new TreeMap<String,Object>();
        Path raw=Boolean.getBoolean("v53.resource.learner.control.close")?
                Files.createDirectories(Path.of("target/v53-store-drain/run-"+UUID.randomUUID())):null;
        if(raw!=null)System.out.println("v53StoreDrainEvidence="+raw.toAbsolutePath()+" listener="+listener+" callback="+callback);
        try(var f=helper.new Fixture()) {
            var local=f.fixture.f.local;var store=local.store;
            capture=new V53PendingListenerDrainTest.Capture(local.source.client,f.baselineObservation);
            var roots=new TreeMap<>(Map.of("operation",local.summary.request().operationDirectory(),
                    "replica",local.summary.request().replicaDirectory(),"typed",local.typed(),"pending",f.fixture.directory()));
            var lockPaths=new TreeMap<>(Map.of("operation",roots.get("operation").resolve(MembershipLearnerAdmissionFiles.LOCK),
                    "replica",roots.get("replica").resolve(MembershipLearnerStore.LOCK),"typed",roots.get("typed").resolve(MembershipLearnerMaterialization.LOCK)));
            try(var gate=new V53PendingListenerDrainTest.Gate(store,capture,callback)) {
                MembershipLearnerCheckpointEndpoint checkpoint=null;MembershipLearnerHeadEndpoint head=null;
                try {
                    if(listener.equals("checkpoint"))checkpoint=f.listen(gate);
                    else{f.pending.endorse();head=f.pending.retainSource().listenHead(local.config.bounds(),gate);}
                    inventories.put("before",files(roots));lockObservations.put("before",locks(lockPaths));
                    assertTrue(list(lockObservations.get("before")).stream().allMatch(v->object(v).get("held").equals(true)));
                    try(var contact=f.contact()) {
                        var request=listener.equals("checkpoint")?f.first():V53LearnerHeadProtocolTest.query(f.fixture.f.head,f.reader);
                        var pending=contact.exchange(f.local,request,listener.equals("checkpoint")?"SOURCE_OFFER":"LEARNER_HEAD_ACK",System.nanoTime()+TimeUnit.SECONDS.toNanos(30));
                        try {
                            assertTrue(gate.entered.await(15,TimeUnit.SECONDS));
                            if(!callback) {
                                var interruptPreserved=new AtomicBoolean();Thread closer=Thread.ofPlatform().start(()->{
                                    Thread.currentThread().interrupt();gate.attemptClose();interruptPreserved.set(Thread.currentThread().isInterrupted());Thread.interrupted();
                                });closer.join(10000);assertFalse(closer.isAlive());assertTrue(interruptPreserved.get());
                            }
                            inventories.put("afterFailure",files(roots));lockObservations.put("afterFailure",locks(lockPaths));
                            assertAll("failed close preserves the complete store",()->assertEquals(inventories.get("before"),inventories.get("afterFailure")),
                                    ()->assertEquals(lockObservations.get("before"),lockObservations.get("afterFailure")),
                                    ()->assertEquals(gate.held.get(),storage(local.source.client.usage())));
                            var error=gate.failure.get();
                            if(callback)assertEquals("joining "+(listener.equals("checkpoint")?"checkpoint":"progress")+" listener not drained",assertInstanceOf(IOException.class,error).getMessage());
                            else assertEquals("membership transport close interrupted",assertInstanceOf(IllegalStateException.class,error).getMessage());
                            assertThrows(IllegalArgumentException.class,store::summary);assertThrows(IllegalArgumentException.class,f.pending::source);
                        }finally{gate.close();}
                        assertThrows(ExecutionException.class,()->pending.get(10,TimeUnit.SECONDS));
                        capture.mark("RETRY_CLOSE_BEGIN",null,false);store.close();capture.mark("OWNER_CLOSE_RETURNED",null,false);
                        assertEquals(0,local.source.client.usage().leases());
                        inventories.put("afterSuccess",files(roots));lockObservations.put("afterSuccess",locks(lockPaths));
                        assertEquals(inventories.get("before"),inventories.get("afterSuccess"));
                        assertTrue(list(lockObservations.get("afterSuccess")).stream().allMatch(v->object(v).get("held").equals(false)));
                        store.close();assertEquals(0,local.source.client.usage().leases());
                    }
                }finally{gate.close();if(checkpoint!=null)checkpoint.close();if(head!=null)head.close();}
            }
        }catch(Throwable error){failure=error;throw error;}
        finally {
            if(raw!=null && capture!=null) {
                capture.mark("FIXTURE_CLOSED",null,false);boolean empty=capture.budget.usage().leases()==0;
                V53ResourceTraceFiles.write(raw.resolve("resources.json"),capture.budget.observations());
                Files.write(raw.resolve("history.json"),canonical(Map.of("schema","gse-v53-store-drain-v1","listener",listener,"mode",callback?"callback":"interrupt",
                        "status",failure==null && empty?"PASS":"FAIL","rows",capture.rows,"inventories",inventories,"locks",lockObservations,
                        "completeMembershipHistory",false),4*1024*1024));
                assertTrue(empty,"fixture must finish retained storage cleanup");
            }
        }
    }
}
