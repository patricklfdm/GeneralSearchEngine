package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;

class V52PublicApiInventoryTest {
    private static String fixture(String name) throws Exception {
        try(var in=V52PublicApiInventoryTest.class.getResourceAsStream("/compatibility/"+name)) {
            if(in==null)throw new IllegalStateException("missing "+name);
            return new String(in.readAllBytes(),StandardCharsets.UTF_8);
        }
    }
    private static String signatures() throws Exception {
        var lines=new TreeSet<String>();var helper=new V50PublicApiInventoryTest();
        for(String line:fixture("v52-read-public-api-v1.txt").lines().toList())helper.collectSignatures(Class.forName(line.split(" ",2)[1]),lines);
        return String.join("\n",lines)+"\n";
    }
    @Test void exactNewDescriptorsAndOnlyOneOldInterfaceDelta() throws Exception {
        assertEquals(fixture("v52-read-public-signatures-v1.txt"),signatures());
        var current=new TreeSet<String>();new V50PublicApiInventoryTest().collectSignatures(AutomaticReplicatedSearchEngine.class,current);
        var old=new TreeSet<>(fixture("v51-automatic-public-signatures-v1.txt").lines().filter(v->v.contains(".AutomaticReplicatedSearchEngine")&&!v.contains(".AutomaticReplicatedSearchEngineBuilder")&&!v.contains(".AutomaticReplicatedSearchEngines")).toList());
        assertTrue(current.containsAll(old));current.removeAll(old);
        assertEquals(new TreeSet<>(fixture("v52-read-method-delta.txt").lines().toList()),current);
        assertTrue(AutomaticReplicatedSearchEngine.class.getDeclaredMethod("read",ReplicaReadOptions.class,java.util.function.Function.class).isDefault());
        assertEquals(7,ReplicaReadView.class.getDeclaredMethods().length);
        assertEquals(0,ReplicaReadView.class.getInterfaces().length);
    }
    public static void main(String[] args) throws Exception {System.out.print(signatures());}
}
