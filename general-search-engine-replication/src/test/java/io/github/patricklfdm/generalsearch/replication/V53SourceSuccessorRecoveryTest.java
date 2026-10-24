package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SourceSuccessorRecoveryTest {
    @TempDir Path temp;
    static MembershipGrantJournal open(V53BootstrapPublicationTest.Fixture f,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return V53CoveredContextTest.open(new V53CoveredContextTest.Prepared(f,null),resources,cut);
    }
    @Test void exactForcedSuccessorIsRequiredThroughRepeatedRetirementRecovery()throws Exception {
        Path out=Path.of("target/v53-source-successor-recovery/run-"+UUID.randomUUID());Files.createDirectories(out);
        System.out.println("v53SourceSuccessorRecoveryEvidence="+out.toAbsolutePath());
        var driver=new V53CoveredContextMixedTest();driver.temp=Files.createDirectory(temp.resolve("producer"));var rows=new ArrayList<Map<String,Object>>();
        var mixed=driver.prepared(4,false,(f,ids)->{
            Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);
            String id=ids.get("node-1");var resources=new MembershipResources(512*MembershipResources.MIB);var original=V53ReplayFilesTest.files(seed);
            MembershipSourceRetirementPlan plan;String currentPromise;
            try(var owner=open(f,resources,e->{})){plan=owner.planSourceRetirement(id);currentPromise=planSourcePromise(node);}
            var sourceIds=new HashSet<String>();try(var dirs=Files.list(node.resolve("sources"))){dirs.filter(Files::isDirectory).forEach(p->sourceIds.add(p.getFileName().toString()));}
            byte[] journal=MembershipJournalRotation.excludingSource(Files.readAllBytes(node.resolve("grants.gsr")),Set.of(currentPromise),sourceIds,plan);
            var expected=new TreeMap<>(original);expected.keySet().removeIf(p->p.startsWith("sources/"+id+"/"));expected.put("grants.gsr",hash(journal));int ordinal=0;
            for(String point:List.of("SOURCE_RETIREMENT_FORCED","SOURCE_RETIREMENT_JOURNAL_PRUNED","SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_DIRECTORY_DELETED")) {
                Files.move(node,temp.resolve("prior-"+ordinal++));V53JournalApplicationTest.copy(seed,node);Path raw=Files.createDirectory(out.resolve(point));
                var events=new ArrayList<List<String>>();
                for(String cut:List.of(point,"SOURCE_RETIREMENT_JOURNAL_PRUNED")) {
                    var trace=new ArrayList<String>();events.add(trace);
                    assertThrows(IOException.class,()->{try(var owner=open(f,resources,e->{trace.add(e);if(e.equals(cut))throw new IOException(e);})){owner.retireSource(id);}});
                    assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve(events.size()==1?"first":"second"));
                    assertArrayEquals(Files.readAllBytes(seed.resolve("pending.accept")),Files.readAllBytes(node.resolve("pending.accept")));
                }
                var trace=new ArrayList<String>();events.add(trace);
                try(var owner=open(f,resources,trace::add)){if(Files.exists(node.resolve("sources/"+id)))owner.retireSource(id);}
                assertEquals(0,resources.usage().leases());assertEquals(expected,V53ReplayFilesTest.files(node));V53JournalApplicationTest.copy(node,raw.resolve("final"));
                Files.write(raw.resolve("events.json"),canonical(events,1024*1024));rows.add(Map.of("case",point,"status","PASS"));
            }
            for(boolean resumed:List.of(false,true))for(String damage:List.of("missing","corrupt")) {
                Files.move(node,temp.resolve("prior-"+ordinal++));V53JournalApplicationTest.copy(seed,node);
                String name=(resumed?"resumed-":"plan-")+damage;Path raw=Files.createDirectory(out.resolve(name));
                if(resumed)assertThrows(IOException.class,()->{try(var owner=open(f,resources,e->{if(e.equals("SOURCE_RETIREMENT_JOURNAL_PRUNED"))throw new IOException(e);})){owner.retireSource(id);}});
                Path restored=temp.resolve("repair-"+ordinal);V53JournalApplicationTest.copy(node,restored);Path vote=node.resolve("pending.accept");
                if(damage.equals("missing"))Files.write(vote,MembershipPendingAccept.empty());else {byte[] bytes=Files.readAllBytes(vote);bytes[bytes.length-1]^=1;Files.write(vote,bytes);}
                V53JournalApplicationTest.copy(node,raw.resolve("invalid"));
                var before=V53ReplayFilesTest.files(node);String reason=null;
                for(int retry=0;retry<2;retry++) {
                    var failure=assertThrows(IllegalArgumentException.class,()->{try(var owner=open(f,resources,e->{})){owner.planSourceRetirement(id);}});
                    if(reason!=null)assertEquals(reason,failure.getMessage());reason=failure.getMessage();
                    assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
                }
                V53JournalApplicationTest.copy(node,raw.resolve("refused"));
                Files.move(node,temp.resolve("damaged-"+ordinal));V53JournalApplicationTest.copy(restored,node);
                try(var owner=open(f,resources,e->{})){if(Files.exists(node.resolve("sources/"+id)))owner.retireSource(id);}
                assertEquals(expected,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
                V53JournalApplicationTest.copy(node,raw.resolve("restored"));
                rows.add(Map.of("case",name,"status","PASS","reason",reason));
            }
            Files.move(node,temp.resolve("last"));V53JournalApplicationTest.copy(seed,node);
        });
        V53CoveredContextMixedTest.complete(mixed);V53JournalApplicationTest.copy(mixed.prepared().f().raw,out.resolve("reference"));
        Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-source-successor-recovery-v1","status","PASS","cases",rows,
                "interruptions",8,"repeatedRefusals",8,"publicBootstrap",true,"freshProcesses",false,"runtimeEnabled",false),65536));
        assertEquals(8,rows.size());
    }
    private static String planSourcePromise(Path node)throws Exception {
        String slot=(String)decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR").value().get("generation");
        return decode(Files.readAllBytes(node.resolve("generations/"+slot+"/promise.gsr")),"records","PROMISE").digest();
    }
}
