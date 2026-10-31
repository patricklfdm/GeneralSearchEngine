package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Malformed complete generations remain conditional rejection fixtures.
 * The real installer now preserves all three original covered-tail objects. */
class V53RetirementTailTest {
    @TempDir Path temp;
    @ParameterizedTest @ValueSource(ints={0,1,2})
    void provenHigherCutCannotAuthorizeLosingAnyOriginalAboveFloorObject(int missing)throws Exception {
        var initial=new V53CurrentGenerationFixture(3,0,true);var oldPath=temp.resolve("old");initial.provision(oldPath);
        var budget=new MembershipResources(512*MembershipResources.MIB);MembershipFloor.Copy old;
        try(var owner=MembershipGrantJournal.openGenerations(oldPath,initial.root(),V53DeclarationsTest.node(1),budget,initial::verify,e->{})) {
            old=owner.floorCopyCurrent();
        }
        var peer=new V53FloorTest().copy(temp.resolve("peer"),3,0,2);var copies=List.of(old,peer);
        var retained=new MembershipFloorFiles.Retained(MembershipFloor.create(initial.root(),old,copies),copies);
        var accept=decode(old.fileBytes("owned-tail.gsr"),"records","ACCEPT");
        var entry=decode(old.capsule.packet.objectBytes((String)accept.value().get("entry")),"records","ENTRY");
        var originals=List.of(accept.digest(),entry.digest(),(String)entry.value().get("payload"));
        var f=new V53CurrentGenerationFixture(3,1,false);var path=temp.resolve("higher");f.provision(path);
        var objects=new TreeMap<String,byte[]>();
        for(String h:f.admitted.packet.objectNames())objects.put(h,f.admitted.packet.objectBytes(h));
        for(String h:originals)objects.put(h,old.capsule.packet.objectBytes(h));objects.remove(originals.get(missing));
        var cap=new TreeMap<>(f.admitted.packet.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,f.admitted.packet.images())));
        byte[] packet=MembershipSourcePacket.encode(decode(encode("records","CAPSULE",cap),"records","CAPSULE"),objects,f.admitted.packet.images());
        var directory=path.resolve("generations/b");Files.move(path.resolve("generations/a"),directory);Files.write(directory.resolve("source.gscp"),packet);
        var fields=new TreeMap<>(decode(Files.readAllBytes(directory.resolve("generation.gsr")),"records","GENERATION").value());
        fields.put("generation","b");fields.put("capsule",MembershipSourcePacket.decode(packet).capsule().digest());
        var files=new ArrayList<Map<String,Object>>();
        for(Object row:list(fields.get("files"))) {
            var value=new TreeMap<>(object(row));byte[] bytes=Files.readAllBytes(directory.resolve((String)value.get("path")));
            value.put("size",(long)bytes.length);value.put("sha256",hash(bytes));files.add(value);
        }
        fields.put("files",files);var manifest=decode(encode("records","GENERATION",fields),"records","GENERATION");
        Files.write(directory.resolve("generation.gsr"),manifest.bytes());
        Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",f.root().manifestDigest(),"node","node-1","generation","b","digest",manifest.digest())));
        var promise=decode(Files.readAllBytes(directory.resolve("promise.gsr")),"records","PROMISE");
        var before=V53ReplayFilesTest.files(oldPath);
        try(var current=new MembershipCurrentGeneration(path,f.root(),V53DeclarationsTest.node(1),budget,List.of(promise),List.of(),f::verify,e->{})) {
            assertEquals(1L,current.capsule.context.cut.get("index"));
            assertEquals("missing packet object",assertThrows(IllegalArgumentException.class,()->
                    MembershipRetirementPlan.create(f.root(),V53DeclarationsTest.node(1),current,retained,old)).getMessage());
        }
        assertEquals(before,V53ReplayFilesTest.files(oldPath));assertEquals(0,budget.usage().leases());
    }
}
