package fixture.v52;

import java.lang.reflect.Modifier;
import java.nio.file.*;
import java.util.*;

/** Run and compile only with the immutable published 5.1 JARs. */
public final class LegacyGenerator {
    public static void main(String[] args) throws Exception {
        Class<?> api=Class.forName("io.github.patricklfdm.generalsearch.replication.AutomaticReplicatedSearchEngine");
        var methods=new TreeMap<String,java.lang.reflect.Method>();
        for(var m:api.getMethods())if(Modifier.isAbstract(m.getModifiers())) {
            String key=m.getName()+Arrays.toString(m.getParameterTypes());
            var prior=methods.get(key);
            if(prior==null || prior.getReturnType().isAssignableFrom(m.getReturnType()))methods.put(key,m);
        }
        var text=new StringBuilder("package fixture.v52; public final class LegacyAutomatic implements "+api.getName()+" {\n");
        for(var m:methods.values()) {
            text.append("public ").append(m.getReturnType().getCanonicalName()).append(' ').append(m.getName()).append('(');
            var parameters=m.getParameterTypes();
            for(int i=0;i<parameters.length;i++) {
                if(i>0)text.append(',');text.append(parameters[i].getCanonicalName()).append(" p").append(i);
            }
            text.append(") {throw new AssertionError(\"old method called\");}\n");
        }
        Files.writeString(Path.of(args[0]),text.append("}\n"));
    }
}
