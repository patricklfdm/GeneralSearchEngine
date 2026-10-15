package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.V52ReadQueries.*;
import static io.github.patricklfdm.generalsearch.admission.V52MeasurementQueries.*;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Actual published-core replay, one advancing application and one JVM per history. */
public final class V52MeasurementOracle {
    private static String hash(String value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
    }
    private static Doc from(Map<String,Object> value) {
        return new Doc(((Number)value.get("id")).intValue(),(String)value.get("value"));
    }
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]),input=Path.of(args[1]);Files.createDirectory(root);
        if(Files.size(input)>1<<20)throw new IllegalArgumentException("oracle input bound");
        var value=(Map<String,Object>)AdmissionJson.parse(Files.readString(input));
        boolean selected="gse-v52-measurement-query-input-v2".equals(value.get("schema"));
        if(!(selected?value.keySet().equals(Set.of("schema","corpus","updates","requests","offeredOrdinals")):
                value.keySet().equals(Set.of("schema","corpus","updates","requests"))&&"gse-v52-measurement-query-input-v1".equals(value.get("schema"))))
            throw new IllegalArgumentException("oracle input fields");
        var corpus=(List<Map<String,Object>>)value.get("corpus");var updates=(List<Map<String,Object>>)value.get("updates");
        var requests=(List<Map<String,Object>>)value.get("requests");
        if(corpus.size()!=64||updates.size()>180||requests.isEmpty()||requests.size()>4096)throw new IllegalArgumentException("oracle input count");
        if(selected) {
            var ordinals=(List<Object>)value.get("offeredOrdinals");long previous=-1;
            if(ordinals.size()!=updates.size())throw new IllegalArgumentException("oracle selected update count");
            for(int i=0;i<ordinals.size();i++) {
                Object raw=ordinals.get(i);
                if(!(raw instanceof Long)&&!(raw instanceof Integer))throw new IllegalArgumentException("oracle offered ordinal type");
                long ordinal=((Number)raw).longValue();
                if(ordinal<=previous||ordinal>=180)throw new IllegalArgumentException("oracle offered ordinal order");previous=ordinal;
                int id=1+(int)(ordinal%64),revision=1+(int)(ordinal/64);
                var expected=Map.of("id",id,"value","java search memory group "+((id+52)%8)+" item "+id+" revision "+revision);
                if(!AdmissionJson.canonical(updates.get(i)).equals(AdmissionJson.canonical(expected)))throw new IllegalArgumentException("oracle selected update differs from offered ordinal");
            }
        }
        System.err.println("coreSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        int applied=0;long outputBytes=0;long lastSequence=0;String stateHash=null,lastKey="";
        try(var engine=measurementBuilder().buildDurable(V52MeasurementQueries.storage(root.resolve("store")));
            var output=Files.newBufferedWriter(root.resolve("answers.jsonl"),StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW)) {
            engine.addAll(corpus.stream().map(V52MeasurementOracle::from).toList()).join();var view=core(engine);
            for(var request:requests) {
                long sequence=((Number)request.get("sequence")).longValue();String key=(String)request.get("key");
                if(sequence<1||sequence>updates.size()+1||sequence<lastSequence||sequence==lastSequence&&key.compareTo(lastKey)<=0)
                    throw new IllegalArgumentException("oracle sequence/order");
                while(applied<sequence-1)engine.update(from(updates.get(applied++))).join();
                if(engine.currentSequence()!=sequence)throw new IllegalStateException("oracle application sequence");
                if(sequence!=lastSequence)stateHash=hash(AdmissionJson.canonical(Map.of("sequence",sequence,
                        "documents",engine.search(Query.matchAll()).stream().map(V52ReadQueries::doc).toList())));
                var query=(Map<String,Object>)request.get("query");
                if(!key.equals(hash(AdmissionJson.canonical(Map.of("sequence",sequence,"query",query)))))throw new IllegalArgumentException("oracle request hash");
                var row=new LinkedHashMap<String,Object>();row.put("key",key);row.put("sequence",sequence);row.put("query",query);
                row.put("stateSha256",stateHash);row.put("answer",answer(view,query));
                String line=AdmissionJson.canonical(row)+"\n";int bytes=line.getBytes(StandardCharsets.UTF_8).length;
                outputBytes+=bytes;if(bytes>64<<10||outputBytes>32L<<20)throw new IllegalStateException("oracle output bound");
                output.write(line);lastSequence=sequence;lastKey=key;
            }
        }
        System.out.println(AdmissionJson.canonical(Map.of("status","PASS","measured",false,"requests",requests.size(),"updatesApplied",applied,"finalSequence",lastSequence)));
    }
}
