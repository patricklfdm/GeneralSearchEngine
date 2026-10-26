package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.BUDGET;

class V53ScratchActivationTest {
    @TempDir Path temp;
    @Test void driverReopensActualKilledReceiveScopeThenInstallsANewSelection()throws Exception {
        var helper=new V53ActivationDriverTest();helper.temp=temp;
        try(var group=helper.local()) {
            Path raw=Files.createDirectory(temp.resolve("original")),exported=Files.createDirectory(raw.resolve("exported")),scope=temp.resolve("driver-restart");
            var own=group.owners.getFirst().beginActivation();var peer=group.owners.get(1);var original=peer.prepareCurrent(object(own.basis.value().get("ballot")));
            try(var source=peer.exportSource(original,BUDGET)) {
                for(var content:source.contents())Files.write(exported.resolve(content.digest()+".bin"),V53SourceExportTest.complete(source,content));
                V53ScratchProcessTest.save(raw.resolve("grant.json"),Map.of("root",source.context().root,"source",MembershipBootstrapSeed.identity(source.identity()),
                        "local",MembershipBootstrapSeed.identity(group.owners.getFirst().activationIdentity()),"promise",source.promise().digest(),"basis",original.digest(),"capsule",V53SourceReceiveTest.packetOffer(source).digest()));
            }
            var before=new ArrayList<Map<String,String>>();
            for(var target:group.group.fixture.request.targets())before.add(V53ReplayFilesTest.files(target.replicaDirectory()));
            new V53ScratchProcessTest().child(raw,scope,MembershipScratch.Role.OUTGOING,"receive","PARTIAL_PACKET","kill",raw.resolve("crash"));
            try(var driver=new MembershipActivationDriver(group.owners.getFirst(),group.endpoints.getFirst(),group.budgets.getFirst(),group.bound,group.override.get(),
                    V53ActivationEndpointTest.verifier(),List.of(),List.of(),scope,group.clock,BUDGET,2)) {
                assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scope,8));
                for(int n=0;n<3;n++)assertEquals(before.get(n),V53ReplayFilesTest.files(group.group.fixture.request.targets().get(n).replicaDirectory()));
                var selected=driver.run();assertEquals("SELECTED",selected.kind());assertArrayEquals(selected.bytes(),driver.selection().bytes());
            }
            assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scope,8));
        }
    }
}
