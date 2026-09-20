package fixture.v51;

import java.lang.reflect.*;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;
import java.util.*;
import java.util.jar.JarFile;

/** Separate class loaders prevent a locally installed artifact from becoming the old control. */
public final class PublishedApiCheck {
    static boolean visible(int modifiers) { return Modifier.isPublic(modifiers) || Modifier.isProtected(modifiers); }
    static void inspect(Class<?> c, Set<String> out) throws Exception {
        if (!visible(c.getModifiers())) return;
        out.add("type " + c.toGenericString());
        if(c.getGenericSuperclass()!=null) out.add("super "+c.getName()+" "+c.getGenericSuperclass().getTypeName());
        for(var i:c.getGenericInterfaces()) out.add("interface "+c.getName()+" "+i.getTypeName());
        for(var v:c.getDeclaredConstructors()) if(visible(v.getModifiers())&&!v.isSynthetic()) out.add(v.toGenericString());
        for(var v:c.getDeclaredMethods()) if(visible(v.getModifiers())&&!v.isSynthetic()&&!v.isBridge()) out.add(v.toGenericString());
        for(var v:c.getDeclaredFields()) if(visible(v.getModifiers())&&!v.isSynthetic()) {
            String value="";
            if(Modifier.isStatic(v.getModifiers())&&Modifier.isFinal(v.getModifiers())&&(v.getType().isPrimitive()||v.getType()==String.class)) value="="+v.get(null);
            out.add(v.toGenericString()+value);
        }
        if(c.isRecord()) for(var v:c.getRecordComponents()) out.add("component "+c.getName()+" "+v.getName()+" "+v.getGenericType().getTypeName());
        if(c.isEnum()) out.add("enum "+c.getName()+" "+Arrays.toString(c.getEnumConstants()));
        for(var n:c.getDeclaredClasses()) inspect(n,out);
    }
    static Set<String> inventory(Path core,Path replication) throws Exception {
        var result=new TreeSet<String>();
        try(var loader=new URLClassLoader(new URL[]{core.toUri().toURL(),replication.toUri().toURL()},ClassLoader.getPlatformClassLoader())) {
            for(var path:List.of(core,replication))try(var jar=new JarFile(path.toFile())) {
                for(var entry:jar.stream().filter(e->e.getName().endsWith(".class")&&!e.getName().contains("$")&&!e.getName().endsWith("package-info.class")).toList()) {
                    String name=entry.getName().replace('/','.').replaceAll("\\.class$","");
                    inspect(Class.forName(name,false,loader),result);
                }
            }
        }
        return result;
    }
    public static void main(String[] args) throws Exception {
        var old=inventory(Path.of(args[0]),Path.of(args[1]));var current=inventory(Path.of(args[2]),Path.of(args[3]));
        var missing=new TreeSet<>(old);missing.removeAll(current);
        if(!missing.isEmpty()) throw new AssertionError("Published V5.0 declarations changed: "+missing);
        System.out.println("v51PublishedApi=PASS preservedDeclarations="+old.size()+" additiveDeclarations="+(current.size()-old.size()));
    }
}
