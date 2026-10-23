package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact plan metadata without retaining or verifying application bytes. This is
 * not a committed receipt, admission seal, typed reader or ownership authority. */
final class MembershipBootstrapPlanMetadata {
    final MembershipBootstrapLayout layout;
    final long maximumSource,maximumOperation;
    private final byte[] bytes;
    private final Map<String,Object> descriptor;
    MembershipBootstrapPlanMetadata(byte[] supplied) {
        require(supplied.length>48 && supplied.length<=MembershipBootstrapPlanData.MAXIMUM,"bootstrap plan capacity");bytes=supplied.clone();
        var input=ByteBuffer.wrap(bytes);require(input.getInt()==MembershipBootstrapPlanData.MAGIC && input.getShort()==1 && input.getShort()==3 && input.getShort()==1 && input.getShort()==0
                && input.getInt()==bytes.length-48,"bootstrap plan header");
        byte[] digest=new byte[32];input.get(digest);byte[] body=Arrays.copyOfRange(bytes,48,bytes.length);
        require(Arrays.equals(digest,sha(Arrays.copyOf(bytes,16),body)),"bootstrap plan checksum");
        var value=object(parse(body,MembershipBootstrapPlanData.MAXIMUM-48));require(Arrays.equals(body,canonical(value,MembershipBootstrapPlanData.MAXIMUM-48)),"bootstrap plan noncanonical body");
        require(value.keySet().equals(Set.of("schema","root","genesis","application","descriptor","maximumSource","maximumOperation","targets"))
                && value.get("schema").equals("gse-v53-bootstrap-plan/1.3"),"bootstrap plan fields");
        maximumSource=number(value.get("maximumSource"));maximumOperation=number(value.get("maximumOperation"));require(maximumSource>0 && maximumOperation>0,"bootstrap plan budgets");
        var image=object(value.get("application"));require(image.keySet().equals(Set.of("bytes","sha256")),"bootstrap plan image metadata");
        var root=decode(MembershipBootstrapPlanData.unbase(value.get("root"),16384),"records","ROOT");
        var genesis=decode(MembershipBootstrapPlanData.unbase(value.get("genesis"),65536),"records","GENESIS");layout=new MembershipBootstrapLayout(root,genesis,number(image.get("bytes")));
        require(layout.application.equals(image.get("sha256")),"bootstrap plan declared image identity");
        descriptor=object(parse(canonical(value.get("descriptor"),1024*1024),1024*1024));
        require(descriptor.keySet().equals(Set.of("application","core","paths","source","sourceInventory","identities")),"bootstrap retained descriptor keys");
        var core=object(descriptor.get("core"));var config=object(descriptor.get("application"));
        require(root.value().get("codecId").equals(core.get("codecId")) && number(root.value().get("codecVersion"))==number(core.get("codecVersion"))
                && root.value().get("schema").equals(hash(canonical(Map.of("schemaIdentity",core.get("schemaIdentity"),"application",config),1024*1024)))
                && root.value().get("indexes").equals(hash(canonical(config.get("indexes"),262144))),"bootstrap retained application descriptor binding");
        require(descriptor.get("identities").equals(root.value().get("initial")) && descriptor.get("source").equals(genesis.value().get("source")),"bootstrap retained identity/source binding");
        var inventory=list(descriptor.get("sourceInventory"));boolean empty=descriptor.get("source").equals("EMPTY");
        require(empty?inventory.isEmpty():inventory.size()==3 && hash(canonical(inventory,65536)).equals(genesis.value().get("sourceDigest")),"bootstrap retained source inventory binding");
        long sourceBytes=0;
        for(int n=0;n<inventory.size();n++) {
            var row=object(inventory.get(n));require(row.keySet().equals(Set.of("path","kind","size","sha256")) && row.get("path").equals(MembershipApplicationImage.MEMBERS.get(n))
                    && number(row.get("kind"))==1 && number(row.get("size"))>0,"bootstrap retained source member");MembershipValidation.digest((String)row.get("sha256"));sourceBytes=Math.addExact(sourceBytes,number(row.get("size")));
        }
        require(sourceBytes<=maximumSource && sourceBytes<=MembershipApplicationImage.MAXIMUM-MembershipApplicationImage.OVERHEAD,"bootstrap plan source bound");
        var paths=list(descriptor.get("paths"));require(paths.size()==(empty?1:2)+2*layout.identities.size(),"bootstrap retained path count");var names=new ArrayList<Path>();
        for(var v:paths) {
            var binding=object(v);require(binding.keySet().equals(Set.of("path","parentRealPath","fileStoreName","fileStoreType","parentFileKey")),"bootstrap plan binding fields");
            for(Object field:binding.values())require(field instanceof String && !((String)field).isEmpty() && ((String)field).getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=4096,"bootstrap plan binding string");
            require(!((String)binding.get("fileStoreName")).isBlank() && !((String)binding.get("fileStoreType")).isBlank(),"bootstrap plan filesystem identity");
            Path path=Path.of((String)binding.get("path"));require(path.isAbsolute() && path.toString().equals(binding.get("path")) && path.normalize().equals(path) && path.getParent()!=null
                    && path.getParent().toString().equals(binding.get("parentRealPath")),"bootstrap plan canonical path binding");names.add(path);
        }
        MembershipValidation.disjoint(names);var targets=new ArrayList<Map<String,Object>>();long payload=0;
        for(var local:layout.identities) {
            var files=layout.inventory(local);targets.add(Map.of("identity",MembershipBootstrapSeed.identity(local),"directories",MembershipBootstrapSeed.directories().stream().sorted().toList(),"files",files));
            for(var file:files)payload=Math.addExact(payload,number(file.get("bytes")));
        }
        require(value.get("targets").equals(targets),"bootstrap plan exact target inventory");
        require(2L*bytes.length+layout.imageBytes<=maximumOperation && payload<=maximumOperation-layout.imageBytes-2L*bytes.length,"bootstrap plan completion capacity");
    }
    byte[] bytes(){return bytes.clone();}
    String digest(){return hash(bytes);}
    Map<String,Object> descriptor(){return object(parse(canonical(descriptor,1024*1024),1024*1024));}
    List<Map<String,Object>> bindings(){return list(descriptor().get("paths")).stream().map(MembershipFormat::object).toList();}
    Path operation(){return AdmissionConfiguration.path(bindings().getFirst());}
    MembershipBootstrapPlan summary(){var paths=bindings();int begin=layout.genesis.value().get("source").equals("EMPTY")?1:2;
        return new MembershipBootstrapPlan(digest(),layout.identity.groupId(),paths.subList(begin,paths.size()).stream().map(AdmissionConfiguration::path).toList(),operation());}
}
