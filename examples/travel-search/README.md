# Travel search example

This processor-free example uses runtime annotations, structured indexes, analyzed
text, filtered BM25 ranking, atomic bulk insertion, and a dynamic range index.

From the repository root, compile the complete reactor:

```bash
mvn -f reactor/pom.xml clean test
```

Then run the example:

```bash
java -cp target/classes:examples/travel-search/target/classes \
  example.travel.TravelSearchDemo
```

On Windows, replace the classpath separator `:` with `;`.
