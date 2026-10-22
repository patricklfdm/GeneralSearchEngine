package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;

class V53PublicApiInventoryTest {
    private static String fixture(String name) throws Exception {
        try(var in=V53PublicApiInventoryTest.class.getResourceAsStream("/compatibility/"+name)) {
            if(in==null)throw new IllegalStateException("missing "+name);
            return new String(in.readAllBytes(),StandardCharsets.UTF_8);
        }
    }
    private static String signatures() throws Exception {
        var lines=new TreeSet<String>();var helper=new V50PublicApiInventoryTest();
        for(String line:fixture("v53-membership-public-api-v1.txt").lines().toList())helper.collectSignatures(Class.forName(line.split(" ",2)[1]),lines);
        return String.join("\n",lines)+"\n";
    }
    @Test void exactAdditiveDescriptorsAndIndependentStatusCapability() throws Exception {
        assertEquals(fixture("v53-membership-public-signatures-v1.txt"),signatures());
        assertEquals("gse-replication/1.3", MembershipSearchEngines.PROTOCOL);
        assertFalse(AutomaticReplicatedSearchEngine.class.isAssignableFrom(MembershipSearchEngine.class));
        assertTrue(io.github.patricklfdm.generalsearch.durability.DurableSearchEngine.class.isAssignableFrom(MembershipSearchEngine.class));
        assertTrue(MembershipSearchEngine.class.getDeclaredMethod("read", ReplicaReadOptions.class, java.util.function.Function.class).isDefault());
    }
    public static void main(String[] args) throws Exception {System.out.print(signatures());}
}
