package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional original handlers, not native membership promotion or full
 * joining qualification. Keep the request bytes and original budget order. */
class V53JoiningExportRequestTest {
    @TempDir Path temp;
    @Test void retentionSessionBindsItsMetadataAndKeepsTheNestedBorrow()throws Exception {capture(false);}
    @Test void preparationSessionBindsItsCopyAndDoesNotOwnSharedPublication()throws Exception {capture(true);}
    void capture(boolean preparation)throws Exception {
        var helper=new V53JoiningRetentionNetworkTest();helper.temp=temp;
        var preparationHelper=new V53JoiningPreparationTest();preparationHelper.temp=temp;
        Path parent=Path.of("target/v53-joining-export-requests");Files.createDirectories(parent);
        Path raw=Files.createDirectory(parent.resolve("run-"+UUID.randomUUID()));
        String role=preparation?"joining-preparation-export":"joining-retention-export";
        var first=new ArrayList<Map<String,Object>>();var requests=new ArrayList<Decoded>();
        MembershipResources pool;
        try(var local=helper.new Local(true)) {
            pool=local.a;
            try(var endpoint=preparationHelper.endpoint(local);var publication=preparationHelper.publication(local)) {
                if(preparation)endpoint.publishJoiningPreparation(publication);
                try(var pull=local.pull((peer,request,kind,deadline)->{
                    try {
                        long before=pool.observationCheckpoint().sequence();
                        var reply=preparation?endpoint.handle(local.reader.activationIdentity(),request):
                                local.service.handle(local.reader.activationIdentity(),request);
                        if(number(request.value().get("sequence"))==1) {
                            requests.add(request);
                            first.add(Map.of("bytes",Base64.getEncoder().encodeToString(request.bytes()),
                                    "received",before,"offered",pool.observationCheckpoint().sequence()));
                        }
                        return CompletableFuture.completedFuture(reply);
                    }catch(Exception error){return CompletableFuture.failedFuture(error);}
                })) {
                    String reference=preparation?MembershipJoiningPreparation.reference(local.reader.activationContext(),local.reader.activationIdentity()):local.reference();
                    pull.fetchPrefixMetadata(reference,preparation?MembershipJoiningPreparation.MAXIMUM:MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM);
                }
            }
            assertEquals(1,requests.size());var request=requests.getFirst();
            var attachments=pool.controlCloseObservations().rows().stream().filter(r->r.event().equals("ATTACHED")).toList();
            assertEquals(1,attachments.size());var attachment=attachments.getFirst();
            assertEquals(preparation?1:2,attachment.children().size());
            String owned=attachment.children().stream().filter(n->n.startsWith(role+"-")).findFirst().orElseThrow();
            assertTrue(owned.startsWith(role+"-"+request.digest()+"-"),"export must name the original first request");
            assertTrue(owned.length()<=128);assertNotEquals(new UUID(0,0),UUID.fromString(owned.substring(role.length()+66)));
            var initial=new TreeMap<String,Object>(first.getFirst());initial.put("session",attachment.owner());
            Files.write(raw.resolve("initial.json"),canonical(initial,16384),StandardOpenOption.CREATE_NEW);
            Files.write(raw.resolve("scope.json"),canonical(Map.of("schema","gse-v53-joining-export-request-component-v1",
                    "role",role,"node",local.source.activationIdentity().nodeId().value(),"nativeMembershipQualified",false),4096),StandardOpenOption.CREATE_NEW);
        }
        assertEquals(0,pool.usage().leases());
        V53ResourceTraceFiles.write(raw.resolve("resources.json"),pool.observations());
        V53ResourceTraceFiles.writeCloses(raw.resolve("closes.json"),pool.controlCloseObservations());
        System.out.println("v53JoiningExportRequestEvidence="+raw.toAbsolutePath());
    }
    @Test void allFiveRequestRolesFitExistingOwnerLimitAndKeepDistinctAllocations() {
        var source=V53DeclarationsTest.node(1);var peer=V53DeclarationsTest.node(2);
        var request=decode(encode("wire","CHUNK",Map.of("root","aa".repeat(32),"view","bb".repeat(32),
                "sender",MembershipBootstrapSeed.identity(source),"recipient",MembershipBootstrapSeed.identity(peer),
                "ballot",Map.of("counter",2L,"proposer","node-1","incarnation",source.storageId().toString()),
                "trace",UUID.randomUUID().toString(),"sequence",1L,
                "payload",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest","cc".repeat(32),"bytes",""))),"wire","CHUNK");
        for(String role:List.of("joining-retention-export","joining-intent","joining-preparation-export","joining-completion-export","joining-checkpoint-export")) {
            var pool=V53SessionExportOwnershipTest.budget();String a=MembershipSourceResources.request(role,request),b=MembershipSourceResources.request(role,request);
            assertNotEquals(a,b);assertTrue(a.startsWith(role+"-"+request.digest()+"-"));
            assertTrue(a.length()<=128);
            try(var first=pool.reserve(MembershipResources.Unit.CONTROL,a,1024);var second=pool.reserve(MembershipResources.Unit.CONTROL,b,1024)) {
                assertEquals(2,pool.usage().leases());
            }
            assertEquals(0,pool.usage().leases());
        }
    }
}
