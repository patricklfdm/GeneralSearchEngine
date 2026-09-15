"""Allow only the accepted V5 core handoff delta from unchanged published V4 APIs."""
import argparse
import difflib
from pathlib import Path
from scripts.v44.api_inventory import declarations


def delta(before, after):
    return ''.join(difflib.unified_diff([v + '\n' for v in before], [v + '\n' for v in after],
                                      fromfile='published-v4', tofile='candidate-v5', n=0))


def verify(before, after, approved):
    actual = delta(before, after)
    if actual != approved:
        raise ValueError('core API differs from the exact approved public-admission delta\n' + actual)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('published43', type=Path)
    parser.add_argument('published44', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('approved', type=Path)
    args = parser.parse_args()
    previous, published = declarations(args.published43), declarations(args.published44)
    if previous != published:
        raise ValueError('published V4.3/V4.4 closed API baselines differ')
    verify(published, declarations(args.candidate), args.approved.read_text())
    print('v50CoreApprovedApiDelta=PASS publishedBaselines=unchanged additions=exact')
