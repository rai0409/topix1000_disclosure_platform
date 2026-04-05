from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from lxml import etree

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"
NS_LINK = "http://www.xbrl.org/2003/linkbase"
NS_XLINK = "http://www.w3.org/1999/xlink"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
INTERNAL_NAMESPACES = {NS_XBRLI, NS_XBRLDI, NS_LINK, NS_XLINK}
SPACES_PATTERN = re.compile(r"[\s\u3000]+")


@dataclass(frozen=True, slots=True)
class ParsedFact:
    context_ref: str
    unit_ref: str | None
    namespace_uri: str
    concept_name: str
    concept_qname: str
    decimals: str | None
    is_nil: bool
    raw_value_text: str | None
    normalized_value_decimal: Decimal | None
    raw_text_value: str | None


def parse_facts(root: etree._Element) -> list[ParsedFact]:
    facts: list[ParsedFact] = []

    for element in root.iter():
        if not isinstance(element.tag, str):
            continue

        context_ref = (element.get("contextRef") or "").strip()
        if not context_ref:
            continue

        qname = etree.QName(element)
        namespace_uri = qname.namespace or ""
        if namespace_uri in INTERNAL_NAMESPACES:
            continue

        concept_name = qname.localname
        if element.prefix:
            concept_qname = f"{element.prefix}:{concept_name}"
        else:
            concept_qname = concept_name

        decimals = element.get("decimals")
        is_nil = _is_nil_fact(element)
        raw_value_text = element.text if element.text is not None else None
        normalized_value_decimal = None
        raw_text_value = None

        if not is_nil and raw_value_text is not None:
            normalized_value_decimal = _to_decimal(raw_value_text)
            if normalized_value_decimal is None and raw_value_text.strip():
                raw_text_value = raw_value_text

        facts.append(
            ParsedFact(
                context_ref=context_ref,
                unit_ref=_normalize_optional_attr(element.get("unitRef")),
                namespace_uri=namespace_uri,
                concept_name=concept_name,
                concept_qname=concept_qname,
                decimals=decimals,
                is_nil=is_nil,
                raw_value_text=raw_value_text,
                normalized_value_decimal=normalized_value_decimal,
                raw_text_value=raw_text_value,
            )
        )
    return facts


def _is_nil_fact(element: etree._Element) -> bool:
    raw_nil = (element.get(f"{{{NS_XSI}}}nil") or "").strip().lower()
    return raw_nil in {"true", "1"}


def _to_decimal(value: str) -> Decimal | None:
    cleaned = SPACES_PATTERN.sub("", value.replace(",", ""))
    if not cleaned:
        return None
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _normalize_optional_attr(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
