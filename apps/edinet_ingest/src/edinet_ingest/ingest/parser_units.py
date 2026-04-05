from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NAMESPACES = {"xbrli": NS_XBRLI}


@dataclass(frozen=True, slots=True)
class ParsedUnit:
    unit_ref: str
    measure_text: str


def parse_units(root: etree._Element) -> list[ParsedUnit]:
    parsed_units: list[ParsedUnit] = []

    for unit in root.xpath(".//xbrli:unit", namespaces=NAMESPACES):
        unit_ref = (unit.get("id") or "").strip()
        if not unit_ref:
            continue

        measure_text = _extract_measure_text(unit)
        if not measure_text:
            continue

        parsed_units.append(ParsedUnit(unit_ref=unit_ref, measure_text=measure_text))
    return parsed_units


def _extract_measure_text(unit: etree._Element) -> str | None:
    numerator = _collect_measure_values(unit, "./xbrli:divide/xbrli:unitNumerator/xbrli:measure")
    denominator = _collect_measure_values(unit, "./xbrli:divide/xbrli:unitDenominator/xbrli:measure")
    if numerator and denominator:
        return f"{'*'.join(numerator)}/{'*'.join(denominator)}"

    measures = _collect_measure_values(unit, "./xbrli:measure")
    if measures:
        return "*".join(measures)
    return None


def _collect_measure_values(unit: etree._Element, xpath: str) -> list[str]:
    values: list[str] = []
    for measure in unit.xpath(xpath, namespaces=NAMESPACES):
        value = (measure.text or "").strip()
        if value:
            values.append(value)
    return values
