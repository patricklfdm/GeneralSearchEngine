package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

class V53VotePrefixCaptureTest {
    @TempDir Path temp;
    interface Call {void run(MembershipGrantJournal store)throws Exception;}
    @Test void actualThreeOwnerVotesRetainEveryOriginalReplacementPrefix()throws Exception {
        var f=new V53PendingCertificateFixture(3,0);Path group=temp.resolve("group");f.f.provision(group);f.f.install(group);
        Path raw=Files.createDirectories(Path.of("target/v53-vote-prefix-component/run-"+UUID.randomUUID()));
        System.out.println("v53VotePrefixComponentEvidence="+raw.toAbsolutePath());
        var capture=new V53RemoveRetirementCapture(raw,raw.resolve("captures"),V53RemoveRetirementCapture.Mode.VOTE);
        var events=new ArrayList<Map<String,Object>>();var cases=new ArrayList<Map<String,Object>>();
        var accepts=new HashSet<Owned>();var proofs=new HashSet<Owned>();
        for(int node:f.f.nodes)observe(f,group,raw,capture,events,cases,node,"ACCEPT",store->accepts.add(store.acceptCurrent(f.f.entry(),f.f.payload())));
        var proof=f.f.proof(accepts);
        for(int node:f.f.nodes)observe(f,group,raw,capture,events,cases,node,"PROOF",store->proofs.add(store.proveCurrent(proof,accepts)));
        var certificate=f.certificate(proof,proofs);var owned=new HashSet<>(accepts);owned.addAll(proofs);
        for(int node:f.f.nodes)observe(f,group,raw,capture,events,cases,node,"CERTIFICATE",store->assertEquals(certificate.digest(),store.certifyCurrent(certificate,owned).digest()));
        byte[] encoded=canonical(events,1024*1024);Files.write(raw.resolve("events.json"),encoded);
        capture.finishProcess(f.f.f.root().manifestDigest(),2,"CLOSED",encoded);
        Files.write(raw.resolve("result.json"),canonical(Map.of("schema","gse-v53-vote-prefix-component-v1","cases",cases,
                "pid",ProcessHandle.current().pid(),"root",f.f.f.root().manifestDigest(),"protocolAuthority","conditional-initial-history",
                "nativeCarriedProcess",false),65536));
        assertEquals(81L,object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096)).get("captures"));
    }
    private void observe(V53PendingCertificateFixture f,Path group,Path raw,V53RemoveRetirementCapture capture,
            List<Map<String,Object>> events,List<Map<String,Object>> cases,int node,String phase,Call call)throws Exception {
        String owner="node-"+node,name=phase.toLowerCase(Locale.ROOT)+"-"+owner;Path directory=Files.createDirectory(raw.resolve(name));
        Path replica=f.f.node(group,node);var resources=f.f.resources();int begin=events.size();
        V53JournalApplicationTest.copy(replica,directory.resolve("before"));
        try(var store=f.f.open(group,node,resources,point->{
            int at=events.size();events.add(Map.of("node",owner,"event",point));capture.at(owner,replica,point,at);
        })) {
            call.run(store);if(node==1)new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
        }
        assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(replica,directory.resolve("after"));
        cases.add(Map.of("name",name,"node",owner,"phase",phase,"start",begin,"end",events.size()));
    }
    @Test void renameCrashPrefixCannotMasqueradeAsNormalClose()throws Exception {
        for(String phase:List.of("ACCEPT","PROOF")) {
            Path replica=Files.createDirectory(temp.resolve(phase));Files.write(replica.resolve("empty"),new byte[0]);
            var capture=new V53RemoveRetirementCapture(replica,temp.resolve("capture-"+phase),V53RemoveRetirementCapture.Mode.VOTE);
            capture.at("node-1",replica,phase+"_VALIDATED",0);capture.at("node-1",replica,phase+"_RENAMED",1);
            assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
            capture.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]);
        }
    }
    @Test void otherIncompleteTransactionsAndOverlapsCannotFinish()throws Exception {
        for(String point:List.of("ACCEPT_PREFIX_WRITTEN","PROOF_CANDIDATE_FORCED","CERTIFICATE_RENAMED")) {
            Path replica=Files.createDirectory(temp.resolve(point));Files.write(replica.resolve("empty"),new byte[0]);
            var capture=new V53RemoveRetirementCapture(replica,temp.resolve("capture-"+point),V53RemoveRetirementCapture.Mode.VOTE);
            String phase=point.substring(0,point.indexOf('_'));
            capture.at("node-1",replica,phase+"_ACTIVE_FORCED",0);capture.at("node-1",replica,phase+"_ACK_BEFORE_RETURN",1);
            assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,point,2));
            capture.at("node-1",replica,phase+"_VALIDATED",3);capture.at("node-1",replica,point,4);
            assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"ACCEPT_VALIDATED",5));
            assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]));
        }
    }
}
