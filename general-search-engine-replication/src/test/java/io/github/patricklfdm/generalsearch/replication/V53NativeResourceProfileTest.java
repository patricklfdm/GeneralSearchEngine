package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Policy and accounting only; reservations do not prove physical overlap. */
class V53NativeResourceProfileTest {
    @TempDir Path temp;

    @Test void productionDefaultIsExplicitAndNeverAnEmptyOrJsonUpgrade() {
        var profile=V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING;
        assertEquals(16*1024*MIB,profile.stagingBytes);
        assertEquals(ReplicationBounds.defaults().maxSnapshotStagingBytes(),profile.stagingBytes);
        assertEquals(512*MIB,V53NativeResourceProfile.SMALL_FIXTURE.stagingBytes);
        profile.check(MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,V53WireArchive.Layout.SEGMENTED_BACKUP);
        assertThrows(IllegalArgumentException.class,()->profile.check(MembershipBootstrapSource.EMPTY,V53WireArchive.Layout.JSON));
        assertThrows(IllegalArgumentException.class,()->profile.check(MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,V53WireArchive.Layout.JSON));
        assertThrows(IllegalArgumentException.class,()->profile.check(MembershipBootstrapSource.EMPTY,V53WireArchive.Layout.SEGMENTED_BACKUP));
    }

    @Test void everyOldAndJoiningBudgetRecordsOnlyTheDeclaredStagingProfile()throws Exception {
        for(var profile:V53NativeResourceProfile.values()) {
            var root=Files.createDirectory(temp.resolve(profile.name()));
            try(var capture=new V53ResourceTransitionCapture(root,"a".repeat(64),List.of(),false,false,true,profile)) {
                for(int i=1;i<=6;i++) {
                    var budget=capture.create(V53ResourceTransitionCaptureTest.identity(i),0);
                    var observed=budget.observations();
                    assertEquals(profile.stagingBytes,observed.stagingLimit());
                    assertEquals(METADATA_LIMIT,observed.metadataLimit());assertEquals(QUEUE_LIMIT,observed.queueLimit());
                    assertEquals(0,budget.usage().leases());
                }
            }
        }
    }

    @Test void retainedFixtureCannotSilentlyReopenThroughLegacyJsonNetwork()throws Exception {
        var seed=new V53NativeSeedTest();seed.temp=temp;
        var request=seed.request(5,true);var profile=V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING;
        var original=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("original")),request,profile);
        var before=V53ReplayFilesTest.files(request.targets().getFirst().replicaDirectory());
        var copy=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("retained")),original);
        assertEquals(profile,copy.resourceProfile);assertEquals(0,copy.resources.usage().leases());
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        assertThrows(AssertionError.class,()->helper.new Network(copy,ReplicationBounds.defaults(),V53NativeDispatchTest.BUDGET));
        assertEquals(before,V53ReplayFilesTest.files(request.targets().getFirst().replicaDirectory()));
        try(var paths=Files.list(copy.raw)){assertEquals(0,paths.count());}
    }

    @Test void retainedDefaultExportObserverUsesTheDeclaredProductionPool()throws Exception {
        var seed=new V53NativeSeedTest();seed.temp=temp;var request=V53OwnedCrossViewTest.networkRequest(seed.request(3,true));
        var profile=V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING;
        var fixture=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("retained-default")),request,profile);
        fixture.ownedHistory=true;fixture.nativeApplication=true;
        for(var target:request.targets())try(var owner=fixture.open(target,"initialize-retention")) {
            owner.initializePeerRetention();owner.initializeFutureRetention();
        }
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        assertThrows(IllegalArgumentException.class,()->helper.new Network(fixture,ReplicationBounds.defaults(),V53NativeDispatchTest.BUDGET,
                true,true,V53WireArchive.Layout.JSON,profile));
        var n=helper.new Network(fixture,ReplicationBounds.defaults(),V53NativeDispatchTest.BUDGET,
                true,true,V53WireArchive.Layout.SEGMENTED_BACKUP,profile);
        try(n) {
            assertEquals(3,n.resources.size());
            for(var budget:n.resources) {
                assertEquals(profile.stagingBytes,budget.observations().stagingLimit());
                assertEquals(METADATA_LIMIT,budget.observations().metadataLimit());
                assertEquals(QUEUE_LIMIT,budget.observations().queueLimit());
            }
        }
        for(var budget:n.resources){assertEquals(0,budget.usage().leases());assertEquals(0,budget.usage().queued());}
    }

    @Test void networkRejectsWrongSourceBeforeBootstrapOrPreparation()throws Exception {
        var seed=new V53NativeSeedTest();seed.temp=temp;var request=seed.request(5,false);
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        assertThrows(IllegalArgumentException.class,()->helper.new Network(request,ReplicationBounds.defaults(),V53NativeDispatchTest.BUDGET,
                f->{throw new AssertionError("preparation must not run");},true,false,V53WireArchive.Layout.JSON,
                V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING));
        V53BootstrapSeedTest.absent(request);
    }

    @Test void networkRejectsConflictingCallerStagingBeforePreparation()throws Exception {
        var seed=new V53NativeSeedTest();seed.temp=temp;var request=seed.request(5,true);
        var helper=new V53NativeDispatchTest();helper.temp=temp;var b=ReplicationBounds.defaults();
        var conflicting=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),512*MIB);
        var error=assertThrows(AssertionError.class,()->helper.new Network(request,conflicting,V53NativeDispatchTest.BUDGET,
                f->{throw new AssertionError("preparation must not run");},true,false,V53WireArchive.Layout.SEGMENTED_BACKUP,
                V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING));
        assertTrue(error.getMessage().contains("matching transport bounds"));V53BootstrapSeedTest.absent(request);
    }

    @Test void largerStagingDoesNotChangeMetadataImageCountsOrCompletionReservations() {
        var budget=new MembershipResources(V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING.stagingBytes);
        var held=new ArrayList<MembershipResources.Lease>();
        try {
            for(var unit:List.of(Unit.GENERATION,Unit.SOURCE,Unit.LEARNER,Unit.JOURNAL,Unit.CATALOG,Unit.MISC,Unit.APPLICATION))
                for(int i=0;i<unit.count;i++)held.add(budget.reserve(unit,unit.name()+i,unit.bytes));
            assertEquals(324*MIB,budget.usage().metadata());assertEquals(672*MIB,budget.usage().staging());
            assertEquals(7,budget.usage().counts().get(Unit.APPLICATION));
            assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.APPLICATION,"eighth",1));
            assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.SOURCE,"seventh",1));
        }finally {Collections.reverse(held);held.forEach(MembershipResources.Lease::close);}
        assertEquals(0,budget.usage().leases());
    }
}
