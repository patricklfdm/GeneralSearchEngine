package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Conditional frozen-source calculation. No grant, force, installation ACK or READY is performed here. */
final class MembershipSelection {
    static final class Source {
        final MembershipCapsule capsule;
        final Decoded basis;
        final MembershipIdentity owner;
        final Decoded accepted,entry;
        private Source(MembershipCapsule capsule,Decoded basis,MembershipIdentity owner,Decoded accepted,Decoded entry) {
            this.capsule=capsule;this.basis=basis;this.owner=owner;this.accepted=accepted;this.entry=entry;
        }
        Map<String,Object> reference() {return Map.of("voter",owner.nodeId().value(),"basisId",basis.value().get("basisId"),"basisDigest",basis.digest());}
        static Source verify(MembershipCapsule capsule,Decoded basis,Map<String,Object> expected,MembershipIdentity owner,Set<Owned> owned) {
            checkType(expected,"source");capsule.packet.bind(basis);var context=capsule.context;var value=basis.value();
            require(expected.get("basisDigest").equals(basis.digest()) && expected.get("basisId").equals(value.get("basisId"))
                    && expected.get("voter").equals(value.get("voter")) && owner.nodeId().value().equals(value.get("voter")),"original frozen source reference");
            require(owner.equals(context.identities.get(owner.nodeId().value())) && context.voters().contains(owner.nodeId().value()),"source permanent eligible identity");
            context.ballot(value.get("ballot"),true);
            String parent=cutDigest(context.cut);
            require(owned.contains(new Owned(owner.nodeId().value(),owner.storageId(),basis.digest(),parent)),"unowned frozen basis");
            Decoded accepted=null,entry=null;
            if(value.get("accepted")!=null) {
                accepted=context.record((String)value.get("accepted"),"ACCEPT");entry=context.record((String)accepted.value().get("entry"),"ENTRY");
                context.ballot(accepted.value().get("ballot"),true);context.ballot(entry.value().get("origin"),true);
                context.control((String)entry.value().get("kind"),command((String)entry.value().get("kind"),capsule.packet.objectBytes((String)entry.value().get("payload"))));
                require(owned.contains(new Owned(owner.nodeId().value(),owner.storageId(),accepted.digest(),parent)),"unowned frozen tail");
            }
            return new Source(capsule,basis,owner,accepted,entry);
        }
    }

    /** Supplemental same-era CHECKPOINT, authenticated after its exact end was applied. */
    static final class Bridge {
        final Decoded statement;
        final List<Decoded> acknowledgements;
        final Set<Owned> owned;
        Bridge(Decoded statement,List<Decoded> acknowledgements,Set<Owned> owned) {
            require(statement.family().equals("records") && statement.kind().equals("CHECKPOINT"),"ancestry checkpoint kind");
            require(acknowledgements.size()>=2 && acknowledgements.size()<=6 && owned.size()<=6,"ancestry endorsement count");
            long bytes=statement.bytes().length;for(var ack:acknowledgements)bytes+=ack.bytes().length;
            require(bytes<=16*1024,"ancestry range byte capacity");
            this.statement=statement;this.acknowledgements=List.copyOf(acknowledgements);this.owned=Set.copyOf(owned);
        }
        void verify(MembershipCapsule longer,MembershipCapsule.Anchor lower) {
            var s=statement.value();var start=object(s.get("start"));var end=object(s.get("end"));var view=object(start.get("view"));
            var upper=longer.anchor(number(end.get("index")));
            require(s.get("root").equals(longer.context.root) && s.get("scope").equals("RANGE") && view.get("operation")==null
                    && view.equals(end.get("view")) && number(end.get("index"))>number(start.get("index")),"ancestry same stable era");
            require(start.equals(lower.cut()) && s.get("catalogBefore").equals(lower.catalog()) && s.get("applicationBefore").equals(lower.application())
                    && upper!=null && end.equals(upper.cut()) && s.get("catalogAfter").equals(upper.catalog())
                    && s.get("applicationAfter").equals(upper.application()),"ancestry exact frozen endpoints");
            var voters=new ArrayList<String>();
            for(var ack:acknowledgements) {
                require(ack.family().equals("records") && ack.kind().equals("CHECKPOINT_ACK"),"ancestry ACK kind");
                var v=ack.value();String voter=(String)v.get("voter");var identity=longer.context.identities.get(voter);
                require(identity!=null && v.get("root").equals(longer.context.root) && v.get("statement").equals(statement.digest())
                        && v.get("cut").equals(end) && identity.storageId().toString().equals(v.get("incarnation")),"ancestry ACK binding");
                require(owned.contains(new Owned(voter,identity.storageId(),ack.digest(),cutDigest(end))),"ancestry ACK before owned end");voters.add(voter);
            }
            orderedNodes(voters);quorum(view,voters);
        }
    }

    record Decision(Decoded selected,Source longest,Source carried,List<Source> sources) {
        Decision {sources=List.copyOf(sources);}
    }

    static final class Campaign {
        private final Source own;
        private Decision selected;
        private boolean abandoned;
        Campaign(Source own) {
            require(own.owner.nodeId().value().equals(object(own.basis.value().get("ballot")).get("proposer")),"campaign own proposer basis");this.own=own;
        }
        void abandon() {abandoned=true;}
        Decision select(List<Source> sources,List<Bridge> bridges) {
            require(!abandoned && selected==null,"campaign ended or already selected; fresh ballot required");
            require(sources.size()>=2 && sources.size()<=6 && bridges.size()<=6,"selected source/ancestry capacity");
            var ballot=own.basis.value().get("ballot");var voters=new ArrayList<String>();Source longest=own;boolean hasOwn=false;
            for(var source:sources) {
                var value=source.basis.value();var context=source.capsule.context;
                require(context.root.equals(own.capsule.context.root) && value.get("ballot").equals(ballot)
                        && context.authority().equals(own.capsule.context.authority()),"mixed root/ballot/configuration sources");
                voters.add(source.owner.nodeId().value());
                if(source.basis.digest().equals(own.basis.digest()))hasOwn=true;
                if(number(context.cut.get("index"))>number(longest.capsule.context.cut.get("index")))longest=source;
            }
            orderedNodes(voters);own.capsule.context.quorum(voters);require(hasOwn,"selection omitted original proposer basis");
            var used=new HashSet<Bridge>();
            for(var source:sources) {
                longest.capsule.context.monotonicFrom(source.capsule.context);
                var lower=source.capsule.terminal();var existing=longest.capsule.anchor(number(lower.cut().get("index")));
                if(!lower.equals(existing)) {
                    require(existing==null,"conflicting proven capsule anchor");
                    Bridge match=null;
                    for(var bridge:bridges)if(bridge.statement.value().get("start").equals(lower.cut())) {
                        require(match==null,"duplicate ancestry for frozen cut");match=bridge;
                    }
                    require(match!=null,"unproven compacted source ancestry");match.verify(longest.capsule,lower);used.add(match);
                }
            }
            require(used.size()==bridges.size(),"unused/duplicate ancestry evidence");
            long end=number(longest.capsule.context.cut.get("index"));Source carried=null;
            for(var source:sources)if(source.accepted!=null) {
                long index=number(source.accepted.value().get("index"));
                // A certified compatible prefix settles the slot even if a minority accepted another value.
                // Retain that source's original tail as evidence; do not mistake it for the chosen entry.
                if(index<=end)continue;
                require(end<MAX && index==end+1,"tail beyond longest next slot");
                if(carried==null)carried=source;
                else {
                    int order=compareBallot(object(source.accepted.value().get("ballot")),object(carried.accepted.value().get("ballot")));
                    require(order!=0 || source.entry.digest().equals(carried.entry.digest()),"equal ballot conflicting tails");
                    if(order>0)carried=source;
                }
            }
            var value=new TreeMap<String,Object>();value.put("root",own.capsule.context.root);value.put("ballot",ballot);
            value.put("view",own.capsule.context.authority());value.put("cut",longest.capsule.context.cut);
            value.put("sources",sources.stream().map(Source::reference).toList());value.put("nextEntry",carried==null?null:carried.entry.digest());
            selected=new Decision(decode(encode("records","SELECTED",value),"records","SELECTED"),longest,carried,sources);return selected;
        }
    }
}
