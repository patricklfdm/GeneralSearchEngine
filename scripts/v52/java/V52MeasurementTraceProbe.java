package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Exercises the actual writer and interrupted reference append, without replicas. */
public final class V52MeasurementTraceProbe {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]),path=root.resolve("node-1-trace.jsonl");
        String mode=args[1];int generation=Integer.parseInt(args[2]);
        var manifest=new AutomaticRecords.Record("MANIFEST",Map.of("groupId","measurement-trace-probe"),new byte[48]);
        if(mode.equals("limits")) {
            System.out.println(new String(AutomaticRecords.canonical(Map.of(
                    "raw_line",V52MeasurementTrace.RAW_LINE,"encoded_line",V52MeasurementTrace.ENCODED_LINE,
                    "decoded_bytes",V52MeasurementTrace.DECODED_BYTES,"encoded_bytes",V52MeasurementTrace.ENCODED_BYTES,
                    "chunk_bytes",V52MeasurementTrace.CHUNK_BYTES,"chunks",V52MeasurementTrace.MAX_CHUNKS,
                    "rows",V52MeasurementTrace.MAX_ROWS,"chunk_size",V52MeasurementTrace.CHUNK,"inline",V52MeasurementTrace.INLINE)),java.nio.charset.StandardCharsets.US_ASCII));
            return;
        }
        if(mode.equals("restart-bound")) {
            // Invalid synthetic references exercise only cumulative writer admission.
            // These are never decoded or represented as physical observations.
            Files.writeString(path,"{\"encoding\":\"gse-v52-chunk-trace-v1\",\"bytes\":4194304}\n".repeat(2049));
            try {new V52MeasurementTrace(path,root.resolve("unused-arm"),2,"node-1",manifest);throw new AssertionError("restart budget reset");}
            catch(IOException failure) {if(!failure.getMessage().contains("measurement decoded trace budget"))throw failure;}
            System.out.println("PASS");return;
        }
        if(mode.equals("bounds")) {
            var trace=new V52MeasurementTrace(path,root.resolve("unused-arm"),1,"node-1",manifest);
            for(int i=0;i<2;i++) {
                try {trace.write("OVERSIZE",Map.of("payload","x".repeat(V52MeasurementTrace.RAW_LINE)));throw new AssertionError("oversize accepted");}
                catch(IOException failure) {if(!failure.getMessage().contains("measurement decoded trace budget"))throw failure;}
            }
            if(Files.exists(path)||Files.exists(root.resolve("node-1-trace.jsonl.pending")))throw new AssertionError("rejected observation appended");
            System.out.println("PASS");return;
        }
        var trace=new V52MeasurementTrace(path,root.resolve("unused-arm"),generation,"node-1",manifest) {
            @Override byte[] encodeLine(byte[] raw) throws IOException {
                Files.write(root.resolve("expected.jsonl"),raw,StandardOpenOption.CREATE,StandardOpenOption.APPEND);
                return super.encodeLine(raw);
            }
            @Override void append(byte[] line) throws IOException {
                if(order!=2||mode.equals("normal")){super.append(line);return;}
                switch(mode) {
                    case "before" -> {}
                    case "partial" -> super.append(Arrays.copyOf(line,line.length/2));
                    case "complete" -> super.append(line);
                    default -> throw new IOException("unknown trace probe boundary");
                }
                System.out.println("READY");System.out.flush();
                try {Thread.sleep(60000);}catch(InterruptedException error){Thread.currentThread().interrupt();}
                throw new IOException("probe not killed");
            }
        };
        var payload=new StringBuilder();for(int i=0;i<4096;i++)payload.append(AutomaticRecords.sha(Integer.toString(i).getBytes(java.nio.charset.StandardCharsets.US_ASCII)));
        trace.write("STARTED",Map.of());
        for(int i=0;i<20;i++)trace.write("LARGE",Map.of("payload",payload.toString(),"suffix",i));
        trace.write("STOPPED",Map.of());
    }
}
