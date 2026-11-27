"""Fixed-sample bounds; count independent briefs, not their frames or variants."""
import argparse
import json
import math


def lower_successes(successes, count, alpha=.05):
    """Exact one-sided Clopper–Pearson lower bound."""
    if not 0 < alpha < 1 or not 0 <= successes <= count:
        raise ValueError("invalid proportion inputs")
    if not count:
        return None
    if not successes:
        return 0.0
    if successes == count:
        return alpha ** (1 / count)
    coefficients = [math.lgamma(count+1) - math.lgamma(k+1) - math.lgamma(count-k+1)
                    for k in range(successes, count+1)]
    lo, hi = 0.0, 1.0
    for _ in range(60):
        p = (lo+hi)/2
        terms = (factor + k*math.log(p) + (count-k)*math.log1p(-p)
                 for k, factor in enumerate(coefficients, successes))
        if math.fsum(math.exp(t) for t in terms) < alpha:
            lo = p
        else:
            hi = p
    return (lo+hi)/2


def paired(improved, regressed, unchanged, alpha=.05):
    """Distribution-free two-sided CI on paired risk difference, for independent pairs."""
    if min(improved, regressed, unchanged) < 0 or not 0 < alpha < 1:
        raise ValueError("invalid paired inputs")
    count = improved+regressed+unchanged
    if not count:
        return {"difference": None, "interval": None}
    difference = (improved-regressed)/count
    margin = math.sqrt(2*math.log(2/alpha)/count)
    return {"difference": difference, "interval": [max(-1, difference-margin), min(1, difference+margin)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("numerator", "denominator"):
        parser.add_argument(key, type=int)
    parser.add_argument("--alpha", type=float, default=.05)
    row = parser.parse_args()
    lower = lower_successes(row.numerator, row.denominator, row.alpha)
    opposite = lower_successes(row.denominator-row.numerator, row.denominator, row.alpha)
    print(json.dumps({"numerator": row.numerator, "denominator": row.denominator, "confidence": 1-row.alpha,
                      "one_sided_lower": lower, "one_sided_upper": None if opposite is None else 1-opposite}))
