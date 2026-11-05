package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded original observations, encoded per change rather than as one wire message. */
final class V53ResourceTraceFiles {
    static final int MAXIMUM=128*1024*1024;
    static Map<String,Object> usage(MembershipResources.Usage value) {
        var counts=new TreeMap<String,Object>();value.counts().forEach((unit,count)->counts.put(unit.name(),count));
        return Map.of("metadata",value.metadata(),"staging",value.staging(),"queued",value.queued(),"leases",value.leases(),"counts",counts);
    }
    private static Map<String,Object> charge(MembershipResourceObservations.Charge value) {
        return Map.of("unit",value.unit().name(),"owner",value.owner(),"bytes",value.bytes(),"claimSource",value.claimSource());
    }
    private static Map<String,Object> change(MembershipResourceObservations.Change row) {
        return Map.of("sequence",row.sequence(),"event",row.event(),"removed",row.removed().stream().map(V53ResourceTraceFiles::charge).toList(),
                "added",row.added().stream().map(V53ResourceTraceFiles::charge).toList(),"usage",usage(row.usage()));
    }
    static String write(Path path,MembershipResourceObservations.Snapshot value)throws IOException {
        var fields=new TreeMap<String,Object>(Map.of("schema","gse-v53-resource-transitions-v1",
                "metadataLimit",value.metadataLimit(),"stagingLimit",value.stagingLimit(),"queueLimit",value.queueLimit(),
                "transitions",value.transitions(),"truncated",value.truncated(),"failed",value.failed(),"current",usage(value.current())));
        fields.put("changes",true);
        require(value.changes().size()<=MembershipResourceObservations.MAXIMUM,"resource trace row capacity");
        try(var out=new Writer(path)) {
            out.punctuation('{');boolean fieldFirst=true;
            for(var field:fields.entrySet()) {
                if(!fieldFirst)out.punctuation(',');fieldFirst=false;
                out.bytes(canonical(field.getKey(),256));out.punctuation(':');
                if(!field.getKey().equals("changes")){out.bytes(canonical(field.getValue(),4096));continue;}
                out.punctuation('[');boolean rowFirst=true;
                for(var row:value.changes()) {
                    if(!rowFirst)out.punctuation(',');rowFirst=false;out.bytes(canonical(change(row),512*1024));
                }
                out.punctuation(']');
            }
            out.punctuation('}');return out.digest();
        }
    }
    private static final class Writer implements AutoCloseable {
        final OutputStream output;final MessageDigest digest;int bytes;
        Writer(Path path)throws IOException {
            try{digest=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException error){throw new AssertionError(error);}
            output=new BufferedOutputStream(Files.newOutputStream(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE));
        }
        void bytes(byte[] value)throws IOException {
            require(value.length<=MAXIMUM-bytes,"resource trace byte capacity");output.write(value);digest.update(value);bytes+=value.length;
        }
        void punctuation(int value)throws IOException {bytes(new byte[]{(byte)value});}
        String digest(){return HexFormat.of().formatHex(digest.digest());}
        @Override public void close()throws IOException{output.close();}
    }
}
