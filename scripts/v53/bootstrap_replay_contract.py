"""Explicit caller-selected replay source; receipts never select admission policy."""
from .membership_model import need

EMPTY = 'EMPTY'
BACKUP = 'VERIFIED_DURABLE_BACKUP'


def check(value):
    need(type(value) is str and value in (EMPTY, BACKUP), 'joining explicit bootstrap source')
    return value


def options(value):
    """Keep historical EMPTY invocations unchanged, including their keyword set."""
    return {} if check(value) == EMPTY else {'bootstrap_source': value}


def receipt(value, source):
    check(source)
    need(type(value) is dict, 'joining bootstrap source receipt')
    if source == EMPTY:
        need('bootstrapSource' not in value, 'joining bootstrap source receipt')
        return value
    need('bootstrapSource' not in value or value['bootstrapSource'] == source, 'joining bootstrap source receipt')
    return dict(value, bootstrapSource=source)


def check_receipt(value, source):
    check(source)
    need(type(value) is dict and ('bootstrapSource' not in value if source == EMPTY else
         value.get('bootstrapSource') == source), 'joining bootstrap source receipt')


def check_base(base, source):
    """A shared ledger reader must originate from this same explicit contract."""
    check(source)
    need(getattr(base.model, 'bootstrap_source', EMPTY) == source, 'joining shared bootstrap source')
