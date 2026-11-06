package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Explicit long qualification, excluded by the ordinary *Test name pattern.
 * The diagnostic traverses the same storage operations with a separately labelled small image. */
class V53MaximumTransitionQualification {
    @TempDir Path temp;
    static final List<Doc> SMALL=List.of(new Doc(7,"original"),new Doc(2,"你好"));
    @Test void maximumImageRefusalThenRemovalCompletes()throws Exception {run(true);}
    @Test void smallImageDiagnosticTraversesSameRemoval()throws Exception {run(false);}

    void run(boolean maximum)throws Exception {
        String mode=maximum?"maximum":"diagnostic";
        Path out=Files.createDirectories(Path.of(System.getProperty("v53.maximum.transition.output","target/v53-maximum-transition"),"run-"+UUID.randomUUID()));
        System.out.println("v53MaximumTransitionEvidence="+out.toAbsolutePath());
        var config=builder().configuration();Path source;byte[] image;int extra=-1;
        if(maximum) {
            var seed=V53MaximumApplicationTest.captureMaximum(temp,out);source=seed.source();image=seed.image();extra=seed.extra();
        }else {
            source=temp.resolve("source");image=MembershipApplicationImage.capture(config,storage(temp.resolve("core"),2),
                    new io.github.patricklfdm.generalsearch.durability.DurableApplicationState<>(V53MaximumApplicationTest.HISTORY,41,SMALL,config.indexes()),source);
            Files.write(out.resolve("source.image"),image);V53JournalApplicationTest.copy(source,out.resolve("source-backup"));
        }
        var helper=new V53BootstrapSeedTest();helper.temp=temp;
        var request=helper.request(temp.resolve("group"),5,source);Path raw=Files.createDirectory(out.resolve("publication"));
        var f=new V53BootstrapPublicationTest.Fixture(raw,request);int extent=image.length;boolean[] peak={false};
        f.observer=(target,operation,event)->{
            if(peak[0] || !event.equals("FLOOR_BEFORE_RETURN") || f.resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)!=7)return;
            assertEquals("node-1",target.identity().nodeId().value());assertEquals("campaign-3-settled-maintain",operation);
            var images=new ArrayList<Map<String,Object>>();
            try(var paths=Files.walk(target.replicaDirectory())) {for(var path:paths.filter(p->p.toString().endsWith(".image")).sorted().toList()) {
                assertEquals(extent,Files.size(path));assertEquals(1,Files.getAttribute(path,"unix:nlink"));
                images.add(Map.of("path",target.replicaDirectory().relativize(path).toString(),"bytes",Files.size(path),"links",1));
            }}
            assertEquals(7,images.size());var usage=f.resources.usage();
            V53JournalApplicationTest.copy(target.replicaDirectory(),out.resolve("seven-image-floor"));
            Files.write(out.resolve("peak.json"),canonical(Map.of("node","node-1","operation",operation,"event",event,
                    "metadata",usage.metadata(),"staging",usage.staging(),"images",images,"leases",usage.leases()),65536));
            probe(out,temp.resolve("refused"),target,f.resources);
            peak[0]=true;V53MaximumApplicationTest.progress("receiver-refused-and-closed");
        };
        try {
            var walk=new V53AdmittedCrossViewTest.Walk(f);walk.publish("BARRIER",null);walk.campaign();
            assertTrue(peak[0]);walk.removeLast(1);walk.publish("BARRIER",null);walk.campaign();
            assertEquals(10,walk.slot);assertEquals(4,walk.active.size());assertEquals(7,f.peakImages);
            for(var target:walk.active)try(var owner=f.open(target,"inspect-maximum-transition")) {
                var copy=owner.floorCopyCurrent();assertEquals(10L,copy.capsule.context.cut.get("index"));
                assertEquals(1L,copy.capsule.context.view.get("generation"));assertEquals(41L,copy.capsule.context.catalog.get("applicationSequence"));
                byte[] actual=copy.fileBytes(copy.capsule.terminal().application()+".image");assertArrayEquals(f.original.seed.application(),actual);
                if(target==walk.active.getFirst()) {
                    Path typed=temp.resolve("typed-final");var loaded=MembershipApplicationImage.read(config,target.materialization(),actual,typed);
                    assertEquals(maximum?V53MaximumApplicationTest.documents(extra):SMALL,loaded.documents());
                    assertEquals(f.result.root().historyId(),loaded.history());assertEquals(41,loaded.sequence());
                    V53JournalApplicationTest.copy(typed,out.resolve("typed-final"));
                }
            }
            assertEquals(0,f.resources.usage().leases());assertEquals(f.result,MembershipStorageOperations.readBootstrapResult(request.operationDirectory()));
            var receipt=new TreeMap<String,Object>();receipt.put("schema","gse-v53-maximum-transition-v1");receipt.put("status",maximum?"PASS":"DIAGNOSTIC");
            receipt.put("mode",mode);receipt.put("imageBytes",extent);receipt.put("finalValueBytes",extra);receipt.put("slots",10);receipt.put("voters",4);
            receipt.put("generation",1);receipt.put("peakImages",7);receipt.put("publicRuntime",false);receipt.put("phase3Complete",false);
            Files.write(out.resolve("receipt.json"),canonical(receipt,65536));
        }finally {
            Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
            Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        }
    }

    /** No fabricated reservations: the original owner is still inside its real floor callback. */
    static void probe(Path out,Path scratch,MembershipBootstrapTarget<Integer,Doc> target,MembershipResources resources)throws java.io.IOException {
        Path authority=target.replicaDirectory();var before=V53ReplayFilesTest.files(authority);
        Path packetPath;
        try(var files=Files.walk(authority.resolve("generations"))) {
            packetPath=files.filter(p->p.getFileName().toString().equals("source.gscp")).sorted().findFirst().orElseThrow();
        }
        byte[] packet=Files.readAllBytes(packetPath);var decoded=MembershipSourcePacket.decode(packet);var cap=decoded.capsule().value();
        var baseline=V53CombinedReceiveResourcesTest.usage(resources);var states=new ArrayList<Map<String,Object>>();
        states.add(Map.of("stage","before","usage",baseline));String reason;
        try(var receiver=MembershipSourceReceive.learner(scratch,(String)cap.get("root"),target.identity(),object(cap.get("cut")),
                UUID.randomUUID(),UUID.randomUUID(),new MembershipSourceExport.Content(hash(packet),packet.length,MembershipTransfer.Kind.CAPSULE),
                resources,1024,()->0L,0,100)) {
            var binding=receiver.packetBinding();
            for(int at=0;at<packet.length;at+=1024) {
                byte[] chunk=Arrays.copyOfRange(packet,at,Math.min(packet.length,at+1024));receiver.chunk(binding,at,chunk,hash(chunk));
            }
            reason=assertThrows(IllegalArgumentException.class,()->receiver.finish(binding)).getMessage();assertEquals("resource ownership/count",reason);
            assertEquals(Set.of("source.gscp"),MembershipBasisSources.children(scratch,8));assertArrayEquals(packet,Files.readAllBytes(scratch.resolve("source.gscp")));
            assertThrows(IllegalArgumentException.class,receiver::imageBindings);
            states.add(Map.of("stage","refused","usage",V53CombinedReceiveResourcesTest.usage(resources)));
            V53JournalApplicationTest.copy(scratch,out.resolve("receiver-refused"));
        }
        assertFalse(Files.exists(scratch));assertEquals(baseline,V53CombinedReceiveResourcesTest.usage(resources));assertEquals(before,V53ReplayFilesTest.files(authority));
        states.add(Map.of("stage","closed","usage",V53CombinedReceiveResourcesTest.usage(resources)));
        Files.write(out.resolve("receiver.json"),canonical(Map.of("schema","gse-v53-maximum-receiver-v1","reason",reason,
                "packet",authority.relativize(packetPath).toString(),"packetSha256",hash(packet),"packetBytes",packet.length,
                "authorityBefore",hashes(before),"authorityAfter",hashes(V53ReplayFilesTest.files(authority)),"states",states,"scratchAbsent",true),1024*1024));
    }
    static List<Map<String,String>> hashes(Map<String,String> files) {
        return files.entrySet().stream().sorted(Map.Entry.comparingByKey()).map(v->Map.of("path",v.getKey(),"sha256",v.getValue())).toList();
    }
}
