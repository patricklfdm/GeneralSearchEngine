package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import io.github.patricklfdm.generalsearch.admission.AdmissionJson;

/** Closed observer-side M04 fault controls; default consumers have none. */
final class V52MeasurementFaults {
    static final String FILE="measurement-fault.json";
    static final Set<String> NODES=Set.of("node-1","node-2","node-3");
    private final Path root;
    private final String selected;
    final Map<String,Object> configuration;

    @SuppressWarnings("unchecked") V52MeasurementFaults(Path root,String mode) throws IOException {
        this.root=root;Path file=root.resolve(FILE);
        if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS)) {
            if(Files.exists(root.resolve("network-blocks.txt"),LinkOption.NOFOLLOW_LINKS))throw new IOException("measurement undeclared fault controls");
            selected="";configuration=Map.of("enabled",false);return;
        }
        if(!mode.equals("candidate-minimum")||Files.isSymbolicLink(file)||!Files.isRegularFile(file)||Files.size(file)>1024)
            throw new IOException("measurement fault configuration bound/mode");
        Object parsed=AdmissionJson.parse(Files.readString(file));
        if(!(parsed instanceof Map<?,?> values)||!values.keySet().equals(Set.of("schema","case"))||
                !"gse-v52-recovery-fault-v1".equals(values.get("schema"))||
                !Set.of("leader-sigkill-retained-restart","follower-snapshot-carried-token").contains(values.get("case")))
            throw new IOException("measurement fault configuration fields");
        selected=(String)values.get("case");configuration=new LinkedHashMap<>((Map<String,Object>)values);configuration.put("enabled",true);
    }

    boolean blocked(String barrier,Map<String,Object> request) throws IOException {
        Path file=root.resolve("network-blocks.txt");
        if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))return false;
        if(!selected.equals("follower-snapshot-carried-token")||Files.isSymbolicLink(file)||!Files.isRegularFile(file)||Files.size(file)>1024)
            throw new IOException("measurement undeclared/malformed network controls");
        var lines=Files.readAllLines(file);var rules=new HashSet<>(lines);
        if(!lines.isEmpty()) {
            boolean valid=false;
            for(String target:NODES) {
                var cut=new HashSet<String>();for(String a:NODES)for(String b:NODES)if(!a.equals(b)&&(a.equals(target)||b.equals(target)))cut.add(a+" "+b);
                if(lines.size()==4&&rules.equals(cut))valid=true;
            }
            if(!valid)throw new IOException("measurement network controls must be one complete voter cut");
        }
        return (barrier.equals("BEFORE_REQUEST_WRITE")||barrier.equals("AFTER_RESPONSE_READ"))&&
                rules.contains(request.get("sender")+" "+request.get("recipient"));
    }
}
