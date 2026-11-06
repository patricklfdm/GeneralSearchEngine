package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real typed control replay fits the one remaining image slot. Authority of
 * these short scratch fixtures is conditional; native process tests bind it. */
class V53ControlReplayReservationTest {
    @TempDir Path temp;
    static final long IMAGE=MembershipResources.Unit.APPLICATION.bytes;
    V53ReplayFilesTest helper(){var h=new V53ReplayFilesTest();h.temp=temp;return h;}
    static List<MembershipResources.Lease> occupy(MembershipResources r,int count) {
        var held=new ArrayList<MembershipResources.Lease>();
        for(int i=0;i<count;i++)held.add(r.reserve(MembershipResources.Unit.APPLICATION,"original-"+i,IMAGE));
        return held;
    }
    static void release(List<MembershipResources.Lease> held){held.forEach(MembershipResources.Lease::close);}
    MembershipApplicationReplay.Result control(byte[] base,String kind,Path work)throws Exception {
        var fixture=new V53ContextFixture(4,"REMOVE");fixture.transition("REMOVE");
        var entry=fixture.steps.stream().map(v->decode(fixture.inventory.get(v.get("entry")),"records","ENTRY"))
                .filter(v->v.value().get("kind").equals(kind)).findFirst().orElseThrow();
        var app=new V53ApplicationReplayTest();app.temp=temp;
        return MembershipApplicationReplay.replay(app.configuration(),app.storage(),base,hash(base),V53ApplicationImageTest.HISTORY,41,0,
                List.of(new MembershipApplicationReplay.Step(1,kind,fixture.inventory.get(entry.value().get("payload")))),work);
    }
    @Test void intentAndFinalUseOneFullInputWithSixOriginalImagesStillCharged()throws Exception {
        var h=helper();byte[] base=V53ReplayFilesTest.base(temp);
        for(String kind:List.of("INTENT","FINAL")) {
            var r=h.resources();var held=occupy(r,6);Path path=temp.resolve(kind);
            try(var journal=h.journal(r);var files=new MembershipReplayFiles(path,r,false)) {
                files.reserveCompletion(false);
                assertEquals(7,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                var result=h.execute(files,work->{
                    try {var value=control(base,kind,work);assertFalse(Files.exists(work.resolve("output")));return value;}
                    catch(IOException error){throw error;}catch(Exception error){throw new IOException(error);}
                },point->assertTrue(r.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=7));
                assertArrayEquals(base,result.image());assertEquals(41,result.sequence());assertEquals(1,result.index());
                assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));assertFalse(Files.exists(path));
            }finally{release(held);}
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void dataDemandCannotBorrowControlCapacityAndFailedUpgradeKeepsOriginalInput()throws Exception {
        var h=helper();var r=h.resources();var held=occupy(r,6);Path path=temp.resolve("scratch");
        try(var journal=h.journal(r);var files=new MembershipReplayFiles(path,r,false)) {
            files.reserveCompletion(false);var usage=r.usage();
            assertThrows(IllegalArgumentException.class,()->files.reserveCompletion(true));
            assertEquals(usage,r.usage());assertFalse(Files.exists(path));
            held.removeLast().close();files.reserveCompletion(true);
            assertEquals(7,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
            files.reserveCompletion(false);assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
            byte[] base=V53ReplayFilesTest.base(temp);files.reserveCompletion(true);
            assertEquals(42,h.execute(files,work->V53ReplayFilesTest.replay(temp,base,work),point->{}).sequence());
            assertEquals(5,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
        }finally{release(held);}
        assertEquals(0,r.usage().leases());
    }
    @Test void interruptedControlReopensWithOneSlotAndCannotChangeDemandWhileFilesRemain()throws Exception {
        var h=helper();var r=h.resources();var held=occupy(r,6);byte[] base=V53ReplayFilesTest.base(temp);Path path=temp.resolve("scratch");
        try {
            try(var journal=h.journal(r);var files=new MembershipReplayFiles(path,r,false)) {
                assertThrows(IOException.class,()->h.execute(files,work->{
                    try{return control(base,"FINAL",work);}catch(Exception error){throw new IOException(error);}
                },point->{if(point.equals("REPLAY_APPLICATION_FINISHED"))throw new IOException("interrupted");}));
            }
            var before=V53ReplayFilesTest.files(path);
            try(var journal=h.journal(r);var files=new MembershipReplayFiles(path,r,false)) {
                assertEquals(7,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                assertThrows(IllegalArgumentException.class,()->files.reserveCompletion(true));
                assertEquals(before,V53ReplayFilesTest.files(path));
                assertArrayEquals(base,h.execute(files,work->{
                    try{return control(base,"FINAL",work);}catch(Exception error){throw new IOException(error);}
                },point->{}).image());
            }
            assertFalse(Files.exists(path));
        }finally{release(held);}
        assertEquals(0,r.usage().leases());
    }
    @Test void controlReopenRejectsAnOutputWithoutErasingIt()throws Exception {
        var h=helper();var r=h.resources();Path path=temp.resolve("scratch");byte[] base=V53ReplayFilesTest.base(temp);
        try(var journal=h.journal(r);var files=new MembershipReplayFiles(path,r)) {
            assertThrows(IOException.class,()->h.execute(files,work->V53ReplayFilesTest.replay(temp,base,work),point->{
                if(point.equals("REPLAY_APPLICATION_FINISHED"))throw new IOException("retained DATA output");}));
        }
        var before=V53ReplayFilesTest.files(path);
        try(var journal=h.journal(r)) {
            assertThrows(IllegalArgumentException.class,()->new MembershipReplayFiles(path,r,false));
            assertEquals(1,r.usage().leases());assertEquals(before,V53ReplayFilesTest.files(path));
        }
        assertEquals(0,r.usage().leases());
    }
}
