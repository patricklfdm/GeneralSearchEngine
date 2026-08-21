# GeneralSearchEngine v1 API compatibility

The project maintains a compile-time consumer fixture and key erased JVM descriptor
checks for its supported v1 application API. The fixture runs in the normal test suite
and can also be executed alone:

```bash
mvn clean -Papi-compat test
```

The v1 compatibility surface contains:

- `engine`: `SearchEngine`, `SearchEngineBuilder`, configuration, metrics, stable
  operational exceptions, the Product facade, and the two concrete
  `SnapshotSearchEngine` compatibility constructors;
- `schema`: `Field`, `SearchSchema`, annotation configuration and annotations;
- `query`: the Query factory DSL and built-in query value types;
- `index`: the extension interfaces, built-in definition factories and their declared
  return types;
- `model` and deprecated `filter`: the Product reference model and its temporary
  source-compatibility adapter.

The bitmap, storage, concrete index implementation, benchmark, and test packages are
not part of the v1 application compatibility promise even where a type is currently
public. They remain available for internal composition and advanced experiments, but
may be reorganized before a dedicated low-level SPI is declared.

## Change policy

- Adding a new type, method, overload, enum value, or default behavior that does not
  alter existing calls is allowed in a minor release.
- Removing or narrowing a supported type/member, changing an erased parameter or
  return descriptor, changing generic bounds incompatibly, or removing an enum value
  requires a major release.
- Deprecated Product filters remain callable throughout v1. New code should use
  `Query<T>`; removal is reserved for a later major version.
- Behavior documented in `V1_SEMANTICS.md` is part of the compatibility contract even
  when method descriptors are unchanged.

`V1ApiCompatibilityTest` intentionally allows additive APIs. Its source fixture catches
source-incompatible generic and overload changes, while reflection assertions preserve
the JVM descriptors needed by already-compiled clients. Once version 1.0 is published
to an artifact repository, release verification should additionally compare the built
JAR against that artifact with an artifact-level binary compatibility tool.
