package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual original grants plus a read-only deferred inventory resolver. This does not
 * enable context PREPARE/rebind; source completion is still the existing journal path. */
class V53CaptureInventoryTest {
    @TempDir Path temp;
    record Seed(Path path,V53CurrentGenerationFixture fixture,Decoded backing,Decoded promise,
                Map<String,Decoded> promises,Map<String,Decoded> bases) {}
    Seed seed(String name,int size,String point)throws Exception {
        Path node=temp.resolve(name);var f=new V53CurrentGenerationFixture(size,1,true);f.provision(node);var r=resources();Decoded backing;
        try(var owner=MembershipGrantJournal.openCapturing(node,f.root(),V53DeclarationsTest.node(1),r,f::verify,e->{})) {
            backing=owner.prepareCurrent(f.fixture.source.ballot(20));
        }
        try(var owner=MembershipGrantJournal.openCapturing(node,f.root(),V53DeclarationsTest.node(1),r,f::verify,e->{if(e.equals(point))throw new IOException("inventory fixture cut");})) {
            assertThrows(IOException.class,()->owner.prepareCurrent(f.fixture.source.ballot(21)));
        }
        assertEquals(0,r.usage().leases());var promises=new TreeMap<String,Decoded>();var bases=new TreeMap<String,Decoded>();Decoded last=null;
        byte[] raw=Files.readAllBytes(node.resolve("grants.gsr"));int at=0;
        while(at<raw.length) {
            int end=at+HEADER+ByteBuffer.wrap(raw,at+12,4).getInt();String kind=Short.toUnsignedInt(ByteBuffer.wrap(raw,at+8,2).getShort())==3?"PROMISE":"BASIS";
            var d=decode(Arrays.copyOfRange(raw,at,end),"records",kind);at=end;
            if(d.kind().equals("PROMISE")){last=d;promises.put((String)d.value().get("basisId"),d);}
            else if(d.kind().equals("BASIS"))bases.put((String)d.value().get("basisId"),d);
        }
        return new Seed(node,f,backing,last,promises,bases);
    }
    static MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    static MembershipCaptureFiles.Plan plan(Seed seed,MembershipBasisSources.Original original)throws IOException {
        var body=new TreeMap<String,Object>(seed.promise.value());var packet=original.packet();body.put("voter","node-1");
        body.put("cut",packet.capsule().value().get("cut"));body.put("capsule",packet.capsule().digest());
        body.put("inventory",packet.inventoryDigest());body.put("accepted",seed.backing.value().get("accepted"));
        return new MembershipCaptureFiles.Plan(decode(Files.readAllBytes(seed.path.resolve("selector.gsr")),"records","SELECTOR"),
                seed.promise,decode(encode("records","BASIS",body),"records","BASIS"),packet,original.images());
    }
    static MembershipBasisSources open(Seed seed,MembershipResources r,MembershipBasisSources.CaptureResolver resolver)throws IOException {
        return new MembershipBasisSources(seed.path,r,e->{},seed.promises,seed.bases,null,seed.promise,resolver);
    }
    static Map<String,String> files(Path path)throws Exception {return V53BootstrapProgressResumeTest.safeFiles(path);}

    @Test void deferredLookupPrecedesPartialSourceValidationForAllSizesAndStages()throws Exception {
        Path evidence=Path.of("target/v53-capture-inventory/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(String point:List.of("CAPTURE_INTENT_CREATED","SOURCE_PACKET_PREFIX_WRITTEN","SOURCE_IMAGE_PREFIX_WRITTEN","BASIS_FORCED")) {
            String name=size+"-"+point;var seed=seed(name,size,point);Path raw=Files.createDirectory(evidence.resolve(name));
            V53JournalApplicationTest.copy(seed.path,raw.resolve("initial"));var before=files(seed.path);var r=resources();
            var lookup=new AtomicReference<MembershipBasisSources.Originals>();var expected=new AtomicReference<MembershipCaptureFiles.Plan>();
            try(var sources=open(seed,r,originals->{
                lookup.set(originals);var original=originals.read(seed.backing);var plan=plan(seed,original);expected.set(plan);
                assertEquals(seed.bases.size(),r.usage().counts().get(MembershipResources.Unit.SOURCE));
                // The callback exposes bytes, not ownership; independent reads do not alias images.
                original.images().values().iterator().next()[0]^=1;
                return plan(seed,originals.read(seed.backing));
            })) {
                assertEquals(before,files(seed.path));assertEquals(2,r.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertEquals(2,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                assertEquals("capture original lookup expired",assertThrows(IllegalArgumentException.class,()->lookup.get().read(seed.backing)).getMessage());
                assertArrayEquals(expected.get().packet().bytes(),sources.original(seed.backing).packet().bytes());
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(seed.path,raw.resolve("inventory"));
            // Existing exact journal recovery completes the interrupted operation; the
            // deferred constructor itself has not filled any prefix or returned a grant.
            var f=seed.fixture;try(var owner=MembershipGrantJournal.openCapturing(seed.path,f.root(),V53DeclarationsTest.node(1),r,f::verify,e->{})) {
                assertArrayEquals(expected.get().basis().bytes(),owner.originalBasis().orElseThrow().bytes());
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(seed.path,raw.resolve("recovered"));
            Files.write(raw.resolve("intent.gsr"),expected.get().bytes());rows.add(Map.of("case",name,"status","PASS","size",size,"cut",point));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-capture-inventory-v1","status","PASS","cases",rows,
                "contextCaptureEnabled",false,"runtimeEnabled",false),16384));System.out.println("v53CaptureInventoryEvidence="+evidence.toAbsolutePath());
    }
    @Test void incompleteAndSubstitutedBasisAreNotOriginalLookupAuthority()throws Exception {
        var seed=seed("lookup",3,"SOURCE_PACKET_PREFIX_WRITTEN");var before=files(seed.path);var r=resources();
        try(var sources=open(seed,r,originals->{
            var plan=plan(seed,originals.read(seed.backing));
            assertEquals("capture original lookup requires complete retained basis",assertThrows(IllegalArgumentException.class,()->originals.read(plan.basis())).getMessage());
            var altered=new TreeMap<>(seed.backing.value());altered.put("accepted",null);
            assertThrows(IllegalArgumentException.class,()->originals.read(decode(encode("records","BASIS",altered),"records","BASIS")));
            return plan;
        })) {assertEquals(before,files(seed.path));}assertEquals(0,r.usage().leases());
    }
    @Test void callbackFailureRevokesLookupAndReleasesAllReservationsWithoutRepair()throws Exception {
        var seed=seed("callback",3,"SOURCE_IMAGE_PREFIX_WRITTEN");var before=files(seed.path);var r=resources();var saved=new AtomicReference<MembershipBasisSources.Originals>();
        assertThrows(IOException.class,()->open(seed,r,originals->{saved.set(originals);originals.read(seed.backing);throw new IOException("resolver interruption");}));
        assertEquals("capture original lookup expired",assertThrows(IllegalArgumentException.class,()->saved.get().read(seed.backing)).getMessage());
        assertEquals(0,r.usage().leases());assertEquals(before,files(seed.path));
    }
    @Test void corruptedBackingAndUnboundSourcesRefuseBeforeResolverRuns()throws Exception {
        for(String kind:List.of("missing","corrupt","unbound")) {
            var seed=seed(kind,3,"SOURCE_PACKET_PREFIX_WRITTEN");Path packet=seed.path.resolve("sources").resolve((String)seed.backing.value().get("basisId")).resolve("source.gscp");
            if(kind.equals("missing"))Files.delete(packet);
            else if(kind.equals("corrupt")){byte[] bytes=Files.readAllBytes(packet);bytes[bytes.length-1]^=1;Files.write(packet,bytes);}
            else Files.createDirectory(seed.path.resolve("sources/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"));
            var before=files(seed.path);var r=resources();int[] calls={0};
            assertThrows(Exception.class,()->open(seed,r,originals->{calls[0]++;return plan(seed,originals.read(seed.backing));}));
            assertEquals(0,calls[0]);assertEquals(0,r.usage().leases());assertEquals(before,files(seed.path));
        }
    }
    @Test void changedPendingPrefixRefusesWithoutFillingOrLeakingReservations()throws Exception {
        var seed=seed("prefix",3,"SOURCE_PACKET_PREFIX_WRITTEN");Path p=seed.path.resolve("sources").resolve((String)seed.promise.value().get("basisId")).resolve("source.gscp");
        byte[] bytes=Files.readAllBytes(p);bytes[bytes.length-1]^=1;Files.write(p,bytes);var before=files(seed.path);var r=resources();int[] calls={0};
        var error=assertThrows(IllegalArgumentException.class,()->open(seed,r,originals->{calls[0]++;return plan(seed,originals.read(seed.backing));}));
        assertEquals("capture source prefix changed",error.getMessage());assertEquals(1,calls[0]);assertEquals(before,files(seed.path));assertEquals(0,r.usage().leases());
    }
    @Test void resolverCannotSubstitutePromiseCompletedBasisOrImages()throws Exception {
        for(String kind:List.of("promise","basis","image","null")) {
            var seed=seed("substituted-"+kind,3,"BASIS_FORCED");var before=files(seed.path);var r=resources();
            assertThrows(Exception.class,()->open(seed,r,originals->{
                var p=plan(seed,originals.read(seed.backing));if(kind.equals("null"))return null;
                if(kind.equals("promise"))return new MembershipCaptureFiles.Plan(p.selector(),seed.promises.get(seed.backing.value().get("basisId")),p.basis(),p.packet(),p.images());
                if(kind.equals("image"))return new MembershipCaptureFiles.Plan(p.selector(),p.promise(),p.basis(),p.packet(),Map.of());
                var value=new TreeMap<>(p.basis().value());value.put("accepted",null);
                return new MembershipCaptureFiles.Plan(p.selector(),p.promise(),decode(encode("records","BASIS",value),"records","BASIS"),p.packet(),p.images());
            }));assertEquals(0,r.usage().leases());assertEquals(before,files(seed.path));
        }
    }
    @Test void pendingReservationExhaustionPreservesCallerLeasesAndAllBytes()throws Exception {
        var seed=seed("capacity",3,"SOURCE_PACKET_PREFIX_WRITTEN");var before=files(seed.path);var r=resources();var held=new ArrayList<MembershipResources.Lease>();
        for(int i=0;i<6;i++)held.add(r.reserve(MembershipResources.Unit.APPLICATION,"caller-"+i,1));var usage=r.usage();
        assertThrows(IllegalArgumentException.class,()->open(seed,r,originals->plan(seed,originals.read(seed.backing))));
        assertEquals(usage,r.usage());assertEquals(before,files(seed.path));held.forEach(MembershipResources.Lease::close);assertEquals(0,r.usage().leases());
    }
    @Test void callbackCannotReplaceAnOriginalSourceBetweenLookupAndInventorySeal()throws Exception {
        var seed=seed("replaced",3,"SOURCE_PACKET_PREFIX_WRITTEN");var r=resources();
        var error=assertThrows(IllegalArgumentException.class,()->open(seed,r,originals->{
            var p=plan(seed,originals.read(seed.backing));Path path=seed.path.resolve("sources").resolve((String)seed.backing.value().get("basisId")).resolve("source.gscp");
            Path replacement=seed.path.resolve("replacement");Files.write(replacement,Files.readAllBytes(path));Files.move(replacement,path,StandardCopyOption.REPLACE_EXISTING);return p;
        }));assertEquals("retained source inode changed",error.getMessage());assertEquals(0,r.usage().leases());
    }
    @Test void capturePlanRetainsExplicitProtectedImagesInsteadOfCurrentImagesOnly()throws Exception {
        var seed=seed("images",3,"CAPTURE_INTENT_CREATED");var r=resources();var f=seed.fixture;
        try(var current=new MembershipCurrentGeneration(seed.path,f.root(),V53DeclarationsTest.node(1),r,seed.promises.values(),seed.bases.values(),List.of(),f::verify,e->{},true)) {
            var original=current.capsule.packet;var objects=new TreeMap<String,byte[]>();for(String h:original.objectNames())objects.put(h,original.objectBytes(h));
            var images=new TreeMap<>(current.images());byte[] extra={1,2,3,4,5};String digest=hash(extra);images.put(digest,extra);
            var lengths=new TreeMap<String,Long>();images.forEach((h,b)->lengths.put(h,(long)b.length));var value=new TreeMap<>(original.capsule().value());
            value.put("inventory",hash(MembershipSourcePacket.index(objects,lengths)));
            var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",value),"records","CAPSULE"),objects,lengths));
            var plan=MembershipCaptureFiles.plan(current,seed.promise,V53DeclarationsTest.node(1),packet,f.accepted,images);
            assertEquals(2,plan.images().size());extra[0]^=1;plan.packet().verifyImages(plan.images());
            assertThrows(UnsupportedOperationException.class,()->plan.images().clear());
            assertThrows(IllegalArgumentException.class,()->MembershipCaptureFiles.plan(current,seed.promise,V53DeclarationsTest.node(1),packet,f.accepted));
        }assertEquals(0,r.usage().leases());
    }
}
