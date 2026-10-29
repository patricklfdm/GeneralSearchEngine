package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Fixed projection of original placement, never a caller-supplied delete list. */
final class MembershipLearnerJoinedRetirementPlan {
    final Map<String,Path> roots;
    final List<?> inventory;
    final List<Map<String,Object>> deletions;
    final List<Path> locks;
    MembershipLearnerJoinedRetirementPlan(MembershipLearnerPlan summary)throws IOException {
        roots=MembershipLearnerCustody.roots(summary);inventory=MembershipLearnerPlacement.placedOriginalInventory(summary);
        var joined=object(parse(AdmissionPaths.read(MembershipLearnerPlacement.directory(summary).resolve(MembershipLearnerJoinedAdmission.FILE),
                MembershipLearnerJoinedAdmission.MAXIMUM),MembershipLearnerJoinedAdmission.MAXIMUM));
        var receipt=decode(MembershipBootstrapPlanData.unbase(joined.get("receipt"),16384),"records","LEARNER");
        Path typed=MembershipLearnerPlacement.typedOriginal(summary,receipt);
        var deletes=new ArrayList<Map<String,Object>>();var locked=new ArrayList<Path>();int count=0;
        for(Object raw:inventory) {
            var row=object(raw);String root=(String)row.get("name");if(!Boolean.TRUE.equals(row.get("present")))continue;
            var files=files(row);var keep=new HashSet<String>();keep.add(".");
            for(var file:files.entrySet()) {
                require(++count<=512,"joined retirement original inventory capacity");
                String name=file.getKey();var identity=object(file.getValue());boolean directory=Boolean.TRUE.equals(identity.get("directory"));
                if(!directory && name.endsWith(".lock") && number(identity.get("size"))==0) {
                    keep.add(name);locked.add(roots.get(root).resolve(name));
                }
                if(root.equals("replica") && !name.equals("learner") && !name.startsWith("learner/") && !name.equals(MembershipLearnerStore.ADMISSION))keep.add(name);
                if(roots.get(root).equals(typed) && Set.of(MembershipLearnerMaterialization.PLAN,MembershipLearnerMaterialization.RECEIPT).contains(name))keep.add(name);
            }
            for(String name:new ArrayList<>(keep))for(Path parent=Path.of(name).getParent();parent!=null;parent=parent.getParent())keep.add(parent.toString());
            var discarded=new HashSet<String>(files.keySet());discarded.removeAll(keep);
            for(String name:discarded)deletes.add(Map.of("root",root,"name",name));
        }
        deletes.sort(Comparator.<Map<String,Object>,String>comparing(v->(String)v.get("root"))
                .thenComparing(Comparator.comparingInt((Map<String,Object> v)->Path.of((String)v.get("name")).getNameCount()).reversed())
                .thenComparing(v->(String)v.get("name")));
        deletions=List.copyOf(deletes);locks=List.copyOf(locked);
        require(!deletions.isEmpty() && locks.contains(summary.request().replicaDirectory().resolve("replica.lock")),"joined retirement original lock inventory");
    }
    static TreeMap<String,Object> files(Map<String,Object> row) {
        var result=new TreeMap<String,Object>();for(Object raw:list(row.get("files"))){var f=object(raw);result.put((String)f.get("name"),f.get("identity"));}return result;
    }
    Path path(Map<String,Object> deletion)throws IOException {return AdmissionPaths.safe(roots.get((String)deletion.get("root")).resolve((String)deletion.get("name")));}
    int project()throws IOException {
        int prefix=0;boolean present=false;var deleted=new HashMap<String,Set<String>>();
        for(var entry:deletions) {
            if(Files.exists(path(entry),LinkOption.NOFOLLOW_LINKS)){present=true;continue;}
            require(!present,"joined retirement nonprefix deletion");prefix++;
            deleted.computeIfAbsent((String)entry.get("root"),k->new HashSet<>()).add((String)entry.get("name"));
        }
        var expected=new ArrayList<Object>();
        for(Object raw:inventory) {
            var row=new TreeMap<>(object(raw));
            if(Boolean.TRUE.equals(row.get("present"))) {
                var entries=new ArrayList<Object>();for(Object value:list(row.get("files")))
                    if(!deleted.getOrDefault((String)row.get("name"),Set.of()).contains(object(value).get("name")))entries.add(value);
                row.put("files",entries);
            }
            expected.add(row);
        }
        require(expected.equals(MembershipLearnerCustody.capture(roots,null)),"joined retirement original inventory changed");return prefix;
    }
    /** Cold accounting must cover the entire original group, including payloads
     * already deleted. Never derive a smaller reservation from today's disk. */
    void accounting(List<?> rows) {
        require(rows.size()<=32,"joined retirement reservation count");
        var counts=new EnumMap<MembershipResources.Unit,Integer>(MembershipResources.Unit.class);
        var images=new ArrayList<Long>();long metadata=0;
        String previous="";long previousBytes=-1;
        for(Object raw:rows) {
            var row=object(raw);require(row.keySet().equals(Set.of("unit","bytes")),"joined retirement reservation shape");
            var unit=MembershipResources.Unit.valueOf((String)row.get("unit"));long bytes=number(row.get("bytes"));String name=unit.name();
            require(bytes>0 && bytes<=unit.bytes && (name.compareTo(previous)>0 || name.equals(previous) && bytes>=previousBytes),"joined retirement reservation ordering/extent");
            previous=name;previousBytes=bytes;counts.merge(unit,1,Integer::sum);
            if(unit==MembershipResources.Unit.APPLICATION)images.add(bytes);else metadata=Math.addExact(metadata,bytes);
        }
        require(counts.keySet().equals(Set.of(MembershipResources.Unit.GENERATION,MembershipResources.Unit.LEARNER,MembershipResources.Unit.MISC,MembershipResources.Unit.APPLICATION))
                && counts.get(MembershipResources.Unit.GENERATION)==2 && counts.get(MembershipResources.Unit.LEARNER)==1 && counts.get(MembershipResources.Unit.MISC)==1
                && images.size()<=MembershipResources.Unit.APPLICATION.count,"joined retirement reservation categories");
        long required=MembershipLearnerCustody.MAXIMUM+2L*MembershipLearnerPlacement.MAXIMUM+MembershipLearnerJoinedAdmission.MAXIMUM
                +MembershipLearnerJoinedRetirement.MAXIMUM+MembershipLearnerJoinedRetirement.DONE_MAXIMUM;
        var imageSizes=new ArrayList<Long>();
        for(Object raw:inventory) {
            var row=object(raw);if(!Boolean.TRUE.equals(row.get("present")))continue;var files=files(row);long backup=0;int backupMembers=0;
            for(var file:files.entrySet()) {
                var identity=object(file.getValue());if(Boolean.TRUE.equals(identity.get("directory")))continue;long size=number(identity.get("size"));
                if(file.getKey().endsWith(".image"))imageSizes.add(size);
                else if(file.getKey().startsWith("backup/") && MembershipApplicationImage.MEMBERS.contains(file.getKey().substring(7))){backup=Math.addExact(backup,size);backupMembers++;}
                else required=Math.addExact(required,size);
            }
            if(backupMembers>0){require(backupMembers==MembershipApplicationImage.MEMBERS.size(),"joined retirement incomplete original image");imageSizes.add(backup+MembershipApplicationImage.OVERHEAD);}
        }
        Collections.sort(images);Collections.sort(imageSizes);
        require(metadata>=required && images.size()>=imageSizes.size(),"joined retirement original reservations undercharged");
        for(int i=1;i<=imageSizes.size();i++)require(images.get(images.size()-i)>=imageSizes.get(imageSizes.size()-i),"joined retirement original image undercharged");
    }
}
