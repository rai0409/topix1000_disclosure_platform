from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class XbrlSelection:
    main_xbrl_path: str | None
    reason: str


def choose_main_xbrl(
    discovered_files: list[str],
    public_doc_files: list[str],
    _audit_doc_files: list[str],
) -> XbrlSelection:
    public_xbrl = [path for path in public_doc_files if path.lower().endswith(".xbrl")]
    if public_xbrl:
        selected = _sort_by_depth(public_xbrl)[0]
        return XbrlSelection(
            main_xbrl_path=selected,
            reason="selected_public_doc_xbrl_by_depth_priority",
        )

    public_instance_like = [path for path in public_doc_files if _is_public_instance_like(path)]
    if public_instance_like:
        selected = _sort_by_depth(public_instance_like)[0]
        return XbrlSelection(
            main_xbrl_path=selected,
            reason="selected_public_doc_instance_like_by_depth_priority",
        )

    fallback_xbrl = [path for path in discovered_files if path.lower().endswith(".xbrl")]
    if fallback_xbrl:
        selected = fallback_xbrl[0]
        return XbrlSelection(
            main_xbrl_path=selected,
            reason="selected_fallback_first_xbrl",
        )

    return XbrlSelection(main_xbrl_path=None, reason="main_xbrl_not_found")


def _sort_by_depth(paths: list[str]) -> list[str]:
    return sorted(paths, key=lambda path: (len(PurePosixPath(path).parts), path.lower()))


def _is_public_instance_like(path: str) -> bool:
    lowered = path.lower()
    if not lowered.endswith(".xml"):
        return False
    if lowered.endswith(".xsd"):
        return False
    if any(token in lowered for token in ("_lab", "_pre", "_cal", "_def")):
        return False
    filename = PurePosixPath(path).name.lower()
    return "instance" in filename or filename.endswith(".xml")
