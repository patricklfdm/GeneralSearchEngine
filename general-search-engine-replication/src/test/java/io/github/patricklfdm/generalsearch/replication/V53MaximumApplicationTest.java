package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real typed image at the native backup budget, without padded/invalid bytes. */
class V53MaximumApplicationTest {
    @TempDir Path temp;
    static final UUID HISTORY=new UUID(8,640);
    static List<Doc> documents(int finalBytes) {
        var result=new ArrayList<Doc>();
        for(int id=0;id<1023;id++)result.add(new Doc(id,"x".repeat(65536-Integer.toString(id).length()-1)));
        result.add(new Doc(1023,"y".repeat(finalBytes)));return result;
    }
    static void progress(String stage){System.out.println("v53MaximumApplicationProgress="+stage);System.out.flush();}
    @Test void exactMaximumSurvivesAdmittedCapturePublicationAndSevenImageRetirement()throws Exception {
        // Only retained copies may use an external evidence disk. The admitted
        // owner and materialization remain on the original Linux test filesystem.
        Path out=Path.of(System.getProperty("v53.maximum.output","target/v53-max-application"),"run-"+UUID.randomUUID());Files.createDirectories(out);
        System.out.println("v53MaximumApplicationEvidence="+out.toAbsolutePath());progress("calibrate");
        var config=builder().configuration();var core=storage(temp.resolve("core-anchor"),2);
        var base=new DurableApplicationState<>(HISTORY,41,documents(0),config.indexes());
        byte[] calibration=MembershipApplicationImage.capture(config,core,base,temp.resolve("calibration"));
        long exported=0;for(String member:MembershipApplicationImage.MEMBERS)exported+=Files.size(temp.resolve("calibration").resolve(member));
        int administration=Math.toIntExact(exported+MembershipApplicationImage.OVERHEAD-calibration.length);
        // The core writer charges its original request ID before image normalization.
        // It is part of the existing backup budget, not free image capacity.
        assertEquals(32,administration);int nativeImageLimit=MembershipApplicationImage.MAXIMUM-administration;
        int extra=nativeImageLimit-calibration.length;assertTrue(extra>0 && extra+5<=65536);
        Files.write(out.resolve("calibration.image"),calibration);
        var state=new DurableApplicationState<>(HISTORY,41,documents(extra),config.indexes());Path source=temp.resolve("source");
        byte[] full=MembershipApplicationImage.capture(config,core,state,source);assertEquals(nativeImageLimit,full.length);
        Files.write(out.resolve("source.image"),full);V53JournalApplicationTest.copy(source,out.resolve("source-backup"));
        var original=V53ReplayFilesTest.files(source);progress("over-limit-refusal");
        var tooLarge=new DurableApplicationState<>(HISTORY,41,documents(extra+1),config.indexes());
        var failure=assertThrows(DurableOperationException.class,()->MembershipApplicationImage.capture(config,core,tooLarge,temp.resolve("over-limit")));
        assertEquals(DurableOperationException.Reason.CAPACITY_EXCEEDED,failure.reason());assertEquals(original,V53ReplayFilesTest.files(source));
        byte[] oversized=Arrays.copyOf(full,MembershipApplicationImage.MAXIMUM+1);Path refused=temp.resolve("oversized-read");
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationImage.read(config,core,oversized,refused));assertFalse(Files.exists(refused));
        progress("public-bootstrap");var helper=new V53BootstrapSeedTest();helper.temp=temp;
        var request=helper.request(temp.resolve("group"),5,source);Path raw=Files.createDirectory(out.resolve("publication"));
        var f=new V53BootstrapPublicationTest.Fixture(raw,request);assertEquals(nativeImageLimit,f.original.seed.application().length);
        assertNotEquals(HISTORY,f.result.root().historyId());assertEquals(41,f.result.applicationSequence());
        boolean[] peak={false};
        f.observer=(target,operation,event)->{
            var usage=f.resources.usage();
            if(!peak[0] && event.equals("FLOOR_BEFORE_RETURN") && usage.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)==7) {
                var images=new ArrayList<Map<String,Object>>();
                try(var paths=Files.walk(target.replicaDirectory())) {for(var path:paths.filter(p->p.toString().endsWith(".image")).toList()) {
                    assertEquals(nativeImageLimit,Files.size(path));
                    images.add(Map.of("path",target.replicaDirectory().relativize(path).toString(),"bytes",Files.size(path),"links",Files.getAttribute(path,"unix:nlink")));
                }}
                assertEquals(7,images.size());assertTrue(usage.staging()>=7L*nativeImageLimit);
                V53JournalApplicationTest.copy(target.replicaDirectory(),out.resolve("seven-image-floor"));
                Files.write(out.resolve("peak.json"),canonical(Map.of("node",target.identity().nodeId().value(),"operation",operation,"event",event,
                        "metadata",usage.metadata(),"staging",usage.staging(),"images",images,"leases",usage.leases()),65536));peak[0]=true;progress("seven-image-floor-retained");
            }
        };
        try {
            progress("first-campaign");var walk=new V53AdmittedCrossViewTest.Walk(f);
            walk.publish("BARRIER",null);walk.campaign();walk.publish("BARRIER",null);walk.campaign();
            assertTrue(peak[0]);assertEquals(7,f.peakImages);assertEquals(0,f.resources.usage().leases());progress("typed-final-read");
            for(var target:request.targets())try(var owner=f.open(target,"inspect-maximum")) {
                var copy=owner.floorCopyCurrent();assertEquals(2L,copy.capsule.context.cut.get("index"));assertEquals(41L,copy.capsule.context.catalog.get("applicationSequence"));
                assertArrayEquals(f.original.seed.application(),copy.fileBytes(copy.capsule.terminal().application()+".image"));
                if(target==request.targets().getFirst()) {
                    Path inspected=temp.resolve("typed-final");
                    var loaded=MembershipApplicationImage.read(config,target.materialization(),copy.fileBytes(copy.capsule.terminal().application()+".image"),inspected);
                    V53JournalApplicationTest.copy(inspected,out.resolve("typed-final"));
                    assertEquals(state.documents(),loaded.documents());assertEquals(f.result.root().historyId(),loaded.history());assertEquals(41,loaded.sequence());
                }
            }
            assertEquals(0,f.resources.usage().leases());assertEquals(f.result,MembershipStorageOperations.readBootstrapResult(request.operationDirectory()));
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-maximum-application-v1","status","PASS","imageBytes",full.length,"administrationBytes",administration,"finalValueBytes",extra,
                    "documents",1024,"voters",5,"slots",2,"peakImages",f.peakImages,"publicRuntime",false),65536));progress("complete");
        }finally {
            Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        }
    }
}
