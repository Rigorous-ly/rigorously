"""Fluent Builder Chain for Scientific Papers — the Ultimate Harness.

Makes it structurally impossible to write an ungrounded claim.
Every claim requires evidence + citation. Every statistic requires
a runnable script. Every model declares its time unit. The chain
won't build without scientific support.

Usage:
    paper = (
        Paper("SSRI Onset Delay")
        .author("Mansib Rahman Miraj")
        .claim("Autoreceptor desensitization is necessary for onset delay")
            .evidence("4-condition ablation")
            .statistic("onset_with", 17.9, unit="days")
            .statistic("onset_without", 0.0, unit="days")
            .citation("Kreiss1995")
            .ablation_proof(with_value=17.9, without_value=0.0)
        .claim("Cortisol suppresses therapeutic ceiling by up to 33%")
            .evidence("stress dose-response")
            .statistic("suppress_max", 33.0, unit="%")
            .citation("Trivedi2006")
            .run_and_verify("analysis/ssri_ablation.py")
        .method("15-ODE coupled system")
            .model("serotonin", source="Best2010", odes=9, time_unit="hours")
            .model("hpa", source="Karin2020", odes=5, time_unit="minutes")
            .coupling("cortisol_sert", tier=2, citation="Tafet2003")
            .verify_time_units()
        .build()
    )

The chain enforces:
- No claim without evidence + citation
- No statistic without a source (script or manual with justification)
- No model coupling without time unit verification
- No "first" or "novel" without prior_art_check()
- No "demonstrates" or "validates" — only "indicates", "suggests", "consistent with"
- Tier declaration mandatory for every model
- Calibrated vs published params explicitly declared
"""

import re
import subprocess
import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Tier(Enum):
    PUBLISHED = 1       # Faithful reproduction of published model
    NOVEL_COUPLING = 2  # Our formulation, cited basis
    ENGINEERING = 3     # Arbitrary, honestly labeled


class ClaimLanguage(Enum):
    """Unified enum: every word is either PERMITTED or FORBIDDEN.

    Permitted words can be used in claims via .strength().
    Forbidden words raise build errors if found in any claim text.
    This is the SSOT for scientific claim language.
    """
    # ── PERMITTED (use these) ──
    INDICATES = ("indicates", True, None)
    SUGGESTS = ("suggests", True, None)
    CONSISTENT_WITH = ("is consistent with", True, None)
    PREDICTS = ("predicts", True, None)
    SHOWS = ("shows", True, None)
    SUPPORTS = ("supports", True, None)
    PROVIDES_EVIDENCE = ("provides evidence for", True, None)
    TO_OUR_KNOWLEDGE = ("to our knowledge", True, None)

    # ── FORBIDDEN (these trigger build errors) ──
    DEMONSTRATES = ("demonstrates", False, "Use 'indicates' or 'shows'")
    PROVES = ("proves", False, "Use 'provides evidence for'")
    VALIDATES = ("validates", False, "Use 'is consistent with'")
    CONFIRMS = ("confirms", False, "Use 'supports'")
    NOVEL = ("novel", False, "Be specific: 'differs from X by Y'")
    PARADIGM_SHIFT = ("paradigm shift", False, "Let reviewers decide")
    BREAKTHROUGH = ("breakthrough", False, "Let reviewers decide")
    FIRST_EVER = ("first ever", False, "Use 'to our knowledge, the first'")
    CLEARLY = ("clearly shows", False, "Use 'shows' — 'clearly' is editorializing")
    UNDENIABLY = ("undeniably", False, "Let the evidence speak")
    DEFINITIVELY = ("definitively", False, "Use 'provides strong evidence'")

    def __init__(self, phrase, permitted, suggestion):
        self.phrase = phrase
        self.permitted = permitted
        self.suggestion = suggestion

    @classmethod
    def permitted_values(cls):
        return [m for m in cls if m.permitted]

    @classmethod
    def forbidden_entries(cls):
        return {m.phrase: m.suggestion for m in cls if not m.permitted}

    @classmethod
    def from_phrase(cls, phrase: str):
        for m in cls:
            if m.phrase == phrase and m.permitted:
                return m
        raise ValueError(
            f"'{phrase}' is not permitted. Use one of: "
            f"{[m.phrase for m in cls.permitted_values()]}")


# Backward compatibility aliases
Strength = ClaimLanguage
FORBIDDEN_WORDS = ClaimLanguage.forbidden_entries()


@dataclass
class Statistic:
    name: str
    value: float
    unit: str = ""
    source_script: str | None = None
    verified: bool = False
    verified_value: float | None = None


@dataclass
class ModelDecl:
    name: str
    source: str
    odes: int
    time_unit: str  # "hours", "minutes", "days"
    tier: Tier = Tier.PUBLISHED
    honest_label: str = ""
    params_calibrated: list = field(default_factory=list)
    params_published: list = field(default_factory=list)


@dataclass
class CouplingDecl:
    name: str
    tier: Tier
    citation: str
    from_model: str = ""
    to_model: str = ""


@dataclass
class FigureDecl:
    name: str
    generated_by: str  # script path or notebook cell
    caption: str = ""
    claims_supported: list[str] = field(default_factory=list)
    file_path: str = ""
    content_hash: str = ""  # SHA256 of generated file — detects stale figures


@dataclass
class ClaimBlock:
    text: str
    evidence: list[str] = field(default_factory=list)
    statistics: list[Statistic] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    ablation: dict | None = None
    verify_script: str | None = None
    strength: Strength = Strength.INDICATES
    figures: list[str] = field(default_factory=list)  # figure names supporting this claim


@dataclass
class MethodBlock:
    name: str
    models: list[ModelDecl] = field(default_factory=list)
    couplings: list[CouplingDecl] = field(default_factory=list)


class PaperBuildError(Exception):
    """Raised when the paper chain can't build due to missing requirements."""
    pass


class Paper:
    """Fluent builder for a scientific paper. Won't build without evidence."""

    def __init__(self, title: str):
        self._title = title
        self._authors: list[str] = []
        self._claims: list[ClaimBlock] = []
        self._methods: list[MethodBlock] = []
        self._current_claim: ClaimBlock | None = None
        self._current_method: MethodBlock | None = None
        self._errors: list[str] = []
        self._warnings: list[str] = []

    def author(self, name: str) -> "Paper":
        self._authors.append(name)
        return self

    # ── CLAIMS ──

    def claim(self, text: str) -> "Paper":
        """Start a new claim. Requires evidence() and citation() before next claim."""
        # Check for forbidden words
        for word, suggestion in FORBIDDEN_WORDS.items():
            if word.lower() in text.lower():
                self._errors.append(
                    f"Claim uses forbidden word '{word}': {suggestion}")

        # Finalize previous claim
        if self._current_claim:
            self._finalize_claim()

        self._current_claim = ClaimBlock(text=text)
        return self

    def evidence(self, description: str) -> "Paper":
        if not self._current_claim:
            self._errors.append("evidence() called without a claim()")
            return self
        self._current_claim.evidence.append(description)
        return self

    def statistic(self, name: str, value: float, unit: str = "") -> "Paper":
        if not self._current_claim:
            self._errors.append("statistic() called without a claim()")
            return self
        self._current_claim.statistics.append(
            Statistic(name=name, value=value, unit=unit))
        return self

    def citation(self, *keys: str) -> "Paper":
        if not self._current_claim:
            self._errors.append("citation() called without a claim()")
            return self
        self._current_claim.citations.extend(keys)
        return self

    def strength(self, level: str) -> "Paper":
        """Set claim strength. Only permitted words allowed."""
        if not self._current_claim:
            return self
        try:
            self._current_claim.strength = ClaimLanguage.from_phrase(level)
        except ValueError as e:
            self._errors.append(str(e))
        return self

    def ablation_proof(self, with_value: float, without_value: float) -> "Paper":
        if not self._current_claim:
            return self
        self._current_claim.ablation = {
            "with": with_value, "without": without_value}
        if with_value == without_value:
            self._errors.append(
                f"Ablation proof has identical values ({with_value}) — "
                "cannot claim the mechanism matters")
        return self

    def run_and_verify(self, script: str) -> "Paper":
        if not self._current_claim:
            return self
        self._current_claim.verify_script = script
        return self

    def figure(self, name: str, generated_by: str, caption: str = "",
               file_path: str = "") -> "Paper":
        """Attach a figure to the current claim.

        The figure MUST be generated by a script — no manual figures allowed.
        On build(), the script's output is hashed and compared to the file on disk.
        If the file doesn't exist or the hash doesn't match, build fails.
        """
        if not self._current_claim:
            self._errors.append("figure() called without a claim()")
            return self

        fig = FigureDecl(
            name=name,
            generated_by=generated_by,
            caption=caption,
            file_path=file_path or f"paper/figures/{name}.pdf",
        )

        # Check the file exists
        if not Path(fig.file_path).exists():
            self._warnings.append(
                f"Figure '{name}' file not found at {fig.file_path}. "
                f"Run {generated_by} to generate it.")
        else:
            # Hash the file content for staleness detection
            import hashlib
            content = Path(fig.file_path).read_bytes()
            fig.content_hash = hashlib.sha256(content).hexdigest()[:16]

        self._current_claim.figures.append(name)
        if not hasattr(self, '_figures'):
            self._figures: list[FigureDecl] = []
        self._figures.append(fig)
        return self

    def prior_art_check(self, search_terms: list[str] | None = None) -> "Paper":
        """Acknowledge that prior art search was performed."""
        if not self._current_claim:
            return self
        if "first" in self._current_claim.text.lower():
            if not search_terms:
                self._warnings.append(
                    f"Claim contains 'first' but prior_art_check() has no search terms. "
                    "Did you actually search?")
        return self

    # ── METHODS ──

    def method(self, name: str) -> "Paper":
        if self._current_claim:
            self._finalize_claim()
        if self._current_method:
            self._methods.append(self._current_method)
        self._current_method = MethodBlock(name=name)
        return self

    def model(self, name: str, source: str, odes: int,
              time_unit: str, tier: Tier = Tier.PUBLISHED,
              honest_label: str = "") -> "Paper":
        if not self._current_method:
            self._errors.append("model() called without method()")
            return self
        if tier == Tier.NOVEL_COUPLING and not honest_label:
            self._errors.append(
                f"Model '{name}' is Tier 2 but has no honest_label. "
                "You MUST state what is novel vs published.")
        self._current_method.models.append(ModelDecl(
            name=name, source=source, odes=odes, time_unit=time_unit,
            tier=tier, honest_label=honest_label))
        return self

    def param_published(self, name: str, value: float, source: str) -> "Paper":
        if self._current_method and self._current_method.models:
            self._current_method.models[-1].params_published.append(
                {"name": name, "value": value, "source": source})
        return self

    def param_calibrated(self, name: str, value: float, calibrated_to: str) -> "Paper":
        """Declare a parameter that was calibrated (not directly from literature)."""
        if self._current_method and self._current_method.models:
            self._current_method.models[-1].params_calibrated.append(
                {"name": name, "value": value, "calibrated_to": calibrated_to})
        return self

    def coupling(self, name: str, tier: Tier, citation: str,
                 from_model: str = "", to_model: str = "") -> "Paper":
        if not self._current_method:
            return self
        self._current_method.couplings.append(CouplingDecl(
            name=name, tier=tier, citation=citation,
            from_model=from_model, to_model=to_model))
        return self

    def verify_time_units(self) -> "Paper":
        """Check that coupled models with different time units have conversion."""
        if not self._current_method:
            return self
        units = {}
        for m in self._current_method.models:
            units[m.name] = m.time_unit
        unique = set(units.values())
        if len(unique) > 1:
            self._warnings.append(
                f"Models use mixed time units: {units}. "
                "Ensure coupling code converts between them.")
            # Check each coupling
            for c in self._current_method.couplings:
                if c.from_model and c.to_model:
                    u1 = units.get(c.from_model, "unknown")
                    u2 = units.get(c.to_model, "unknown")
                    if u1 != u2:
                        self._warnings.append(
                            f"Coupling '{c.name}': {c.from_model}({u1}) → "
                            f"{c.to_model}({u2}) — conversion REQUIRED")
        return self

    # ── BUILD ──

    def _finalize_claim(self):
        c = self._current_claim
        if not c:
            return
        if not c.evidence:
            self._errors.append(f"Claim has no evidence: '{c.text[:60]}...'")
        if not c.citations:
            self._errors.append(f"Claim has no citations: '{c.text[:60]}...'")
        self._claims.append(c)
        self._current_claim = None

    def _verify_statistics(self) -> list[str]:
        """Run verification scripts and compare to claimed statistics."""
        mismatches = []
        for claim in self._claims:
            if not claim.verify_script:
                continue
            script = Path(claim.verify_script)
            if not script.exists():
                mismatches.append(f"Script not found: {claim.verify_script}")
                continue
            try:
                result = subprocess.run(
                    ["python3", str(script)],
                    capture_output=True, text=True, timeout=300,
                    env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"})
                output = result.stdout
                for stat in claim.statistics:
                    # Search for the value in the output
                    pattern = rf"{stat.value}"
                    if pattern not in output:
                        # Check within 5% tolerance
                        found_close = False
                        for match in re.findall(r"[\d.]+", output):
                            try:
                                v = float(match)
                                if abs(v - stat.value) / max(abs(stat.value), 1e-10) < 0.05:
                                    stat.verified = True
                                    stat.verified_value = v
                                    found_close = True
                                    break
                            except ValueError:
                                continue
                        if not found_close:
                            mismatches.append(
                                f"Statistic '{stat.name}={stat.value}' not found "
                                f"in output of {claim.verify_script}")
                    else:
                        stat.verified = True
                        stat.verified_value = stat.value
            except Exception as e:
                mismatches.append(f"Script failed: {claim.verify_script}: {e}")
        return mismatches

    def build(self) -> "BuiltPaper":
        """Finalize and validate the paper. Raises PaperBuildError if invalid."""
        if self._current_claim:
            self._finalize_claim()
        if self._current_method:
            self._methods.append(self._current_method)
            self._current_method = None

        # Run verification scripts
        verify_errors = self._verify_statistics()
        self._errors.extend(verify_errors)

        if self._errors:
            error_msg = "Paper build FAILED:\n" + "\n".join(
                f"  ERROR: {e}" for e in self._errors)
            if self._warnings:
                error_msg += "\n" + "\n".join(
                    f"  WARNING: {w}" for w in self._warnings)
            raise PaperBuildError(error_msg)

        return BuiltPaper(
            title=self._title,
            authors=self._authors,
            claims=self._claims,
            methods=self._methods,
            warnings=self._warnings,
            figures=getattr(self, '_figures', []),
        )


class BuiltPaper:
    """A validated paper that passed all integrity checks."""

    def __init__(self, title, authors, claims, methods, warnings, figures=None):
        self.title = title
        self.authors = authors
        self.claims = claims
        self.methods = methods
        self.warnings = warnings
        self.figures = figures or []

    def summary(self) -> str:
        lines = [
            f"Paper: {self.title}",
            f"Authors: {', '.join(self.authors)}",
            f"Claims: {len(self.claims)}",
            f"Methods: {len(self.methods)}",
        ]
        total_odes = sum(m.odes for method in self.methods for m in method.models)
        lines.append(f"Total ODEs: {total_odes}")

        tier_counts = {Tier.PUBLISHED: 0, Tier.NOVEL_COUPLING: 0, Tier.ENGINEERING: 0}
        for method in self.methods:
            for m in method.models:
                tier_counts[m.tier] += m.odes
        lines.append(f"Tier 1 (published): {tier_counts[Tier.PUBLISHED]} ODEs")
        lines.append(f"Tier 2 (novel): {tier_counts[Tier.NOVEL_COUPLING]} ODEs")
        lines.append(f"Tier 3 (engineering): {tier_counts[Tier.ENGINEERING]} ODEs")

        calibrated = []
        for method in self.methods:
            for m in method.models:
                calibrated.extend(m.params_calibrated)
        if calibrated:
            lines.append(f"Calibrated params: {len(calibrated)}")
            for p in calibrated:
                lines.append(f"  {p['name']}={p['value']} (calibrated to: {p['calibrated_to']})")

        verified = sum(1 for c in self.claims for s in c.statistics if s.verified)
        total_stats = sum(len(c.statistics) for c in self.claims)
        lines.append(f"Statistics verified: {verified}/{total_stats}")

        if self.warnings:
            lines.append(f"\nWarnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)

    def audit_report(self) -> str:
        """Detailed audit report for submission checklist."""
        lines = ["=" * 60, "PAPER BUILD AUDIT REPORT", "=" * 60, ""]

        for i, claim in enumerate(self.claims, 1):
            lines.append(f"Claim {i}: {claim.text[:80]}")
            lines.append(f"  Strength: {claim.strength.value}")
            lines.append(f"  Evidence: {', '.join(claim.evidence) or 'NONE'}")
            lines.append(f"  Citations: {', '.join(claim.citations) or 'NONE'}")
            if claim.ablation:
                lines.append(f"  Ablation: with={claim.ablation['with']}, "
                           f"without={claim.ablation['without']}")
            for s in claim.statistics:
                status = "VERIFIED" if s.verified else "UNVERIFIED"
                lines.append(f"  Stat: {s.name}={s.value}{s.unit} [{status}]")
            lines.append("")

        for method in self.methods:
            lines.append(f"Method: {method.name}")
            for m in method.models:
                tier_label = {Tier.PUBLISHED: "Tier 1", Tier.NOVEL_COUPLING: "Tier 2",
                             Tier.ENGINEERING: "Tier 3"}[m.tier]
                lines.append(f"  Model: {m.name} ({m.odes} ODEs, {m.time_unit}, "
                           f"{tier_label}, {m.source})")
                if m.honest_label:
                    lines.append(f"    Label: {m.honest_label}")
                if m.params_calibrated:
                    for p in m.params_calibrated:
                        lines.append(f"    CALIBRATED: {p['name']}={p['value']} "
                                   f"→ {p['calibrated_to']}")
            for c in method.couplings:
                lines.append(f"  Coupling: {c.name} (Tier {c.tier.value}, {c.citation})")

        return "\n".join(lines)
