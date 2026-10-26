package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bind an authenticated original PROMISE to complete owned receive files. The
 * reply attests this peer's frozen BASIS/tail only; historical certificate and
 * checkpoint provenance must still be supplied by the capsule verifier. */
final class MembershipPromisedSource {
    private MembershipPromisedSource() {}
    static MembershipSelection.Source verify(MembershipSelection.Source own,MembershipIdentity peer,
            Decoded request,Decoded reply,MembershipSourceReceive received,MembershipCurrentGeneration.Verifier verifier)throws IOException {
        Objects.requireNonNull(received);Objects.requireNonNull(verifier);
        var context=own.capsule.context;var ballot=object(own.basis.value().get("ballot"));
        require(request.kind().equals("PREPARE") && reply.kind().equals("PROMISE"),"promised source exchange kinds");
        var trace=UUID.fromString((String)request.value().get("trace"));long sequence=number(request.value().get("sequence"));
        context.wire(request,own.owner,peer,ballot,trace,sequence);context.wire(reply,peer,own.owner,ballot,trace,sequence);
        require(context.voters().contains(peer.nodeId().value()) && !peer.equals(own.owner)
                && own.owner.nodeId().value().equals(ballot.get("proposer")) && own.owner.storageId().toString().equals(ballot.get("incarnation")),"promised source eligible proposer/peer");
        var fields=new TreeMap<String,Object>();for(String name:List.of("root","view","ballot","basisId"))fields.put(name,own.basis.value().get(name));
        require(object(request.value().get("payload")).get("promise").equals(hash(encode("records","PROMISE",fields))),"promised source original proposer grant");
        var basis=received.basis();var promise=received.promise();
        require(received.sourceIdentity().equals(peer) && basis.value().get("voter").equals(peer.nodeId().value())
                && basis.value().get("root").equals(context.root) && basis.value().get("view").equals(context.authority())
                && basis.value().get("ballot").equals(ballot) && object(reply.value().get("payload")).get("basis").equals(basis.digest()),"promised source exact frozen grant");
        for(String name:List.of("root","view","ballot","basisId"))require(Objects.equals(promise.value().get(name),basis.value().get(name)),"promised source original promise binding");
        var packet=received.packet();var images=received.images();packet.bind(basis);
        var root=decode(own.capsule.packet.objectBytes(context.recordRootDigest()),"records","ROOT");
        var capsule=Objects.requireNonNull(verifier.verify(root,packet,images),"promised source capsule verifier");
        require(capsule.context.root.equals(context.root) && capsule.context.authority().equals(context.authority())
                && Arrays.equals(capsule.packet.bytes(),packet.bytes()),"promised source verifier substituted prefix");
        // These are observations of the matched peer's real grant reply, not an
        // inferred set of historical witness ACKs from hashes in the packet.
        String parent=cutDigest(object(basis.value().get("cut")));var owned=new HashSet<Owned>();
        owned.add(new Owned(peer.nodeId().value(),peer.storageId(),basis.digest(),parent));
        if(basis.value().get("accepted")!=null)owned.add(new Owned(peer.nodeId().value(),peer.storageId(),(String)basis.value().get("accepted"),parent));
        var reference=Map.<String,Object>of("voter",peer.nodeId().value(),"basisId",basis.value().get("basisId"),"basisDigest",basis.digest());
        var result=MembershipSelection.Source.verify(capsule,basis,reference,peer,owned);
        // The borrowed physical owner must still be live after potentially costly verification.
        received.recheck();return result;
    }
}
