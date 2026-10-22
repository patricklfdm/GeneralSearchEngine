package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** All new grants, selected installs and phased votes come from actual separate local owners.
 * The initial applied history/application image remains an explicit historical fixture. */
final class V53PendingProofFixture {
    final V53CurrentGenerationFixture f;
    final List<Integer> nodes;
    V53PendingProofFixture(int size,int through) {
        f=new V53CurrentGenerationFixture(size,through,false);
        nodes=f.admitted.context.voters().stream().map(n->Integer.parseInt(n.substring(5))).sorted().toList();
    }
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    Path node(Path root,int node){return root.resolve("node-"+node);}
    MembershipGrantJournal open(Path root,int node,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openVoting(node(root,node),f.root(),V53DeclarationsTest.node(node),r,f::verify,cut);
    }
    void provision(Path root)throws Exception {
        Files.createDirectories(root);
        for(int node:nodes) {
            Path path=node(root,node);f.provision(path);String name="node-"+node;
            Files.write(path.resolve("node.gsr"),encode("records","NODE",Map.of("identity",V53ContextFixture.member(node),"root",f.root().manifestDigest())));
            Files.write(path.resolve(MembershipBallotAllocator.CURRENT),encode("records","ALLOCATOR",Map.of("counter",0L,"node",name,"root",f.root().manifestDigest())));
            var manifest=new TreeMap<>(decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value());manifest.put("node",name);
            byte[] raw=encode("records","GENERATION",manifest);Files.write(path.resolve("generations/a/generation.gsr"),raw);
            Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",f.root().manifestDigest(),"node",name,"generation","a","digest",hash(raw))));
            AdmissionPaths.write(path.resolve(MembershipPendingAccept.FILE),MembershipPendingAccept.empty());AdmissionPaths.forceDirectory(path);
        }
    }
    void install(Path root)throws Exception {
        var sources=new ArrayList<MembershipSelection.Source>();
        for(int node:nodes)try(var store=open(root,node,resources(),e->{})) {
            store.prepareCurrent(f.fixture.source.ballot(20));sources.add(store.originalSource());
        }
        for(int node:nodes)try(var store=open(root,node,resources(),e->{})) {
            store.selectCurrent(sources,List.of());store.installCurrent(sources,List.of(),f.fixture.source.images);
        }
    }
    byte[] payload() {
        if(f.admitted.context.view.get("operation")!=null)
            return canonical(Map.of("binding",f.admitted.context.view.get("operation")),8192);
        return "original-real-quorum-payload".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
    }
    Decoded entry() {
        var context=f.admitted.context;
        return decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),
                "index",number(context.cut.get("index"))+1,"previous",context.cut.get("entry"),"origin",f.fixture.source.ballot(20),
                "kind",context.view.get("operation")==null?"DATA":"FINAL","payload",hash(payload()))),"records","ENTRY");
    }
    Set<Owned> accept(Path root)throws Exception {
        var observations=new HashSet<Owned>();
        for(int node:nodes)try(var store=open(root,node,resources(),e->{})){observations.add(store.acceptCurrent(entry(),payload()));}
        return observations;
    }
    Set<Owned> observations(Path root)throws Exception {
        var observations=new HashSet<Owned>();
        for(int node:nodes)try(var store=open(root,node,resources(),e->{})){observations.add(store.currentOwnedTail().orElseThrow());}
        return observations;
    }
    Decoded proof(Set<Owned> observations) {
        var entry=entry();var accept=new TreeMap<String,Object>();
        accept.put("root",f.root().manifestDigest());accept.put("authority",f.admitted.context.authority());accept.put("ballot",f.fixture.source.ballot(20));
        accept.put("entry",entry.digest());accept.put("index",entry.value().get("index"));String digest=hash(encode("records","ACCEPT",accept));
        var witnesses=new ArrayList<Map<String,Object>>();
        for(var owned:observations.stream().sorted(Comparator.comparing(Owned::voter)).toList()) {
            var receipt=Map.of("root",f.root().manifestDigest(),"voter",owned.voter(),"incarnation",owned.storage().toString(),"phase","ACCEPT","record",digest);
            witnesses.add(Map.of("voter",owned.voter(),"incarnation",owned.storage().toString(),"receipt",hash(canonical(receipt,2048))));
        }
        accept.put("accepts",witnesses);return decode(encode("records","PROOF",accept),"records","PROOF");
    }
}
