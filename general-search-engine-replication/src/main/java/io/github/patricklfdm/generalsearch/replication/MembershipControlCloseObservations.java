package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Optional bounded cleanup-call observations, not authority or a close hook.
 * Only the resource monitor calls this recorder; no I/O or external callbacks. */
final class MembershipControlCloseObservations {
    static final int MAXIMUM=65536, CHILDREN_MAXIMUM=262144;
    record Row(long sequence,String event,long call,long resourceSequence,String owner,List<String> children) {}
    record Snapshot(int maximum,long observations,boolean truncated,boolean failed,List<Row> rows) {}
    private final int maximum;
    private final List<Row> rows=new ArrayList<>();
    private long observations;
    private int children;
    private boolean truncated,failed;
    MembershipControlCloseObservations(int maximum) {
        require(maximum>0 && maximum<=MAXIMUM,"control close observation bound");this.maximum=maximum;
    }
    boolean accepting(){return !truncated && !failed;}
    void failed(){failed=true;}
    long record(String event,long call,long resourceSequence,String owner,List<String> members) {
        long sequence=observations++;
        if(!accepting())return -1;
        if(rows.size()==maximum || members.size()>CHILDREN_MAXIMUM-children){truncated=true;return -1;}
        rows.add(new Row(sequence,event,call<0?sequence:call,resourceSequence,owner,List.copyOf(members)));
        children+=members.size();return sequence;
    }
    Snapshot snapshot(){return new Snapshot(maximum,observations,truncated,failed,List.copyOf(rows));}
}
