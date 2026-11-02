package io.github.patricklfdm.generalsearch.replication;

import java.io.PrintStream;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/** Test instrumentation only. Never sent on the observation ACK pipe or used
 * as protocol authority. Failure reporting precedes close and is bounded even
 * when a service-state getter is blocked on an owner monitor. */
final class V53NodeProcessDiagnostics {
    static final int MAX_ACTIVE=16, MAX_CAUSES=4;
    static final long STATE_WAIT_MILLIS=250;
    private static final Set<String> ACTIONS=Set.of("event","response","snapshot","installed","started","opened","cut","closed");
    @FunctionalInterface interface Checked {void run()throws Exception;}

    static String clipped(String value,int maximum) {
        return value==null?"":value.length()<=maximum?value:value.substring(0,maximum)+"[truncated]";
    }
    static List<Map<String,Object>> causes(Throwable failure) {
        var seen=Collections.newSetFromMap(new IdentityHashMap<Throwable,Boolean>());
        var rows=new ArrayList<Map<String,Object>>();
        while(failure!=null && rows.size()<MAX_CAUSES && seen.add(failure)) {
            rows.add(Map.of("type",clipped(failure.getClass().getName(),256),"message",clipped(failure.getMessage(),384)));
            failure=failure.getCause();
        }
        if(failure!=null)rows.add(Map.of("truncated",true));
        return rows;
    }
    /** Preserve the operation failure if either diagnostics or drain fails. */
    static void finish(Throwable primary,Checked diagnostics,Checked close)throws Exception {
        if(primary!=null)try{diagnostics.run();}catch(Exception|Error error){if(error!=primary)primary.addSuppressed(error);}
        try{close.run();}catch(Exception|Error error){if(primary==null)throw error;if(error!=primary)primary.addSuppressed(error);}
    }

    /** Counters are bounded by fixed labels. A snapshot does not take the pipe
     * monitor, so a missing ACK remains observable. Durations overlap across
     * threads; their sum is not a decomposition of service elapsed time. */
    static final class Meter {
        private final LongSupplier clock;
        private final Map<String,long[]> totals=new TreeMap<>();
        private final Set<Span> active=new LinkedHashSet<>();
        private long omitted;
        Meter(){this(System::nanoTime);}
        Meter(LongSupplier clock){this.clock=clock;}
        synchronized Span begin(String action) {
            var span=new Span(ACTIONS.contains(action)?action:"other",clock.getAsLong());
            if(active.size()<MAX_ACTIVE)active.add(span);else omitted++;
            return span;
        }
        final class Span implements AutoCloseable {
            final String action;final long began;
            long acquired;boolean entered,success,closed;
            String phase="queue";
            Span(String action,long began){this.action=action;this.began=began;}
            void acquired(){synchronized(Meter.this){acquired=clock.getAsLong();entered=true;phase="work";}}
            void phase(String value){synchronized(Meter.this){phase=value;}}
            void success(){synchronized(Meter.this){success=true;}}
            @Override public void close(){synchronized(Meter.this){
                if(closed)return;closed=true;long now=clock.getAsLong();
                long queue=Math.max(0,(entered?acquired:now)-began),work=entered?Math.max(0,now-acquired):0;
                var total=totals.computeIfAbsent(action,key->new long[6]);total[0]++;if(!success)total[1]++;
                total[2]+=queue;total[3]=Math.max(total[3],queue);total[4]+=work;total[5]=Math.max(total[5],work);active.remove(this);
            }}
        }
        synchronized Map<String,Object> snapshot() {
            long now=clock.getAsLong();var done=new TreeMap<String,Object>();
            totals.forEach((key,v)->done.put(key,Map.of("completed",v[0],"failed",v[1],"queueNanos",v[2],"maxQueueNanos",v[3],"workNanos",v[4],"maxWorkNanos",v[5])));
            var pending=active.stream().map(v->Map.of("action",v.action,"phase",v.phase,"elapsedNanos",Math.max(0,now-v.began),
                "queueNanos",Math.max(0,(v.entered?v.acquired:now)-v.began),"workNanos",v.entered?Math.max(0,now-v.acquired):0)).toList();
            return Map.of("completed",done,"active",pending,"omittedActiveSamples",omitted,"durationsMayOverlap",true);
        }
    }

    static Map<String,Object> node(MembershipNodeOwner<?,?> node) {
        var result=new TreeMap<String,Object>();result.put("nodeState",node.state().name());
        result.put("serviceState",node.serviceState().map(Enum::name).orElse("ABSENT"));
        result.put("failure",causes(node.failure().orElse(null)));
        node.recovery().ifPresent(v->{result.put("rounds",v.rounds());result.put("losses",v.losses().stream().map(Enum::name).toList());});
        result.put("atomicSnapshot",false);return result;
    }
    static Map<String,Object> sample(Supplier<Map<String,Object>> state,long waitMillis) {
        var task=new FutureTask<>(state::get);
        Thread.ofPlatform().daemon().name("v53-process-diagnostic-state").start(task);
        try{return Map.of("status","SAMPLED","value",task.get(waitMillis,TimeUnit.MILLISECONDS));}
        catch(TimeoutException error){return Map.of("status","UNAVAILABLE","reason","state sample timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();return Map.of("status","UNAVAILABLE","reason","diagnostic interrupted");}
        catch(ExecutionException error){return Map.of("status","UNAVAILABLE","failure",causes(error.getCause()));}
        finally{task.cancel(true);}
    }
    static List<Map<String,Object>> threads() {
        var rows=new ArrayList<Map<String,Object>>();var bean=ManagementFactory.getThreadMXBean();
        for(long id:bean.getAllThreadIds()) {
            var info=bean.getThreadInfo(id,0);
            if(info==null || !info.getThreadName().startsWith("gse-membership-"))continue;
            if(rows.size()==8){rows.add(Map.of("truncated",true));break;}
            info=bean.getThreadInfo(id,12);if(info==null)continue;
            rows.add(Map.of("name",clipped(info.getThreadName(),128),"state",info.getThreadState().name(),
                "stack",Arrays.stream(info.getStackTrace()).map(v->clipped(v.toString(),192)).toList(),"frameLimit",12));
        }
        return rows;
    }
    static void report(PrintStream output,String role,String phase,int life,long phaseBegan,Throwable failure,
            Meter meter,Supplier<Map<String,Object>> state) {
        var record=new TreeMap<String,Object>();record.put("schema","gse-v53-node-process-diagnostic-v1");
        record.put("authority",false);record.put("role",role);record.put("phase",phase);record.put("life",life);
        record.put("phaseElapsedNanos",Math.max(0,System.nanoTime()-phaseBegan));
        record.put("serviceBudgetNanos",V53NodeOwnerNetworkTest.BUDGET);record.put("failure",causes(failure));
        record.put("observations",meter.snapshot());record.put("state",sample(state,STATE_WAIT_MILLIS));record.put("threads",threads());
        record.put("threadScope","platform membership threads only; virtual I/O workers are not sampled");
        output.println("v53NodeProcessDiagnostic="+new String(MembershipFormat.canonical(record,65536),StandardCharsets.UTF_8));output.flush();
    }
}
