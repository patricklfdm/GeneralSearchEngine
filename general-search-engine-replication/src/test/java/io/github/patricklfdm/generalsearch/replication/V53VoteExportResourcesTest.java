package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Public bootstrap and actual native TCP ACCEPT/PROOF, then direct overlapping
 * payload/ACCEPT-receipt/PROOF-receipt exports on the same original owner. */
class V53VoteExportResourcesTest {
    @TempDir Path temp;
    @ParameterizedTest @ValueSource(ints={3,4,5})
    void payloadAndBothPhaseReceiptsRetainTheirOriginalIdentities(int size)throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        var n=helper.new Network(size,true,false,true);boolean passed=false;
        List<Map<String,Object>> cases=List.of();var budget=n.budgets.getFirst();
        System.out.println("v53VoteExportResources="+n.f.raw.toAbsolutePath()+" size="+size);
        try(n) {
            for(int i=1;i<size;i++)n.send(i,n.request(i,n.accept));var proof=n.proof();
            for(int i=1;i<size;i++)n.send(i,n.request(i,proof));
            for(int i=0;i<size;i++)assertEquals(proof.digest(),n.observation(i,proof).record());
            Files.write(n.f.raw.resolve("proof.gsr"),proof.bytes());
            Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","size",size,"kind","DATA",
                    "acknowledgements",2*(size-1)),4096));
            for(var endpoint:n.endpoints)endpoint.close();for(var transport:n.transports)transport.close();
            var owner=n.owners.getFirst();var context=owner.activationContext();var original=new TreeMap<String,byte[]>();
            var references=new ArrayList<String>();original.put(hash(n.payload),n.payload);references.add(hash(n.payload));
            for(var record:List.of(n.accept,proof)) {
                byte[] bytes=MembershipVoteReceipt.bytes(context,owner.activationIdentity(),record);
                String digest=hash(bytes),alias=MembershipVoteReceipt.reference(bytes);assertNotEquals(digest,alias);
                original.put(digest,bytes);references.add(alias);
                assertThrows(IllegalArgumentException.class,()->owner.exportTransfer(digest,context.authority(),n.f.ballot,()->0,0,100));
            }
            var factories=new ArrayList<V53SpecialExportResources.Open>();
            for(String reference:references)factories.add(clock->owner.exportTransfer(reference,context.authority(),n.f.ballot,
                    clock::get,0,V53SpecialExportResources.BUDGET));
            cases=V53SpecialExportResources.probe(budget,factories,original);passed=true;
        }catch(Throwable failure){passed=false;throw failure;}
        finally{V53SpecialExportResources.save(n.f.raw,"vote",cases,budget,passed);}
    }
}
