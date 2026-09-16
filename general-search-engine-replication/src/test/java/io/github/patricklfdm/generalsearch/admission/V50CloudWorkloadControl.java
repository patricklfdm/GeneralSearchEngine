package io.github.patricklfdm.generalsearch.admission;

import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import static io.github.patricklfdm.generalsearch.admission.CloudWorkload.*;

/** The published V4.4 JAR is the only core on this independently compiled classpath. */
public final class V50CloudWorkloadControl {
    private V50CloudWorkloadControl() { }
    public static void main(String[] args) throws Exception {
        String command=args[0]; Path root=Path.of(args[1]); var plan=plan(Path.of(args[2]));
        String profile=args.length==4?args[3]:"local-qualification"; var local=parameters(plan,profile);
        Path output=root.resolve(command.equals("measure")?"control-streams":"restore-streams"); CloudWorkloadTelemetry.initialize(output);
        var builder=PerformanceWorkload.builder(); var storage=storage(root.resolve("control-"+command),plan);
        if(command.equals("restore")) builder.restoreDurableBackup(root.resolve("export"),storage);
        var result=new TreeMap<String,Object>();
        result.put("identity",PerformanceTelemetry.identity(Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString(),plan.digest()));
        try(var engine=builder.buildDurable(storage)) {
            CloudWorkloadTelemetry.startSampling(() -> Map.of("sequence",engine.currentSequence()));
            if(command.equals("measure")) {
                populate(engine,plan); engine.backup(new DurableBackupRequest(root.resolve("source"),128L<<20)).join();
                int cycle=0; var windows=new ArrayList<Object>();
                for(String name:List.of("warmup","baseline-a","instrumented-a","instrumented-b","baseline-b")) {
                    int cycles=number(local,name.equals("warmup")?"warmupCycles":"cyclesPerWindow");
                    windows.add(execute(engine,plan,profile,name,cycle,cycles*10,number(local,"healthyIntervalNanos"),false,() -> Map.of("sequence",engine.currentSequence())));
                    cycle+=cycles;
                }
                if(number(local,"sustainedCalls")>0) windows.add(execute(engine,plan,profile,"sustained",cycle,number(local,"sustainedCalls"),number(local,"sustainedIntervalNanos"),true,() -> Map.of("sequence",engine.currentSequence())));
                result.put("windows",windows);
            } else if(!command.equals("restore")) throw new IllegalArgumentException(command);
            result.put("semantic",state(engine,command)); CloudWorkloadTelemetry.stopSampling();
        } finally { CloudWorkloadTelemetry.stopSampling(); CloudWorkloadTelemetry.close(); }
        System.out.println(AdmissionJson.canonical(result));
    }
}
