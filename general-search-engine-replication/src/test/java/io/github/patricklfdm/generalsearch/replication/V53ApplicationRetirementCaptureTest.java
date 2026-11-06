package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ApplicationRetirementCaptureTest {
    @TempDir Path temp;
    private V53RemoveRetirementCapture fixture(String name)throws Exception {
        Path raw=Files.createDirectory(temp.resolve(name));Files.writeString(raw.resolve("selector.gsr"),"new");
        Files.createDirectory(raw.resolve("applied-end"));Files.writeString(raw.resolve("applied-end/selector.gsr"),"old");
        return new V53RemoveRetirementCapture(raw,temp.resolve(name+"-captures"),V53RemoveRetirementCapture.Mode.APPLICATION_RETIREMENT);
    }
    @Test void coldAndFreshApplicationForcesCannotMasqueradeAsRetirement()throws Exception {
        var c=fixture("cold");Files.writeString(c.raw.resolve("selector.gsr"),"old");
        c.at("node-1",c.raw,"CERTIFICATE_ACTIVE_FORCED",0);c.at("node-1",c.raw,"CERTIFICATE_ACTIVE_PARENT_FORCED",1);
        c.at("node-1",c.raw,"REPLAY_RESERVED",2);c.at("node-1",c.raw,"REPLAY_BEFORE_RETURN",3);
        try(var paths=Files.list(c.root)){assertEquals(0,paths.filter(p->p.getFileName().toString().startsWith("capture-")).count());}
        assertThrows(IllegalArgumentException.class,()->c.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
        Files.delete(c.raw.resolve("applied-end/selector.gsr"));Files.delete(c.raw.resolve("applied-end"));
        c.at("node-1",c.raw,"CERTIFICATE_ACTIVE_FORCED",4);c.at("node-1",c.raw,"CERTIFICATE_ACTIVE_PARENT_FORCED",5);
        assertThrows(IllegalArgumentException.class,()->c.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
    }
    @Test void exactRetirementKeepsReplayInsideItsOwningTransaction()throws Exception {
        var c=fixture("retirement");String[] points={"CERTIFICATE_ACTIVE_FORCED","CERTIFICATE_ACTIVE_PARENT_FORCED",
            "NATIVE_RETIREMENT_CERTIFICATE_RETAINED","STAGED_RETIREMENT_AUTHORITY_VALIDATED","REPLAY_RESERVED",
            "REPLAY_BEFORE_RETURN","SUPERSEDED_END_VALIDATED","STAGED_RETIREMENT_BEFORE_RETURN"};
        for(int i=0;i<points.length;i++)c.at("node-1",c.raw,points[i],i);
        c.at("node-1",c.raw,"REPLAY_RESERVED",8);c.at("node-1",c.raw,"REPLAY_BEFORE_RETURN",9);
        assertThrows(IllegalArgumentException.class,()->c.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]));
        c.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]);
        var header=object(parse(Files.readAllBytes(c.root.resolve("collection.json")),4096));
        assertEquals(V53RemoveRetirementCapture.PROCESS_APPLICATION_RETIREMENT_SCHEMA,header.get("schema"));
        assertEquals(8L,header.get("captures"));
        var replay=object(parse(Files.readAllBytes(c.root.resolve("capture-0005.json")),16384));
        assertEquals("application-retirement",replay.get("kind"));
    }
    @Test void missingStartOpenOwnerAndSecondStartCannotSealRecovery()throws Exception {
        var c=fixture("unfinished");
        assertThrows(IllegalArgumentException.class,()->c.at("node-1",c.raw,"STAGED_RETIREMENT_AUTHORITY_VALIDATED",0));
        c.at("node-1",c.raw,"CERTIFICATE_ACTIVE_FORCED",1);
        assertThrows(IllegalArgumentException.class,()->c.at("node-1",c.raw,"CERTIFICATE_ACTIVE_FORCED",2));
        assertThrows(IllegalArgumentException.class,()->c.at("node-2",c.raw,"STAGED_RETIREMENT_BEFORE_RETURN",3));
        assertThrows(IllegalArgumentException.class,()->c.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
        assertFalse(Files.exists(c.root.resolve("collection.json")));
    }
}
