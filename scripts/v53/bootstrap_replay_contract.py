"""Explicit caller-selected replay source; receipts never select admission policy."""
from .membership_model import need

EMPTY = 'EMPTY'
BACKUP = 'VERIFIED_DURABLE_BACKUP'
JSON = 'JSON'
SEGMENTED = 'SEGMENTED_BACKUP'
ORIGINAL_BYTES = 128 * 1024**3


def check(value):
    need(type(value) is str and value in (EMPTY, BACKUP), 'joining explicit bootstrap source')
    return value


def check_layout(source, layout):
    check(source)
    need(type(layout) is str and layout in (JSON, SEGMENTED), 'joining explicit wire layout')
    need(layout == JSON or source == BACKUP, 'joining segmented wire requires backup')
    return layout


def options(value, wire_layout=JSON):
    """Keep historical EMPTY invocations unchanged, including their keyword set."""
    check_layout(value,wire_layout)
    result={} if value == EMPTY else {'bootstrap_source': value}
    if wire_layout != JSON:result['wire_layout']=wire_layout
    return result


def inventory(root, *, bootstrap_source=EMPTY, wire_layout=JSON):
    """One whole-original allowance, selected by the caller, never by evidence.

    Segments, observed cuts, physical copies and all other retained files share
    the existing maximum-original bound. Ordinary JSON retains its old policy.
    Imports are deferred because the legacy collector imports replay readers.
    """
    check_layout(bootstrap_source, wire_layout)
    if wire_layout == SEGMENTED:
        from . import maximum_transition_inventory as large
        return large.inventory(root, maximum=ORIGINAL_BYTES)
    from . import joining_history_run as legacy
    return legacy.inventory(root)


def receipt(value, source, wire_layout=JSON):
    check_layout(source,wire_layout)
    need(type(value) is dict, 'joining bootstrap source receipt')
    need('wireLayout' not in value if wire_layout == JSON else
         'wireLayout' not in value or value['wireLayout'] == wire_layout, 'joining wire layout receipt')
    if wire_layout != JSON:value=dict(value,wireLayout=wire_layout)
    if source == EMPTY:
        need('bootstrapSource' not in value, 'joining bootstrap source receipt')
        return value
    need('bootstrapSource' not in value or value['bootstrapSource'] == source, 'joining bootstrap source receipt')
    return dict(value, bootstrapSource=source)


def check_receipt(value, source, wire_layout=JSON):
    check_layout(source,wire_layout)
    need(type(value) is dict and ('bootstrapSource' not in value if source == EMPTY else
         value.get('bootstrapSource') == source), 'joining bootstrap source receipt')
    need('wireLayout' not in value if wire_layout == JSON else value.get('wireLayout') == wire_layout,
         'joining wire layout receipt')


def check_base(base, source, wire_layout=JSON):
    """A shared ledger reader must originate from this same explicit contract."""
    check_layout(source,wire_layout)
    need(getattr(base.model, 'bootstrap_source', EMPTY) == source, 'joining shared bootstrap source')
    need(getattr(base.model, 'wire_layout', JSON) == wire_layout, 'joining shared wire layout')
