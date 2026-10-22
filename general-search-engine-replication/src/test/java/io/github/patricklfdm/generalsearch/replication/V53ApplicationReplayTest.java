package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53ApplicationReplayTest {
    @TempDir Path temp;
    static final UUID HISTORY=V53ApplicationImageTest.HISTORY;
    SearchEngineConfiguration<Integer,Doc> configuration(){return V53ApplicationImageTest.config();}
    DurableStorageConfig<Integer,Doc> storage(){return io.github.patricklfdm.generalsearch.admission.OfflineApplication.storage(temp.resolve("anchor"),2);}
    byte[] initial(long sequence)throws Exception {
        return MembershipApplicationImage.capture(configuration(),storage(),new DurableApplicationState<>(HISTORY,sequence,
                List.of(new Doc(7,"old"),new Doc(2,"retained")),List.of(IndexDefinition.prefix(VALUE),IndexDefinition.range(ID))),temp.resolve("base-"+sequence));
    }
    ReplicaApplication<Integer,Doc> encoder(){return new ReplicaApplication<>(configuration(),storage(),ReplicationBounds.defaults());}
    MembershipApplicationReplay.Step step(long index,String operation,byte[] body){return new MembershipApplicationReplay.Step(index,"DATA",MembershipApplicationReplay.data(operation,body));}
    MembershipApplicationReplay.Result replay(byte[] base,long sequence,long index,List<MembershipApplicationReplay.Step> steps,String path)throws Exception {
        return MembershipApplicationReplay.replay(configuration(),storage(),base,MembershipFormat.hash(base),HISTORY,sequence,index,steps,temp.resolve(path));
    }
    DurableApplicationState<Doc> read(byte[] bytes,String path)throws Exception {return MembershipApplicationImage.read(configuration(),storage(),bytes,temp.resolve(path));}
    @Test void realOperationsMatchOnePassAndEveryIntermediateRecoveryBoundary()throws Exception {
        byte[] base=initial(41);var operations=new ArrayList<MembershipApplicationReplay.Step>();
        try(var e=encoder()) {
            operations.add(step(11,"ADD",e.documents("ADD",List.of(new Doc(3,"new")))));
            operations.add(step(12,"UPDATE",e.documents("UPDATE",List.of(new Doc(7,"changed")))));
            operations.add(step(13,"REMOVE",e.keys("REMOVE",List.of(2))));
            operations.add(step(14,"ADD_ALL",e.documents("ADD_ALL",List.of(new Doc(8,"a"),new Doc(9,"b")))));
            operations.add(step(15,"UPDATE_ALL",e.documents("UPDATE_ALL",List.of(new Doc(8,"aa"),new Doc(9,"bb")))));
            operations.add(step(16,"REMOVE_ALL",e.keys("REMOVE_ALL",List.of(8,9))));
            operations.add(step(17,"INDEX_DROP",e.dropIndex("value")));
            operations.add(step(18,"INDEX_CREATE",e.index(IndexDefinition.text(V53ApplicationImageTest.TEXT))));
            operations.add(new MembershipApplicationReplay.Step(19,"BARRIER",new byte[0]));
        }
        var whole=replay(base,41,10,operations,"whole");assertEquals(49,whole.sequence());assertEquals(19,whole.index());
        var state=read(whole.image(),"read-final");assertEquals(List.of(new Doc(7,"changed"),new Doc(3,"new")),state.documents());
        assertEquals(List.of("id","value"),state.indexes().stream().map(v->v.field().name()).toList());
        for(int split=1;split<operations.size();split++) {
            var first=replay(base,41,10,operations.subList(0,split),"first-"+split);
            var second=replay(first.image(),first.sequence(),first.index(),operations.subList(split,operations.size()),"second-"+split);
            assertEquals(whole.index(),second.index());assertEquals(whole.sequence(),second.sequence());assertArrayEquals(whole.image(),second.image());
        }
        assertFalse(Files.exists(storage().directory()));assertEquals(41,read(base,"original").sequence());
    }
    @Test void controlOnlyCutsRetainExactOriginalEvenWithNoncanonicalStartupOrder()throws Exception {
        byte[] base=initial(41);var result=replay(base,41,10,List.of(new MembershipApplicationReplay.Step(11,"BARRIER",new byte[0])),"barrier");
        assertEquals(11,result.index());assertEquals(41,result.sequence());assertArrayEquals(base,result.image());assertFalse(Files.exists(temp.resolve("barrier/output")));
        result=replay(base,41,10,List.of(),"empty");assertEquals(10,result.index());assertArrayEquals(base,result.image());
    }
    @Test void originalHashHistorySequenceAndContiguousIndicesAreMandatory()throws Exception {
        byte[] base=initial(41);var hash=MembershipFormat.hash(base);
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationReplay.replay(configuration(),storage(),base,"00".repeat(32),HISTORY,41,10,List.of(),temp.resolve("wrong-hash")));
        assertFalse(Files.exists(temp.resolve("wrong-hash")));
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationReplay.replay(configuration(),storage(),base,hash,new UUID(1,9),41,10,List.of(),temp.resolve("wrong-history")));
        assertThrows(IllegalArgumentException.class,()->replay(base,40,10,List.of(),"wrong-sequence"));
        assertThrows(IllegalArgumentException.class,()->replay(base,41,10,List.of(new MembershipApplicationReplay.Step(12,"BARRIER",new byte[0])),"gap"));
        assertFalse(Files.exists(temp.resolve("gap")));
    }
    @Test void malformedPayloadsAndAtomicBusinessFailuresNeverPublishOrAlterBase()throws Exception {
        byte[] base=initial(41),copy=base.clone();
        for(int code:List.of(0,9,10,255))assertThrows(IllegalArgumentException.class,()->replay(base,41,10,List.of(new MembershipApplicationReplay.Step(11,"DATA",new byte[]{(byte)code,0,0})),"code-"+code));
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationReplay.data("NO_OP",new byte[0]));
        assertThrows(IllegalArgumentException.class,()->replay(base,41,10,List.of(new MembershipApplicationReplay.Step(11,"BARRIER",new byte[]{1})),"barrier-body"));
        try(var e=encoder()) {
            var duplicate=step(11,"ADD_ALL",e.documents("ADD_ALL",List.of(new Doc(20,"new"),new Doc(7,"duplicate"))));
            assertThrows(RuntimeException.class,()->replay(base,41,10,List.of(duplicate),"duplicate"));assertFalse(Files.exists(temp.resolve("duplicate/output")));
            var invalid=step(11,"INDEX_CREATE",e.index(IndexDefinition.text(V53ApplicationImageTest.TEXT)));
            assertThrows(RuntimeException.class,()->replay(base,41,10,List.of(invalid),"index-conflict"));
        }
        assertArrayEquals(copy,base);assertEquals(List.of(new Doc(7,"old"),new Doc(2,"retained")),read(base,"base-unchanged").documents());
    }
    @Test void sequenceAndCommandCapsRemainBoundedAndOutputsAreDefensiveCopies()throws Exception {
        byte[] base=initial(MembershipValidation.MAX);
        try(var e=encoder()) {
            var data=step(11,"ADD",e.documents("ADD",List.of(new Doc(20,"new"))));
            assertThrows(IllegalArgumentException.class,()->replay(base,MembershipValidation.MAX,10,List.of(data),"overflow"));
        }
        var barrier=new MembershipApplicationReplay.Step(11,"BARRIER",new byte[0]);var result=replay(base,MembershipValidation.MAX,10,List.of(barrier),"terminal-control");
        assertEquals(MembershipValidation.MAX,result.sequence());byte[] returned=result.image();returned[0]^=1;assertArrayEquals(base,result.image());
        byte[] body=new byte[]{1,2,3};var step=new MembershipApplicationReplay.Step(1,"DATA",body);body[0]=0;assertEquals(1,step.payload()[0]);
        assertThrows(IllegalArgumentException.class,()->MembershipApplicationReplay.data("ADD",new byte[MembershipFormat.FRAME]));
        assertThrows(IllegalArgumentException.class,()->new MembershipApplicationReplay.Step(1,"DATA",new byte[MembershipFormat.FRAME+1]));
        assertThrows(IllegalArgumentException.class,()->replay(base,MembershipValidation.MAX,10,Collections.nCopies(10001,barrier),"too-many"));
        assertFalse(Files.exists(temp.resolve("too-many")));
    }
}
