package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapCommitMetadataTest {
    @TempDir Path temp;
    static Map<String,Object> fixture()throws Exception {
        try(var input=V53BootstrapCommitMetadataTest.class.getResourceAsStream("/v53-bootstrap-commit-metadata.json")) {
            assertNotNull(input);return object(parse(input.readAllBytes(),256*1024));
        }
    }
    static Map<String,Object> info(byte[] bytes){return Map.of("bytes",(long)bytes.length,"sha256",hash(bytes));}
    static MembershipBootstrapPlanMetadata metadata(Map<String,Object> row){return new MembershipBootstrapPlanMetadata(MembershipBootstrapPlanData.unbase(row.get("plan"),2*1024*1024));}
    @Test void decisionsReceiptsAndAllLocalSealsMatchOriginalAcceptedBytes()throws Exception {
        var f=fixture();assertEquals("gse-v53-bootstrap-original-transaction-v1",f.get("schema"));assertEquals(6,list(f.get("cases")).size());int targets=0;
        for(var v:list(f.get("cases"))) {
            var row=object(v);var plan=metadata(row);var data=new MembershipBootstrapCommitMetadata(plan);
            assertEquals(row.get("planSha256"),plan.digest());assertEquals(row.get("completionBytes"),data.completionBytes);
            assertEquals(row.get("receipt"),info(data.receipt()));assertEquals(plan.layout.identities,data.identities);
            for(int i=0;i<data.targets.size();i++) {
                assertEquals(list(row.get("preparations")).get(i),info(data.preparation(i)));
                assertEquals(list(row.get("seals")).get(i),info(data.seal(i)));targets++;
            }
            var journal=new java.io.ByteArrayOutputStream();
            for(int phase=1;phase<=4;phase++) {
                assertEquals(list(row.get("decisions")).get(phase-1),info(data.row(phase)));journal.writeBytes(data.row(phase));assertArrayEquals(journal.toByteArray(),data.journal(phase));
            }
        }
        assertEquals(24,targets);
    }
    @Test void fullActualImageAndMetadataOnlyDerivationHaveIdenticalResultsAndAccounting()throws Exception {
        var helper=new V53BootstrapPlanTest();helper.temp=temp;
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var plan=helper.fixture("full-"+size+"-"+backup,size,backup).plan();var full=new MembershipBootstrapCommitData(plan);
            var only=new MembershipBootstrapCommitMetadata(new MembershipBootstrapPlanMetadata(plan.bytes()));
            assertEquals(full.result(),only.result());assertEquals(full.completionBytes,only.completionBytes);assertEquals(full.targets,only.targets);
            long bytes=2L*plan.bytes().length+plan.seed.application().length+2L*full.receipt().length+full.journal(4).length;
            for(int i=0;i<size;i++) {
                assertArrayEquals(full.preparation(i),only.preparation(i));assertArrayEquals(full.seal(i),only.seal(i));
                bytes+=full.preparation(i).length+2L*full.seal(i).length;
                for(var raw:full.payload(i).values())bytes+=raw.length;
            }
            assertEquals(bytes,only.completionBytes);
        }
    }
    @Test void metadataInspectionDoesNotReadOrCreateAnyOriginalPath()throws Exception {
        var helper=new V53BootstrapPlanTest();helper.temp=temp;var plan=helper.fixture("absent",3,true).plan();Path original=temp.resolve("absent");
        Path retained=temp.resolve("retained");Files.move(original,retained);var before=V53ReplayFilesTest.files(retained);
        var meta=new MembershipBootstrapPlanMetadata(plan.bytes());var data=new MembershipBootstrapCommitMetadata(meta);
        assertEquals(plan.digest(),data.result().planDigest());assertFalse(Files.exists(original));assertEquals(before,V53ReplayFilesTest.files(retained));
        assertTrue(data.targets.stream().noneMatch(Files::exists));assertFalse(Files.exists(meta.operation()));
    }
    @Test void maximumDeclaredImagesAndExactCompletionBoundaryNeedNoImageAllocation()throws Exception {
        var original=metadata(object(list(fixture().get("cases")).getLast()));var body=V53BootstrapPlanTest.body(original.bytes());
        var layout=new MembershipBootstrapLayout(original.layout.root,original.layout.genesis,MembershipApplicationImage.MAXIMUM);
        object(body.get("application")).put("bytes",(long)MembershipApplicationImage.MAXIMUM);
        var targets=new ArrayList<Map<String,Object>>();for(var local:layout.identities)targets.add(Map.of("identity",MembershipBootstrapSeed.identity(local),"directories",MembershipBootstrapSeed.directories().stream().sorted().toList(),"files",layout.inventory(local)));
        body.put("targets",targets);body.put("maximumOperation",Long.MAX_VALUE);var data=new MembershipBootstrapCommitMetadata(new MembershipBootstrapPlanMetadata(MembershipBootstrapPlanData.encode(body)));
        assertTrue(data.completionBytes>6L*MembershipApplicationImage.MAXIMUM);assertEquals(5,data.targets.size());
        // The exact original budget is part of the plan hash/length. Reach the length-stable boundary first.
        for(int i=0;i<3;i++) {body.put("maximumOperation",data.completionBytes);data=new MembershipBootstrapCommitMetadata(new MembershipBootstrapPlanMetadata(MembershipBootstrapPlanData.encode(body)));}
        assertEquals(number(body.get("maximumOperation")),data.completionBytes);
        body.put("maximumOperation",data.completionBytes-1);var below=new MembershipBootstrapPlanMetadata(MembershipBootstrapPlanData.encode(body));
        assertThrows(IllegalArgumentException.class,()->new MembershipBootstrapCommitMetadata(below));
    }
    @Test void returnedMetadataCannotMutateTheOriginalTransaction()throws Exception {
        var data=new MembershipBootstrapCommitMetadata(metadata(object(list(fixture().get("cases")).getFirst())));
        byte[] receipt=data.receipt(),prep=data.preparation(0),seal=data.seal(0),row=data.row(4),journal=data.journal(4);
        var expected=List.of(hash(receipt),hash(prep),hash(seal),hash(row),hash(journal));for(byte[] bytes:List.of(receipt,prep,seal,row,journal))bytes[0]^=1;
        assertEquals(expected,List.of(hash(data.receipt()),hash(data.preparation(0)),hash(data.seal(0)),hash(data.row(4)),hash(data.journal(4))));
        assertThrows(UnsupportedOperationException.class,()->data.targets.clear());assertThrows(UnsupportedOperationException.class,()->data.identities.clear());
    }
}
