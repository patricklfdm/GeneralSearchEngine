package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Native actual-owner recovery through every original adoption boundary. */
class V53OwnedAdoptionProcessTest {
    @TempDir Path temp;
    @Test void actualRemovalSurvivesDeathDuringTypedAdoptionAndRecovery()throws Exception {
        Path out=Files.createDirectories(Path.of("target/v53-owned-adoption-process/run-"+UUID.randomUUID()));
        System.out.println("v53OwnedAdoptionProcessEvidence="+out.toAbsolutePath());
        Path work=Files.createDirectory(temp.resolve("work")),raw=Files.createDirectory(out.resolve("reference")),casesRoot=Files.createDirectory(out.resolve("cases"));
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(work.resolve("producer")),raw,4,false);f.ownedHistory=true;
        var walk=new V53AdmittedCrossViewTest.Walk(f);var cases=new ArrayList<Map<String,Object>>();
        walk.beforeAdoption=(target,remote)->{
            Path node=target.replicaDirectory(),seed=work.resolve("seed"),inputs=out.resolve("inputs.json");V53JournalApplicationTest.copy(node,seed);
            var source=f.request.targets().getFirst();var sourceBefore=V53ReplayFilesTest.files(source.replicaDirectory());
            Files.write(inputs,canonical(Map.of("node",node.toString(),"materialization",target.materialization().directory().toString(),
                    "source",source.replicaDirectory().toString(),"sourceMaterialization",source.materialization().directory().toString()),65536));int ordinal=0;
            for(String mode:List.of("halt","kill"))for(String cut:V53AdoptionInstallTest.CUTS) {
                Files.move(node,work.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);
                String name=mode+"-"+cut;Path sample=Files.createDirectory(casesRoot.resolve(name));
                int first=V53RetirementSourceProcessTest.child(V53OwnedAdoptionProcessWorker.class,inputs,node,sample,"fault",cut,mode);
                V53JournalApplicationTest.copy(node,sample.resolve("first"));
                String second=Set.of("INSTALL_SELECTOR_RENAMED","INSTALL_PARENT_FORCED","ADOPTION_INSTALL_BEFORE_RETURN").contains(cut)?"ACCEPT_ACTIVE_FORCED":"INSTALL_SELECTOR_FORCED";
                int again=V53RetirementSourceProcessTest.child(V53OwnedAdoptionProcessWorker.class,inputs,node,sample,"recovery",second,"halt");
                V53JournalApplicationTest.copy(node,sample.resolve("second"));
                int last=V53RetirementSourceProcessTest.child(V53OwnedAdoptionProcessWorker.class,inputs,node,sample,"resume","none","none");
                V53JournalApplicationTest.copy(node,sample.resolve("final"));
                assertEquals(sourceBefore,V53ReplayFilesTest.files(source.replicaDirectory()));
                cases.add(Map.of("case",name,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,last)));
                System.out.println("v53OwnedAdoptionProcessCase="+name+" PASS");System.out.flush();
            }
            Files.move(node,work.resolve("last"));V53JournalApplicationTest.copy(seed,node);
        };
        walk.adoption=(target,remote,images,number)->{try(var owner=f.open(target,"removed-adopt-"+number)) {
            var manifest=owner.adoptCurrent(remote.capsule,images,List.of());assertArrayEquals(manifest.bytes(),owner.adoptCurrent(remote.capsule,images,List.of()).bytes());
        }};
        try {
            walk.publish("BARRIER",null);walk.removeLast(1);walk.publish("DATA",V53DistinctMinorityTest.payload(f,707,"after-removal"));walk.publish("BARRIER",null);
            for(var target:walk.active)try(var owner=f.open(target,"inspect-final")) {
                var copy=owner.floorCopyCurrent();assertEquals(1L,copy.capsule.context.view.get("generation"));
                var loaded=MembershipApplicationImage.read(builder().configuration(),target.materialization(),copy.fileBytes(copy.capsule.terminal().application()+".image"),raw.resolve("typed-"+target.identity().nodeId().value()));
                assertEquals(1,loaded.documents().stream().filter(d->d.equals(new Doc(707,"after-removal"))).count());
            }
            assertEquals(38,cases.size());assertEquals(0,f.resources.usage().leases());
        }finally {
            Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-owned-adoption-process-v1","status",cases.size()==38?"PASS":"INCOMPLETE",
                    "cases",cases,"freshProcesses",114,"lockProbes",19,"historicalObservationsSupplied",false,"publicRuntime",false,"powerLoss",false),65536));
        }
    }
}
