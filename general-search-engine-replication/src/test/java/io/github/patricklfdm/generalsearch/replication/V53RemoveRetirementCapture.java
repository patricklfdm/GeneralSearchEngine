package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Writer-held observations only. The sidecar cannot authorize a runtime action
 * and never changes the original callback trace or owned replica files. */
final class V53RemoveRetirementCapture {
    static final int MAXIMUM_CAPTURES=2048;
    static final String SCHEMA="gse-v53-remove-retirement-capture-v1";
    static final String CARRIED_SCHEMA="gse-v53-carried-retirement-capture-v1";
    static final String PROCESS_SCHEMA="gse-v53-carried-process-retirement-capture-v1";
    static final String FLOOR_SCHEMA="gse-v53-carried-floor-capture-v1";
    static final String PROCESS_FLOOR_SCHEMA="gse-v53-carried-process-floor-capture-v1";
    static final String CAMPAIGN_SCHEMA="gse-v53-carried-campaign-capture-v1";
    static final String PROCESS_CAMPAIGN_SCHEMA="gse-v53-carried-process-campaign-capture-v1";
    static final String VOTE_SCHEMA="gse-v53-carried-vote-capture-v1";
    static final String PROCESS_VOTE_SCHEMA="gse-v53-carried-process-vote-capture-v1";
    static final String COMPLETION_SCHEMA="gse-v53-carried-completion-capture-v1";
    static final String PROCESS_COMPLETION_SCHEMA="gse-v53-carried-process-completion-capture-v1";
    static final String LEDGER_SCHEMA="gse-v53-carried-ledger-capture-v1";
    static final String PROCESS_LEDGER_SCHEMA="gse-v53-carried-process-ledger-capture-v1";
    static final String REPLAY_SCHEMA="gse-v53-carried-replay-capture-v1";
    static final String PROCESS_REPLAY_SCHEMA="gse-v53-carried-process-replay-capture-v1";
    enum Mode { RETIREMENT, FLOOR, CAMPAIGN, VOTE, COMPLETION, LEDGER, REPLAY }
    final Path raw,root;
    private final Mode mode;
    private final Path objects;
    private final Map<String,String> active=new HashMap<>();
    private final Map<String,Integer> previous=new HashMap<>();
    private final Map<String,String> lastPoint=new HashMap<>();
    private long bytes;
    private int count;
    private boolean finished;
    V53RemoveRetirementCapture(Path raw)throws IOException {
        this(raw,raw.resolveSibling("retirement-captures-"+raw.getFileName()));
    }
    V53RemoveRetirementCapture(Path raw,Path directory)throws IOException {
        this(raw,directory,false);
    }
    V53RemoveRetirementCapture(Path raw,Path directory,boolean floorOnly)throws IOException {
        this(raw,directory,floorOnly?Mode.FLOOR:Mode.RETIREMENT);
    }
    V53RemoveRetirementCapture(Path raw,Path directory,Mode mode)throws IOException {
        this.raw=raw;this.mode=Objects.requireNonNull(mode);root=Files.createDirectory(directory);
        objects=Files.createDirectory(root.resolve("objects"));
    }
    synchronized void at(String node,Path replica,String point,int eventIndex)throws IOException {
        boolean floorOnly=mode==Mode.FLOOR,campaign=mode==Mode.CAMPAIGN,vote=mode==Mode.VOTE,completion=mode==Mode.COMPLETION,ledger=mode==Mode.LEDGER,replay=mode==Mode.REPLAY;
        boolean generation=point.startsWith("RETIREMENT_"),source=point.startsWith("SOURCE_RETIREMENT_");
        String campaignKind=campaign?campaignKind(point):null;
        String voteKind=vote?voteKind(point):null;
        String completionKind=completion?completionKind(point,active.get(node)):null;
        String ledgerKind=ledger?ledgerKind(point):null;
        if(replay) {
            if(!point.startsWith("REPLAY_"))return;
        } else if(ledger) {
            if(ledgerKind==null)return;
        } else if(completion) {
            if(completionKind==null)return;
        } else if(vote) {
            if(voteKind==null)return;
        } else if(campaign) {
            if(campaignKind==null || campaignKind.equals("install") && !"install".equals(active.get(node)))return;
        } else if(floorOnly) {
            if(!point.startsWith("FLOOR_") || point.equals("FLOOR_COPY_BEFORE_RETURN"))return;
        } else if(!generation && !source && !(point.startsWith("JOURNAL_ROTATION_") && "source".equals(active.get(node))))return;
        require(!finished && eventIndex>=0 && eventIndex>previous.getOrDefault(node,-1),"REMOVE capture event lifetime");
        String kind=replay?"replay":ledger?ledgerKind:completion?completionKind:vote?voteKind:campaign?campaignKind:floorOnly?(point.startsWith("FLOOR_RELEASE_")?"floor-release":"floor"):(generation?"generation":"source");
        if(replay?point.equals("REPLAY_RESERVED"):ledger?point.endsWith("_BEFORE_WRITE") || Set.of("RETENTION_RECOVERY_ACTIVE_FORCED","FUTURE_RETENTION_RECOVERY_FORCED").contains(point):completion?Set.of("APPLY_VALIDATED","PUBLICATION_VALIDATED").contains(point):vote?point.endsWith("_VALIDATED"):campaign?Set.of("ALLOCATOR_BEFORE_WRITE","PROMISE_BEFORE_WRITE","SELECTED_BEFORE_WRITE").contains(point):
                point.equals(floorOnly?"FLOOR_RESERVED":"RETIREMENT_OLD_FILES_FORCED") ||
                point.equals(floorOnly?"FLOOR_RELEASE_AUTHORITY_CREATED":"SOURCE_RETIREMENT_CREATED")) {
            require(!active.containsKey(node),"REMOVE capture overlapping transaction");active.put(node,kind);
        }
        require(kind.equals(active.get(node)),"REMOVE capture original transaction start");
        require(count<MAXIMUM_CAPTURES,"REMOVE capture count capacity");
        var before=V53GrantCapture.inventory(replica);
        for(var item:before.entrySet()) {
            var identity=object(item.getValue());if(identity.containsKey("directory"))continue;
            byte[] value=AdmissionPaths.read(replica.resolve(item.getKey()),V53GrantCapture.MAXIMUM_FILE);
            require(value.length==number(identity.get("size")) && hash(value).equals(identity.get("sha256")),"REMOVE capture original changed");
            Path target=objects.resolve((String)identity.get("sha256"));
            if(Files.exists(target,LinkOption.NOFOLLOW_LINKS))AdmissionPaths.exact(target,value);
            else {charge(value.length);Files.write(target,value,StandardOpenOption.CREATE_NEW);}
        }
        require(before.equals(V53GrantCapture.inventory(replica)),"REMOVE capture original changed");
        var metadata=new TreeMap<String,Object>();metadata.put("schema",replay?REPLAY_SCHEMA:ledger?LEDGER_SCHEMA:completion?COMPLETION_SCHEMA:vote?VOTE_SCHEMA:campaign?CAMPAIGN_SCHEMA:floorOnly?FLOOR_SCHEMA:SCHEMA);metadata.put("node",node);
        metadata.put("point",point);metadata.put("eventIndex",eventIndex);metadata.put("kind",kind);
        metadata.put("files",before.entrySet().stream().map(e->Map.of("name",e.getKey(),"identity",e.getValue())).toList());
        byte[] encoded=canonical(metadata,1024*1024);charge(encoded.length);
        Files.write(root.resolve(String.format(Locale.ROOT,"capture-%04d.json",++count)),encoded,StandardOpenOption.CREATE_NEW);
        previous.put(node,eventIndex);lastPoint.put(node,point);
        if(campaign && point.equals("SELECTED_BEFORE_RETURN"))active.put(node,"install");
        else if(replay?point.equals("REPLAY_BEFORE_RETURN"):ledger?Set.of("RETENTION_PARENT_FORCED","RETENTION_RECOVERY_PARENT_FORCED","FUTURE_RETENTION_PARENT_FORCED","FUTURE_RETENTION_RECOVERY_PARENT_FORCED").contains(point):completion?Set.of("APPLY_BEFORE_RETURN","PUBLICATION_BEFORE_RETURN").contains(point):vote?point.endsWith("_BEFORE_RETURN"):campaign?Set.of("ALLOCATOR_BEFORE_RETURN","GRANT_BEFORE_RETURN","INSTALL_BEFORE_RETURN").contains(point):
                point.equals(floorOnly?"FLOOR_BEFORE_RETURN":"RETIREMENT_BEFORE_RETURN") ||
                point.equals(floorOnly?"FLOOR_RELEASE_BEFORE_RETURN":"SOURCE_RETIREMENT_BEFORE_RETURN"))active.remove(node);
    }
    static String ledgerKind(String point) {
        for(String phase:List.of("RETENTION","FUTURE_RETENTION")) {
            if(!point.startsWith(phase+"_"))continue;
            String suffix=point.substring(phase.length()+1);
            if(Set.of("BEFORE_WRITE","PREFIX_WRITTEN","WRITTEN","FORCED","CANDIDATE_PARENT_FORCED","RENAMED","PARENT_FORCED",
                    "RECOVERY_PARENT_FORCED").contains(suffix) || suffix.equals(phase.equals("RETENTION")?"RECOVERY_ACTIVE_FORCED":"RECOVERY_FORCED"))
                return phase.equals("RETENTION")?"peer":"future";
        }
        return null;
    }
    private static String completionKind(String point,String active) {
        if(point.startsWith("APPLY_"))return "application";
        if(Set.of("PUBLICATION_VALIDATED","PUBLICATION_SELECTOR_FORCED","PUBLICATION_COVERAGE_VALIDATED",
                "PUBLICATION_RETIRED","PUBLICATION_BEFORE_RETURN").contains(point) || point.startsWith("COVERED_"))return "publication";
        if("publication".equals(active) && point.startsWith("INSTALL_") ||
                "publication".equals(active) && point.startsWith("CURRENT_"))return "publication";
        return null;
    }
    private static String voteKind(String point) {
        for(String phase:List.of("ACCEPT","PROOF","CERTIFICATE"))
            if(point.startsWith(phase+"_") && Set.of("VALIDATED","CANDIDATE_CREATED","PREFIX_WRITTEN","CANDIDATE_WRITTEN",
                    "CANDIDATE_FORCED","CANDIDATE_PARENT_FORCED","RENAMED","PARENT_FORCED","BEFORE_RETURN").contains(point.substring(phase.length()+1)))
                return phase.toLowerCase(Locale.ROOT);
        return null;
    }
    private static String campaignKind(String point) {
        if(point.startsWith("ALLOCATOR_"))return "allocator";
        if(point.startsWith("INSTALL_"))return "install";
        if(Set.of("SELECTED_BEFORE_WRITE","SELECTED_WRITTEN","SELECTED_FORCED","SELECTED_BEFORE_RETURN").contains(point))return "selected";
        if(point.startsWith("PROMISE_") || point.startsWith("CAPTURE_INTENT_") || point.startsWith("BASIS_") ||
                point.startsWith("GRANT_") || point.startsWith("SOURCE_BEFORE_") || point.equals("SOURCE_CREATED") ||
                point.startsWith("SOURCE_PACKET_") || point.startsWith("SOURCE_IMAGE_") ||
                point.startsWith("SOURCE_FILES_") || point.startsWith("SOURCE_DIRECTORY_"))return "grant";
        return null;
    }
    private void charge(long extent) {
        require(extent>=0 && extent<=V53GrantCapture.MAXIMUM_BYTES-bytes,"REMOVE capture aggregate byte capacity");bytes+=extent;
    }
    synchronized void finish(String profile)throws IOException {
        require(Set.of("4-REMOVE","5-REMOVE").contains(profile),"REMOVE capture profile");
        finish(SCHEMA,profile,"transition-round-result.json");
    }
    synchronized void finishCarried(String kind)throws IOException {
        require(Set.of("INTENT","FINAL").contains(kind),"carried capture kind");
        finish(CARRIED_SCHEMA,kind,"carried-transition-result.json");
    }
    synchronized void finishProcess(String history,int life,String terminal,byte[] events)throws IOException {
        MembershipValidation.digest(history);
        boolean voteCut=mode==Mode.VOTE && life==1 && terminal.equals("CUT_PREFIX") && active.size()==1 &&
                Set.of("accept","proof").contains(active.getOrDefault("node-1","")) &&
                (active.get("node-1").toUpperCase(Locale.ROOT)+"_RENAMED").equals(lastPoint.get("node-1"));
        require(!finished && (active.isEmpty() || voteCut) && (life==1 && terminal.equals("CUT_PREFIX") || life==2 && terminal.equals("CLOSED")),
                "process retirement original terminal");
        // INTENT/ACCEPT can die before the first retirement. Empty coverage is
        // explicit and must match the original callback inventory in replay.
        String schema=switch(mode){case RETIREMENT->PROCESS_SCHEMA;case FLOOR->PROCESS_FLOOR_SCHEMA;case CAMPAIGN->PROCESS_CAMPAIGN_SCHEMA;case VOTE->PROCESS_VOTE_SCHEMA;case COMPLETION->PROCESS_COMPLETION_SCHEMA;case LEDGER->PROCESS_LEDGER_SCHEMA;case REPLAY->PROCESS_REPLAY_SCHEMA;};
        Files.write(root.resolve("collection.json"),canonical(Map.of("schema",schema,"root",history,
                "life",life,"pid",ProcessHandle.current().pid(),"terminal",terminal,"eventsSha256",hash(events),
                "captures",count,"storedBytes",bytes),4096),StandardOpenOption.CREATE_NEW);
        finished=true;
    }
    private void finish(String schema,String profile,String resultName)throws IOException {
        require(mode==Mode.RETIREMENT && !finished && active.isEmpty() && count>0,"REMOVE capture incomplete collection");
        byte[] events=AdmissionPaths.read(raw.resolve("events.json"),32*1024*1024);
        byte[] result=AdmissionPaths.read(raw.resolve(resultName),4096);
        byte[] collection=canonical(Map.of("schema",schema,"profile",profile,"eventsSha256",hash(events),
                "resultSha256",hash(result),"captures",count,"storedBytes",bytes),4096);
        Files.write(root.resolve("collection.json"),collection,StandardOpenOption.CREATE_NEW);finished=true;
    }
}
