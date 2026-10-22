package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Fresh physical local voters; no transport ACKs or public application publication. */
public final class V53PendingProofWorker {
    private static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args)throws Exception {
        String command=args[0];Path root=Path.of(args[1]);var f=new V53PendingProofFixture(Integer.parseInt(args[2]),Integer.parseInt(args[3]));
        try {
            if(command.equals("init")){f.provision(root);print(map("status","PASS","command",command));return;}
            if(command.equals("install")){f.install(root);print(map("status","PASS","command",command));return;}
            if(command.equals("accept-all")) {
                for(int node:f.nodes) {
                    var r=f.resources();try(var store=f.open(root,node,r,e->print(map("event",e,"node","node-"+node)))) {
                        var owned=store.acceptCurrent(f.entry(),f.payload());print(map("node",owned.voter(),"accepted",owned.record(),"parent",owned.parent(),"storage",owned.storage().toString()));
                    }
                    if(r.usage().leases()!=0)throw new IllegalArgumentException("proof fixture lease leak");
                }
                print(map("status","PASS","command",command));return;
            }
            if(!Set.of("prove","capture","inspect","accept-duplicate").contains(command))throw new IllegalArgumentException("unknown proof command");
            // Observe actual separately reopened peer owners. Excluding node 1 still forms
            // both majorities for every fixture; a partially written local PROOF is never
            // silently completed by an uninstrumented extra open of the target.
            var accepts=new HashSet<Owned>();
            for(int node:f.nodes)if(node!=1) {
                var r=f.resources();try(var store=f.open(root,node,r,e->{})){accepts.add(store.currentOwnedTail().orElseThrow());}
                if(r.usage().leases()!=0)throw new IllegalArgumentException("proof peer lease leak");
            }
            var proof=f.proof(accepts);String point=args.length>4?args[4]:"none",mode=args.length>5?args[5]:"none";var r=f.resources();
            try(var store=f.open(root,1,r,event->{
                print(map("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")){print(map("event","AWAITING_KILL","cut",point));try{Thread.sleep(120_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}throw new java.io.IOException("external kill did not arrive");}
                }
            })) {
                if(command.equals("prove"))store.proveCurrent(proof,accepts);
                if(command.equals("capture"))store.prepareCurrent(f.f.fixture.source.ballot(21));
                if(command.equals("accept-duplicate"))store.acceptCurrent(f.entry(),f.payload());
                var owned=store.currentOwnedProof().orElseThrow();var basis=store.originalBasis().orElseThrow();
                print(map("status","PASS","command",command,"proof",owned.record(),"accepted",store.currentOwnedTail().orElseThrow().record(),
                        "parent",owned.parent(),"basis",basis.digest(),"captured",basis.value().get("accepted")));
            }
            if(r.usage().leases()!=0)throw new IllegalArgumentException("proof target lease leak");
        }catch(Exception error){print(map("status","FAIL","command",command,"type",error.getClass().getSimpleName(),"reason",String.valueOf(error.getMessage())));System.exit(2);}
    }
}
