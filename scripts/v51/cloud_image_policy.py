"""Frozen image admission shared by observer and Runner; never follow a replacement."""
from . import performance_model as m

WARNING = 'Frozen image is DEPRECATED; explicit name/ID remains usable. Replacement is not selected.'


def observe(response, expected):
    m.need(type(response) is dict and all(response.get(k) == v for k, v in expected.items()),
           'frozen image identity/status/architecture changed')
    value = {k: response[k] for k in expected}
    deprecated = response.get('deprecated')
    if deprecated is None or (type(deprecated) is dict and not deprecated):
        return value
    m.need(type(deprecated) is dict and type(deprecated.get('state')) is str and
           deprecated['state'] in ('ACTIVE', 'DEPRECATED'), 'frozen image deprecation state not usable')
    # GCP's state is authoritative. Optional replacement/timestamps are advisory
    # metadata, not a new identity or permission to follow an image family.
    # Keep only the state so permission observations remain bounded/idempotent.
    value['deprecated'] = dict(state=deprecated['state'])
    return value


def warnings(value):
    return [WARNING] if value.get('deprecated', {}).get('state') == 'DEPRECATED' else []
