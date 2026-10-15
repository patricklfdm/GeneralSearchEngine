package io.github.patricklfdm.generalsearch.admission;

import java.lang.management.ManagementFactory;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Supplier;

/** JVM-local observations only. Allocation/CPU include observer overhead. */
public final class V52MeasurementSampler implements AutoCloseable {
    private final Supplier<Map<String,Object>> queues;
    private final Supplier<Long> retained;
    private final ThreadPoolExecutor clients;
    private final ScheduledExecutorService timer=Executors.newSingleThreadScheduledExecutor(r->{var t=new Thread(r,"v52-measurement-sampler");t.setDaemon(true);return t;});
    private ScheduledFuture<?> task;
    private volatile Throwable failure;
    private long origin,ordinal;
    private String state="NEW";
    private static final long INTERVAL=1_000_000_000L;
    public V52MeasurementSampler(Supplier<Map<String,Object>> queues,Supplier<Long> retained,ThreadPoolExecutor clients){this.queues=queues;this.retained=retained;this.clients=clients;}
    private static Map<String,Object> counter(long value,String unavailable){return value<0?Map.of("status",unavailable):Map.of("status","AVAILABLE","value",value);}
    private Map<String,Object> collect(String kind,long due,String marker) {
        if(ordinal>=1024)throw new IllegalStateException("measurement sample count bound");
        long start=System.nanoTime();var row=new LinkedHashMap<String,Object>();
        row.put("sampleKind",kind);row.put("sampleOrdinal",ordinal++);row.put("dueNanos",due);row.put("sampleStartNanos",start);row.put("marker",marker);
        var memory=ManagementFactory.getMemoryMXBean();var heap=memory.getHeapMemoryUsage();var nonheap=memory.getNonHeapMemoryUsage();
        row.put("heapUsedBytes",heap.getUsed());row.put("heapCommittedBytes",heap.getCommitted());row.put("heapMaxBytes",counter(heap.getMax(),"UNDEFINED"));row.put("nonHeapUsedBytes",nonheap.getUsed());
        var os=ManagementFactory.getOperatingSystemMXBean();
        row.put("processCpuNanos",os instanceof com.sun.management.OperatingSystemMXBean extended?counter(extended.getProcessCpuTime(),"UNAVAILABLE"):Map.of("status","UNSUPPORTED"));
        var threads=ManagementFactory.getThreadMXBean();row.put("liveThreads",threads.getThreadCount());row.put("peakLiveThreads",threads.getPeakThreadCount());
        Map<String,Object> allocation=Map.of("status","UNSUPPORTED");
        if(threads instanceof com.sun.management.ThreadMXBean extended && extended.isThreadAllocatedMemorySupported()) {
            if(!extended.isThreadAllocatedMemoryEnabled())allocation=Map.of("status","DISABLED");
            else try {allocation=counter(extended.getTotalThreadAllocatedBytes(),"UNAVAILABLE");}
            catch(UnsupportedOperationException unavailable){allocation=Map.of("status","UNSUPPORTED");}
        }
        row.put("allocatedBytes",allocation);
        var gc=new ArrayList<Map<String,Object>>();
        for(var collector:ManagementFactory.getGarbageCollectorMXBeans())gc.add(Map.of("name",collector.getName(),"count",counter(collector.getCollectionCount(),"UNAVAILABLE"),"millis",counter(collector.getCollectionTime(),"UNAVAILABLE")));
        row.put("gc",gc);row.put("queues",queues.get());row.put("retainedBytes",retained.get());
        row.put("consumerActive",clients.getActiveCount());row.put("consumerQueued",clients.getQueue().size());row.put("sampleEndNanos",System.nanoTime());
        V52MeasurementConsumer.event("CLIENT_SAMPLE",row);return row;
    }
    private void healthy(){if(failure!=null)throw new IllegalStateException("measurement sampler failed",failure);}
    public synchronized Map<String,Object> start(){
        healthy();if(!state.equals("NEW"))throw new IllegalStateException("measurement sampler already started");
        origin=System.nanoTime();var first=collect("START",origin,"");state="RUNNING";
        // Keep each original due time, including after a delayed sample. Never
        // replace a missing interval with a fictitious on-time measurement.
        task=timer.scheduleAtFixedRate(()->{synchronized(this){if(!state.equals("RUNNING"))return;try{collect("PERIODIC",origin+periodic++*INTERVAL,"");}catch(Throwable error){failure=error;state="FAILED";throw error;}}},Math.max(0,origin+INTERVAL-System.nanoTime()),INTERVAL,TimeUnit.NANOSECONDS);
        return first;
    }
    private long periodic=1;
    public synchronized Map<String,Object> mark(String marker){healthy();if(!state.equals("RUNNING")||!Set.of("warmup-start","measured-start","measured-end").contains(marker))throw new IllegalArgumentException("measurement sample marker");return collect("MARK",System.nanoTime(),marker);}
    public synchronized Map<String,Object> stop(){
        healthy();if(!state.equals("RUNNING"))throw new IllegalStateException("measurement sampler not running");
        task.cancel(false);state="STOPPED";return collect("STOP",System.nanoTime(),"");
    }
    public void close() throws Exception {
        synchronized(this){if(state.equals("RUNNING"))stop();timer.shutdown();}
        if(!timer.awaitTermination(5,TimeUnit.SECONDS))throw new IllegalStateException("measurement sampler did not stop");healthy();
    }
}
