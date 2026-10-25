package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Repeated process death on a genuinely admitted, subsequently removed voter. */
class V53AdmittedAdoptionProcessTest {
    @TempDir Path temp;
    @Test void certifiedRemovalSurvivesAdoptionAndRecoveryDeath()throws Exception {
        Path out=Path.of("target/v53-admitted-adoption-process/run-"+UUID.randomUUID());Files.createDirectories(out);
        System.out.println("v53AdmittedAdoptionProcessEvidence="+out.toAbsolutePath());var profiles=new ArrayList<Map<String,Object>>();
        for(int size:List.of(5,4))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");Path path=Files.createDirectory(out.resolve(name));
            Path work=Files.createDirectory(temp.resolve(name)),raw=Files.createDirectory(path.resolve("reference"));
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(work.resolve("producer")),raw,size,backup);
            var walk=new V53AdmittedCrossViewTest.Walk(f);var cases=new ArrayList<Map<String,Object>>();boolean[] exercised={false};
            walk.beforeAdoption=(target,remote)->{
                if(exercised[0])return;exercised[0]=true;
                Path node=target.replicaDirectory(),seed=work.resolve("seed"),inputs=path.resolve("inputs.json");V53JournalApplicationTest.copy(node,seed);
                Path source=Files.createDirectory(path.resolve("remote"));Files.write(source.resolve("source.gscp"),remote.capsule.packet.bytes());
                for(String h:remote.capsule.packet.images().keySet())Files.write(source.resolve(h+".image"),remote.fileBytes(h+".image"));
                Files.write(inputs,canonical(Map.of("node",node.toString(),"materialization",target.materialization().directory().toString(),
                        "observations",V53JournalApplicationTest.observations(f.observations)),1024*1024));int ordinal=0;
                for(String mode:List.of("halt","kill"))for(String cut:V53AdoptionInstallTest.CUTS) {
                    Files.move(node,work.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);
                    String caseName=mode+"-"+cut;Path sample=Files.createDirectory(path.resolve(caseName));
                    int first=V53RetirementSourceProcessTest.child(V53AdmittedAdoptionProcessWorker.class,inputs,node,sample,"fault",cut,mode);
                    V53JournalApplicationTest.copy(node,sample.resolve("first"));
                    String second=Set.of("INSTALL_SELECTOR_RENAMED","INSTALL_PARENT_FORCED","ADOPTION_INSTALL_BEFORE_RETURN").contains(cut)?"ACCEPT_ACTIVE_FORCED":"INSTALL_SELECTOR_FORCED";
                    int again=V53RetirementSourceProcessTest.child(V53AdmittedAdoptionProcessWorker.class,inputs,node,sample,"recovery",second,"halt");
                    V53JournalApplicationTest.copy(node,sample.resolve("second"));
                    int last=V53RetirementSourceProcessTest.child(V53AdmittedAdoptionProcessWorker.class,inputs,node,sample,"resume","none","none");
                    V53JournalApplicationTest.copy(node,sample.resolve("final"));
                    assertEquals(f.immutable.get(target.identity().nodeId().value()),V53BootstrapStoreAdmissionTest.originals(node));
                    cases.add(Map.of("case",caseName,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,last)));
                    System.out.println("v53AdmittedAdoptionProcessCase="+name+"/"+caseName+" PASS");System.out.flush();
                }
                Files.move(node,work.resolve("last"));V53JournalApplicationTest.copy(seed,node);
            };
            try {
                walk.publish("BARRIER",null);for(int number=1;walk.active.size()>3;number++)walk.removeLast(number);
                walk.publish("DATA",V53DistinctMinorityTest.payload(f,707,"after-removal"));walk.publish("BARRIER",null);
                for(var target:walk.active)try(var owner=f.open(target,"inspect-final")) {
                    var copy=owner.floorCopyCurrent();assertEquals((long)size-3,copy.capsule.context.view.get("generation"));
                    assertEquals(f.result.applicationSequence()+1,copy.capsule.context.catalog.get("applicationSequence"));
                    var loaded=MembershipApplicationImage.read(builder().configuration(),target.materialization(),copy.fileBytes(copy.capsule.terminal().application()+".image"),raw.resolve("typed-"+target.identity().nodeId().value()));
                    assertEquals(1,loaded.documents().stream().filter(d->d.equals(new Doc(707,"after-removal"))).count());assertEquals(f.result.root().historyId(),loaded.history());
                }
                assertEquals(f.result,MembershipStorageOperations.readBootstrapResult(f.request.operationDirectory()));assertEquals(0,f.resources.usage().leases());
                assertTrue(exercised[0]);assertEquals(38,cases.size());
                Files.write(path.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-admitted-adoption-process-v1","status","PASS","cases",cases,
                        "freshProcesses",cases.size()*3,"lockProbes",cases.size()/2,"inputsSha256",hash(Files.readAllBytes(path.resolve("inputs.json"))),
                        "publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
                profiles.add(Map.of("case",name,"status","PASS","cases",cases.size()));
            }finally {
                Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
                Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
            }
        }
        Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-admitted-adoption-matrix-v1","status","PASS","profiles",profiles,"cases",152,"freshProcesses",456,"lockProbes",76,"publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
    }
}
