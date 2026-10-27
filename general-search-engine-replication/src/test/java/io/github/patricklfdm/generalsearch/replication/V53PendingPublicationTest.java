package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53PendingPublicationTest {
    @TempDir Path temp;
    static V53BootstrapPublicationTest.Fixture certified(Path home,Path raw,int size,boolean backup)throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(home,raw,size,backup);f.ownedHistory=true;f.nativeApplication=true;f.campaign(1);
        f.observer=(target,operation,event)->{if(operation.equals("apply-1"))throw new V53NativeApplicationTest.Stop();};
        assertThrows(V53NativeApplicationTest.Stop.class,()->f.publish(1,false));f.observer=(target,operation,event)->{};
        f.observations.clear();f.snapshot("certified");return f;
    }
    static void save(MembershipGrantJournal.PendingPublication pending,Path path)throws Exception {
        Files.createDirectory(path);var records=pending.originals();
        for(var row:records.entrySet())Files.write(path.resolve(row.getKey()),row.getValue());
        Files.write(path.resolve("target.json"),canonical(Map.of("owner",MembershipPeerRetentionPlan.identity(pending.owner()),
                "parent",MembershipRetentionIntent.anchor(pending.parent()),"target",MembershipRetentionIntent.anchor(pending.target())),16384));
    }
    @Test void exactNativeTargetsForAllBootstrapSizesAndKindsDoNotPublishOrAllocateImages()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-pending-publication/histories-"+UUID.randomUUID()));
        System.out.println("v53PendingPublicationEvidence="+raw.toAbsolutePath());
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");
            var f=certified(Files.createDirectory(temp.resolve(name)),Files.createDirectory(raw.resolve(name)),size,backup);
            try {
                for(var t:f.request.targets()) {
                    MembershipGrantJournal.PendingPublication pending;
                    try(var owner=f.open(t,"pending-apply")) {
                        var applied=owner.applyCurrent(builder().configuration(),t.materialization());
                        var files=V53ReplayFilesTest.files(t.replicaDirectory());var usage=f.resources.usage();
                        pending=owner.pendingPublication(applied);assertEquals(t.identity(),pending.owner());
                        assertEquals(1L,pending.target().cut().get("index"));assertEquals(0L,pending.parent().cut().get("index"));
                        save(pending,f.raw.resolve(t.identity().nodeId().value()+"-target"));
                        byte[] catalog=pending.originals().get("catalog.gsr");catalog[0]^=1;
                        assertArrayEquals(applied.plan().catalog.bytes(),pending.originals().get("catalog.gsr"));
                        assertThrows(UnsupportedOperationException.class,()->pending.target().cut().put("index",99L));
                        assertEquals(files,V53ReplayFilesTest.files(t.replicaDirectory()));assertEquals(usage,f.resources.usage());
                        assertEquals(0L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
                        assertThrows(IllegalArgumentException.class,()->applied.plan().complete(List.of(applied.endorsement().acknowledgement()),Set.of(applied.endorsement().owned())));
                    }
                    assertThrows(IllegalArgumentException.class,pending::target);
                }
                f.snapshot("applied");
            }finally{V53NativeApplicationTest.save(f);}
        }
    }
    @Test void refusesCallerConstructedForeignAndPreviousOwnerApplications()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-pending-publication/guards-"+UUID.randomUUID()));
        var f=certified(Files.createDirectory(temp.resolve("guards")),raw,3,false);var a=f.request.targets().get(0);var b=f.request.targets().get(1);
        try {
            MembershipGrantJournal.Applied old;
            try(var owner=f.open(a,"first-owner")){old=owner.applyCurrent(builder().configuration(),a.materialization());}
            try(var owner=f.open(b,"foreign-owner")){assertThrows(IllegalArgumentException.class,()->owner.pendingPublication(old));}
            try(var owner=f.open(a,"reopened-owner")) {
                assertThrows(IllegalArgumentException.class,()->owner.pendingPublication(old));
                var fresh=owner.applyCurrent(builder().configuration(),a.materialization());
                assertThrows(IllegalArgumentException.class,()->owner.pendingPublication(new MembershipGrantJournal.Applied(fresh.plan(),fresh.endorsement())));
                var pending=owner.pendingPublication(fresh);assertEquals(1L,pending.target().cut().get("index"));
                owner.observeCurrent(Map.of("counter",9L,"proposer","node-1","incarnation",a.identity().storageId().toString()));
                assertThrows(IllegalArgumentException.class,pending::target);assertThrows(IllegalArgumentException.class,pending::parent);
                assertThrows(IllegalArgumentException.class,pending::owner);assertThrows(IllegalArgumentException.class,pending::originals);
            }
        }finally{V53NativeApplicationTest.save(f);}
    }
    @Test void applicationFileReplacementRevokesTheCapability()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-pending-publication/tamper-"+UUID.randomUUID()));
        var f=certified(Files.createDirectory(temp.resolve("tamper")),raw,3,false);var t=f.request.targets().getFirst();
        try(var owner=f.open(t,"tamper")) {
            var pending=owner.pendingPublication(owner.applyCurrent(builder().configuration(),t.materialization()));
            Path file=t.replicaDirectory().resolve("applied-end/ack.gsr"),replaced=temp.resolve("old-ack");
            Files.move(file,replaced);Files.write(file,Files.readAllBytes(replaced));
            assertThrows(IllegalArgumentException.class,pending::target);
        }finally{V53NativeApplicationTest.save(f);}
    }
    @Test void twoFreshProcessesRecoverTheSameTargetFromOriginalDiskOnly()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-pending-publication/process-"+UUID.randomUUID()));
        System.out.println("v53PendingPublicationProcessEvidence="+raw.toAbsolutePath());
        var f=certified(Files.createDirectory(temp.resolve("process")),raw,3,false);var t=f.request.targets().getFirst();
        try {
            for(int run=1;run<=2;run++) {
                Path evidence=raw.resolve("process-"+run),log=raw.resolve("process-"+run+".log");
                var child=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                        V53PendingPublicationWorker.class.getName(),t.replicaDirectory().toString(),t.materialization().directory().toString(),evidence.toString())
                        .redirectErrorStream(true).redirectOutput(log.toFile()).start();
                try {assertTrue(child.waitFor(60,TimeUnit.SECONDS));assertEquals(0,child.exitValue(),Files.readString(log));}
                finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
                V53JournalApplicationTest.copy(t.replicaDirectory(),raw.resolve("recovered-"+run));
            }
            assertEquals(V53ReplayFilesTest.files(raw.resolve("process-1")),V53ReplayFilesTest.files(raw.resolve("process-2")));
            assertEquals(V53ReplayFilesTest.files(raw.resolve("recovered-1")),V53ReplayFilesTest.files(raw.resolve("recovered-2")));
            for(String name:List.of("selector.gsr","pending.accept","grants.gsr"))
                assertArrayEquals(Files.readAllBytes(raw.resolve("certified/node-1").resolve(name)),Files.readAllBytes(t.replicaDirectory().resolve(name)));
        }finally{V53NativeApplicationTest.save(f);}
    }
}
