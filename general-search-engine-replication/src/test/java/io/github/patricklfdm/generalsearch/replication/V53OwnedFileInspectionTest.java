package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.nio.ByteBuffer;
import java.nio.channels.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53OwnedFileInspectionTest {
    @TempDir Path temp;
    @Test void evidenceSnapshotsPreserveLocksAndHashAliasedAndOrdinaryFiles()throws Exception {
        Path lock=temp.resolve("replica.lock"),data=temp.resolve("payload.bin");byte[] bytes={1,2,3};Files.write(data,bytes);
        try(var owner=MembershipOwnership.own(lock,true)) {
            Files.createSymbolicLink(temp.resolve("symbolic-link"),lock);
            var expected=Map.of("replica.lock",hash(new byte[0]),"symbolic-link",hash(new byte[0]),"payload.bin",hash(bytes));
            assertEquals(expected,V53ReplayFilesTest.files(temp));new V53MembershipOwnershipTest().probe(lock);
            Files.createLink(temp.resolve("hard-link"),lock);
            Files.createLink(temp.resolve("data-link"),data);
            var linked=new TreeMap<>(expected);linked.put("hard-link",hash(new byte[0]));linked.put("data-link",hash(bytes));
            assertEquals(linked,V53ReplayFilesTest.files(temp));new V53MembershipOwnershipTest().probe(lock);
            Files.delete(temp.resolve("hard-link"));Files.delete(temp.resolve("data-link"));
            assertEquals(expected,V53ReplayFilesTest.files(temp));new V53MembershipOwnershipTest().probe(lock);
        }
    }
    @Test void inspectingAnOwnedEmptyLockDoesNotReleaseItsKernelLock()throws Exception {
        Path path=temp.resolve("replica.lock");var probe=new V53MembershipOwnershipTest();
        try(var owner=MembershipOwnership.own(path,true)) {
            probe.probe(path);var identity=MembershipBasisSources.inspect(path,0,hash(new byte[0]));
            assertEquals(MembershipBasisSources.key(path),identity.key());assertTrue(owner.lock().isValid());probe.probe(path);
        }
    }
    @Test void learnerFingerprintsDoNotReleaseTheTypedPreparationLock()throws Exception {
        Path directory=Files.createDirectory(temp.resolve("typed")),path=directory.resolve("preparation.lock");
        try(var owner=MembershipOwnership.own(path,true)) {
            var names=new TreeSet<>(List.of(".","preparation.lock"));var probe=new V53MembershipOwnershipTest();probe.probe(path);
            var fingerprints=MembershipLearnerFingerprints.capture(directory,names,Set.of(),false,4096);
            assertEquals(2,fingerprints.size());assertTrue(owner.lock().isValid());probe.probe(path);
        }
    }
    @Test void nonemptyReceiveInspectionForceAndRetainedRenameKeepKernelOwnership()throws Exception {
        Path path=temp.resolve("received"),retained=temp.resolve("retained");byte[] body={1,2,3,4,5,6};
        var resources=V53SourceReceiveTest.budget();var binding=V53ResourceTransferTest.binding(body);var probe=new V53MembershipOwnershipTest();
        try(var file=V53SourceReceiveTest.file(path,body,resources,new AtomicLong(),e->{})) {
            V53SourceReceiveTest.complete(file,body);probe.probe(path);
            file.finish(binding,p->{assertArrayEquals(body,AdmissionPaths.read(p,body.length));probeUnchecked(p);});
            assertArrayEquals(body,file.bytes());probe.probe(path);
            try(var view=MembershipFileAccess.open(path,StandardOpenOption.WRITE)){view.force(true);}probe.probe(path);
            try(var custody=file.detachChecked()) {
                Files.move(path,retained,StandardCopyOption.ATOMIC_MOVE);custody.check(retained);
                assertEquals(1,AdmissionPaths.inventory(temp,body.length).size());probe.probe(retained);
                file.close();custody.check(retained);probe.probe(retained);
            }
        }
        assertEquals(0,resources.usage().leases());
        try(var channel=FileChannel.open(retained,StandardOpenOption.WRITE);var acquired=channel.tryLock()){assertNotNull(acquired);}
    }
    private static void probeUnchecked(Path path)throws java.io.IOException {
        try{new V53MembershipOwnershipTest().probe(path);}catch(Exception error){throw new java.io.IOException(error);}
    }
    @Test void borrowedReadersAndWriterUseIndependentCursorsWithoutMovingReceiveAppend()throws Exception {
        Path path=temp.resolve("receive-cursor");byte[] body={1,2,3,4,5,6};var binding=V53ResourceTransferTest.binding(body);
        try(var file=V53SourceReceiveTest.file(path,body,V53SourceReceiveTest.budget(),new AtomicLong(),e->{})) {
            byte[] first={1,2,3};file.chunk(binding,0,first,hash(first));
            try(var a=MembershipFileAccess.open(path,StandardOpenOption.READ);var b=MembershipFileAccess.open(path,StandardOpenOption.READ);
                    var writer=MembershipFileAccess.open(path,StandardOpenOption.WRITE)) {
                var buf=ByteBuffer.allocate(2);assertEquals(2,a.read(buf));assertArrayEquals(new byte[]{1,2},buf.array());
                assertEquals(0,b.position());writer.position(1);assertEquals(1,writer.write(ByteBuffer.wrap(new byte[]{2})));
                assertEquals(2,a.position());byte[] last={4,5,6};file.chunk(binding,3,last,hash(last));
                var all=ByteBuffer.allocate(6);assertEquals(6,b.read(all));assertArrayEquals(body,all.array());
                assertThrows(NonWritableChannelException.class,()->a.write(ByteBuffer.wrap(new byte[]{1})));
                assertThrows(NonReadableChannelException.class,()->writer.read(ByteBuffer.allocate(1)));
            }
            file.finish(binding,p->{});assertArrayEquals(body,file.bytes());new V53MembershipOwnershipTest().probe(path);
        }
    }
    @Test void closingOldViewsCannotUnlockReopenedOwnerAndClosingOwnerRevokesBorrowers()throws Exception {
        Path path=temp.resolve("revocation.lock");var owner=MembershipOwnership.own(path,true);
        var borrowed=MembershipFileAccess.open(path,StandardOpenOption.READ);owner.close();
        assertThrows(ClosedChannelException.class,borrowed::size);
        try(var next=MembershipOwnership.own(path,false)) {
            borrowed.close();owner.close();new V53MembershipOwnershipTest().probe(path);
        }
    }
    @Test void ownershipCannotBeginWhileAnyEarlierOrdinaryDescriptorRemainsOpen()throws Exception {
        Path path=Files.createFile(temp.resolve("ordinary.lock"));
        var first=MembershipFileAccess.open(path,StandardOpenOption.READ);var second=MembershipFileAccess.open(path,StandardOpenOption.WRITE);
        assertThrows(ReplicationException.class,()->MembershipOwnership.own(path,false));first.close();
        assertThrows(ReplicationException.class,()->MembershipOwnership.own(path,false));second.close();
        try(var owner=MembershipOwnership.own(path,false)) {
            first.close();second.close();new V53MembershipOwnershipTest().probe(path);
        }
    }
    @Test void unsupportedAndDuplicateOperationsRefuseWithoutUnlockingOrChangingBytes()throws Exception {
        Path path=temp.resolve("negative.lock");
        try(var owner=MembershipOwnership.own(path,true);var view=MembershipFileAccess.open(path,StandardOpenOption.READ)) {
            assertThrows(FileAlreadyExistsException.class,()->MembershipFileAccess.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE));
            assertThrows(IllegalArgumentException.class,()->MembershipFileAccess.open(path,StandardOpenOption.WRITE,StandardOpenOption.TRUNCATE_EXISTING));
            assertThrows(UnsupportedOperationException.class,view::tryLock);
            assertThrows(UnsupportedOperationException.class,()->view.map(FileChannel.MapMode.READ_ONLY,0,0));
            assertEquals(0,Files.size(path));new V53MembershipOwnershipTest().probe(path);
        }
    }
    @Test void nonemptyDescriptorCustodyRevokesOldViewsAndTheirCloseCannotUnlockSuccessor()throws Exception {
        Path path=temp.resolve("nonempty-transfer");var old=MembershipFileAccess.own(path,true,false,c->{});
        AdmissionPaths.write(old.channel(),new byte[]{1,2,3});var view=MembershipFileAccess.open(path,StandardOpenOption.READ);
        try(var next=old.transfer()) {
            old.close();assertThrows(IllegalArgumentException.class,old::channel);
            assertThrows(IllegalArgumentException.class,view::size);view.close();
            assertArrayEquals(new byte[]{1,2,3},AdmissionPaths.read(path,3));new V53MembershipOwnershipTest().probe(path);
        }finally{view.close();old.close();}
    }
    @Test void custodyTransferKeepsBorrowedInspectionOnTheSameDescriptor()throws Exception {
        Path path=temp.resolve("handoff.lock");var old=MembershipOwnership.own(path,true);
        try(var view=MembershipFileAccess.open(path,StandardOpenOption.READ);var next=old.transfer()) {
            old.close();assertEquals(0,view.size());view.close();
            MembershipBasisSources.inspect(path,0,hash(new byte[0]));new V53MembershipOwnershipTest().probe(path);
        }finally{old.close();}
    }
}
