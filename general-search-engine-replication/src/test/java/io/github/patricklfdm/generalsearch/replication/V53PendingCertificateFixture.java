package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual new local phased votes; the pre-provisioned applied prefix remains a fixture. */
final class V53PendingCertificateFixture {
    final V53PendingProofFixture f;
    V53PendingCertificateFixture(int size,int through){f=new V53PendingProofFixture(size,through);}
    Decoded certificate(Decoded proof,Set<Owned> observations) {
        var values=new TreeMap<>(proof.value());var witnesses=new ArrayList<Map<String,Object>>();
        for(var owned:observations.stream().sorted(Comparator.comparing(Owned::voter)).toList()) {
            var receipt=Map.of("root",f.f.root().manifestDigest(),"voter",owned.voter(),"incarnation",owned.storage().toString(),"phase","PROOF","record",proof.digest());
            witnesses.add(Map.of("voter",owned.voter(),"incarnation",owned.storage().toString(),"receipt",hash(canonical(receipt,2048))));
        }
        values.put("proofs",witnesses);return decode(encode("records","CERTIFICATE",values),"records","CERTIFICATE");
    }
    Set<Owned> prove(Path root,Decoded proof,Set<Owned> accepts)throws Exception {
        var observations=new HashSet<Owned>();
        for(int node:f.nodes)try(var store=f.open(root,node,f.resources(),e->{})){observations.add(store.proveCurrent(proof,accepts));}
        return observations;
    }
    record Cohort(Decoded proof,Decoded certificate,Set<Owned> accepts,Set<Owned> proofs) {
        Set<Owned> owned(){var result=new HashSet<>(accepts);result.addAll(proofs);return result;}
    }
    Cohort setup(Path root)throws Exception {
        f.provision(root);f.install(root);var accepts=f.accept(root);var proof=f.proof(accepts);var proofs=prove(root,proof,accepts);
        return new Cohort(proof,certificate(proof,proofs),accepts,proofs);
    }
}
