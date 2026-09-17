"""Integer profile weights approximating explicit execution-count shares."""
from fractions import Fraction
from functools import reduce
from math import gcd

def weights_for_counts(counts, targets):
    if set(counts)!=set(targets) or any(n<=0 for n in counts.values()):
        raise ValueError('Each profile group needs a positive execution count and target')
    if any(t<=0 for t in targets.values()):raise ValueError('Targets must be positive')
    ratios={k:Fraction(targets[k],counts[k]) for k in counts}
    smallest=min(ratios.values())
    # Give even the smallest weight 100 quantization steps before reduction.
    weights={k:max(1,round(100*r/smallest)) for k,r in ratios.items()}
    divisor=reduce(gcd,weights.values())
    weights={k:w//divisor for k,w in weights.items()}
    if max(weights.values())>=2**32 or sum(weights[k]*counts[k] for k in counts)>=2**63:
        raise ValueError('Profile counts/weights exceed conservative integer limits')
    total=sum(weights[k]*counts[k] for k in counts)
    shares={k:weights[k]*counts[k]/total for k in counts}
    return weights,shares
