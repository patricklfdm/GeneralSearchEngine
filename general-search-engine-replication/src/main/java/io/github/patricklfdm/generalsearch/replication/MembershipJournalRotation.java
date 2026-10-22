package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.compareBallot;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded exact-frame compaction of an already validated journal; no authority is synthesized. */
final class MembershipJournalRotation {
    static final String PENDING="grants.rotation.gsr";
    static final int MAXIMUM=1024*1024;
    static final int WORST_CASE=6*(8192+16384+65536)+3*8192;
    private MembershipJournalRotation() {}
    /** Candidate only: a forced source-retirement transaction must own publication/deletion. */
    static byte[] excludingSource(byte[] original,Set<String> protectedPromises,Set<String> retainedSources,MembershipSourceRetirementPlan plan) {
        compact(original,protectedPromises,retainedSources); // Validate every original group first.
        require(retainedSources.contains(plan.basisId) && !protectedPromises.contains(plan.promise.digest()),"source rotation protected or absent source");
        var out=new ByteArrayOutputStream();boolean skip=false,found=false,basisFound=false;int offset=0;
        while(offset<original.length) {
            int kind=Short.toUnsignedInt(ByteBuffer.wrap(original,offset,HEADER).getShort(offset+8));
            String name=switch(kind){case 3->"PROMISE";case 4->"BASIS";case 5->"SELECTED";default->throw new IllegalArgumentException("source rotation record kind");};
            int length=HEADER+header(Arrays.copyOfRange(original,offset,offset+HEADER),"records",name);
            var row=decode(Arrays.copyOfRange(original,offset,offset+length),"records",name);offset+=length;
            if(name.equals("PROMISE")) {
                skip=plan.basisId.equals(row.value().get("basisId"));
                if(skip){require(!found && Arrays.equals(row.bytes(),plan.promise.bytes()),"source rotation original promise changed");found=true;}
            }else if(skip && name.equals("BASIS")) {
                require(!basisFound && Arrays.equals(row.bytes(),plan.basis.bytes()),"source rotation original basis changed");basisFound=true;
            }
            if(!skip)out.writeBytes(row.bytes());
        }
        require(found && basisFound && !skip,"source rotation cannot drop highest grant");
        var retained=new HashSet<>(retainedSources);retained.remove(plan.basisId);
        return compact(out.toByteArray(),protectedPromises,retained);
    }
    static byte[] compact(byte[] original,Set<String> protectedPromises,Set<String> retainedSources) {
        require(original.length<=MembershipGrantJournal.MAXIMUM && protectedPromises.size()<=2 && retainedSources.size()<=6,"journal rotation input capacity");
        var groups=new ArrayList<List<Decoded>>();int offset=0;Decoded previous=null;var found=new HashSet<String>();var sourceIds=new HashSet<String>();int bases=0;
        while(offset<original.length) {
            require(original.length-offset>=HEADER,"torn rotation journal header");
            int kind=Short.toUnsignedInt(ByteBuffer.wrap(original,offset,HEADER).getShort(offset+8));
            String name=switch(kind){case 3->"PROMISE";case 4->"BASIS";case 5->"SELECTED";default->throw new IllegalArgumentException("rotation journal kind");};
            int length=HEADER+header(Arrays.copyOfRange(original,offset,offset+HEADER),"records",name);
            require(length<=original.length-offset,"torn rotation journal body");
            var row=decode(Arrays.copyOfRange(original,offset,offset+length),"records",name);offset+=length;
            if(name.equals("PROMISE")) {
                require(previous==null || compareBallot(object(previous.value().get("ballot")),object(row.value().get("ballot")))<0,"rotation promise order");
                require(previous==null || previous.value().get("root").equals(row.value().get("root")),"rotation foreign root");
                groups.add(new ArrayList<>());previous=row;found.add(row.digest());
                if(row.value().get("basisId")!=null)require(sourceIds.add((String)row.value().get("basisId")),"rotation reused basis identity");
            }else {
                require(!groups.isEmpty(),"rotation orphan journal record");var group=groups.getLast();
                require(group.size()==(name.equals("BASIS")?1:2),"rotation duplicate/orphan grant record");
                for(String field:List.of("root","view","ballot"))require(row.value().get(field).equals(group.getFirst().value().get(field)),"rotation grant context");
                if(name.equals("BASIS")){require(++bases<=6 && retainedSources.contains(row.value().get("basisId")),"rotation retained source count/binding");require(row.value().get("basisId").equals(previous.value().get("basisId")),"rotation original basis identity");}
            }
            groups.getLast().add(row);
        }
        require(!groups.isEmpty() && found.containsAll(protectedPromises) && sourceIds.containsAll(retainedSources),"rotation protected promise absent");
        var out=new ByteArrayOutputStream();
        for(var group:groups)if((group.getFirst().value().get("basisId")!=null && retainedSources.contains(group.getFirst().value().get("basisId"))) || group==groups.getLast() || protectedPromises.contains(group.getFirst().digest()))
            for(var row:group){require(row.bytes().length<=MAXIMUM-out.size(),"rotation compact journal capacity");out.writeBytes(row.bytes());}
        require(out.size()<=WORST_CASE && out.size()<=original.length,"rotation compact bound");return out.toByteArray();
    }
}
