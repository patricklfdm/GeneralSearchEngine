package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53RetirementSourceImagesTest {
    @TempDir Path temp;
    record Seed(V53CoveredMinorityTest producer,V53CoveredMinorityTest.Prepared prepared,Path node,Path copy,Path raw,String oldSlot) {}
    Seed seed(String name)throws Exception {
        var producer=new V53CoveredMinorityTest();producer.temp=Files.createDirectory(temp.resolve(name));var p=producer.prepared(4,false);var f=p.f();
        for(var target:f.request.targets())try(var owner=f.open(target,"install-4")){owner.installCurrent(p.installation().sources(),List.of(),p.installation().images());}
        var copies=new ArrayList<MembershipFloor.Copy>();for(var target:f.request.targets())try(var owner=f.open(target,"copy")){copies.add(owner.floorCopyCurrent());}
        var first=f.request.targets().getFirst();try(var owner=f.open(first,"floor")){owner.establishFloor(copies.subList(0,3));}
        Path node=first.replicaDirectory(),copy=temp.resolve(name+"-seed");V53JournalApplicationTest.copy(node,copy);
        String active=(String)decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR").value().get("generation");
        String old=active.equals("a")?"b":"a";assertFalse(Files.exists(node.resolve("retirement")));
        Path raw=Path.of("target/v53-retirement-source-images/run-"+UUID.randomUUID());Files.createDirectories(raw);
        Files.write(f.raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        V53JournalApplicationTest.copy(f.raw,raw.resolve("reference"));V53JournalApplicationTest.copy(node,raw.resolve("initial"));
        System.out.println("v53RetirementSourceImagesEvidence="+raw.toAbsolutePath());return new Seed(producer,p,node,copy,raw,old);
    }
    Map<String,String> protectedBytes(Seed seed)throws Exception {
        var result=new TreeMap<>(V53ReplayFilesTest.files(seed.node()));result.keySet().removeIf(n->n.startsWith("retirement/") || n.startsWith("generations/"+seed.oldSlot()+"/"));return result;
    }
    @Test void exactPinnedSourceSupportsRepeatedInterruptedRetirementWithinSevenImages()throws Exception {
        var seed=seed("interruptions");var points=new ArrayList<>(V53RetirementTest.CUTS);points.remove("RETIREMENT_IMAGE_WRITTEN");points.remove("RETIREMENT_IMAGE_FORCED");points.addAll(V53RetirementImagesTest.BORROW_CUTS);
        points.addAll(List.of("CONTEXT_SOURCE_MEMBER_FORCED","CONTEXT_SOURCE_DIRECTORY_FORCED","CONTEXT_SOURCE_PARENT_FORCED","RETIREMENT_BORROWED_SOURCE_FORCED"));
        var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        for(String point:points) {
            seed.producer().reset(seed.prepared(),seed.copy(),"retirement-previous-"+ordinal++);Path raw=Files.createDirectory(seed.raw().resolve(point));var before=protectedBytes(seed);var budget=new MembershipResources(512*MembershipResources.MIB);var first=new ArrayList<String>();
            try(var owner=seed.producer().open(seed.prepared(),budget,event->{first.add(event);if(event.equals(point))throw new java.io.IOException(point);})) {assertThrows(java.io.IOException.class,owner::retireInactive,point);}
            assertEquals(0,budget.usage().leases());assertEquals(before,protectedBytes(seed));V53JournalApplicationTest.copy(seed.node(),raw.resolve("first"));
            var second=new ArrayList<String>();boolean repeat=Files.exists(seed.node().resolve("retirement/retirement.gsr"));
            if(repeat)try(var owner=seed.producer().open(seed.prepared(),budget,event->{second.add(event);if(event.equals("RETIREMENT_AUTHORITY_RESEALED"))throw new java.io.IOException("again");})) {
                assertThrows(java.io.IOException.class,owner::retireInactive,point);
            }
            assertEquals(0,budget.usage().leases());assertEquals(before,protectedBytes(seed));V53JournalApplicationTest.copy(seed.node(),raw.resolve("second"));
            var resumed=new ArrayList<String>();try(var owner=seed.producer().open(seed.prepared(),budget,resumed::add)) {owner.retireInactive();assertTrue(owner.retireInactive().isEmpty());}
            assertEquals(0,budget.usage().leases());assertEquals(before,protectedBytes(seed));assertFalse(Files.exists(seed.node().resolve("generations/"+seed.oldSlot())));assertFalse(Files.exists(seed.node().resolve("retirement")));
            V53JournalApplicationTest.copy(seed.node(),raw.resolve("final"));Files.write(raw.resolve("events.json"),canonical(Map.of("first",first,"second",second,"final",resumed),1024*1024));rows.add(Map.of("cut",point,"secondInterrupted",repeat,"status","PASS"));
        }
        Files.write(seed.raw().resolve("receipt.json"),canonical(Map.of("status","PASS","cases",rows,"maximumImages",7,"freshProcesses",false),65536));
    }
    @Test void damagedBindingOrBackingNeverRepairsOrReplacesOriginalAuthority()throws Exception {
        var seed=seed("refusals");var budget=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=seed.producer().open(seed.prepared(),budget,e->{if(e.equals("RETIREMENT_PARENT_FORCED"))throw new java.io.IOException("stop");})) {assertThrows(java.io.IOException.class,owner::retireInactive);}
        Path original=temp.resolve("retained");V53JournalApplicationTest.copy(seed.node(),original);var binding=object(parse(Files.readAllBytes(seed.node().resolve("retirement/images.json")),65536));
        assertEquals(MembershipRetirementSourceImages.SCHEMA,binding.get("schema"));int ordinal=0;
        for(String mutation:List.of("missing-binding","changed-binding","wrong-basis","missing-source","changed-source-image")) {
            seed.producer().reset(seed.prepared(),original,"negative-previous-"+ordinal++);Path bound=seed.node().resolve("retirement/images.json");
            if(mutation.equals("missing-binding"))Files.delete(bound);
            else if(mutation.equals("changed-binding"))Files.writeString(bound,"{}");
            else if(mutation.equals("wrong-basis")){var changed=new TreeMap<>(binding);changed.put("basis","0".repeat(64));Files.write(bound,canonical(changed,65536));}
            else {
                String id=(String)seed.prepared().installation().sources().getFirst().basis.value().get("basisId");Path source=seed.node().resolve("sources/"+id);
                if(mutation.equals("missing-source"))Files.delete(source.resolve("source.gscp"));
                else try(var members=Files.list(source)){Files.writeString(members.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow(),"changed");}
            }
            var before=V53ReplayFilesTest.files(seed.node());
            for(int attempt=0;attempt<2;attempt++) {
                assertThrows(Exception.class,()->{try(var owner=seed.producer().open(seed.prepared(),budget,e->{})){owner.retireInactive();}});
                assertEquals(before,V53ReplayFilesTest.files(seed.node()));assertEquals(0,budget.usage().leases());
            }
            V53JournalApplicationTest.copy(seed.node(),seed.raw().resolve(mutation));
        }
    }
    @Test void liveBackingReplacementCannotAuthorizeDeletingOldImage()throws Exception {
        var seed=seed("inode");var budget=new MembershipResources(512*MembershipResources.MIB);
        String id=(String)seed.prepared().installation().sources().getFirst().basis.value().get("basisId");Path image;
        try(var members=Files.list(seed.node().resolve("sources/"+id))){image=members.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow();}
        try(var owner=seed.producer().open(seed.prepared(),budget,e->{if(e.equals("RETIREMENT_DELETE_VALIDATED")) {
            Path replacement=temp.resolve("same-image");Files.copy(image,replacement);Files.move(replacement,image,StandardCopyOption.REPLACE_EXISTING);
        }})) {assertThrows(IllegalArgumentException.class,owner::retireInactive);}
        assertEquals(0,budget.usage().leases());assertTrue(Files.exists(seed.node().resolve("generations/"+seed.oldSlot()+"/generation.gsr")));
        V53JournalApplicationTest.copy(seed.node(),seed.raw().resolve("refused"));
    }

}
