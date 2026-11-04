package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53RestartLifecycleCaptureTest {
    @TempDir Path temp;
    Path raw()throws IOException {
        var raw=Files.createDirectory(temp.resolve("run-"+UUID.randomUUID()));
        Files.write(raw.resolve("original-plan.gsbp"),new byte[]{1});return raw;
    }
    @Test void clocksAndLifecycleBindUntouchedOriginalEventsAndRealConstruction()throws Exception {
        var raw=raw();List<Map<String,Object>> events=Collections.synchronizedList(new ArrayList<>());
        events.add(Map.of("node","node-1","event","OPENED"));var before=new ArrayList<>(events);
        var capture=new V53RestartLifecycleCapture(raw,events);capture.opened(300_000_000_000L);
        long began=System.nanoTime();capture.lifecycle.at("node-1",new MembershipAutomaticOwner.Observation("START",MembershipAutomaticOwner.State.STARTING,0,0,began,""));
        var event=Map.<String,Object>of("node","node-1","event","ALLOCATOR_FORCED");
        synchronized(events){capture.event(events.size(),event);events.add(event);}
        Files.write(raw.resolve("events.json"),canonical(events,65536));
        capture.save(raw,true,true,Optional.empty(),List.of(new MembershipResources(1024),new MembershipResources(1024),new MembershipResources(1024)));
        var value=object(parse(Files.readAllBytes(capture.directory.resolve("capture.json")),1024*1024));
        assertEquals(1L,value.get("firstEvent"));assertEquals(hash(canonical(before,65536)),value.get("prefixSha256"));
        assertEquals(hash(Files.readAllBytes(raw.resolve("events.json"))),value.get("eventsSha256"));
        var clocks=list(value.get("events"));assertEquals(1,clocks.size());var at=object(clocks.getFirst());
        assertEquals(1L,at.get("index"));assertEquals(hash(canonical(event,65536)),at.get("sha256"));
        var rows=list(parse(Files.readAllBytes(capture.directory.resolve(V53AutomaticLifecycleCapture.FILE)),1024*1024));
        assertEquals(0L,object(rows.getFirst()).get("afterEvent"));assertEquals(List.of(before.getFirst(),event),events);
        assertThrows(FileAlreadyExistsException.class,()->capture.save(raw,true,true,Optional.empty(),List.of()));
        assertThrows(IllegalArgumentException.class,()->capture.opened(1));
    }
    @Test void failedClockCollectionIsRetainedWithoutThrowingIntoProtocolEvent()throws Exception {
        var raw=raw();List<Map<String,Object>> events=new ArrayList<>();var capture=new V53RestartLifecycleCapture(raw,events);
        assertDoesNotThrow(()->capture.event(1,Map.of("event","wrong-index")));events.add(Map.of("event","real-event"));
        Files.write(raw.resolve("events.json"),canonical(events,65536));
        assertThrows(IOException.class,()->capture.save(raw,false,false,Optional.empty(),List.of()));
        var value=object(parse(Files.readAllBytes(capture.directory.resolve("capture.json")),1024*1024));
        assertNotEquals("",value.get("captureFailure"));assertEquals(false,value.get("producerPassed"));
        assertEquals(List.of(Map.of("event","real-event")),events);
    }
    @Test void observerFailureAndResidualResourcesCannotDisappearFromAttachment()throws Exception {
        var raw=raw();List<Map<String,Object>> events=new ArrayList<>();var capture=new V53RestartLifecycleCapture(raw,events);
        Files.write(raw.resolve("events.json"),canonical(events,65536));var resources=new MembershipResources(1024);
        try(var lease=resources.reserve(MembershipResources.Unit.CONTROL,"held",1)) {
            assertThrows(IOException.class,()->capture.save(raw,false,false,Optional.of(new IOException("observation lost")),List.of(resources)));
            var value=object(parse(Files.readAllBytes(capture.directory.resolve("capture.json")),1024*1024));
            assertTrue(((String)value.get("observationFailure")).contains("observation lost"));
            assertEquals(List.of(1L),value.get("resourceLeases"));assertEquals(false,value.get("ownerDrained"));
        }
    }
}
