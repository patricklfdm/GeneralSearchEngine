package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact structural comparison with an independently retained SEALED source and
 * typed receipt. This value is not original force ownership, a stored certificate
 * capability, an installed end or an acknowledgement. */
final class MembershipJoiningIntentMetadata {
    static final int MAXIMUM=(int)(MembershipResources.Unit.CONTROL.bytes/3);
    private final byte[] bytes;
    private final Map<String,Decoded> records;
    private MembershipJoiningIntentMetadata(byte[] bytes,Map<String,Decoded> records) {
        this.bytes=bytes.clone();this.records=Map.copyOf(records);
    }
    byte[] bytes(){return bytes.clone();}
    Decoded record(String kind){return Objects.requireNonNull(records.get(kind));}

    static MembershipJoiningIntentMetadata inspect(MembershipLearnerRequest request,MembershipIdentity peer,
            MembershipCapsule before,Decoded typedReceipt,byte[] bytes) {
        require(bytes.length>0 && bytes.length<=MAXIMUM,"joining metadata body capacity");
        var body=object(parse(bytes,MAXIMUM));
        require(body.keySet().equals(Set.of("schema","root","owner","learner","request","parent","target","records","payload"))
                && Arrays.equals(bytes,canonical(body,MAXIMUM)),"joining metadata exact canonical fields");
        var context=before.context;
        MembershipLearnerProgressAccess.original(context,request,peer);
        require(body.get("schema").equals("gse-v53-joining-intent-metadata/1.3") && body.get("root").equals(context.root)
                && body.get("owner").equals(MembershipBootstrapSeed.identity(peer))
                && body.get("learner").equals(MembershipBootstrapSeed.identity(request.identity()))
                && body.get("request").equals(MembershipLearnerDiscovery.request(request.change()))
                && body.get("parent").equals(MembershipRetentionIntent.anchor(before.terminal())),"joining metadata original source binding");
        var row=MembershipLearnerProgressAccess.operation(context,request.identity());
        require(row.get("phase").equals("SEALED") && context.view.get("operation")==null
                && typedReceipt.kind().equals("LEARNER") && typedReceipt.value().get("root").equals(context.root)
                && typedReceipt.value().get("receipt").equals(row.get("receipt")),"joining metadata original typed SEALED receipt");
        var raw=object(body.get("records"));
        require(raw.keySet().equals(Set.of("ENTRY","ACCEPT","PROOF","CERTIFICATE","CATALOG","CHECKPOINT")),"joining metadata exact record inventory");
        var records=new TreeMap<String,Decoded>();
        raw.forEach((kind,value)->records.put(kind,decode(original(value),"records",kind)));
        var entry=records.get("ENTRY");var certificate=records.get("CERTIFICATE");
        byte[] payload=original(body.get("payload"));var value=entry.value();
        require(value.get("kind").equals("INTENT") && value.get("root").equals(context.root)
                && value.get("authority").equals(context.authority()) && value.get("previous").equals(context.cut.get("entry"))
                && number(context.cut.get("index"))<MembershipValidation.MAX
                && number(value.get("index"))==number(context.cut.get("index"))+1
                && value.get("payload").equals(hash(payload)),"joining metadata original next INTENT");
        context.control("INTENT",command("INTENT",payload));
        context.persistedCertificate(certificate,records.get("PROOF"),records.get("ACCEPT"));
        require(certificate.value().get("entry").equals(entry.digest())
                && MembershipContext.compareBallot(context.ballot(value.get("origin"),true),
                        context.ballot(certificate.value().get("ballot"),true))<=0,"joining metadata original phased entry");

        // INTENT changes only the sealed operation's phase and joint cut. Do not
        // allocate or replay another application image to check that projection.
        var projected=new TreeMap<>(context.catalog);var rows=new ArrayList<Map<String,Object>>();
        for(var item:list(context.catalog.get("results"))) {
            var next=new TreeMap<>(object(item));
            if(object(next.get("request")).get("number").equals(context.catalog.get("active")))next.put("phase","JOINT");
            rows.add(next);
        }
        var view=new TreeMap<>(context.view);view.put("operation",row.get("binding"));
        view.put("new",request.change().target().stream().map(id->id.nodeId().value()).toList());
        var end=Map.of("entry",entry.digest(),"index",value.get("index"),"view",view);
        projected.put("results",rows);projected.put("cut",end);
        var catalog=records.get("CATALOG");
        require(Arrays.equals(encode("records","CATALOG",projected),catalog.bytes()),"joining metadata exact projected catalog");
        var statement=Map.of("root",context.root,"scope","MEMBERSHIP","start",context.cut,"end",end,
                "catalogBefore",before.terminal().catalog(),"catalogAfter",catalog.digest(),
                "applicationBefore",before.terminal().application(),"applicationAfter",before.terminal().application());
        require(Arrays.equals(encode("records","CHECKPOINT",statement),records.get("CHECKPOINT").bytes())
                && body.get("target").equals(MembershipRetentionIntent.anchor(new MembershipCapsule.Anchor(
                        end,catalog.digest(),before.terminal().application()))),"joining metadata exact target checkpoint");
        return new MembershipJoiningIntentMetadata(bytes,records);
    }
    private static byte[] original(Object value) {
        require(value instanceof String,"joining metadata encoded original");String encoded=(String)value;
        require(encoded.length()<=MAXIMUM,"joining metadata encoded capacity");byte[] bytes=Base64.getDecoder().decode(encoded);
        require(bytes.length>0 && Base64.getEncoder().encodeToString(bytes).equals(encoded),"joining metadata canonical original");return bytes;
    }
}
