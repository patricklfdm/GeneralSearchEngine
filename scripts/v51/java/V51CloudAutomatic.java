package io.github.patricklfdm.generalsearch.replication;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.admission.*;
import java.nio.file.*;
import java.util.*;

public final class V51CloudAutomatic {
    public static void main(String[] args) throws Exception {
        V51Measurement.cloudMode=true;
        if(args[1].equals("setup")){V51MeasuredAutomatic.main(args);return;}
        Path root=Path.of(args[0]);String node="node-"+args[1];
        var manifest=decode(Files.readAllBytes(root.resolve(node+"/manifest.gsr")),"MANIFEST");
        Object lock=new Object();long[] order={0};
        AutomaticRuntime.Events trace=(name,values)->{
            synchronized(lock) {
                var row=new LinkedHashMap<>(values);
                if(name.equals("PUBLIC_READ_INVOKE")) {
                    String opId=V51Measurement.callId.get();
                    if(opId==null)throw new java.io.IOException("public read without an issuing command");
                    row.put("opId",opId);
                }
                row.put("event",name);row.put("order",++order[0]);row.put("pid",ProcessHandle.current().pid());
                row.put("generation",1);row.put("node",node);row.put("localNanos",System.nanoTime());
                row.put("groupId",text(manifest.value(),"groupId"));row.put("manifestDigest",manifest.digest());
                V51CloudJournal.append(root.resolve(node+"-trace.jsonl"),row);
            }
        };
        V51PerformanceObserver.install(root,node,manifest,trace);
        try {V51MeasuredAutomatic.main(args);}finally{AutomaticRuntimeHooks.CURRENT.remove();V51CloudJournal.closeAll();}
    }
}
