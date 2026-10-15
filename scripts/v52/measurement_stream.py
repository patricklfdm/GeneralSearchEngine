"""Repeatable negative views; mutate one decoded row, never materialize a trace."""
import copy
from .evidence import need


class ChangedRow:
    def __init__(self,source,identity,change):
        # Identity includes a process generation: an order can repeat after restart.
        self.source,self.identity,self.change=source,identity,change
    def __iter__(self):
        found=0
        for row in self.source:
            if (row['node'],row['pid'],row['generation'],row['order'])==self.identity:
                found+=1;replacement=self.change(copy.deepcopy(row))
                if replacement is not None:yield replacement
            else:yield row
        need(found==1,'measurement negative target missing/duplicate')


def first(traces,predicate):
    for node,rows in traces.items():
        for row in rows:
            if predicate(row):return node,(row['node'],row['pid'],row['generation'],row['order'])
    raise ValueError('measurement negative target not found')


def changed(traces,predicate,change):
    node,identity=first(traces,predicate)
    return {key:ChangedRow(rows,identity,change) if key==node else rows for key,rows in traces.items()}
