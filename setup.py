"""Setuptools build hook to bundle skills/medical-research-harness into wheels."""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

SKILL_FILES = ("SKILL.md", "LICENSE")
SKILL_DIRS = ("scripts", "assets", "references")
IGNORE_PATTERNS = ("__pycache__", "*.pyc", "*.pyo")


def _copy_skill_bundle(skill_src: Path, bundle_dst: Path) -> None:
    if not (skill_src / "SKILL.md").is_file():
        raise FileNotFoundError(f"Cannot locate skill source directory: {skill_src}")
    if bundle_dst.exists():
        shutil.rmtree(bundle_dst)
    bundle_dst.mkdir(parents=True, exist_ok=True)
    for filename in SKILL_FILES:
        src_file = skill_src / filename
        if src_file.is_file():
            shutil.copy2(src_file, bundle_dst / filename)
    ignore = shutil.ignore_patterns(*IGNORE_PATTERNS)
    for dirname in SKILL_DIRS:
        src_dir = skill_src / dirname
        if src_dir.is_dir():
            shutil.copytree(src_dir, bundle_dst / dirname, ignore=ignore)


class BundleSkillBuildPy(build_py):
    """Copy skills/medical-research-harness into build_lib for standalone wheels."""

    def run(self) -> None:
        super().run()
        if getattr(self, "editable_mode", False):
            return
        repo_root = Path(__file__).resolve().parent
        skill_src = repo_root / "skills" / "medical-research-harness"
        bundle_dst = Path(self.build_lib) / "medical_research_harness" / "_skill_bundle"
        _copy_skill_bundle(skill_src, bundle_dst)


class BundleSkillSdist(sdist):
    """Ensure source distributions also include skills/medical-research-harness."""

    def make_release_tree(self, base_dir: str, files: list[str]) -> None:
        super().make_release_tree(base_dir, files)
        repo_root = Path(__file__).resolve().parent
        skill_src = repo_root / "skills" / "medical-research-harness"
        if (skill_src / "SKILL.md").is_file():
            skill_dst = Path(base_dir) / "skills" / "medical-research-harness"
            _copy_skill_bundle(skill_src, skill_dst)


setup(
    cmdclass={
        "build_py": BundleSkillBuildPy,
        "sdist": BundleSkillSdist,
    },
)
