package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53ScratchTest {
    @TempDir Path temp;
    static final String ROOT="ab".repeat(32);
    static final String IMAGE="cd".repeat(32)+".image";
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipScratch open(Path path,MembershipScratch.Role role,MembershipResources budget,MembershipScratch.Events events)throws IOException {
        return MembershipScratch.open(path,ROOT,V53DeclarationsTest.node(1),role,budget,()->{},events);
    }
    Path initialized(String name,MembershipScratch.Role role)throws Exception {
        Path path=temp.resolve(name);var budget=resources();try(var ignored=open(path,role,budget,e->{})){}assertEquals(0,budget.usage().leases());return path;
    }
    Path source(Path root,MembershipScratch.Role role)throws Exception {
        Path source;
        if(role==MembershipScratch.Role.OUTGOING)source=Files.createDirectory(root.resolve("source-"+UUID.randomUUID()));
        else source=Files.createDirectory(Files.createDirectory(root.resolve("selected-"+UUID.randomUUID())).resolve("source-1"));
        Files.write(source.resolve("source.gscp"),new byte[]{1,2,3});Files.write(source.resolve(IMAGE),new byte[]{4,5});return source;
    }
    @Test void exclusiveScopeRetainsOnlySmallOwnerMetadataAndReopens()throws Exception {
        for(var role:MembershipScratch.Role.values()) {
            Path path=temp.resolve(role.name());var budget=resources();
            try(var owner=open(path,role,budget,e->{})) {
                assertTrue(owner.recovered().isEmpty());assertEquals(path,owner.directory());
                assertThrows(ReplicationException.class,()->open(path,role,budget,e->{}));owner.check();
                new V53MembershipOwnershipTest().probe(path.resolve("scope.lock"));
            }
            assertEquals(0,budget.usage().leases());var before=V53ReplayFilesTest.files(path);
            try(var owner=open(path,role,budget,e->{})){assertTrue(owner.recovered().isEmpty());assertEquals(before,V53ReplayFilesTest.files(path));}
            assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(path,8));
        }
    }
    @Test void abandonedPartialTreesAreDiscardedWithoutInterpretingThemAsAuthority()throws Exception {
        for(var role:MembershipScratch.Role.values()) {
            Path path=initialized(role.name(),role);source(path,role);var budget=resources();var events=new ArrayList<String>();
            try(var owner=open(path,role,budget,events::add)) {
                assertEquals(role==MembershipScratch.Role.INCOMING?4:3,owner.recovered().size());
                assertEquals(5,owner.recovered().stream().mapToLong(MembershipScratch.Discarded::bytes).sum());
                assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(path,8));
                assertEquals(1,budget.usage().leases());assertEquals("RECOVERY_COMPLETE",events.getLast());
            }
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void unknownAndLinkedInventoryRejectsBeforeDeletingAnyValidChild()throws Exception {
        for(String variant:List.of("extra-root","extra-source","symlink","hardlink","bad-source","nested","too-many")) {
            var role=MembershipScratch.Role.OUTGOING;Path path=initialized(variant,role);Path good=source(path,role);
            switch(variant) {
                case "extra-root" -> Files.writeString(path.resolve("operator.txt"),"keep");
                case "extra-source" -> Files.writeString(good.resolve("operator.txt"),"keep");
                case "symlink" -> {Files.delete(good.resolve(IMAGE));Files.createSymbolicLink(good.resolve(IMAGE),Files.writeString(temp.resolve("outside"),"keep"));}
                case "hardlink" -> Files.createLink(temp.resolve("alias"),good.resolve(IMAGE));
                case "bad-source" -> Files.createDirectory(path.resolve("source-invalid"));
                case "nested" -> Files.createDirectory(good.resolve("nested"));
                case "too-many" -> {for(int i=0;i<6;i++)Files.createDirectory(path.resolve("source-"+UUID.randomUUID()));}
            }
            var budget=resources();assertThrows(Exception.class,()->open(path,role,budget,e->{}));
            assertArrayEquals(new byte[]{1,2,3},Files.readAllBytes(good.resolve("source.gscp")));assertTrue(Files.exists(good.resolve(IMAGE)));assertEquals(0,budget.usage().leases());
        }
    }
    @Test void foreignRootIdentityRoleAndRelocatedDirectoryAreNotAdopted()throws Exception {
        for(String variant:List.of("root","identity","role","relocated")) {
            Path original=initialized(variant,MembershipScratch.Role.OUTGOING);source(original,MembershipScratch.Role.OUTGOING);Path path=original;
            if(variant.equals("relocated")){path=temp.resolve("moved");Files.move(original,path);}
            Path selected=path;var before=V53ReplayFilesTest.files(path);var budget=resources();
            assertThrows(IllegalArgumentException.class,()->MembershipScratch.open(selected,variant.equals("root")?"ef".repeat(32):ROOT,
                    V53DeclarationsTest.node(variant.equals("identity")?2:1),variant.equals("role")?MembershipScratch.Role.INCOMING:MembershipScratch.Role.OUTGOING,budget,()->{},e->{}));
            assertEquals(before,V53ReplayFilesTest.files(path));assertEquals(0,budget.usage().leases());
        }
    }
    @Test void recoveryReservesAllBytesBeforeItsFirstDeletion()throws Exception {
        Path path=initialized("capacity",MembershipScratch.Role.OUTGOING);source(path,MembershipScratch.Role.OUTGOING);
        var before=V53ReplayFilesTest.files(path);var budget=resources();var held=new ArrayList<MembershipResources.Lease>();
        try {
            for(int i=0;i<7;i++)held.add(budget.reserve(MembershipResources.Unit.APPLICATION,"held-"+i,1));
            assertThrows(IllegalArgumentException.class,()->open(path,MembershipScratch.Role.OUTGOING,budget,e->{}));
            assertEquals(before,V53ReplayFilesTest.files(path));assertEquals(7,budget.usage().leases());
        }finally{for(var lease:held)lease.close();}
        try(var owner=open(path,MembershipScratch.Role.OUTGOING,budget,e->{})){assertEquals(3,owner.recovered().size());}
        assertEquals(0,budget.usage().leases());
    }
    @Test void interruptedDeletionRescansOnlyRemainingOriginalScope()throws Exception {
        for(String cut:List.of("RECOVERY_VALIDATED","FILE_REMOVED","FILE_REMOVAL_FORCED","DIRECTORY_REMOVED","DIRECTORY_REMOVAL_FORCED")) {
            Path path=initialized(cut,MembershipScratch.Role.INCOMING);source(path,MembershipScratch.Role.INCOMING);var budget=resources();var once=new AtomicBoolean();
            assertThrows(IOException.class,()->open(path,MembershipScratch.Role.INCOMING,budget,event->{if(event.equals(cut) && once.compareAndSet(false,true))throw new IOException("injected");}));
            assertTrue(once.get());assertEquals(0,budget.usage().leases());
            try(var owner=open(path,MembershipScratch.Role.INCOMING,budget,e->{})){assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(owner.directory(),8));}
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void closeCannotDeleteLiveOrForeignChildren()throws Exception {
        Path path=temp.resolve("live");var budget=resources();var owner=open(path,MembershipScratch.Role.OUTGOING,budget,e->{});
        Path file=Files.writeString(path.resolve("operator.txt"),"keep");assertThrows(IllegalArgumentException.class,owner::close);
        assertEquals("keep",Files.readString(file));assertEquals(1,budget.usage().leases());new V53MembershipOwnershipTest().probe(path.resolve("scope.lock"));
        Files.delete(file);owner.close();owner.close();assertEquals(0,budget.usage().leases());
    }
    @Test void markerInitializationCanResumeOnlyWithoutAnyStagedData()throws Exception {
        for(boolean data:List.of(false,true)) {
            Path path=initialized("torn-"+data,MembershipScratch.Role.OUTGOING);Path marker=path.resolve("owner.json");var original=Files.readAllBytes(marker);
            Files.write(marker,Arrays.copyOf(original,original.length/2));if(data)source(path,MembershipScratch.Role.OUTGOING);var budget=resources();
            if(data){var before=V53ReplayFilesTest.files(path);assertThrows(IllegalArgumentException.class,()->open(path,MembershipScratch.Role.OUTGOING,budget,e->{}));assertEquals(before,V53ReplayFilesTest.files(path));}
            else try(var owner=open(path,MembershipScratch.Role.OUTGOING,budget,e->{})){assertArrayEquals(original,Files.readAllBytes(marker));}
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void oversizeFileRejectsBeforeAnyDeletion()throws Exception {
        for(String name:List.of("source.gscp",IMAGE)) {
            Path path=initialized("oversize-"+name,MembershipScratch.Role.OUTGOING);Path data=source(path,MembershipScratch.Role.OUTGOING);
            long bytes=(name.equals("source.gscp")?32:64)*MembershipResources.MIB+1;
            try(var file=new java.io.RandomAccessFile(data.resolve(name).toFile(),"rw")){file.setLength(bytes);}
            var budget=resources();assertThrows(IllegalArgumentException.class,()->open(path,MembershipScratch.Role.OUTGOING,budget,e->{}));
            assertEquals(bytes,Files.size(data.resolve(name)));assertTrue(Files.exists(data.resolve("source.gscp")));assertTrue(Files.exists(data.resolve(IMAGE)));assertEquals(0,budget.usage().leases());
        }
    }
    @Test void replacedFilesBetweenScanAndDeletionArePreserved()throws Exception {
        Path path=initialized("replaced",MembershipScratch.Role.OUTGOING);Path data=source(path,MembershipScratch.Role.OUTGOING);var budget=resources();
        Path saved=temp.resolve("original-image");
        assertThrows(IllegalArgumentException.class,()->open(path,MembershipScratch.Role.OUTGOING,budget,event->{
            if(event.equals("RECOVERY_VALIDATED")){Files.move(data.resolve(IMAGE),saved);Files.write(data.resolve(IMAGE),new byte[]{9,9});}
        }));
        assertArrayEquals(new byte[]{4,5},Files.readAllBytes(saved));assertArrayEquals(new byte[]{9,9},Files.readAllBytes(data.resolve(IMAGE)));
        assertArrayEquals(new byte[]{1,2,3},Files.readAllBytes(data.resolve("source.gscp")));assertEquals(0,budget.usage().leases());
    }
    @Test void failedProtocolOwnerDoesNotPreventReleasingAnEmptyScope()throws Exception {
        var live=new AtomicBoolean(true);var budget=resources();Path path=temp.resolve("failed-owner");
        var owner=MembershipScratch.open(path,ROOT,V53DeclarationsTest.node(1),MembershipScratch.Role.OUTGOING,budget,
                ()->{if(!live.get())throw new IOException("owner failed");},e->{});
        live.set(false);owner.close();assertEquals(0,budget.usage().leases());
        var before=V53ReplayFilesTest.files(path);
        assertThrows(IOException.class,()->MembershipScratch.open(path,ROOT,V53DeclarationsTest.node(1),MembershipScratch.Role.OUTGOING,budget,
                ()->{throw new IOException("owner failed");},e->{}));assertEquals(before,V53ReplayFilesTest.files(path));
    }
    @Test void journalRejectsOverlappingAuthorityAndUnsharedBudgetBeforeCreatingScratch()throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local()) {
            var target=local.base.f.request.targets().get(1);var before=V53ReplayFilesTest.files(target.replicaDirectory());
            for(Path path:List.of(target.replicaDirectory().resolve("scratch"),target.materialization().directory().resolve("scratch"),target.replicaDirectory().getParent()))
                assertThrows(ReplicationException.class,()->local.base.peer.openScratch(path,MembershipScratch.Role.INCOMING,local.base.peerResources,e->{}));
            Path unrelated=temp.resolve("wrong-budget");assertThrows(IllegalArgumentException.class,()->local.base.peer.openScratch(unrelated,MembershipScratch.Role.INCOMING,resources(),e->{}));
            assertFalse(Files.exists(unrelated));assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
        }
    }
    @Test void ownerCapacityIsReservedBeforeEvenCreatingAnEmptyDirectory()throws Exception {
        Path path=temp.resolve("owner-capacity");var budget=resources();var held=new ArrayList<MembershipResources.Lease>();
        try {
            for(int n=0;n<256;n++)held.add(budget.reserve(MembershipResources.Unit.CONTROL,"held-"+n,1));
            assertThrows(IllegalArgumentException.class,()->open(path,MembershipScratch.Role.OUTGOING,budget,e->{}));
            assertFalse(Files.exists(path));assertEquals(256,budget.usage().leases());
        }finally{for(var lease:held)lease.close();}
        assertEquals(0,budget.usage().leases());
    }
}
