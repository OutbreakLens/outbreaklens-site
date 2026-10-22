"""
categories.py: the eight disease categories that every OutbreakLens output is built around.

categorise(text) maps a source's disease name to one slug, or None when the disease is out of
scope (for example West Nile fever or anthrax). The order of the rules matters: classical swine
fever must not fall into African swine fever, and swine or equine influenza must not fall into
bird flu.
"""
from __future__ import annotations
import re

# slug, label for pages, one-line scope note
CATEGORIES = [
    ("bird-flu", "Bird flu", "Avian influenza in poultry, captive birds, wild birds and mammals"),
    ("bluetongue", "Bluetongue", "Bluetongue virus, all serotypes"),
    ("asf", "African swine fever", "African swine fever in domestic pigs and wild boar"),
    ("fmd", "Foot-and-mouth disease", "Foot-and-mouth disease, all serotypes"),
    ("sheep-goat-pox", "Sheep and goat pox", "Sheep pox and goat pox, with peste des petits ruminants"),
    ("lsd", "Lumpy skin disease", "Lumpy skin disease"),
    ("newcastle-disease", "Newcastle disease", "Newcastle disease"),
    ("other", "Other exotic diseases", "Classical swine fever, Aujeszky's disease, swine vesicular disease, "
                                       "epizootic haemorrhagic disease, African horse sickness and rabies"),
]
SLUGS = [c[0] for c in CATEGORIES]
LABELS = {c[0]: c[1] for c in CATEGORIES}

_RULES = [
    ("other", r"classical swine fever|\bcsf\b|aujeszky|pseudorabies|swine vesicular|\bsvd\b|epizootic ha?emorrhagic|"
              r"\behd\b|african horse sickness|\bahs\b|\brabies\b|\brabv\b"),
    ("asf", r"african swine fever|a\.s\.f\.|\basf\b"),
    ("bird-flu", r"avian influenza|influenza - avian|influenza a viruses of high pathogenicity|"
                 r"high pathogenicity avian|low pathogenicity avian|low pathogenic avian|\bhpai\b|\blpai\b|"
                 r"bird flu|\bai\b\s*\(|^ai$"),
    ("bluetongue", r"bluetongue|\bbtv\b"),
    ("fmd", r"foot[- ]and[- ]mouth|\bfmd\b"),
    ("sheep-goat-pox", r"sheep pox|goat pox|sheep and goat pox|capripox|peste des petits ruminants|\bppr\b"),
    ("lsd", r"lumpy skin"),
    ("newcastle-disease", r"newcastle disease|^nd$"),
]
_COMPILED = [(slug, re.compile(rx, re.I)) for slug, rx in _RULES]
_EXCLUDE = re.compile(r"influenza - (equine|swine)|swine influenza|equine influenza", re.I)


def categorise(text: str | None) -> str | None:
    if not text:
        return None
    t = " ".join(text.split())
    if _EXCLUDE.search(t):
        return None
    for slug, rx in _COMPILED:
        if rx.search(t):
            return slug
    return None


def short_disease(text: str) -> str:
    """A readable disease name: WAHIS adds '(Inf. with)' and year ranges that mean little to readers."""
    t = " ".join((text or "").split())
    t = re.sub(r"\s*\(Inf\. with\)\s*", " ", t)
    t = re.sub(r"\s*\((19|20)\d\d-\)\s*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


if __name__ == "__main__":
    tests = {
        "Influenza A viruses of high pathogenicity (Inf. with) (non-poultry including wild birds) (2017-)": "bird-flu",
        "High pathogenicity avian influenza viruses (Inf. with) (poultry)": "bird-flu",
        "Influenza - Avian": "bird-flu", "Swine influenza": None, "Influenza - Equine": None,
        "African swine fever virus (Inf. with) ": "asf", "A.S.F. in wild boar": "asf",
        "Classical swine fever virus (Inf. with) ": "other", "Aujeszky's disease virus (Inf. with) ": "other",
        "Bluetongue virus (Inf. with) ": "bluetongue", "Foot and mouth disease virus (Inf. with) ": "fmd",
        "Sheep pox and goat pox": "sheep-goat-pox", "Peste des petits ruminants virus (Inf. with) ": "sheep-goat-pox",
        "Lumpy skin disease virus (Inf. with) ": "lsd", "Newcastle disease virus (Inf. with) ": "newcastle-disease",
        "Rabies virus (Inf. with) ": "other", "West Nile Fever": None, "Anthrax": None,
        "Epizootic haemorrhagic disease virus (Inf. with)": "other", "African horse sickness virus (Inf. with)": "other",
        "Mycobacterium tuberculosis complex (Inf. with)(2019-)": None, "HPAI(NON-P) in Wild Birds": "bird-flu",
        "Avian influenza A viruses of high pathogenicity (Inf. with) (bovines [Bos taurus]) (2025-)": "bird-flu",
    }
    bad = {k: (categorise(k), v) for k, v in tests.items() if categorise(k) != v}
    print("all category tests pass" if not bad else bad)
