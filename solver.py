"""Deterministic solver for the DSO 429 hourly quiz.

Each question template is parsed with a regex, the answer is computed
exactly, and the closest option is picked. A question is only "solved"
if exactly one option matches the computed value; anything else is
returned as None so the caller can fall back to an LLM.
"""

import re
from datetime import date, datetime, timedelta

LETTERS = "ABCD"
NUM = r"\$?(-?[\d,]+(?:\.\d+)?)"


def num(s):
    return float(s.replace(",", "").replace("$", ""))


def parse_option(s):
    """Option text -> float, date, or the raw string."""
    t = s.strip()
    try:
        return datetime.strptime(t, "%d %B %Y").date()
    except ValueError:
        pass
    m = re.fullmatch(r"\$?\s*(-?[\d,]+(?:\.\d+)?)\s*(%|units?)?", t)
    if m:
        return num(m.group(1))
    return t


# ---------- templates: each returns the computed value or None ----------

def compound_interest(q):
    m = re.search(rf"investment of {NUM} grows at {NUM}% compounded annually.*?after {NUM} years?", q)
    if m:
        p, r, n = map(num, m.groups())
        return p * (1 + r / 100) ** n


def gross_margin(q):
    m = re.search(rf"generates {NUM} in revenue against {NUM} in cost of goods sold.*gross margin", q)
    if m:
        rev, cogs = map(num, m.groups())
        return (rev - cogs) / rev * 100


def next_in_series(q):
    m = re.search(r"series runs ([\d,.\s-]+?)\. If the pattern continues", q)
    if not m:
        return None
    xs = [num(x) for x in m.group(1).split(",") if x.strip()]
    if len(xs) < 3:
        return None
    diffs = [b - a for a, b in zip(xs, xs[1:])]
    if len(set(diffs)) == 1:
        return xs[-1] + diffs[0]
    if all(x != 0 for x in xs):
        ratios = [b / a for a, b in zip(xs, xs[1:])]
        if max(ratios) - min(ratios) < 1e-9:
            return xs[-1] * ratios[0]
    second = [b - a for a, b in zip(diffs, diffs[1:])]
    if len(set(second)) == 1:
        return xs[-1] + diffs[-1] + second[0]
    return None


def discount(q):
    m = re.search(rf"listed at {NUM} is discounted by {NUM}%.*sale price", q)
    if m:
        p, d = map(num, m.groups())
        return p * (1 - d / 100)


def total_revenue(q):
    m = re.search(rf"sells {NUM} units at {NUM} each.*total revenue", q)
    if m:
        u, p = map(num, m.groups())
        return u * p


def currency(q):
    # "$X is converted to euros at R euros per US dollar" -> multiply;
    # "... at R US dollars per euro" -> divide.
    m = re.search(rf"for {NUM} is converted to (\w[\w ]*?) at {NUM} ([\w ]+?) per ([\w ]+?)\.", q)
    if not m:
        return None
    amt, target, rate, unit_num, unit_den = num(m.group(1)), m.group(2), num(m.group(3)), m.group(4), m.group(5)
    stem = target.rstrip("s").lower()
    if stem in unit_num.lower():
        return amt * rate
    if stem in unit_den.lower():
        return amt / rate
    return None


def weighted_average(q):
    m = re.search(rf"had {NUM} orders averaging {NUM}; region B had {NUM} orders averaging {NUM}", q)
    if m:
        n1, a1, n2, a2 = map(num, m.groups())
        return (n1 * a1 + n2 * a2) / (n1 + n2)


def break_even(q):
    m = re.search(rf"Fixed costs are {NUM}\. Each unit sells for {NUM} with a variable cost of {NUM}", q)
    if m:
        f, p, v = map(num, m.groups())
        return round(f / (p - v))


def probability(q):
    m = re.search(r"holds ([\d,]+) (\w+) tickets, ([\d,]+) (\w+) tickets and ([\d,]+) (\w+) tickets.*probability it is an? (\w+) ticket", q)
    if not m:
        return None
    counts = {m.group(2): num(m.group(1)), m.group(4): num(m.group(3)), m.group(6): num(m.group(5))}
    target = m.group(7)
    if target not in counts:
        return None
    p = counts[target] / sum(counts.values()) * 100
    if re.search(r"probability it is not", q):
        return 100 - p
    return p


def percent_change(q):
    m = re.search(rf"moved from {NUM} to {NUM}.*percentage change", q)
    if m:
        a, b = map(num, m.groups())
        return (b - a) / a * 100


def ratio_split(q):
    m = re.search(rf"A {NUM} .*? split between two channels in the ratio (\d+):(\d+)\. What does the (first|second) channel receive", q)
    if m:
        total, a, b = num(m.group(1)), num(m.group(2)), num(m.group(3))
        share = a if m.group(4) == "first" else b
        return total * share / (a + b)


def settlement_date(q):
    m = re.search(r"signed on (\d{1,2} \w+ \d{4}) has an? (\d+)-day settlement period", q)
    if m:
        d = datetime.strptime(m.group(1), "%d %B %Y").date()
        return d + timedelta(days=int(m.group(2)))


TEMPLATES = [compound_interest, gross_margin, next_in_series, discount, total_revenue,
             currency, weighted_average, break_even, probability, percent_change,
             ratio_split, settlement_date]


def pick(value, options):
    """Return the letter of the single option matching value, else None."""
    parsed = [parse_option(o) for o in options]
    if isinstance(value, date):
        hits = [i for i, o in enumerate(parsed) if o == value]
        return LETTERS[hits[0]] if len(hits) == 1 else None
    nums = [(i, o) for i, o in enumerate(parsed) if isinstance(o, float)]
    if not nums:
        return None

    def tol(i):
        # Half a unit in the last displayed decimal place, plus float slack.
        m = re.search(r"\.(\d+)", options[i])
        return 0.5 * 10 ** -(len(m.group(1)) if m else 0) + 1e-6

    hits = [i for i, o in nums if abs(o - value) <= tol(i)]
    if len(hits) != 1:
        return None
    best_i = hits[0]
    return LETTERS[best_i]


def solve(question, options):
    """Return (letter, template_name) or (None, None) if not confidently solved."""
    for t in TEMPLATES:
        try:
            v = t(question)
        except (ValueError, ZeroDivisionError):
            v = None
        if v is None:
            continue
        letter = pick(v, options)
        if letter:
            return letter, t.__name__
    return None, None
