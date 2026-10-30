package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Explicit whole-history qualification (select with -Dtest=V53CompetingNodeQualification).
 * This non-default gate retains failures until the complete native history qualifies.
 * Ungated native competition. No injected promises, chosen winner or mutation retry.
 * Producer success is PARTIAL until independent original-history qualification. */
class V53CompetingNodeQualification {
    @TempDir Path temp;
    static String stack(Throwable error) {
        var text=new StringWriter();error.printStackTrace(new PrintWriter(text));return text.toString();
    }
    @Test void threeAutomaticOwnersConvergeAndPublishOneOriginalData()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-competing-node/run-"+UUID.randomUUID()));
        System.out.println("v53CompetingNodeEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group")),3,false));
        f.ownedHistory=true;f.nativeApplication=true;
        for(var target:f.request.targets())try(var journal=f.open(target,"initialize-retention")){journal.initializePeerRetention();journal.initializeFutureRetention();}
        f.snapshot("before-network");
        var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var nodes=new ArrayList<MembershipNodeOwner<Integer,Doc>>();var calls=new ArrayList<MembershipAutomaticOwner.Call>();
        var observations=new ArrayList<Map<String,Object>>();var bounds=ReplicationBounds.defaults();
        var policy=AutomaticLeadershipPolicy.forBounds(bounds);boolean success=false;Throwable failed=null;
        try {
            for(int i=0;i<3;i++) {
                var target=f.request.targets().get(i);String name=target.identity().nodeId().value();
                Path scratch=Files.createDirectory(temp.resolve("scratch-"+i));
                var config=new MembershipReplicaConfig<>(f.result.root(),target.identity(),f.request.targets().stream().map(MembershipBootstrapTarget::identity)
                    .filter(v->!v.equals(target.identity())).toList(),target.replicaDirectory(),target.materialization(),bounds,policy);
                var hooks=new MembershipNodeOwner.Hooks(event->events.add(Map.of("node",name,"event",event)),
                    (event,request,response)->{
                        if(event.equals("BEFORE_REQUEST_WRITE"))events.add(Map.of("node",name,"event","NETWORK_SEND","request",request.digest(),"kind",request.kind(),"bytes",Base64.getEncoder().encodeToString(request.bytes())));
                        if(event.equals("AFTER_REQUEST_READ"))events.add(Map.of("node",name,"event","NETWORK_REQUEST","request",request.digest(),"kind",request.kind()));
                        if(event.equals("AFTER_RESPONSE_READ"))events.add(Map.of("node",name,"event","NETWORK_RECEIVED","kind",response.kind(),"response",response.digest()));
                        if(event.equals("BEFORE_RESPONSE_WRITE")) {
                            var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",false);wire.add(row);
                            events.add(Map.of("node",name,"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest()));
                        }
                    },(event,record)->events.add(Map.of("node",name,"event","ROUND_"+event,"record",record.digest(),"bytes",Base64.getEncoder().encodeToString(record.bytes()))),
                    (event,record,voters)->events.add(Map.of("node",name,"event","SLOT_"+event,"record",record.digest(),"bytes",Base64.getEncoder().encodeToString(record.bytes()),"voters",voters.stream().sorted().toList())));
                var node=new MembershipNodeOwner<>(config,builder().configuration(),scratch.resolve("incoming"),scratch.resolve("outgoing"),System::nanoTime,V53NodeOwnerNetworkTest.BUDGET,hooks);
                nodes.add(node);node.open();assertThrows(IllegalArgumentException.class,node::readiness);
                events.add(Map.of("node",name,"event","NODE_OPEN"));
            }
            long began=System.nanoTime();for(var node:nodes)calls.add(node.start());
            var seen=new boolean[3];int winner=-1;long stable=0;String barrier=null;
            while(System.nanoTime()-began<V53NodeOwnerNetworkTest.BUDGET) {
                for(int i=0;i<3;i++) {
                    var node=nodes.get(i);
                    if(node.failure().isPresent())throw new AssertionError("automatic owner failed: node-"+(i+1),node.failure().orElseThrow());
                    if(!seen[i] && calls.get(i).isDone()) {
                        var ready=calls.get(i).await(1,TimeUnit.SECONDS);seen[i]=true;
                        observations.add(Map.of("node","node-"+(i+1),"event","START_COMPLETED","bytes",Base64.getEncoder().encodeToString(ready.bytes())));
                    }
                }
                var ready=new ArrayList<Integer>();
                for(int i=0;i<3;i++)if(nodes.get(i).serviceState().orElseThrow()==MembershipAutomaticOwner.State.READY)ready.add(i);
                if(ready.size()==1) {
                    int index=ready.getFirst();Decoded current;
                    try{current=nodes.get(index).readiness().await(20,TimeUnit.SECONDS);}
                    catch(ExecutionException error) {
                        if(!(error.getCause() instanceof MembershipCampaignLost lost))throw error;
                        observations.add(Map.of("node","node-"+(index+1),"event","READINESS_LOST","reason",lost.reason.name()));
                        winner=-1;barrier=null;continue;
                    }
                    catch(IllegalArgumentException error) {
                        // The state snapshot is diagnostic; admission can race a
                        // restart. Only that explicit state transition permits
                        // another readiness observation, never another mutation.
                        if(nodes.get(index).serviceState().orElseThrow()!=MembershipAutomaticOwner.State.RESTARTING)throw error;
                        observations.add(Map.of("node","node-"+(index+1),"event","READINESS_RESTARTING"));
                        winner=-1;barrier=null;continue;
                    }
                    if(index!=winner || !current.digest().equals(barrier)){winner=index;barrier=current.digest();stable=System.nanoTime();}
                    if(System.nanoTime()-stable>=TimeUnit.MILLISECONDS.toNanos(2L*policy.heartbeatIntervalMillis()))break;
                } else {winner=-1;barrier=null;}
                Thread.sleep(50);
            }
            assertTrue(winner>=0 && System.nanoTime()-stable>=TimeUnit.MILLISECONDS.toNanos(2L*policy.heartbeatIntervalMillis()),"no stable automatic winner");
            byte[] payload;
            try(var encoder=new ReplicaApplication<>(builder().configuration(),f.request.targets().get(winner).materialization(),bounds)) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(100,"competing-node-100"))));
            }
            // Exactly one client mutation attempt. An indeterminate result fails
            // this history; it is never submitted to another elected owner.
            var result=nodes.get(winner).submit("DATA",payload).await(180,TimeUnit.SECONDS);assertEquals("PUBLISH_ACK",result.kind());
            observations.add(Map.of("node","node-"+(winner+1),"event","DATA_COMPLETED","bytes",Base64.getEncoder().encodeToString(result.bytes())));
            for(var node:nodes)assertTrue(node.failure().isEmpty(),"healthy automatic owner failed after DATA");
            success=true;
        }catch(Exception|Error error){failed=error;throw error;}
        finally {
            var diagnostics=new ArrayList<Map<String,Object>>();IOException closing=null;
            for(int i=0;i<nodes.size();i++) {
                var node=nodes.get(i);diagnostics.add(Map.of("node","node-"+(i+1),"state",node.serviceState().map(Enum::name).orElse("UNOPENED"),
                    "failure",node.failure().map(V53CompetingNodeQualification::stack).orElse("")));
            }
            Files.write(raw.resolve("diagnostics.json"),canonical(diagnostics,65536));
            Files.writeString(raw.resolve("failure.txt"),failed==null?"":stack(failed));
            var drains=new ArrayList<Map<String,Object>>();
            for(int i=nodes.size()-1;i>=0;i--) {
                var node=nodes.get(i);Throwable error=null;
                try{node.close();assertEquals(0,node.usage().leases());}
                catch(IOException|RuntimeException|AssertionError failure){
                    error=failure;var drain=failure instanceof IOException io?io:new IOException("node resource drain failed",failure);
                    if(closing==null)closing=drain;else closing.addSuppressed(drain);
                }
                var files=new ArrayList<Map<String,Object>>();Path scratch=temp.resolve("scratch-"+i);
                try(var paths=Files.walk(scratch)) {
                    for(Path path:paths.filter(Files::isRegularFile).toList()) {
                        String relative=scratch.relativize(path).toString();byte[] bytes=Files.readAllBytes(path);
                        files.add(Map.of("path",relative,"bytes",bytes.length,"sha256",hash(bytes)));
                        Path retained=raw.resolve("drain-scratch/node-"+(i+1)).resolve(relative);
                        Files.createDirectories(retained.getParent());Files.write(retained,bytes);
                    }
                }
                drains.add(Map.of("node","node-"+(i+1),"failure",error==null?"":stack(error),
                        "leases",node.usage().leases(),"files",files));
            }
            Files.write(raw.resolve("drains.json"),canonical(drains,1024*1024));
            Files.write(raw.resolve("events.json"),canonical(events,16*1024*1024));Files.write(raw.resolve("wire.json"),canonical(wire,32*1024*1024));
            Files.write(raw.resolve("observations.json"),canonical(observations,65536));Files.write(raw.resolve("diagnostics.json"),canonical(diagnostics,65536));
            Files.writeString(raw.resolve("failure.txt"),failed==null?"":stack(failed));Files.writeString(raw.resolve("close-failure.txt"),closing==null?"":stack(closing));
            f.snapshot("after-close");V53NativeApplicationTest.save(f);
            Files.write(raw.resolve("result.json"),canonical(Map.of("status",success && closing==null?"PARTIAL":"FAIL","producerPassed",success && closing==null,
                "nodes",3,"automaticOwners",3,"defaultBounds",true,"physicalReplay",false,"phase3Complete",false),4096));
            if(closing!=null){if(failed!=null)failed.addSuppressed(closing);else throw closing;}
        }
    }
}
