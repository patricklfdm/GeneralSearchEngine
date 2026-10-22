package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Pure next-catalog projection. The owner separately verifies receipts/certificates and forces publication. */
final class MembershipCatalog {
    private MembershipCatalog() { }

    static Decoded project(MembershipContext before,Decoded proposed,byte[] payload,MembershipApplicationReplay.Result application) {
        var entry=decode(proposed.bytes(),"records","ENTRY");var value=entry.value();
        long index=number(value.get("index")),previous=number(before.cut.get("index"));
        require(previous<MAX && index==previous+1 && value.get("previous").equals(before.cut.get("entry"))
                && value.get("root").equals(before.root) && value.get("authority").equals(before.authority()),"catalog entry parent/root/view");
        before.ballot(value.get("origin"),true);
        require(hash(payload).equals(value.get("payload")),"catalog entry payload identity");
        String kind=(String)value.get("kind");Object command=command(kind,payload);before.control(kind,command);
        require(application.index()==index,"catalog application result index");
        String image=hash(application.image());long sequence=number(before.catalog.get("applicationSequence"));
        if(kind.equals("DATA"))require(sequence<MAX && application.sequence()==sequence+1,"catalog DATA sequence");
        else require(application.sequence()==sequence && image.equals(before.catalog.get("application")),"catalog control changed application");

        var result=new TreeMap<>(before.catalog);var view=new TreeMap<>(before.view);
        var rows=new ArrayList<Map<String,Object>>();
        for(var row:list(result.get("results")))rows.add(new TreeMap<>(object(row)));
        Map<String,Object> active=null;
        for(var row:rows)if(Objects.equals(object(row.get("request")).get("number"),result.get("active")))active=row;
        Map<String,Object> args=kind.equals("DATA")||kind.equals("BARRIER")?Map.of():object(command);
        switch(kind) {
            case "DATA" -> {result.put("application",image);result.put("applicationSequence",application.sequence());result.put("lastDataIndex",index);}
            case "BARRIER" -> { }
            case "RESERVE" -> {
                var request=object(args.get("request"));long operation=number(request.get("number"));
                var row=new TreeMap<String,Object>();row.put("request",request);row.put("revision",0L);row.put("phase","RESERVED");
                row.put("prepared",null);row.put("receipt",null);row.put("binding",null);row.put("terminalIndex",null);rows.add(row);
                result.put("active",operation);result.put("nextOperation",operation+1);
                var identities=new TreeMap<String,Map<String,Object>>();
                for(var id:list(result.get("identities")))identities.put((String)object(id).get("node"),object(id));
                for(var id:list(request.get("target")))identities.put((String)object(id).get("node"),object(id));
                result.put("identities",new ArrayList<>(identities.values()));
            }
            case "PREPARE" -> {
                active.put("revision",args.get("revision"));active.put("phase","PREPARING");active.put("receipt",null);
                active.put("prepared",Map.of("revision",args.get("revision"),"cut",before.cut,
                        "catalog",hash(encode("records","CATALOG",before.catalog)),"application",before.catalog.get("application")));
            }
            case "READY" -> {active.put("phase","READY");active.put("receipt",args.get("receipt"));}
            case "SEAL" -> {
                var sealed=new TreeMap<String,Object>();for(String key:List.of("request","prepared","receipt"))sealed.put(key,active.get(key));
                active.put("phase","SEALED");active.put("binding",hash(canonical(sealed,8192)));
            }
            case "INTENT" -> {
                active.put("phase","JOINT");view.put("new",targets(active));view.put("operation",active.get("binding"));
            }
            case "FINAL" -> {
                active.put("phase","COMPLETED");active.put("terminalIndex",index);result.put("active",null);
                view.put("old",targets(active));view.put("new",targets(active));view.put("operation",null);
                require(number(view.get("generation"))<256,"catalog generation capacity");view.put("generation",number(view.get("generation"))+1);
            }
            case "CANCEL" -> {active.put("phase","CANCELLED");active.put("terminalIndex",index);result.put("active",null);}
            case "RETIRE" -> {long through=number(args.get("through"));rows.removeIf(row->number(object(row.get("request")).get("number"))<=through);result.put("retiredThrough",through);}
            default -> throw new IllegalArgumentException("catalog command kind");
        }
        result.put("results",rows);result.put("cut",Map.of("entry",entry.digest(),"index",index,"view",view));
        return decode(encode("records","CATALOG",result),"records","CATALOG");
    }
    private static List<String> targets(Map<String,Object> operation) {
        return list(object(operation.get("request")).get("target")).stream().map(MembershipFormat::object).map(row->(String)row.get("node")).toList();
    }
}
