package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real local install/ACCEPT/capture, with historical remote ownership supplied by fixtures. */
final class V53PendingAcceptFixture {
    final V53GenerationInstallFixture f;
    V53PendingAcceptFixture(int size,boolean carried){f=new V53GenerationInstallFixture(size,0,1,carried);}
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openVoting(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,cut);
    }
    void provision(Path path)throws Exception {
        f.provision(path);try(var store=f.open(path,resources(),e->{})){store.installCurrent(f.offers(store,20),f.bridges,f.images());}
        AdmissionPaths.write(path.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());AdmissionPaths.forceDirectory(path);
    }
    MembershipSourcePacket packet(Path path)throws Exception {
        var selector=decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR");
        return MembershipSourcePacket.decode(Files.readAllBytes(path.resolve("generations").resolve((String)selector.value().get("generation")).resolve("source.gscp")));
    }
    Decoded entry(Path path,byte[] payload)throws Exception {
        var selector=decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR");
        var selected=decode(Files.readAllBytes(path.resolve("generations").resolve((String)selector.value().get("generation")).resolve("selected.gsr")),"records","SELECTED");
        if(selected.value().get("nextEntry")!=null)return decode(packet(path).objectBytes((String)selected.value().get("nextEntry")),"records","ENTRY");
        var parent=object(selected.value().get("cut"));
        return decode(encode("records","ENTRY",Map.of("root",f.root().manifestDigest(),"authority",selected.value().get("view"),
                "index",number(parent.get("index"))+1,"previous",parent.get("entry"),"origin",selected.value().get("ballot"),"kind","DATA","payload",hash(payload))),"records","ENTRY");
    }
    byte[] payload(Path path)throws Exception {
        if(!f.tail)return "pending-original-payload".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        var packet=packet(path);var selector=decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR");
        var manifest=decode(Files.readAllBytes(path.resolve("generations").resolve((String)selector.value().get("generation")).resolve("generation.gsr")),"records","GENERATION");
        var accept=decode(packet.objectBytes((String)manifest.value().get("ownedTail")),"records","ACCEPT");
        var entry=decode(packet.objectBytes((String)accept.value().get("entry")),"records","ENTRY");return packet.objectBytes((String)entry.value().get("payload"));
    }
}
