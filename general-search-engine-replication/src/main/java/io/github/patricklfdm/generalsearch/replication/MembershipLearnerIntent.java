package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** A locally forced, complete matching INTENT source under the live typed
 * learner owner. This is input to voter installation, not a voter, new ballot,
 * public readiness result or permission to remove the prepared image. */
final class MembershipLearnerIntent implements AutoCloseable {
    static final String PLAN="intent.json",NEXT="intent.next.json",SOURCE="source";
    private final MembershipLearnerDisposition retained;
    private final MembershipLearnerDisposition recoveredPending;
    private MembershipLearnerIntent(MembershipLearnerDisposition retained){this(retained,null);}
    private MembershipLearnerIntent(MembershipLearnerDisposition retained,MembershipLearnerDisposition recoveredPending){this.retained=retained;this.recoveredPending=recoveredPending;}
    static Path directory(MembershipLearnerPlan plan){return MembershipLearnerDisposition.directory(plan,MembershipLearnerDisposition.Kind.INTENT);}

    static Map<String,Object> match(MembershipLearnerHead head,MembershipFloor.Copy copy)throws IOException {
        head.check();copy.check();var result=match(head,copy.capsule,copy.owner,
                copy.fileNames().contains("ancestry.gsr")?copy.fileBytes("ancestry.gsr"):new byte[0]);
        copy.check();head.check();return result;
    }
    /** The caller supplies an already verified owned source, never a decoded
     * capsule or a caller's set of expected checkpoint voters. */
    static Map<String,Object> match(MembershipLearnerHead head,MembershipCapsule source,MembershipIdentity peer,byte[] ancestry)throws IOException {
        head.check();var request=head.request();var original=head.source();var receipt=head.receipt();
        MembershipLearnerProgressAccess.original(source.context,request,peer);
        MembershipLearnerSource.successor(original,source,ancestry);
        var result=matchReceipt(request,receipt,source);head.check();return result;
    }
    /** Shared semantic binding for the actual retained owner and its later
     * placement custody. This method does not issue ownership or a vote. */
    static Map<String,Object> matchReceipt(MembershipLearnerRequest request,Decoded receipt,MembershipCapsule source) {
        var row=matchJoinedReceipt(request,receipt,source);
        var target=request.change().target().stream().map(i->i.nodeId().value()).toList();var view=source.context.view;
        var old=object(object(object(row.get("prepared")).get("cut")).get("view"));String binding=(String)row.get("binding");
        if(row.get("phase").equals("JOINT"))require(binding.equals(view.get("operation")) && view.get("old").equals(old.get("old"))
                && view.get("new").equals(target) && view.get("generation").equals(old.get("generation")),"learner INTENT current joint view");
        else require(view.get("operation")==null && view.get("old").equals(target) && view.get("new").equals(target)
                && number(view.get("generation"))==number(old.get("generation"))+1,"learner INTENT completed target view");
        return row;
    }
    /** Original enrollment provenance may outlive its immediate target view. */
    static Map<String,Object> matchJoinedReceipt(MembershipLearnerRequest request,Decoded receipt,MembershipCapsule source) {
        require(source.context.root.equals(request.root().manifestDigest()),"learner INTENT root changed");
        var row=MembershipLearnerProgressAccess.operation(source.context,request.identity());
        require(row.get("request").equals(MembershipLearnerDiscovery.request(request.change())),"learner INTENT request changed");
        require(Set.of("JOINT","COMPLETED").contains(row.get("phase")),"learner requires certified matching INTENT");
        var actual=object(receipt.value().get("receipt"));
        require(receipt.kind().equals("LEARNER") && receipt.value().get("root").equals(request.root().manifestDigest())
                && actual.equals(row.get("receipt")) && actual.get("prepared").equals(row.get("prepared"))
                && actual.get("identity").equals(MembershipPeerRetentionPlan.identity(request.identity())),"learner INTENT differs from forced typed receipt");
        var descriptor=new TreeMap<String,Object>();for(String field:List.of("request","prepared","receipt"))descriptor.put(field,row.get(field));
        String binding=hash(canonical(descriptor,8192));require(binding.equals(row.get("binding")),"learner INTENT sealed binding");
        var target=request.change().target().stream().map(i->i.nodeId().value()).toList();
        var old=object(object(object(row.get("prepared")).get("cut")).get("view"));String node=request.identity().nodeId().value();
        require(!MembershipContext.nodes(old,"old").contains(node) && target.contains(node)
                && source.context.identities.get(node).equals(request.identity()),"learner INTENT joining identity");
        Decoded found=null;
        for(Object item:list(source.packet.capsule().value().get("items"))) {
            var edge=object(item);if(!edge.get("kind").equals("MEMBERSHIP") || !binding.equals(edge.get("descriptor")))continue;
            var certificate=source.context.record((String)edge.get("certificate"),"CERTIFICATE");
            var entry=source.context.record((String)certificate.value().get("entry"),"ENTRY");
            if(!entry.value().get("kind").equals("INTENT"))continue;
            var statement=source.context.record((String)edge.get("statement"),"CHECKPOINT");
            require(found==null && Arrays.equals(source.packet.objectBytes(binding),canonical(descriptor,8192))
                    && object(command("INTENT",source.packet.objectBytes((String)entry.value().get("payload")))).get("sealed").equals(descriptor)
                    && statement.value().get("applicationAfter").equals(actual.get("image")),"learner INTENT original edge/image");
            found=certificate;
        }
        require(found!=null,"learner INTENT original certificate missing");return row;
    }
    static MembershipLearnerIntent install(MembershipLearnerHead head,MembershipSourceReceive receiver,MembershipFloor.Copy copy,
            MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerIntent(MembershipLearnerDisposition.install(head,receiver,copy,cut,MembershipLearnerDisposition.Kind.INTENT));
    }
    static MembershipLearnerIntent resume(MembershipLearnerHead head,MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerIntent(MembershipLearnerDisposition.resume(head,cut,MembershipLearnerDisposition.Kind.INTENT));
    }
    static MembershipLearnerIntent installPublished(MembershipLearnerProgress.PublishedIntent original,MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerIntent(MembershipLearnerDisposition.installPublished(original,cut));
    }
    static MembershipLearnerIntent resumePublished(MembershipLearnerHead head,MembershipBallotAllocator.Cut cut)throws IOException {
        var pair=MembershipLearnerDisposition.resumePublished(head,cut);return new MembershipLearnerIntent(pair.intent(),pair.pending());
    }
    final class Forced {
        private Forced() {}
        MembershipCapsule source()throws IOException{return retained.forcedIntent();}
        void check()throws IOException{retained.forcedIntent();}
        void guard()throws IOException{retained.guardIntent();}
        MembershipLearnerHead head()throws IOException{return retained.intentHead();}
        MembershipLearnerPlan plan()throws IOException{return retained.intentPlan();}
        byte[] member(String name)throws IOException{return retained.intentMember(name);}
        byte[] ancestry()throws IOException{return retained.intentAncestry();}
        void attach(MembershipLearnerVoterStage stage)throws IOException{retained.attachVoterStage(stage);}
    }
    Forced forced()throws IOException {retained.requireStandaloneVoterHandoff();retained.forcedIntent();return new Forced();}
    Map<String,Object> result()throws IOException{return retained.result();}
    @Override public void close()throws IOException{MembershipLearnerSource.closeChildren(retained,recoveredPending);}
}
