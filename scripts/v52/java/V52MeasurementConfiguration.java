package io.github.patricklfdm.generalsearch.admission;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Closed harness configuration; never an arbitrary runtime tuning surface. */
public record V52MeasurementConfiguration(String family,int pendingLimit,int waitTimeoutMillis,int operationTimeoutMillis) {
    private static final String SCHEMA="gse-v52-read-measurement-parameters-v1";
    public V52MeasurementConfiguration {
        if(!(family.equals("M01")&&pendingLimit==64&&waitTimeoutMillis==5000&&operationTimeoutMillis==9600 ||
             family.equals("M02")&&pendingLimit==64&&Set.of(0,1000,5000).contains(waitTimeoutMillis)&&operationTimeoutMillis==9600 ||
             family.equals("M03")&&Set.of(4,65).contains(pendingLimit)&&waitTimeoutMillis==60000&&operationTimeoutMillis==120000))
            throw new IllegalArgumentException("measurement undeclared read parameters");
    }
    public Map<String,Object> value(){return Map.of("schema",SCHEMA,"family",family,"pendingLimit",pendingLimit,
            "waitTimeoutMillis",waitTimeoutMillis,"operationTimeoutMillis",operationTimeoutMillis);}
    private static int integer(Object value) {
        if(!(value instanceof Long n)||n<0||n>120000)throw new IllegalArgumentException("measurement read parameter integer");
        return ((Long)value).intValue();
    }
    @SuppressWarnings("unchecked") public static V52MeasurementConfiguration read(Path root) throws IOException {
        Path path=root.resolve("measurement-options.json");
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS))return new V52MeasurementConfiguration("M01",64,5000,9600);
        if(Files.isSymbolicLink(path)||!Files.isRegularFile(path)||Files.size(path)<=0||Files.size(path)>4096)
            throw new IOException("measurement configuration file bound/type");
        byte[] bytes;
        try(var input=Files.newInputStream(path)){bytes=input.readNBytes(4097);}
        if(bytes.length>4096)throw new IOException("measurement configuration file bound");
        Object parsed=AdmissionJson.parse(new String(bytes,java.nio.charset.StandardCharsets.UTF_8));
        if(!(parsed instanceof Map<?,?> raw)||!raw.keySet().equals(Set.of("schema","family","pendingLimit","waitTimeoutMillis","operationTimeoutMillis"))||
           !SCHEMA.equals(raw.get("schema"))||!(raw.get("family") instanceof String family)||family.equals("M01"))
            throw new IllegalArgumentException("measurement read parameter shape");
        return new V52MeasurementConfiguration(family,integer(raw.get("pendingLimit")),integer(raw.get("waitTimeoutMillis")),integer(raw.get("operationTimeoutMillis")));
    }
}
