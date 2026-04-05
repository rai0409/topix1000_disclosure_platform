from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lxml import etree

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"
NAMESPACES = {"xbrli": NS_XBRLI, "xbrldi": NS_XBRLDI}


@dataclass(frozen=True, slots=True)
class ParsedContext:
    context_ref: str
    entity_identifier: str | None
    period_kind: str
    instant_date: date | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True, slots=True)
class ParsedContextDimension:
    context_ref: str
    dimension_qname: str
    member_qname: str


def parse_contexts(
    root: etree._Element,
) -> tuple[list[ParsedContext], list[ParsedContextDimension]]:
    contexts: list[ParsedContext] = []
    dimensions: list[ParsedContextDimension] = []

    for context in root.xpath(".//xbrli:context", namespaces=NAMESPACES):
        context_ref = (context.get("id") or "").strip()
        if not context_ref:
            continue

        entity_identifier_node = context.find("./xbrli:entity/xbrli:identifier", namespaces=NAMESPACES)
        entity_identifier = None
        if entity_identifier_node is not None and entity_identifier_node.text is not None:
            entity_identifier = entity_identifier_node.text.strip() or None

        period_kind, instant_date, start_date, end_date = _parse_period(context)
        contexts.append(
            ParsedContext(
                context_ref=context_ref,
                entity_identifier=entity_identifier,
                period_kind=period_kind,
                instant_date=instant_date,
                start_date=start_date,
                end_date=end_date,
            )
        )
        dimensions.extend(_parse_dimensions(context_ref=context_ref, context=context))

    return contexts, dimensions


def _parse_period(context: etree._Element) -> tuple[str, date | None, date | None, date | None]:
    period = context.find("./xbrli:period", namespaces=NAMESPACES)
    if period is None:
        return "unknown", None, None, None

    instant_text = _find_text(period, "./xbrli:instant")
    if instant_text is not None:
        return "instant", _parse_iso_date(instant_text), None, None

    start_text = _find_text(period, "./xbrli:startDate")
    end_text = _find_text(period, "./xbrli:endDate")
    if start_text is not None or end_text is not None:
        return "duration", None, _parse_iso_date(start_text), _parse_iso_date(end_text)

    if period.find("./xbrli:forever", namespaces=NAMESPACES) is not None:
        return "forever", None, None, None

    return "unknown", None, None, None


def _parse_dimensions(context_ref: str, context: etree._Element) -> list[ParsedContextDimension]:
    parsed: list[ParsedContextDimension] = []
    members = context.xpath(
        ".//xbrldi:explicitMember | .//xbrldi:typedMember",
        namespaces=NAMESPACES,
    )
    for member in members:
        dimension_qname = (member.get("dimension") or "").strip()
        if not dimension_qname:
            continue

        member_qname = _extract_member_qname(member)
        if not member_qname:
            continue

        parsed.append(
            ParsedContextDimension(
                context_ref=context_ref,
                dimension_qname=dimension_qname,
                member_qname=member_qname,
            )
        )
    return parsed


def _extract_member_qname(member: etree._Element) -> str | None:
    local_name = etree.QName(member).localname
    if local_name == "explicitMember":
        return ((member.text or "").strip()) or None

    if local_name == "typedMember":
        if len(member) > 0:
            child = member[0]
            child_qname = etree.QName(child)
            if child.prefix:
                return f"{child.prefix}:{child_qname.localname}"
            return child_qname.localname
        return ((member.text or "").strip()) or None

    return None


def _find_text(node: etree._Element, xpath: str) -> str | None:
    target = node.find(xpath, namespaces=NAMESPACES)
    if target is None or target.text is None:
        return None
    value = target.text.strip()
    return value or None


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return date.fromisoformat(candidate[:10])
    except ValueError:
        return None
