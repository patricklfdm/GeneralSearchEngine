package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Deterministic SIGKILL of the real observer writer; no replication runtime. */
public final class V51PublicTraceProbe {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]),path=root.resolve("node-1-trace.jsonl");
        String mode=args[1];int generation=Integer.parseInt(args[2]);
        var manifest=new AutomaticRecords.Record("MANIFEST",Map.of("groupId","trace-probe"),new byte[48]);
        var trace=new V51PublicWorker.Trace(path,root.resolve("unused-arm"),generation,"node-1",manifest) {
            @Override void append(byte[] line) throws IOException {
                if(line.length<8192||mode.equals("normal")){super.append(line);return;}
                int count=switch(mode){case "before"->0;case "partial"->8192;case "complete"->line.length;default->throw new IOException("probe mode");};
                if(count>0)Files.write(path,Arrays.copyOf(line,count),StandardOpenOption.CREATE,StandardOpenOption.APPEND);
                System.out.println("READY");System.out.flush();
                try{Thread.sleep(30000);}catch(InterruptedException e){Thread.currentThread().interrupt();}
                throw new IOException("probe was not killed at append boundary");
            }
        };
        trace.write("STARTED",Map.of());
        trace.write("LARGE",Map.of("payload","x".repeat(32768)));
    }
}
