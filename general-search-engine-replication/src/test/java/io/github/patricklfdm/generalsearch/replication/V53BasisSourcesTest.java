package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BasisSourcesTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("SOURCE_BEFORE_CREATE","SOURCE_CREATED","SOURCE_PACKET_WRITTEN","SOURCE_PACKET_FORCED",
            "SOURCE_IMAGE_WRITTEN","SOURCE_IMAGE_FORCED","SOURCE_FILES_DIRECTORY_FORCED","SOURCE_DIRECTORY_FORCED");
    static Path provision(Path path,int size) throws Exception {
        V53BallotAllocatorWorker.provision(path,size);AdmissionPaths.write(path.resolve(MembershipGrantJournal.FILE),new byte[0]);
        Files.createDirectory(path.resolve(MembershipBasisSources.DIRECTORY));AdmissionPaths.forceDirectory(path);return path;
    }
    MembershipResources resources() {return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,int size,MembershipResources r,MembershipBallotAllocator.Cut cut) throws Exception {
        return MembershipGrantJournal.openRetained(path,V53BallotAllocatorWorker.root(new V53ContextFixture(size,"REPLACE")),V53DeclarationsTest.node(1),r,cut);
    }
    static Decoded prepare(MembershipGrantJournal store,int size,int through,long ballot) throws Exception {
        var f=new V53CapsuleFixture(size,"REPLACE",through);return store.prepare(f.verify(),f.source.ballot(ballot),null,f.source.images);
    }
    Path folder(Path path,Decoded basis) {return path.resolve("sources").resolve((String)basis.value().get("basisId"));}

    @Test void originalPacketAndImagesSurviveDuplicateProgressAndRestart() throws Exception {
        for(int size:List.of(3,4,5)) {
            Path path=provision(temp.resolve("size"+size),size);var r=resources();Decoded original;
            try(var store=open(path,size,r,e->{})) {
                original=prepare(store,size,0,20);assertEquals(1,r.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertArrayEquals(original.bytes(),prepare(store,size,1,20).bytes());
            }
            assertEquals(0,r.usage().leases());byte[] packet=Files.readAllBytes(folder(path,original).resolve("source.gscp"));
            try(var store=open(path,size,r,e->{})) {
                assertEquals(1,r.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertArrayEquals(original.bytes(),prepare(store,size,1,20).bytes());prepare(store,size,1,21);
                assertArrayEquals(packet,Files.readAllBytes(folder(path,original).resolve("source.gscp")));
                assertEquals(2,r.usage().counts().get(MembershipResources.Unit.SOURCE));
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void incompleteSourceIsNotRepairedAndCompleteUnacknowledgedSourceIsNotResampled() throws Exception {
        for(String point:CUTS) {
            Path path=provision(temp.resolve(point),3);var r=resources();
            try(var store=open(path,3,r,e->{if(e.equals(point))throw new IOException("injected");})) {
                assertThrows(IOException.class,()->prepare(store,3,0,20));
            }
            assertEquals(0,r.usage().leases());
            if(List.of("SOURCE_CREATED","SOURCE_PACKET_WRITTEN","SOURCE_PACKET_FORCED").contains(point)) {
                byte[] journal=Files.readAllBytes(path.resolve("grants.gsr"));assertThrows(Exception.class,()->open(path,3,r,e->{}));
                assertArrayEquals(journal,Files.readAllBytes(path.resolve("grants.gsr")));assertEquals(0,r.usage().leases());
            } else try(var store=open(path,3,r,e->{})) {
                assertThrows(IllegalArgumentException.class,()->prepare(store,3,1,20));assertNotNull(prepare(store,3,1,21));
            }
        }
    }
    @Test void everySourceCutFencesHigherObservationBeforeGrant() throws Exception {
        for(String point:CUTS) {
            Path path=provision(temp.resolve("fence"+point),3);var source=new V53CapsuleFixture(3,"REPLACE",0).verify();var holder=new MembershipGrantJournal[1];
            try(var store=open(path,3,resources(),e->{if(e.equals(point))holder[0].observe(source.context,new V53ContextFixture(3,"REPLACE").ballot(21));})) {
                holder[0]=store;assertTrue(assertThrows(IllegalArgumentException.class,()->prepare(store,3,0,20)).getMessage().contains("higher ballot"));
            }
        }
    }
    @Test void exhaustionAndSharedReservationsRefuseBeforePromiseAndSurviveReopen() throws Exception {
        Path path=provision(temp.resolve("full"),3);var r=resources();
        try(var store=open(path,3,r,e->{})) {
            for(int i=0;i<6;i++)prepare(store,3,0,20+i);
            byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));
            assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,assertThrows(MembershipOperationException.class,()->prepare(store,3,0,26)).reason());
            assertArrayEquals(before,Files.readAllBytes(path.resolve("grants.gsr")));assertEquals(6,r.usage().counts().get(MembershipResources.Unit.SOURCE));
        }
        try(var store=open(path,3,r,e->{})){assertThrows(MembershipOperationException.class,()->prepare(store,3,0,27));}
        assertEquals(0,r.usage().leases());
        Path tight=provision(temp.resolve("tight"),3);var small=new MembershipResources(1);
        try(var store=open(tight,3,small,e->{})) {
            assertThrows(MembershipOperationException.class,()->prepare(store,3,0,20));assertEquals(0,Files.size(tight.resolve("grants.gsr")));
            assertEquals(1,small.usage().leases());
        }
        assertEquals(0,small.usage().leases());
    }
    @Test void corruptMissingExtraLinkedAndReplacedOriginalFilesBlockReturnAndOpen() throws Exception {
        for(String variant:List.of("missing","corrupt","extra","symlink","hardlink","packet","directory","old-source")) {
            Path path=provision(temp.resolve(variant),3);var r=resources();
            try(var store=open(path,3,r,e->{})) {
                var basis=prepare(store,3,0,20);Path dir=folder(path,basis);
                if(variant.equals("old-source"))prepare(store,3,1,21);
                Path file;try(var files=Files.list(dir)){file=files.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow();}
                byte[] bytes=Files.readAllBytes(file);
                switch(variant) {
                    case "missing","old-source" -> Files.delete(file);
                    case "corrupt" -> {bytes[0]^=1;Files.write(file,bytes);}
                    case "extra" -> Files.write(dir.resolve("extra"),new byte[]{1});
                    case "symlink" -> {Path copy=temp.resolve("symlink-copy");Files.move(file,copy);Files.createSymbolicLink(file,copy);}
                    case "hardlink" -> Files.createLink(temp.resolve("hardlink-copy"),file);
                    case "packet" -> Files.write(dir.resolve("source.gscp"),new byte[]{1});
                    case "directory" -> {Files.move(dir,temp.resolve("old-dir"));Files.createDirectory(dir);}
                }
                assertThrows(Exception.class,()->prepare(store,3,0,22));
            }
            assertThrows(Exception.class,()->open(path,3,r,e->{}));assertEquals(0,r.usage().leases());
        }
    }
    @Test void invalidImagesDoNotWritePromiseAndRetainedModeCannotOmitImages() throws Exception {
        Path path=provision(temp.resolve("images"),3);var f=new V53CapsuleFixture(3,"REPLACE",0);var r=resources();
        try(var store=open(path,3,r,e->{})) {
            assertThrows(IllegalArgumentException.class,()->store.prepare(f.verify(),f.source.ballot(20),null));
            assertThrows(IllegalArgumentException.class,()->store.prepare(f.verify(),f.source.ballot(20),null,Map.of()));
            assertEquals(0,Files.size(path.resolve("grants.gsr")));assertEquals(1,r.usage().leases());
        }
    }
    @Test void acceptedTailPayloadAndRootAreRetainedExactly() throws Exception {
        Path path=provision(temp.resolve("tail"),3);var f=new V53SelectionFixture(3,"REPLACE",0);var selected=f.source("node-1",20,"original",3);
        try(var store=open(path,3,resources(),e->{})) {
            var basis=store.prepare(selected.capsule,new V53ContextFixture(3,"REPLACE").ballot(20),selected.accepted.digest(),f.capsule.source.images);
            var packet=MembershipSourcePacket.decode(Files.readAllBytes(folder(path,basis).resolve("source.gscp")));packet.bind(basis);
            assertArrayEquals(selected.accepted.bytes(),packet.objectBytes(selected.accepted.digest()));
        }
    }
    @Test void exclusiveOwnerAndFailedOpenReleaseResourcesWithoutMetadataDowngrade() throws Exception {
        Path path=provision(temp.resolve("lock"),3);var r=resources();
        try(var store=open(path,3,r,e->{})) {
            assertThrows(Exception.class,()->open(path,3,resources(),e->{}));
            assertThrows(Exception.class,()->MembershipGrantJournal.open(path,V53BallotAllocatorWorker.root(new V53ContextFixture(3,"REPLACE")),V53DeclarationsTest.node(1)));
            prepare(store,3,0,20);
        }
        assertEquals(0,r.usage().leases());try(var store=open(path,3,r,e->{})){assertTrue(store.originalBasis().isPresent());}
    }
}
