package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Evidence collection must not release the process lock it is observing. */
class V53EvidenceSnapshotTest {
    @TempDir Path temp;
    @Test void recursiveCopyPreservesRealProcessLocksAndIndependentBytes()throws Exception {
        Path root=Files.createDirectory(temp.resolve("original")),nested=Files.createDirectory(root.resolve("nested"));
        Path lock=root.resolve("replica.lock"),second=nested.resolve("operation.lock");
        byte[] payload=new byte[131083];new java.util.Random(53).nextBytes(payload);Files.write(nested.resolve("data"),payload);
        var probe=new V53MembershipOwnershipTest();
        try(var first=MembershipOwnership.own(lock,true);var other=MembershipOwnership.own(second,true)) {
            probe.probe(lock,second);
            for(int attempt=0;attempt<2;attempt++) {
                Path copy=temp.resolve("copy-"+attempt);V53JournalApplicationTest.copy(root,copy);
                probe.probe(lock,second);
                assertArrayEquals(payload,Files.readAllBytes(copy.resolve("nested/data")));
                assertEquals(0,Files.size(copy.resolve("replica.lock")));
                assertNotEquals(MembershipBasisSources.key(lock),MembershipBasisSources.key(copy.resolve("replica.lock")));
                try(var independent=MembershipOwnership.own(copy.resolve("replica.lock"),false)) {
                    probe.probe(lock,second,copy.resolve("replica.lock"));
                }
            }
            Files.writeString(nested.resolve("data"),"later mutation");
            assertArrayEquals(payload,Files.readAllBytes(temp.resolve("copy-0/nested/data")));
        }
        try(var reopened=MembershipOwnership.own(lock,false)){probe.probe(lock);}
    }
    @Test void existingEvidenceRefusesOverwriteWithoutDisturbingTheOriginalOwner()throws Exception {
        Path root=Files.createDirectory(temp.resolve("original")),copy=Files.createDirectory(temp.resolve("prior-evidence"));
        Files.writeString(copy.resolve("receipt"),"preserve");Path lock=root.resolve("replica.lock");
        try(var owner=MembershipOwnership.own(lock,true)) {
            assertThrows(FileAlreadyExistsException.class,()->V53JournalApplicationTest.copy(root,copy));
            assertEquals("preserve",Files.readString(copy.resolve("receipt")));
            new V53MembershipOwnershipTest().probe(lock);
        }
    }
    @Test void linkedNegativeEvidenceKeepsContentSemanticsWithoutReleasingAnOwnedInode()throws Exception {
        Path root=Files.createDirectory(temp.resolve("links")),lock=root.resolve("replica.lock");
        var probe=new V53MembershipOwnershipTest();
        try(var owner=MembershipOwnership.own(lock,true)) {
            Files.createSymbolicLink(root.resolve("symbolic"),lock);
            Path copy=temp.resolve("symbolic-copy");V53JournalApplicationTest.copy(root,copy);probe.probe(lock);
            assertFalse(Files.isSymbolicLink(copy.resolve("symbolic")));
            Files.createLink(root.resolve("hard"),lock);
            V53JournalApplicationTest.copy(root,temp.resolve("hard-copy"));probe.probe(lock);
            assertNotEquals(MembershipBasisSources.key(temp.resolve("hard-copy/replica.lock")),
                    MembershipBasisSources.key(temp.resolve("hard-copy/hard")));
            // Production still rejects this deliberately malformed input.
            assertEquals(ReplicationException.Reason.STORAGE_FAILURE,
                    assertThrows(ReplicationException.class,()->AdmissionPaths.regular(lock)).reason());
        }
    }
}
