package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53SessionExportOwnershipTest {
    @TempDir Path temp;
    static MembershipResources budget(){return new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,65536,4096,true);}
    @Test void optInRequiresBothRecordersAndDisabledOwnershipDoesNothing() {
        assertThrows(IllegalArgumentException.class,()->new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,4096,0,true));
        var b=new MembershipResources(512*MIB);
        try(var session=b.reserve(Unit.CONTROL,"session",10)) {
            assertFalse(session.observesExports());session.observeExportOwnership(null);
        }
        assertEquals(0,b.usage().leases());
    }
    @Test void attachmentSurvivesRevocationBeforeOrAfterCapture() {
        for(boolean early:List.of(false,true)) {
            var b=budget();var export=b.reserve(Unit.CONTROL,"export",20);var session=b.reserve(Unit.CONTROL,"session",10);
            if(early)export.close();session.observeExportOwnership(List.of(export));if(!early)export.close();
            long call=session.observeCloseBegin((MembershipResources.Lease)null);session.close();session.observeCloseReturned(call);
            var snapshot=b.controlCloseObservations();assertFalse(snapshot.failed());assertFalse(snapshot.truncated());
            assertEquals(List.of("ATTACHED","BEGIN","RETURNED"),snapshot.rows().stream().map(MembershipControlCloseObservations.Row::event).toList());
            assertEquals(List.of("export"),snapshot.rows().getFirst().children());assertEquals(0,b.usage().leases());
        }
    }
    @Test void releasedForeignHandleWithTheSameNameIsStillForeign() {
        var b=budget();var other=budget();var foreign=other.reserve(Unit.CONTROL,"export",20);foreign.close();
        try(var export=b.reserve(Unit.CONTROL,"export",20);var session=b.reserve(Unit.CONTROL,"session",10)) {
            session.observeExportOwnership(List.of(foreign));assertTrue(b.controlCloseObservations().failed());
            assertEquals(2,b.usage().leases());
        }
        assertEquals(0,b.usage().leases());
    }
    @Test void duplicateEmptyAndStorageClaimsFailOnlyObservation() {
        for(int mode=0;mode<4;mode++) {
            var b=budget();try(var export=b.reserve(Unit.CONTROL,"export",20);var storage=b.reserve(Unit.APPLICATION,"image",20);
                              var session=b.reserve(Unit.CONTROL,"session",10)) {
                session.observeExportOwnership(switch(mode){case 0->List.of();case 1->List.of(export,export);case 2->List.of(storage);default->List.of(session);});
                assertTrue(b.controlCloseObservations().failed());assertEquals(3,b.usage().leases());
            }
            assertEquals(0,b.usage().leases());
        }
    }
    @Test void boundedRecorderCannotSilentlyLoseAnAttachment() {
        var b=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,4096,1,true);
        var export=b.reserve(Unit.CONTROL,"export",20);var session=b.reserve(Unit.CONTROL,"session",10);
        session.observeExportOwnership(List.of(export));long call=session.observeCloseBegin((MembershipResources.Lease)null);
        export.close();session.close();session.observeCloseReturned(call);
        assertTrue(b.controlCloseObservations().truncated());assertEquals(0,b.usage().leases());
    }
    @Test void independentRevocationAndAttachmentKeepOneResourceOrder()throws Exception {
        var b=budget();try(var executor=Executors.newFixedThreadPool(2)) {
            for(int i=0;i<64;i++) {
                var export=b.reserve(Unit.CONTROL,"export-"+i,20);var session=b.reserve(Unit.CONTROL,"session-"+i,10);
                var start=new CountDownLatch(1);
                var capture=executor.submit(()->{start.await();session.observeExportOwnership(List.of(export));return null;});
                var revoke=executor.submit(()->{start.await();export.close();return null;});
                start.countDown();capture.get(5,TimeUnit.SECONDS);revoke.get(5,TimeUnit.SECONDS);session.close();
            }
        }
        assertFalse(b.controlCloseObservations().failed());assertEquals(64,b.controlCloseObservations().rows().size());assertEquals(0,b.usage().leases());
    }
    @Test void preparationSessionReleasesItsCopyWhilePublicationRemainsOwned()throws Exception {
        var helper=new V53JoiningRetentionNetworkTest();helper.temp=temp;
        MembershipResources b;
        try(var l=helper.new Local(true)) {
            b=l.a;var preparation=new V53JoiningPreparationTest();preparation.temp=temp;
            try(var endpoint=preparation.endpoint(l);var publication=preparation.publication(l)) {
                endpoint.publishJoiningPreparation(publication);
                try(var pull=l.pull((p,q,k,d)->{
                    try{return CompletableFuture.completedFuture(endpoint.handle(l.reader.activationIdentity(),q));}
                    catch(Exception error){return CompletableFuture.failedFuture(error);}
                })) {
                    byte[] bytes=pull.fetchPrefixMetadata(MembershipJoiningPreparation.reference(l.reader.activationContext(),l.reader.activationIdentity()),MembershipJoiningPreparation.MAXIMUM);
                    assertArrayEquals(MembershipJoiningPreparation.bytes(V53JoiningPreparationTest.hint(l)),bytes);
                }
                var rows=b.controlCloseObservations().rows();var attached=rows.stream().filter(row->row.event().equals("ATTACHED")).toList();
                assertEquals(1,attached.size());assertEquals(1,attached.getFirst().children().size());
                assertTrue(attached.getFirst().children().getFirst().startsWith("joining-preparation-export-"));
                assertTrue(rows.stream().anyMatch(row->row.event().equals("RETURNED") && row.owner().equals(attached.getFirst().owner())));
                assertTrue(publication.poll());publication.belongsTo(l.source,b);
                // The publication can still serve a second independent session.
                try(var pull=l.pull((p,q,k,d)->{
                    try{return CompletableFuture.completedFuture(endpoint.handle(l.reader.activationIdentity(),q));}
                    catch(Exception error){return CompletableFuture.failedFuture(error);}
                })) {pull.fetchPrefixMetadata(MembershipJoiningPreparation.reference(l.reader.activationContext(),l.reader.activationIdentity()),MembershipJoiningPreparation.MAXIMUM);}
                assertEquals(2,b.controlCloseObservations().rows().stream().filter(row->row.event().equals("ATTACHED")).count());
            }
        }
        assertEquals(0,b.usage().leases());assertFalse(b.controlCloseObservations().failed());
    }
}
