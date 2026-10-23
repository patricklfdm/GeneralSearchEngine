package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapLayoutTest {
    @TempDir Path temp;
    MembershipBootstrapPlanData fixture(String name,int size,boolean backup)throws Exception {
        var helper=new V53BootstrapPlanTest();helper.temp=temp;return helper.fixture(name,size,backup).plan();
    }
    @Test void everyMetadataByteMatchesThePreRefactorFrozenOriginalInventories()throws Exception {
        Map<String,Object> fixture;try(var input=getClass().getResourceAsStream("/v53-bootstrap-layout.json")){assertNotNull(input);fixture=object(parse(input.readAllBytes(),256*1024));}
        assertEquals("gse-v53-bootstrap-layout-pinned-v1",fixture.get("schema"));assertEquals(6,list(fixture.get("cases")).size());int voters=0;
        for(var v:list(fixture.get("cases"))) {
            var row=object(v);var root=decode(MembershipBootstrapPlanData.unbase(row.get("root"),16384),"records","ROOT");var genesis=decode(MembershipBootstrapPlanData.unbase(row.get("genesis"),65536),"records","GENESIS");
            var image=object(row.get("application"));var layout=new MembershipBootstrapLayout(root,genesis,number(image.get("bytes")));assertEquals(image.get("sha256"),layout.application);
            for(var t:list(row.get("targets"))) {
                var target=object(t);var local=MembershipContext.identity(object(target.get("identity")));var wanted=list(target.get("files")).stream().map(MembershipFormat::object).toList();
                assertEquals(wanted,layout.inventory(local));var actual=new TreeMap<String,Map<String,Object>>();layout.metadata(local).forEach((name,bytes)->actual.put(name,Map.of("path",name,"bytes",(long)bytes.length,"sha256",hash(bytes))));
                assertFalse(actual.containsKey(layout.imagePath()));assertEquals(wanted.stream().filter(m->!m.get("path").equals(layout.imagePath())).toList(),new ArrayList<>(actual.values()));voters++;
            }
        }
        assertEquals(24,voters);
    }
    @Test void metadataPlanAgreesWithActualSeedAndRemainsIndependentOfCallerMutations()throws Exception {
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var plan=fixture("metadata-"+size+"-"+backup,size,backup);var meta=new MembershipBootstrapPlanMetadata(plan.bytes());
            assertEquals(plan.summary(),meta.summary());assertEquals(plan.digest(),meta.digest());assertEquals(plan.maximumOperation,meta.maximumOperation);
            assertEquals(plan.seed.root,meta.layout.identity);assertArrayEquals(plan.seed.capsule.packet.bytes(),meta.layout.packet.bytes());
            byte[] mutated=meta.bytes();mutated[0]^=1;assertArrayEquals(plan.bytes(),meta.bytes());
            var descriptor=meta.descriptor();assertThrows(UnsupportedOperationException.class,()->descriptor.put("source","changed"));assertEquals(plan.seed.descriptor(),meta.descriptor());
            for(var local:meta.layout.identities) {
                var bytes=meta.layout.metadata(local);byte[] original=bytes.get("root.gsr").clone();bytes.get("root.gsr")[0]^=1;
                assertArrayEquals(original,meta.layout.metadata(local).get("root.gsr"));
                var actual=plan.seed.payloads(local);assertEquals(actual.size()-1,meta.layout.metadata(local).size());
            }
        }
    }
    @Test void metadataDoesNotSubstituteForAnActualImageOrTypedAdmission()throws Exception {
        var plan=fixture("image",3,true);var meta=new MembershipBootstrapPlanMetadata(plan.bytes());byte[] image=plan.seed.application();image[image.length-1]^=1;
        assertEquals(plan.summary(),meta.summary());assertThrows(IllegalArgumentException.class,()->MembershipBootstrapPlanData.decode(plan.bytes(),image));
        var maximum=new MembershipBootstrapLayout(plan.seed.rootRecord,plan.seed.genesis,MembershipApplicationImage.MAXIMUM);
        assertEquals(MembershipApplicationImage.MAXIMUM,maximum.imageBytes);assertTrue(maximum.packet.bytes().length<65536);
        assertThrows(IllegalArgumentException.class,()->MembershipCapsule.verify(plan.seed.rootRecord,maximum.packet,plan.seed.images(),Set.of()));
    }
    @Test void malformedHeadersDescriptorsInventoriesAndBoundsCannotBecomeMetadataAuthority()throws Exception {
        var plan=fixture("negative",3,true);
        for(String kind:List.of("header","checksum","image-zero","image-large","image-digest","codec","schema","path","parent","oversized-binding","blank-filesystem","target","source-budget","operation-budget")) {
            byte[] raw=plan.bytes();var body=V53BootstrapPlanTest.body(raw);var descriptor=object(body.get("descriptor"));
            switch(kind) {
                case "header"->raw[0]^=1;case "checksum"->raw[16]^=1;
                case "image-zero"->object(body.get("application")).put("bytes",0L);
                case "image-large"->object(body.get("application")).put("bytes",(long)MembershipApplicationImage.MAXIMUM+1);
                case "image-digest"->object(body.get("application")).put("sha256","0".repeat(64));
                case "codec"->object(descriptor.get("core")).put("codecVersion",2L);
                case "schema"->object(descriptor.get("core")).put("schemaIdentity","changed");
                case "path"->object(list(descriptor.get("paths")).getFirst()).put("path","/a/../b");
                case "parent"->object(list(descriptor.get("paths")).getFirst()).put("parentRealPath","/wrong-parent");
                case "oversized-binding"->object(list(descriptor.get("paths")).getFirst()).put("parentFileKey","汉".repeat(3000));
                case "blank-filesystem"->object(list(descriptor.get("paths")).getFirst()).put("fileStoreName"," ");
                case "target"->object(list(object(list(body.get("targets")).getFirst()).get("files")).getFirst()).put("bytes",999L);
                case "source-budget"->body.put("maximumSource",1L);case "operation-budget"->body.put("maximumOperation",1L);default->throw new AssertionError();
            }
            byte[] input=kind.equals("header")||kind.equals("checksum")?raw:MembershipBootstrapPlanData.encode(body);
            assertThrows(RuntimeException.class,()->new MembershipBootstrapPlanMetadata(input),kind);
        }
    }
    @Test void layoutRejectsForeignOriginalsIdentitiesAndInvalidDeclaredImageSizes()throws Exception {
        var plan=fixture("root",3,false);var foreign=fixture("foreign",5,true);
        assertThrows(IllegalArgumentException.class,()->new MembershipBootstrapLayout(plan.seed.rootRecord,foreign.seed.genesis,1024));
        for(long size:List.of(-1L,0L,(long)MembershipApplicationImage.MAXIMUM+1,Long.MAX_VALUE))assertThrows(IllegalArgumentException.class,()->new MembershipBootstrapLayout(plan.seed.rootRecord,plan.seed.genesis,size));
        assertThrows(IllegalArgumentException.class,()->plan.seed.layout.metadata(V53DeclarationsTest.node(4)));
        var root=new TreeMap<>(plan.seed.rootRecord.value());root.put("limits","0".repeat(64));var wrong=decode(encode("records","ROOT",root),"records","ROOT");
        assertThrows(IllegalArgumentException.class,()->new MembershipBootstrapLayout(wrong,plan.seed.genesis,plan.seed.application().length));
    }
}
