package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Small original deletion inventories. Paths are derived from known formats,
 * never taken from a decision as filesystem commands. */
final class MembershipLearnerFingerprints {
    private MembershipLearnerFingerprints(){}
    static SortedSet<String> typed() {
        var names=new TreeSet<>(List.of(".","preparation.lock","preparation.json","learner.gsr","backup"));
        for(String name:MembershipApplicationImage.MEMBERS)names.add("backup/"+name);return names;
    }
    static SortedSet<String> seed() {
        return new TreeSet<>(List.of(".",MembershipLearnerSuccessor.LOCK,MembershipLearnerSuccessor.PLAN,
                MembershipLearnerSuccessor.SELECTED,MembershipLearnerSuccessor.HEAD,MembershipLearnerRetirement.FILE));
    }
    static void shape(Object value,SortedSet<String> names) {
        var rows=list(value).stream().map(MembershipFormat::object).toList();
        require(rows.stream().allMatch(r->r.keySet().equals(Set.of("path","sha256")) && r.get("sha256") instanceof String
                && ((String)r.get("sha256")).matches("[0-9a-f]{64}"))
                && rows.stream().map(r->(String)r.get("path")).toList().equals(List.copyOf(names)),"learner slot fingerprint paths/fields");
    }
    static List<Map<String,String>> capture(Path directory,SortedSet<String> names,Set<String> optionalRoot,boolean remaining,int maximum)throws IOException {
        AdmissionPaths.safe(directory);if(remaining && !Files.exists(directory,LinkOption.NOFOLLOW_LINKS))return List.of();
        var root=new TreeSet<String>();for(String name:names)if(!name.equals("."))root.add(name.split("/")[0]);
        var actual=children(directory,root.size()+optionalRoot.size());var allowed=new TreeSet<>(root);allowed.addAll(optionalRoot);
        require(allowed.containsAll(actual) && (remaining || actual.containsAll(root)),"learner slot fingerprint inventory");
        for(String top:root)if(names.stream().anyMatch(n->n.startsWith(top+"/")) && actual.contains(top)) {
            var expected=new TreeSet<String>();for(String name:names)if(name.startsWith(top+"/"))expected.add(name.substring(top.length()+1));
            var found=children(directory.resolve(top),expected.size());
            require(remaining?expected.containsAll(found):expected.equals(found),"learner slot fingerprint nested inventory");
        }
        var result=new ArrayList<Map<String,String>>();
        for(String name:names) {
            Path file=name.equals(".")?directory:directory.resolve(name);if(remaining && !Files.exists(file,LinkOption.NOFOLLOW_LINKS))continue;
            Object value;
            if(name.equals(".") || names.stream().anyMatch(n->n.startsWith(name+"/"))) {
                require(Files.isDirectory(AdmissionPaths.safe(file),LinkOption.NOFOLLOW_LINKS),"learner slot fingerprint directory");
                value=Map.of("key",key(file).toString(),"directory",true);
            }else {
                byte[] bytes=AdmissionPaths.read(file,maximum);var original=inspect(file,bytes.length,hash(bytes));
                value=Map.of("key",original.key().toString(),"bytes",original.bytes(),"sha256",original.digest());
            }
            result.add(Map.of("path",name,"sha256",hash(canonical(value,16384))));
        }
        return result;
    }
    static void check(Path directory,SortedSet<String> names,Set<String> optionalRoot,Object originals,boolean remaining,int maximum)throws IOException {
        shape(originals,names);var expected=list(originals).stream().map(MembershipFormat::object).toList();
        var actual=capture(directory,names,optionalRoot,remaining,maximum);
        require(remaining?expected.containsAll(actual):expected.equals(actual),"learner slot original covered members changed");
    }
    static List<Path> removalOrder(Path directory,SortedSet<String> names) {
        var paths=new ArrayList<>(names);paths.sort(Comparator.<String>comparingInt(n->n.equals(".")?0:n.split("/").length).reversed().thenComparing(n->n));
        return paths.stream().map(n->n.equals(".")?directory:directory.resolve(n)).toList();
    }
}
