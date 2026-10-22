package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Actual local ACCEPT/PROOF owners; retained certificate is not public application publication. */
public final class V53PendingCertificateWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args)throws Exception {
        String command=args[0];Path root=Path.of(args[1]);var fixture=new V53PendingCertificateFixture(Integer.parseInt(args[2]),Integer.parseInt(args[3]));var f=fixture.f;
        try {
            if(Set.of("init","install","accept-all").contains(command)){V53PendingProofWorker.main(args);return;}
            var accepts=new HashSet<Owned>();var proofs=new HashSet<Owned>();
            for(int node:f.nodes)if(node!=1) {
                var r=f.resources();try(var store=f.open(root,node,r,e->{})) {
                    accepts.add(store.currentOwnedTail().orElseThrow());if(!command.equals("prove-all"))proofs.add(store.currentOwnedProof().orElseThrow());
                }
                if(r.usage().leases()!=0)throw new IllegalArgumentException("certificate peer lease leak");
            }
            var proof=f.proof(accepts);
            if(command.equals("prove-all")) {
                for(int node:f.nodes) {
                    var r=f.resources();try(var store=f.open(root,node,r,e->print(map("event",e,"node","node-"+node)))) {
                        var owned=store.proveCurrent(proof,accepts);print(map("node",owned.voter(),"proof",owned.record(),"parent",owned.parent(),"storage",owned.storage().toString()));
                    }
                    if(r.usage().leases()!=0)throw new IllegalArgumentException("certificate fixture lease leak");
                }
                print(map("status","PASS","command",command));return;
            }
            if(!Set.of("certify","capture","inspect","accept-duplicate","proof-duplicate").contains(command))throw new IllegalArgumentException("unknown certificate command");
            var certificate=fixture.certificate(proof,proofs);var owned=new HashSet<>(accepts);owned.addAll(proofs);
            String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";var r=f.resources();
            try(var store=f.open(root,1,r,event->{
                print(map("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")){print(map("event","AWAITING_KILL","cut",point));try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}throw new java.io.IOException("external kill did not arrive");}
                }
            })) {
                if(command.equals("certify"))store.certifyCurrent(certificate,owned);
                if(command.equals("capture"))store.prepareCurrent(f.f.fixture.source.ballot(21));
                if(command.equals("accept-duplicate"))store.acceptCurrent(f.entry(),f.payload());
                if(command.equals("proof-duplicate"))store.proveCurrent(proof,Set.of());
                var actual=store.currentOwnedProof().orElseThrow();var basis=store.originalBasis().orElseThrow();
                print(map("status","PASS","command",command,"certificate",store.currentCertificate().orElseThrow().digest(),"proof",actual.record(),
                        "accepted",store.currentOwnedTail().orElseThrow().record(),"parent",actual.parent(),"basis",basis.digest(),"captured",basis.value().get("accepted")));
            }
            if(r.usage().leases()!=0)throw new IllegalArgumentException("certificate target lease leak");
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
