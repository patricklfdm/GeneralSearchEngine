package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.function.IntSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.canonical;

/** Observe the real owner's recovery before starting a replacement endpoint.
 * Snapshots are evidence only; recovery never opens these copied directories. */
final class V53JointFloorScratch {
    static final String SCHEMA="gse-v53-joint-floor-scratch-recovery-v1";
    static void recover(MembershipGrantJournal owner,MembershipResources budget,Path scratch,Path authority,
            Path evidence,IntSupplier eventCount)throws IOException {
        Files.createDirectory(evidence);Files.createDirectory(evidence.resolve("states"));
        var rows=new ArrayList<Map<String,Object>>();var discarded=new TreeMap<String,Object>();boolean success=false;
        try {
            for(var role:List.of(MembershipScratch.Role.INCOMING,MembershipScratch.Role.OUTGOING)) {
                Path path=scratch.resolve(role.name().toLowerCase(Locale.ROOT));
                MembershipScratch.Events capture=event->{
                    String state=String.format(Locale.ROOT,"%03d",rows.size());
                    copy(path,evidence.resolve("states/"+state));
                    rows.add(Map.of("role",role.name(),"event",event,"state",state,"eventCount",eventCount.getAsInt(),
                        "usage",V53CombinedReceiveResourcesTest.usage(budget),"authority",authority(authority)));
                };
                capture.at("BEFORE_OPEN");
                try(var scope=owner.openScratch(path,role,budget,capture)) {
                    discarded.put(role.name(),scope.recovered().stream().map(d->Map.of("path",d.path(),"directory",d.directory(),"bytes",d.bytes())).toList());
                    capture.at("OPEN_RETURN");
                }
                capture.at("CLOSED");
            }
            success=true;
        }finally {
            Files.write(evidence.resolve("recovery.json"),canonical(Map.of("schema",SCHEMA,"status",success?"PARTIAL":"FAIL",
                "paths",Map.of("scratch",scratch.toString(),"replica",authority.toString()),"rows",rows,"discarded",discarded,
                "processDeathQualified",false,"phase3Complete",false),16*1024*1024));
        }
    }
    static List<Map<String,String>> authority(Path path)throws IOException {
        return V53ReplayFilesTest.files(path).entrySet().stream().map(row->Map.of("path",row.getKey(),"sha256",row.getValue())).toList();
    }
    static void copy(Path source,Path target)throws IOException {
        try{V53JournalApplicationTest.copy(source,target);}
        catch(IOException e){throw e;}
        catch(Exception e){throw new IOException(e);}
    }
}
