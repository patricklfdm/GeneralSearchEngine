# Travel search example

This processor-free example uses runtime annotations and only supported public APIs.
It demonstrates structured search, V3 ranked TEXT with a filter, cross-field
BOOL/BOOST composition, exact PHRASE, FUZZY typo correction, Explain, atomic bulk
insertion, and the create/drop lifecycle of a dynamic range index.

From the repository root, build and run it with one command:

```bash
bash scripts/run-travel-example.sh
```

The script builds the core and example modules directly from the checkout; a prior
local install is not required.
