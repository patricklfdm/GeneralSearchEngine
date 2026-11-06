package io.github.patricklfdm.generalsearch.replication;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53StorageTransferObservationsTest {
    @TempDir Path temp;
    static MembershipResources budget(int maximum){return new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,maximum);}

    @Test void equalImagesRetainActualSuccessorPairingAndImmutableSnapshot()throws Exception {
        var budget=budget(32);
        var left=budget.reserve(Unit.APPLICATION,"initial-image",837);
        var right=budget.reserve(Unit.APPLICATION,"intent-image",837);
        var requested=new LinkedHashMap<MembershipResources.Lease,String>();
        requested.put(right,"custody-4");requested.put(left,"custody-2");
        var issued=budget.transferCompleteStorage(requested);left.close();right.close();
        var snapshot=budget.storageTransferObservations();var row=snapshot.rows().getFirst();
        assertEquals(3,row.resourceSequence());assertEquals(4,snapshot.transitions());
        assertFalse(snapshot.truncated());assertFalse(snapshot.failed());
        assertEquals(List.of("initial-image","intent-image"),row.moves().stream().map(m->m.before().owner()).toList());
        assertEquals(List.of("custody-2","custody-4"),row.moves().stream().map(m->m.after().owner()).toList());
        assertTrue(row.moves().stream().allMatch(m->m.before().bytes()==837 && m.after().bytes()==837));
        assertThrows(UnsupportedOperationException.class,()->row.moves().clear());
        assertThrows(UnsupportedOperationException.class,()->snapshot.rows().clear());
        issued.values().forEach(MembershipResources.Lease::close);
        assertEquals(4,snapshot.transitions());assertEquals(6,budget.storageTransferObservations().transitions());
        var path=temp.resolve("transfers.json");String hash=V53ResourceTraceFiles.writeTransfers(path,budget.storageTransferObservations());
        byte[] raw=Files.readAllBytes(path);assertEquals(MembershipFormat.hash(raw),hash);
        assertArrayEquals(raw,MembershipFormat.canonical(MembershipFormat.parse(raw,65536),65536));
        assertThrows(FileAlreadyExistsException.class,()->V53ResourceTraceFiles.writeTransfers(path,snapshot));
        assertEquals(0,budget.usage().leases());
    }

    @Test void cyclicSameSizeRenamesAreObservedEvenWhenTheResourceDeltaIsEmpty() {
        var budget=budget(32);var a=budget.reserve(Unit.APPLICATION,"a",7);var b=budget.reserve(Unit.APPLICATION,"b",7);
        var issued=budget.transferStorage(Map.of(a,"b",b,"a"));
        var change=budget.observations().changes().getLast();assertTrue(change.removed().isEmpty());assertTrue(change.added().isEmpty());
        var moves=budget.storageTransferObservations().rows().getFirst().moves();
        assertEquals(List.of("b","a"),moves.stream().map(m->m.after().owner()).toList());
        a.close();b.close();assertEquals(14,budget.usage().staging());issued.values().forEach(MembershipResources.Lease::close);
        assertEquals(0,budget.usage().leases());
    }

    @Test void disabledAndTruncatedObservationNeverChangeTransferOrClose() {
        for(int maximum:List.of(0,2)) {
            var budget=budget(maximum);var source=budget.reserve(Unit.SOURCE,"source",20);
            var next=budget.transferStorage(Map.of(source,"next")).get(source);source.close();
            assertEquals(20,budget.usage().staging());next.close();assertEquals(0,budget.usage().leases());
            if(maximum==0)assertThrows(IllegalArgumentException.class,budget::storageTransferObservations);
            else {var value=budget.storageTransferObservations();assertTrue(value.truncated());assertEquals(4,value.transitions());assertTrue(value.rows().isEmpty());}
        }
    }

    @Test void failedPairRecordingCannotRollBackCommittedOwnership()throws Exception {
        var budget=budget(32);var source=budget.reserve(Unit.SOURCE,"source",20);
        var field=MembershipResources.class.getDeclaredField("observations");field.setAccessible(true);
        var journal=field.get(budget);var transfers=MembershipResourceObservations.class.getDeclaredField("transfers");transfers.setAccessible(true);
        // Fail only the optional recorder, after the real atomic switch.
        transfers.set(journal,Collections.emptyList());
        var next=budget.transferStorage(Map.of(source,"next")).get(source);source.close();
        assertTrue(budget.storageTransferObservations().failed());assertFalse(budget.observationCheckpoint().complete());
        assertEquals(20,budget.usage().staging());next.close();assertEquals(0,budget.usage().leases());
    }
}
