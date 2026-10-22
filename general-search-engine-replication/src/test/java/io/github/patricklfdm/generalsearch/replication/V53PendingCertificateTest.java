package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

class V53PendingCertificateTest {
    @TempDir Path temp;
    static final List<String> CUTS=V53PendingAcceptTest.CUTS.stream().map(s->s.replace("ACCEPT","CERTIFICATE")).toList();
    final V53PendingCertificateFixture f=new V53PendingCertificateFixture(3,0);
    Map<String,String> files(Path path)throws Exception{return new V53CaptureRecoveryTest().files(path);}
    @Test void actualPhasedMajoritiesPersistCaptureAndReopenWithoutPublishingTheApplication()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7)) {
            var fixture=new V53PendingCertificateFixture(size,through);Path root=temp.resolve(size+"-"+through);var cohort=fixture.setup(root);var r=fixture.f.resources();
            Path path=fixture.f.node(root,1);var before=files(path);
            try(var store=fixture.f.open(root,1,r,e->{})) {
                assertArrayEquals(cohort.certificate().bytes(),store.certifyCurrent(cohort.certificate(),cohort.owned()).bytes());
                var raw=Files.readAllBytes(path.resolve(MembershipPendingAccept.FILE));
                store.certifyCurrent(cohort.certificate(),Set.of());store.proveCurrent(cohort.proof(),Set.of());store.acceptCurrent(fixture.f.entry(),fixture.f.payload());
                assertArrayEquals(raw,Files.readAllBytes(path.resolve(MembershipPendingAccept.FILE)));
                assertEquals(cohort.certificate().digest(),store.currentCertificate().orElseThrow().digest());
            }
            var after=files(path);for(var row:before.entrySet())if(!row.getKey().equals(MembershipPendingAccept.FILE))assertEquals(row.getValue(),after.get(row.getKey()));
            assertEquals(0,r.usage().leases());
            try(var store=fixture.f.open(root,1,r,e->{})) {
                assertEquals(cohort.certificate().digest(),store.currentCertificate().orElseThrow().digest());
                var basis=store.prepareCurrent(fixture.f.f.fixture.source.ballot(21));assertEquals(fixture.f.f.admitted.context.cut,basis.value().get("cut"));
                assertArrayEquals(cohort.certificate().bytes(),store.originalSource().capsule.packet.objectBytes(cohort.certificate().digest()));
                assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(cohort.certificate(),cohort.owned()));
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void requiresBothActualPhasesAndExactParentAndCannotReplaceWitnessRepresentation()throws Exception {
        Path root=temp.resolve("invalid");var c=f.setup(root);
        try(var store=f.f.open(root,1,f.f.resources(),e->{})) {
            var before=files(root);
            for(var incomplete:List.of(Set.<Owned>of(),c.accepts(),c.proofs()))assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(c.certificate(),incomplete));
            for(String field:List.of("record","parent","storage")) {
                var wrong=new HashSet<Owned>();for(var a:c.owned())wrong.add(new Owned(a.voter(),field.equals("storage")?new UUID(0,99):a.storage(),field.equals("record")?"00".repeat(32):a.record(),field.equals("parent")?"00".repeat(32):a.parent()));
                assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(c.certificate(),wrong));
            }
            assertEquals(before,files(root));store.certifyCurrent(c.certificate(),c.owned());before=files(root);
            var two=c.proofs().stream().filter(o->!o.voter().equals("node-3")).collect(java.util.stream.Collectors.toSet());
            assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(f.certificate(c.proof(),two),c.owned()));assertEquals(before,files(root));
        }
    }
    @Test void mismatchedPhasedFramesAndCertificateWithoutLocalProofFailBeforeWriting()throws Exception {
        Path root=temp.resolve("mismatch");var c=f.setup(root);
        try(var store=f.f.open(root,1,f.f.resources(),e->{})) {
            for(String field:List.of("root","authority","ballot","index","entry","accepts","proofs")) {
                var value=new TreeMap<>(c.certificate().value());value.put(field,switch(field){case "ballot"->f.f.f.fixture.source.ballot(21);case "index"->2L;case "accepts","proofs"->{var rows=new ArrayList<Object>(list(value.get(field)));var row=new TreeMap<>(object(rows.getFirst()));row.put("receipt","00".repeat(32));rows.set(0,row);yield rows;}default->"00".repeat(32);});
                var wrong=decode(encode("records","CERTIFICATE",value),"records","CERTIFICATE");var before=files(root);
                assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(wrong,c.owned()));assertEquals(before,files(root));
            }
        }
        Path other=temp.resolve("unproven");f.f.provision(other);f.f.install(other);f.f.accept(other);
        try(var store=f.f.open(other,1,f.f.resources(),e->{})){assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(c.certificate(),c.owned()));}
    }
    @Test void partialCertificateCannotBeOverwrittenByAcceptOrProofAndResumesOnlyOriginal()throws Exception {
        for(String point:CUTS) {
            Path root=temp.resolve(point);var c=f.setup(root);var r=f.f.resources();
            try(var store=f.f.open(root,1,r,e->{if(e.equals(point))throw new IOException("cut");})){assertThrows(IOException.class,()->store.certifyCurrent(c.certificate(),c.owned()));}
            assertEquals(0,r.usage().leases());
            try(var store=f.f.open(root,1,r,e->{})) {
                if(Files.exists(f.f.node(root,1).resolve(MembershipPendingAccept.NEXT))) {
                    var before=files(root);assertThrows(IllegalArgumentException.class,store::currentCertificate);
                    assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(f.f.entry(),f.f.payload()));
                    assertThrows(IllegalArgumentException.class,()->store.proveCurrent(c.proof(),c.accepts()));
                    assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(c.certificate(),Set.of()));assertEquals(before,files(root));
                }
                assertArrayEquals(c.certificate().bytes(),store.certifyCurrent(c.certificate(),c.owned()).bytes());
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void repeatedRecoveryRetainsOriginalCertificateAndDoesNotInventPublication()throws Exception {
        for(String point:List.of("CERTIFICATE_RECOVERY_VALIDATED","CERTIFICATE_PREFIX_WRITTEN","CERTIFICATE_CANDIDATE_FORCED","CERTIFICATE_RENAMED","CERTIFICATE_PARENT_FORCED","CERTIFICATE_ACTIVE_FORCED","CERTIFICATE_ACTIVE_PARENT_FORCED")) {
            Path root=temp.resolve(point);var c=f.setup(root);var r=f.f.resources();
            try(var store=f.f.open(root,1,r,e->{if(e.equals("CERTIFICATE_CANDIDATE_WRITTEN"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.certifyCurrent(c.certificate(),c.owned()));}
            assertThrows(IOException.class,()->f.f.open(root,1,r,e->{if(e.equals(point))throw new IOException("again");}));assertEquals(0,r.usage().leases());
            try(var store=f.f.open(root,1,r,e->{})){assertEquals(c.certificate().digest(),store.currentCertificate().orElseThrow().digest());assertEquals(f.f.f.admitted.context.cut,store.floorCopyCurrent().capsule.context.cut);}
        }
    }
    @Test void higherObservationAndSameByteReplacementPreventOldSuccess()throws Exception {
        for(String point:CUTS) {
            Path root=temp.resolve(point);var c=f.setup(root);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.f.open(root,1,f.f.resources(),e->{if(e.equals(point))ref[0].observeCurrent(f.f.f.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(c.certificate(),c.owned()));
            }
        }
        for(String point:List.of("CERTIFICATE_CANDIDATE_FORCED","CERTIFICATE_RENAMED","CERTIFICATE_BEFORE_RETURN")) {
            Path root=temp.resolve("inode-"+point);var c=f.setup(root);
            try(var store=f.f.open(root,1,f.f.resources(),e->{if(e.equals(point)) {
                Path file=f.f.node(root,1).resolve(point.equals("CERTIFICATE_CANDIDATE_FORCED")?MembershipPendingAccept.NEXT:MembershipPendingAccept.FILE);
                Path copy=file.resolveSibling("copy");Files.write(copy,Files.readAllBytes(file));Files.move(copy,file,StandardCopyOption.REPLACE_EXISTING);
            }})){assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(c.certificate(),c.owned()));}
        }
    }
    @Test void completeCertificateCandidateRequiresActualActiveProofAndCorruptionCannotReopen()throws Exception {
        for(boolean missingProof:List.of(false,true)) {
            Path root=temp.resolve("corrupt-"+missingProof);var c=f.setup(root);Path path=f.f.node(root,1);var r=f.f.resources();
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(path.resolve(MembershipPendingAccept.FILE)));
            if(missingProof) {
                Files.write(path.resolve(MembershipPendingAccept.NEXT),vote.withCertificate(c.certificate()).bytes());
                Files.write(path.resolve(MembershipPendingAccept.FILE),vote.withProof(null).bytes());
            }else {
                try(var store=f.f.open(root,1,r,e->{})){store.certifyCurrent(c.certificate(),c.owned());}
                byte[] raw=Files.readAllBytes(path.resolve(MembershipPendingAccept.FILE));raw[raw.length-1]^=1;Files.write(path.resolve(MembershipPendingAccept.FILE),raw);
            }
            var before=files(root);assertThrows(IllegalArgumentException.class,()->f.f.open(root,1,r,e->{}));assertEquals(before,files(root));assertEquals(0,r.usage().leases());
        }
    }
    @Test void unwrittenWitnessSuffixHasNoAuthorityButEveryRetainedPrefixAndForcedRecordIsImmutable()throws Exception {
        for(String point:List.of("CERTIFICATE_CANDIDATE_CREATED","CERTIFICATE_PREFIX_WRITTEN")) {
            Path root=temp.resolve("suffix-"+point);var c=f.setup(root);var a=c.proofs().stream().filter(v->!v.voter().equals("node-3")).collect(java.util.stream.Collectors.toSet());
            var b=c.proofs().stream().filter(v->!v.voter().equals("node-2")).collect(java.util.stream.Collectors.toSet());
            var first=f.certificate(c.proof(),a);var alternative=f.certificate(c.proof(),b);
            try(var store=f.f.open(root,1,f.f.resources(),e->{if(e.equals(point))throw new IOException("cut");})){assertThrows(IOException.class,()->store.certifyCurrent(first,c.owned()));}
            Path candidate=f.f.node(root,1).resolve(MembershipPendingAccept.NEXT);byte[] prefix=Files.readAllBytes(candidate);
            var prior=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(root,1).resolve(MembershipPendingAccept.FILE)));
            assertArrayEquals(prefix,Arrays.copyOf(prior.withCertificate(alternative).bytes(),prefix.length));
            try(var store=f.f.open(root,1,f.f.resources(),e->{})) {
                assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(alternative,Set.of()));
                assertArrayEquals(prefix,Files.readAllBytes(candidate));
                assertEquals(alternative.digest(),store.certifyCurrent(alternative,c.owned()).digest());
                assertThrows(IllegalArgumentException.class,()->store.certifyCurrent(first,c.owned()));
            }
        }
    }

}
