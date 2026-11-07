package io.github.patricklfdm.generalsearch.replication;

import java.io.RandomAccessFile;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Streaming object-store components and actual backup writer observations. */
class V53CaptureObjectsTest {
    @TempDir Path temp;
    @Test void deduplicatesButRechecksOriginalAndExistingObjectBytes()throws Exception {
        Path original=Files.createDirectory(temp.resolve("original"));Path pool=Files.createDirectory(temp.resolve("pool"));
        byte[] raw={1,2,3};Files.write(original.resolve("one"),raw);Files.write(original.resolve("two"),raw);
        var snapshot=new V53CaptureFiles(original);var store=new V53CaptureFiles.ObjectStore(pool);
        store.retain(snapshot);store.retain(snapshot);assertEquals(3,store.bytes());assertEquals(1,store.count());
        Files.write(pool.resolve(hash(raw)),new byte[]{3,2,1});
        assertThrows(IllegalArgumentException.class,()->store.retain(snapshot));
        Files.write(pool.resolve(hash(raw)),raw);Files.write(original.resolve("one"),new byte[]{3,2,1});
        assertThrows(IllegalArgumentException.class,()->store.retain(snapshot));
    }
    @Test void rejectsUntrackedObjectsAndInvalidPolicyBeforeCreatingCaptures()throws Exception {
        Path pool=Files.createDirectory(temp.resolve("pool"));Files.write(pool.resolve("untracked"),new byte[0]);
        assertThrows(IllegalArgumentException.class,()->new V53CaptureFiles.ObjectStore(pool));
        assertThrows(IllegalArgumentException.class,()->new V53SourceRetirementCapture(temp,new ArrayList<>(),
                MembershipBootstrapSource.EMPTY,V53WireArchive.Layout.SEGMENTED_BACKUP));
        assertThrows(IllegalArgumentException.class,()->new V53PublicationResourceCapture(temp,
                MembershipBootstrapSource.EMPTY,V53WireArchive.Layout.SEGMENTED_BACKUP));
        assertFalse(Files.exists(temp.resolve(V53SourceRetirementCapture.DIRECTORY)));
        assertFalse(Files.exists(temp.resolve(V53PublicationResourceCapture.DIRECTORY)));
    }
    @Test void streamsFiveDistinct64MiBObjectsWith32MiBHeap()throws Exception {
        Path original=Files.createDirectory(temp.resolve("original"));Path pool=Files.createDirectory(temp.resolve("pool"));
        for(int i=0;i<5;i++)try(var out=new RandomAccessFile(original.resolve("image-"+i).toFile(),"rw")) {
            out.write(i+1);out.setLength(64L*1024*1024);
        }
        Path log=temp.resolve("probe.log");
        var child=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-Xmx32m","-XX:-UsePerfData","-cp",
                System.getProperty("java.class.path"),Probe.class.getName(),original.toString(),pool.toString())
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {assertTrue(child.waitFor(90,TimeUnit.SECONDS),"streaming object probe timeout");assertEquals(0,child.exitValue(),Files.readString(log));}
        finally {if(child.isAlive())child.destroyForcibly();}
        assertThrows(IllegalArgumentException.class,()->V53GrantCapture.inventory(original));
    }

    @Test void capturesRealBackupPublicationAndRetirementWithoutReleasingWriterLocks()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-capture-objects/run-"+UUID.randomUUID()));
        System.out.println("v53CaptureObjectsEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(temp,raw,3,true);f.ownedHistory=true;f.nativeApplication=true;
        for(var target:f.request.targets())try(var owner=f.open(target,"initialize")) {
            owner.initializePeerRetention();owner.initializeLearnerRetention();owner.initializeFutureRetention();
        }
        var events=new ArrayList<Map<String,Object>>();
        var retirement=new V53SourceRetirementCapture(raw,events,f.request.source(),V53WireArchive.Layout.SEGMENTED_BACKUP);
        var publication=new V53PublicationResourceCapture(raw,f.request.source(),V53WireArchive.Layout.SEGMENTED_BACKUP);
        f.observer=(member,scope,point)->{
            String node=member.identity().nodeId().value();int index=events.size();
            events.add(Map.of("node",node,"scope",scope,"event",point));
            retirement.at(node,scope,member.replicaDirectory(),point);
            publication.at(node,scope,member.replicaDirectory(),f.resources,point,index);
        };
        f.campaign(1);f.publishOnce(1,false);f.campaign(2);
        for(var target:f.request.targets())try(var owner=f.open(target,"lock-probe")) {
            new V53MembershipOwnershipTest().probe(target.replicaDirectory().resolve("replica.lock"));
        }
        publication.save();Files.write(raw.resolve("events.json"),canonical(events,8*1024*1024),StandardOpenOption.CREATE_NEW);
        assertEquals(0,f.resources.usage().leases());
        assertEquals(45,events.stream().filter(v->V53SourceRetirementCapture.EVENT.equals(v.get("event"))).count());
        var index=object(parse(Files.readAllBytes(raw.resolve(V53PublicationResourceCapture.DIRECTORY).resolve("index.json")),1024*1024));
        assertEquals(true,index.get("complete"));assertEquals(33,((List<?>)index.get("captures")).size());
    }

    public static final class Probe {
        public static void main(String[] args)throws Exception {
            var snapshot=new V53CaptureFiles(Path.of(args[0]));var store=new V53CaptureFiles.ObjectStore(Path.of(args[1]));
            store.retain(snapshot);store.retain(snapshot);
            if(store.bytes()!=320L*1024*1024 || store.count()!=5)throw new AssertionError("streaming objects accounting");
            System.out.println("v53CaptureObjects=PASS bytes=335544320 heap=33554432");
        }
    }
}
