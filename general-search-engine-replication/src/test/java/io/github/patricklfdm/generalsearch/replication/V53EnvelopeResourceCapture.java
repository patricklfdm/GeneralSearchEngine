package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original per-open budgets and publication files for the conditional continuation.
 * No reservation, receiving lifetime or production limit is changed. */
final class V53EnvelopeResourceCapture {
    record Opened(MembershipGrantJournal journal,V53EnvelopeResourceCapture capture,String scope,Path replica) implements AutoCloseable {
        @Override public void close()throws IOException {
            if(capture==null)journal.close();else capture.closeOwner(scope,replica,journal);
        }
    }
    private record Owner(String scope,String node,String operation,MembershipResources budget) {}
    private final Path directory;
    private final String root;
    private final List<Owner> owners=new ArrayList<>();
    private final List<Map<String,Object>> events=new ArrayList<>(),boundaries=new ArrayList<>();
    private final V53PublicationResourceCapture publication;
    private final Set<String> closing=new HashSet<>();
    private boolean saved;
    V53EnvelopeResourceCapture(Path output,String root)throws IOException {
        directory=Files.createDirectory(output.resolve("completion-resources"));this.root=root;
        publication=new V53PublicationResourceCapture(output);
    }
    String register(String node,String operation,MembershipResources budget) {
        require(!saved && owners.size()<1024 && budget.usage().leases()==0,"completion resource original registration");
        var point=budget.observationCheckpoint();require(point.complete() && point.sequence()==0,"completion resource empty start");
        String scope=String.format(Locale.ROOT,"open-%04d",owners.size());owners.add(new Owner(scope,node,operation==null?"":operation,budget));
        return scope;
    }
    void event(String scope,String event,Path replica)throws IOException {
        require(!saved && events.size()<65536,"completion resource event bound");
        Owner owner=owners.get(owners.size()-1);require(owner.scope.equals(scope),"completion resource sequential owner");
        var point=owner.budget.observationCheckpoint();require(point.complete(),"completion resource incomplete observations");
        int index=events.size();events.add(Map.of("node",owner.node,"scope",scope,"event",event));
        boundaries.add(Map.of("eventIndex",index,"sequence",point.sequence(),"usage",V53ResourceTraceFiles.usage(point.usage())));
        publication.at(owner.node,scope,replica,owner.budget,event,index);
    }
    void closeOwner(String scope,Path replica,MembershipGrantJournal journal)throws IOException {
        Owner owner=owners.getLast();
        require(!saved && owner.scope.equals(scope) && owner.node.equals(journal.activationIdentity().nodeId().value()) &&
                !closing.contains(scope),"completion resource original close owner");
        journal.activationContext(); // Reject an already closed journal before recording an invocation.
        closing.add(scope);event(scope,"RESOURCE_OWNER_CLOSE_BEGIN",replica);
        journal.close(); // Failure deliberately leaves no successful-return marker.
        event(scope,"RESOURCE_OWNER_CLOSE_RETURNED",replica);
    }
    void save()throws IOException {
        require(!saved && !owners.isEmpty(),"completion resource already saved/empty");saved=true;
        var refs=new ArrayList<Map<String,Object>>();
        for(var owner:owners) {
            String file=owner.scope+".json";String digest=V53ResourceTraceFiles.write(directory.resolve(file),owner.budget.observations());
            refs.add(Map.of("scope",owner.scope,"node",owner.node,"operation",owner.operation,"path",file,"sha256",digest));
        }
        byte[] originalEvents=V53EvidenceArray.encode(events,32*1024*1024),points=V53EvidenceArray.encode(boundaries,32*1024*1024);
        Files.write(directory.resolve("events.json"),originalEvents,StandardOpenOption.CREATE_NEW);
        Files.write(directory.resolve("boundaries.json"),points,StandardOpenOption.CREATE_NEW);
        Files.write(directory.resolve("index.json"),canonical(Map.of("schema","gse-v53-completion-resources-v2","root",root,
                "owners",refs,"eventsSha256",hash(originalEvents),"boundariesSha256",hash(points)),1024*1024),StandardOpenOption.CREATE_NEW);
        publication.save();
    }
}
