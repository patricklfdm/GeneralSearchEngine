package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CaptureJournalTest {
    @TempDir Path temp;
    final V53CaptureRecoveryTest helper=new V53CaptureRecoveryTest();
    MembershipGrantJournal open(Path p,V53CurrentGenerationFixture f,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception{return helper.open(p,f,r,cut);}
    void provision(Path p,V53CurrentGenerationFixture f)throws Exception{f.provision(p);helper.interrupt(p,f,"BASIS_PREFIX_WRITTEN");}
    @Test void exactPartialBasisRecoversWithoutRewritingOriginalSource()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7))for(boolean tail:List.of(false,true)) {
            Path p=temp.resolve(size+"-"+through+"-"+tail);var f=new V53CurrentGenerationFixture(size,through,tail);provision(p,f);var before=helper.files(p);byte[] prefix=Files.readAllBytes(p.resolve("grants.gsr"));var r=helper.resources();
            try(var store=open(p,f,r,e->{})) {
                assertEquals(f.accepted,store.originalBasis().orElseThrow().value().get("accepted"));byte[] after=Files.readAllBytes(p.resolve("grants.gsr"));assertArrayEquals(prefix,Arrays.copyOf(after,prefix.length));
                var files=helper.files(p);for(var item:before.entrySet())if(!Set.of("grants.gsr",MembershipCaptureFiles.FILE).contains(item.getKey()))assertEquals(item.getValue(),files.get(item.getKey()));
                assertArrayEquals(store.originalBasis().orElseThrow().bytes(),store.prepareCurrent(f.fixture.source.ballot(20)).bytes());
            }
            assertFalse(Files.exists(p.resolve(MembershipCaptureFiles.FILE)));assertEquals(0,r.usage().leases());
        }
    }
    @Test void repeatedJournalRecoveryDeathPreservesTheCompleteOriginalPrefix()throws Exception {
        for(String point:List.of("BASIS_RECOVERY_VALIDATED","BASIS_RECOVERY_PREFIX_WRITTEN","BASIS_RECOVERY_WRITTEN","BASIS_RECOVERY_FORCED","BASIS_RECOVERY_PARENT_FORCED","CAPTURE_INTENT_DELETED","CAPTURE_INTENT_CLEARED")) {
            Path p=temp.resolve(point);var f=new V53CurrentGenerationFixture(5,6,true);provision(p,f);byte[] prefix=Files.readAllBytes(p.resolve("grants.gsr"));var r=helper.resources();
            assertThrows(IOException.class,()->open(p,f,r,e->{if(e.equals(point))throw new IOException("cut");}));assertEquals(0,r.usage().leases());
            try(var store=open(p,f,r,e->{})){assertEquals(f.accepted,store.originalBasis().orElseThrow().value().get("accepted"));}
            assertArrayEquals(prefix,Arrays.copyOf(Files.readAllBytes(p.resolve("grants.gsr")),prefix.length));assertEquals(0,r.usage().leases());
        }
    }
    @Test void wrongPartialBytesMissingOriginalAndPartialIntentCannotAuthorizeRepair()throws Exception {
        for(String change:List.of("tail","kind","intent","packet","image","promise","unmarked")) {
            Path p=temp.resolve(change);var f=new V53CurrentGenerationFixture(3,1,true);provision(p,f);Path journal=p.resolve("grants.gsr"),intent=p.resolve(MembershipCaptureFiles.FILE),source;
            try(var paths=Files.list(p.resolve("sources"))){source=paths.findFirst().orElseThrow();}
            switch(change) {
                case "tail" -> {byte[] raw=Files.readAllBytes(journal);raw[raw.length-1]^=1;Files.write(journal,raw);}
                case "kind" -> {byte[] raw=Files.readAllBytes(journal);int offset=0;for(int i=0;i<2;i++)offset+=HEADER+java.nio.ByteBuffer.wrap(raw).getInt(offset+12);raw[offset+9]=3;Files.write(journal,raw);}
                case "intent" -> {byte[] raw=Files.readAllBytes(intent);Files.write(intent,Arrays.copyOf(raw,raw.length-1));}
                case "packet" -> {Path file=source.resolve("source.gscp");byte[] raw=Files.readAllBytes(file);Files.write(file,Arrays.copyOf(raw,raw.length-1));}
                case "image" -> {Path file;try(var paths=Files.list(source)){file=paths.filter(x->x.toString().endsWith(".image")).findFirst().orElseThrow();}Files.delete(file);}
                case "promise" -> {byte[] raw=Files.readAllBytes(journal);int length=HEADER+java.nio.ByteBuffer.wrap(raw).getInt(12);Files.write(journal,Arrays.copyOf(raw,length));}
                case "unmarked" -> Files.delete(intent);
            }
            var before=helper.files(p);var r=helper.resources();assertThrows(Exception.class,()->open(p,f,r,e->{}));assertEquals(before,helper.files(p));assertEquals(0,r.usage().leases());
        }
    }
    @Test void everyHeaderAndPayloadPrefixNeedsExactCompleteRecoveryAuthority()throws Exception {
        for(int length:List.of(1,8,9,16,47,48,49,100)) {
            Path p=temp.resolve("prefix-"+length);var f=new V53CurrentGenerationFixture(3,1,true);provision(p,f);byte[] raw=Files.readAllBytes(p.resolve("grants.gsr"));int offset=0;for(int i=0;i<2;i++)offset+=HEADER+java.nio.ByteBuffer.wrap(raw).getInt(offset+12);
            assertTrue(length<raw.length-offset);Files.write(p.resolve("grants.gsr"),Arrays.copyOf(raw,offset+length));var r=helper.resources();
            try(var store=open(p,f,r,e->{})){assertEquals(f.accepted,store.originalBasis().orElseThrow().value().get("accepted"));}assertEquals(0,r.usage().leases());
        }
    }
    @Test void olderOpenStillRefusesPartialJournalAndNeverRepairsIt()throws Exception {
        Path p=temp.resolve("legacy");var f=new V53CurrentGenerationFixture(3,0,false);provision(p,f);var before=helper.files(p);var r=helper.resources();
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openReclaiming(p,f.root(),V53DeclarationsTest.node(1),r,f::verify,e->{}));assertEquals(before,helper.files(p));assertEquals(0,r.usage().leases());
    }
}
