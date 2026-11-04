package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53FloorResumeCopyTest {
    @TempDir Path temp;
    final class Case {
        final Path path;
        final V53CurrentGenerationFixture fixture=new V53CurrentGenerationFixture(4,0,false);
        final List<MembershipFloor.Copy> copies=new ArrayList<>();
        final MembershipResources budget=new MembershipResources(512*MembershipResources.MIB);
        final Decoded proposal;
        Case(String name,int forced)throws Exception {
            path=temp.resolve(name);var helper=new V53FloorTest();
            for(int i=1;i<=3;i++)copies.add(helper.copy(i==1?path:temp.resolve(name+"-"+i),4,0,i));
            proposal=MembershipFloor.create(fixture.root(),copies.getFirst(),copies);
            var count=new AtomicInteger();
            try(var owner=open(event->{if(event.equals("FLOOR_COPY_HANDED_OFF") && count.incrementAndGet()==forced)throw new IOException("cut");})) {
                assertThrows(IOException.class,()->owner.establishFloor(copies,copy->{}));
            }
            assertEquals(0,budget.usage().leases());
            assertFalse(Files.exists(path.resolve("floor-copies/floor.gsr")));
        }
        MembershipGrantJournal open(MembershipBallotAllocator.Cut cut)throws Exception {
            return MembershipGrantJournal.openFloors(path,fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,cut);
        }
    }
    @Test void oneTwoAndAllRetainedCopiesResumeWithOnlyOneReceivingSourceSlot()throws Exception {
        for(int forced:List.of(1,2,3)) {
            var c=new Case("copies-"+forced,forced);var old=new ArrayList<MembershipResources.Lease>();
            for(int i=0;i<2;i++)old.add(c.budget.reserve(MembershipResources.Unit.SOURCE,"old-"+i,1));
            var events=new ArrayList<String>();
            try(var owner=c.open(event->{events.add(event);assertTrue(c.budget.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0)<=6);})) {
                assertArrayEquals(c.proposal.bytes(),owner.pendingFloorProposal().orElseThrow().bytes());
                for(var copy:c.copies) {
                    try(var receive=c.budget.reserve(MembershipResources.Unit.SOURCE,"receiving",1)) {
                        owner.resumeFloorCopy(c.proposal,copy,()->{});
                        assertEquals("FLOOR_RESUME_COPY_FORCED",events.getLast());
                        for(var file:copy.copyFiles().entrySet())assertArrayEquals(file.getValue(),Files.readAllBytes(c.path.resolve("floor-copies/"+copy.generation.digest()+"/"+file.getKey())));
                        assertTrue(owner.governingFloor().isEmpty());
                        assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(c.fixture.fixture.source.ballot(20)));
                    }
                }
                assertEquals(5,c.budget.usage().counts().get(MembershipResources.Unit.SOURCE));
                owner.establishFloor(c.copies,copy->{});
                assertArrayEquals(c.proposal.bytes(),owner.governingFloor().orElseThrow().bytes());
            }finally{old.forEach(MembershipResources.Lease::close);}
            assertEquals(0,c.budget.usage().leases());
            try(var owner=c.open(event->{})){assertTrue(owner.pendingFloorProposal().isEmpty());assertArrayEquals(c.proposal.bytes(),owner.governingFloor().orElseThrow().bytes());}
            assertEquals(0,c.budget.usage().leases());
        }
    }
    @Test void sameCutDifferentGenerationAndOtherQuorumCannotReplaceOriginals()throws Exception {
        for(boolean proposal:List.of(false,true)) {
            var c=new Case("wrong-"+proposal,1);var copy=c.copies.get(1);
            var changed=new TreeMap<>(copy.generation.value());changed.put("generation","b");
            var generation=decode(encode("records","GENERATION",changed),"records","GENERATION");
            var files=new TreeMap<>(copy.copyFiles());files.put("generation.gsr",generation.bytes());
            var other=MembershipFloor.Copy.verify(generation,copy.capsule,copy.owner,
                Set.of(new MembershipContext.Owned("node-2",copy.owner.storageId(),generation.digest(),MembershipContext.cutDigest(copy.capsule.context.cut))),files);
            var alternate=MembershipFloor.create(c.fixture.root(),c.copies.getFirst(),List.of(c.copies.getFirst(),other,c.copies.get(2)));
            var before=V53CombinedResourceRecoveryTest.disk(c.path);
            try(var owner=c.open(event->{})) {
                var error=assertThrows(IllegalArgumentException.class,()->owner.resumeFloorCopy(proposal?alternate:c.proposal,other,()->{}));
                assertEquals(proposal?"floor requires exact original proposal":"partial floor requires exact original copy",error.getMessage());
            }
            assertEquals(before,V53CombinedResourceRecoveryTest.disk(c.path));assertEquals(0,c.budget.usage().leases());
        }
    }
    @Test void interruptedCopyResumesButNeverPublishesAuthorityOnItsOwn()throws Exception {
        for(String cut:List.of("FLOOR_RESUME_RESERVED","FLOOR_MANIFEST_WRITTEN","FLOOR_MEMBER_FORCED","FLOOR_RESUME_COPY_FORCED")) {
            var c=new Case(cut,1);
            try(var owner=c.open(event->{if(event.equals(cut))throw new IOException(cut);})) {
                assertThrows(IOException.class,()->owner.resumeFloorCopy(c.proposal,c.copies.getFirst(),()->{}));
            }
            assertFalse(Files.exists(c.path.resolve("floor-copies/floor.gsr")));assertEquals(0,c.budget.usage().leases());
            try(var owner=c.open(event->{})) {
                for(var copy:c.copies)owner.resumeFloorCopy(c.proposal,copy,()->{});
                assertTrue(owner.governingFloor().isEmpty());owner.establishFloor(c.copies,copy->{});
                assertArrayEquals(c.proposal.bytes(),owner.governingFloor().orElseThrow().bytes());
            }
            assertEquals(0,c.budget.usage().leases());
        }
    }
    @Test void revocationAtForceStopsBeforeAuthorityAndKeepsOriginalProposal()throws Exception {
        var c=new Case("revoked",1);var revoked=new AtomicBoolean();
        try(var owner=c.open(event->{if(event.equals("FLOOR_MEMBER_FORCED"))revoked.set(true);})) {
            var error=assertThrows(IOException.class,()->owner.resumeFloorCopy(c.proposal,c.copies.getFirst(),()->{if(revoked.get())throw new IOException("revoked");}));
            assertEquals("revoked",error.getMessage());
        }
        assertFalse(Files.exists(c.path.resolve("floor-copies/floor.gsr")));
        assertArrayEquals(c.proposal.bytes(),Files.readAllBytes(c.path.resolve("floor-copies/proposal.gsr")));
        assertEquals(0,c.budget.usage().leases());
    }
    @Test void tornProposalAndAlteredOriginalMemberStayFailClosed()throws Exception {
        for(boolean proposal:List.of(true,false)) {
            var c=new Case("corrupt-"+proposal,3);
            Path member=c.path.resolve("floor-copies/"+(proposal?"proposal.gsr":c.copies.getFirst().generation.digest()+"/promise.gsr"));
            byte[] bytes=Files.readAllBytes(member);
            if(proposal)Files.write(member,Arrays.copyOf(bytes,bytes.length/2));
            else {bytes[bytes.length-1]^=1;Files.write(member,bytes);}
            var before=V53CombinedResourceRecoveryTest.disk(c.path);
            try(var owner=c.open(event->{})) {
                assertThrows(IllegalArgumentException.class,()->owner.resumeFloorCopy(c.proposal,c.copies.getFirst(),()->{}));
            }
            assertEquals(before,V53CombinedResourceRecoveryTest.disk(c.path));assertEquals(0,c.budget.usage().leases());
        }
    }
}
