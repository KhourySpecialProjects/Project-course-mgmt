"""Turning team names into the names used in outside services, and matching them up."""

import re
from collections.abc import Callable, Iterable

# Shorter names than this are only matched exactly (guessing from "A" or "Red" is risky).
MIN_PARTIAL_MATCH = 4


def slugify(name: str) -> str:
    """Lower case, with runs of anything but letters and digits turned into one hyphen.

    "Team Alpha!" -> "team-alpha". Empty if the name has no letters or digits.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def compact(name: str) -> str:
    """Only the letters and digits, lower case: "Before Dawn" and "BeforeDawn" -> "beforedawn"."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def best_match[T](
    name: str, candidates: Iterable[T], *, names: Callable[[T], Iterable[str]]
) -> T | None:
    """The candidate that belongs to the team called ``name``, or None if it's not clear.

    ``names`` gives each candidate's names (e.g. a droplet's name and its tags).
    Spaces, punctuation, and case never matter. In order of preference:

    1. A name equal to the team's: "Before Dawn" finds "before-dawn" or "BeforeDawn".
    2. The only name that starts with it: "BeforeDawnArchitecturePatterns".
    3. The only name that contains it: "cs4530-before-dawn".

    If two candidates are equally good (say two repos start with the team's name),
    nothing is picked, so the wrong thing is never linked.
    """
    target = compact(name)
    if not target:
        return None
    items = [(c, [compact(n) for n in names(c)]) for c in candidates]

    exact = [c for c, ns in items if target in ns]
    if exact:
        return exact[0]
    if len(target) < MIN_PARTIAL_MATCH:
        return None
    for test in (str.startswith, str.__contains__):
        hits = [c for c, ns in items if any(test(n, target) for n in ns)]
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None  # ambiguous
    return None
