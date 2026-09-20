package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51AutomaticWireTest {
    @TempDir Path root;
    @Test void frozenNineteenMessagesHaveExactProductionBytes() throws Exception {
        try(var in=getClass().getResourceAsStream("/replication/v51/format-fixtures.json")) {
            var fixtures=object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(in.readAllBytes(),StandardCharsets.UTF_8)));
            var manifest=decode(unbase(object(fixtures.get("storage")).get("MANIFEST")),"MANIFEST");
            for(var row:object(fixtures.get("wire")).entrySet()) {
                byte[] raw=unbase(row.getValue());var message=AutomaticWire.decode(raw,manifest,IMAGE);
                assertArrayEquals(raw,AutomaticWire.encode(message,manifest,IMAGE),row.getKey());
            }
        }
    }
    @Test void selectedPairIsBoundAndOldVersionsAndChangedDescriptorsReject() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);var installation=group.requests(AutomaticProtocol.Kind.INSTALL).getFirst();
            @SuppressWarnings("unchecked") var bases=(List<AutomaticRecovery.Basis>)installation.payload();
            var manifest=decode(group.manifest,"MANIFEST");var selected=AutomaticRecovery.select(manifest,AutomaticRecovery.ballotOf(installation.ballot()),bases);
            var body=Map.<String,Object>of("selected",b64(selected.record().bytes()),"bases",bases.stream().map(b->b64(b.record().bytes())).toList(),"response",false);
            var message=AutomaticWire.message(manifest,installation.ballot(),"node-1","node-2","SELECTED_OFFER",UUID.randomUUID(),1,body);
            byte[] bytes=AutomaticWire.encode(message,manifest,128*1024);assertEquals("SELECTED_OFFER",AutomaticWire.decode(bytes,manifest,128*1024).get("type"));
            var swapped=new LinkedHashMap<>(body);swapped.put("bases",List.of(b64(bases.getLast().record().bytes()),b64(bases.getFirst().record().bytes())));
            message.put("payload",swapped);assertThrows(AutomaticReplicationException.class,()->AutomaticWire.encode(message,manifest,128*1024));
            ByteBuffer.wrap(bytes).putShort(6,(short)1);assertThrows(AutomaticReplicationException.class,()->AutomaticWire.decode(bytes,manifest,128*1024));
        }
    }
    @Test void independentExtensionBytesAndDeclarativeSchemasAgree() throws Exception {
        Map<String,Object> original,extension,fixtures;
        try(var in=getClass().getResourceAsStream("/replication/v51/format-catalog.json")) {original=object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(in.readAllBytes(),StandardCharsets.UTF_8)));}
        try(var in=getClass().getResourceAsStream("/replication/v51/runtime-wire-extension.json")) {extension=object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(in.readAllBytes(),StandardCharsets.UTF_8)));}
        object(original.get("wire")).putAll(object(extension.get("wire")));
        var types=object(object(object(original.get("envelope")).get("object")).get("type"));
        list(types.get("enum")).addAll(object(extension.get("wire")).keySet());
        assertArrayEquals(canonical(Map.of("wire",original.get("wire"),"envelope",original.get("envelope"))),canonical(AutomaticWire.CATALOG));
        try(var in=getClass().getResourceAsStream("/replication/v51/runtime-wire-fixtures.json")) {fixtures=object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(in.readAllBytes(),StandardCharsets.UTF_8)));}
        var manifest=decode(unbase(V51StorageFixture.samples().get("MANIFEST")),"MANIFEST");
        for(String kind:List.of("request","response")) {byte[] bytes=unbase(fixtures.get(kind));assertArrayEquals(bytes,AutomaticWire.encode(AutomaticWire.decode(bytes,manifest,IMAGE),manifest,IMAGE));}
    }
}
