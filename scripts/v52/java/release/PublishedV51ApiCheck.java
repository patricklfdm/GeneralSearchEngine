package fixture.v51;

import java.nio.file.Path;
import java.util.TreeSet;

/** Reuses the existing isolated-classloader inventory with the published 5.1 control. */
public final class PublishedV51ApiCheck {
    public static void main(String[] args) throws Exception {
        var old = PublishedApiCheck.inventory(Path.of(args[0]), Path.of(args[1]));
        var current = PublishedApiCheck.inventory(Path.of(args[2]), Path.of(args[3]));
        var missing = new TreeSet<>(old); missing.removeAll(current);
        if (!missing.isEmpty()) throw new AssertionError("Published V5.1 declarations changed: " + missing);
        System.out.println("v52PublishedApi=PASS preservedDeclarations=" + old.size()
                + " additiveDeclarations=" + (current.size() - old.size()));
    }
}
