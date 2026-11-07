"""Transport envelope for one explicit segmented-backup replica observation.

This is not a runtime reservation or an assertion that all peaks coexist. The
independent physical and resource readers still establish the actual owners.
Legacy JSON collectors and the whole-original 128 GiB bound are unchanged.
"""
MIB = 1024**2
METADATA_BYTES = 384*MIB
APPLICATION_COUNT = 7
FILE_BYTES = 64*MIB
SNAPSHOT_BYTES = METADATA_BYTES + APPLICATION_COUNT*FILE_BYTES
MEMBERS = 512
DEPTH = 8
