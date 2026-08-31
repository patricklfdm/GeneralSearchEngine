# Travel search example

This processor-free example uses runtime annotations and only supported public APIs.
It demonstrates structured search, V3 ranked TEXT with a filter, cross-field
BOOL/BOOST composition, exact PHRASE, V3.1 ordered phrase slop and
`minimumShouldMatch`, FUZZY typo correction, Explain, V3.2 snapshot-bound structured
highlighting, V3.3 strict search-after with exact totals, atomic bulk insertion, and
the create/drop lifecycle of a dynamic range index. The pagination example consumes
two pages from one unchanged snapshot; its opaque cursor is not serialized or reused
after publication. Highlight output is plain source text plus absolute UTF-16 spans;
presentation markup remains the consumer's responsibility.

From the repository root, build and run it with one command:

```bash
bash scripts/run-travel-example.sh
```

The script builds the core and example modules directly from the checkout; a prior
local install is not required.
