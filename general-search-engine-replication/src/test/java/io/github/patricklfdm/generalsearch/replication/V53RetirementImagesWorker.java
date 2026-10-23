package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** The existing actual retirement worker, with one additional retained original source. */
public final class V53RetirementImagesWorker {
    public static void main(String[] args)throws Exception {
        if(!args[0].equals("init")){V53RetirementWorker.main(args);return;}
        Path path=Path.of(args[1]);int size=Integer.parseInt(args[2]),through=Integer.parseInt(args[3]);
        V53RetirementWorker.provision(path,size,through);Path baseline=path.getParent().resolve("baseline");
        try(var walk=Files.walk(path)){for(Path file:walk.toList()) {
            Path target=baseline.resolve(path.relativize(file));
            if(Files.isDirectory(file))Files.createDirectories(target);else Files.copy(file,target);
        }}
        var fixture=new V53CurrentGenerationFixture(size,through,false);var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openRetirement(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,event->{})) {
            owner.prepareCurrent(fixture.fixture.source.ballot(101));
        }
        if(resources.usage().leases()!=0)throw new IllegalStateException("retirement image setup leaked resources");
        System.out.println(new String(canonical(Map.of("command","init","status","PASS"),16384),java.nio.charset.StandardCharsets.US_ASCII));
    }
}
