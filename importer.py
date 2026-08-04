from __future__ import annotations

import io
import json
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
import zipfile


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"m": MAIN_NS, "r": DOC_REL_NS}
CELL_RE = re.compile(r"([A-Z]+)(\d+)")
WEIGHT_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*[＜<]\s*W\s*≤\s*(\d+(?:\.\d+)?)\s*(?:KG)?\s*$",
    re.IGNORECASE,
)
ONE_WEIGHT_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(?:[-—–]|≤\s*W\s*≤)\s*"
    r"(\d+(?:\.\d+)?)\s*(?:KG)?\s*$",
    re.IGNORECASE,
)
ONE_DATE_RE = re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})")

CHANNEL_DEFINITIONS = [
    {
        "key": "economy_general",
        "name": "云途特惠普货",
        "fullName": "云途全球专线挂号（特惠普货）",
        "cargoType": "普货",
    },
    {
        "key": "economy_battery",
        "name": "云途特惠带电",
        "fullName": "云途全球专线挂号（特惠带电）",
        "cargoType": "带电",
    },
    {
        "key": "standard_general",
        "name": "云途标快普货",
        "fullName": "云途全球专线挂号（标快普货）",
        "cargoType": "普货",
    },
    {
        "key": "standard_battery",
        "name": "云途标快带电",
        "fullName": "云途全球专线挂号（标快带电）",
        "cargoType": "带电",
    },
    {
        "key": "cosmetics",
        "name": "云途化妆品",
        "fullName": "云途全球化妆品类专线挂号",
        "cargoType": "化妆品",
    },
    {
        "key": "yt_eu_amz_general",
        "name": "云途欧洲AMZ特惠普货",
        "fullName": "云途欧洲专线（特惠普货）-AMZ",
        "cargoType": "普货",
    },
    {
        "key": "yt_eu_amz_battery",
        "name": "云途欧洲AMZ特惠带电",
        "fullName": "云途欧洲专线（特惠带电）-AMZ",
        "cargoType": "带电",
    },
    {
        "key": "yt_eu_amz_cosmetics",
        "name": "云途欧洲AMZ化妆品",
        "fullName": "云途欧洲化妆品专线-AMZ",
        "cargoType": "化妆品",
    },
    {
        "key": "yt_selected_general",
        "name": "云途精选普货",
        "fullName": "云途全球精选专线挂号（特惠普货）",
        "cargoType": "普货",
    },
    {
        "key": "yt_selected_battery",
        "name": "云途精选带电",
        "fullName": "云途全球精选专线挂号（特惠带电）",
        "cargoType": "带电",
    },
]

SHANGPAI_CHANNEL_DEFINITIONS = [
    {
        "key": "sp_us_standard_general",
        "name": "商派美国标快普货",
        "fullName": "云途全球商派专线（标快普货）",
        "cargoType": "普货",
    },
    {
        "key": "sp_us_standard_battery",
        "name": "商派美国标快带电",
        "fullName": "云途全球商派专线（标快带电）",
        "cargoType": "带电",
    },
    {
        "key": "sp_ca_standard_battery",
        "name": "商派加拿大标快带电",
        "fullName": "云途加拿大商派专线（标快带电）",
        "cargoType": "带电",
    },
    {
        "key": "sp_ca_standard_general",
        "name": "商派加拿大标快普货",
        "fullName": "云途加拿大商派专线（标快普货）",
        "cargoType": "普货",
    },
    {
        "key": "sp_us_a01_general",
        "name": "商派美国A01特惠普货",
        "fullName": "A01特惠普货",
        "cargoType": "普货",
    },
    {
        "key": "sp_us_a01_battery",
        "name": "商派美国A01带电",
        "fullName": "A01带电",
        "cargoType": "带电",
    },
    {
        "key": "sp_us_economy_general",
        "name": "商派美国特惠普货",
        "fullName": "云途商派专线（特惠普货）",
        "cargoType": "普货",
    },
    {
        "key": "sp_ca_economy_general",
        "name": "商派加拿大特惠普货",
        "fullName": "云途加拿大商派专线（特惠普货）",
        "cargoType": "普货",
    },
    {
        "key": "sp_ca_economy_battery",
        "name": "商派加拿大特惠带电",
        "fullName": "云途加拿大商派专线（特惠带电）",
        "cargoType": "带电",
    },
]

ONE_CHANNEL_DEFINITIONS = [
    {
        "key": "one_us_special_a",
        "name": "壹号美国特货A",
        "fullName": "美国专线小包特货A",
        "sheetName": "标准线（含税)",
        "dateLookup": "标准线",
        "cargoType": "特货A",
        "defaultCountry": "美国",
        "minimumWeightKg": 0,
        "volumeDivisor": 8000,
    },
    {
        "key": "one_us_p",
        "name": "壹号美国P价",
        "fullName": "美国专线小包P价",
        "sheetName": "标准线（含税)",
        "dateLookup": "标准线",
        "cargoType": "P普货",
        "defaultCountry": "美国",
        "minimumWeightKg": 0,
        "volumeDivisor": 8000,
    },
    {
        "key": "one_us_dp",
        "name": "壹号美国DP价",
        "fullName": "美国专线小包DP价",
        "sheetName": "标准线（含税)",
        "dateLookup": "标准线",
        "cargoType": "DP价",
        "defaultCountry": "美国",
        "minimumWeightKg": 0,
        "volumeDivisor": 6000,
    },
    {
        "key": "one_us_special_s",
        "name": "壹号美国特货S",
        "fullName": "美国专线小包特货S",
        "sheetName": "标准线（含税)",
        "dateLookup": "标准线",
        "cargoType": "特货S",
        "defaultCountry": "美国",
        "minimumWeightKg": 0,
        "volumeDivisor": 6000,
    },
    {
        "key": "one_uk_p",
        "name": "壹号英国P价",
        "fullName": "英国专线小包P价",
        "sheetName": "英国专线小包",
        "dateLookup": "英国专线小包P价",
        "cargoType": "P价",
        "minimumWeightKg": 0.05,
        "volumeDivisor": 8000,
    },
    {
        "key": "one_eu_special",
        "name": "壹号欧洲特货",
        "fullName": "欧洲专线小包特货",
        "sheetName": "欧洲专线小包",
        "dateLookup": "欧洲专线小包特货",
        "cargoType": "特货",
        "minimumWeightKg": 0.05,
        "volumeDivisor": 8000,
    },
    {
        "key": "one_eu_special_p",
        "name": "壹号欧洲特货P",
        "fullName": "欧洲专线小包特货P",
        "sheetName": "欧洲专线小包",
        "dateLookup": "欧洲专线小包特货P",
        "cargoType": "特货P",
        "minimumWeightKg": 0.05,
        "volumeDivisor": 6000,
    },
    {
        "key": "one_yifan_uk_special_a",
        "name": "壹号英国特货A",
        "fullName": "壹号-英国专线小包特货A",
        "sourceName": "英国专线小包特货A",
        "sheetName": "英国专线小包",
        "dateLookup": "英国专线小包特货A",
        "cargoType": "特货A",
        "minimumWeightKg": 0.05,
        "volumeDivisor": 8000,
    },
    {
        "key": "one_yifan_eu_special_a",
        "name": "壹号欧洲特货A",
        "fullName": "壹号-欧洲专线小包特货A",
        "sourceName": "欧洲专线小包特货A",
        "sheetName": "欧洲专线小包",
        "dateLookup": "欧洲专线小包特货A",
        "cargoType": "特货A",
        "minimumWeightKg": 0.05,
        "volumeDivisor": 6000,
    },
    {
        "key": "one_yifan_ca_special_a",
        "name": "壹号加拿大特货A",
        "fullName": "壹号-加拿大专线小包特货A",
        "sourceName": "加拿大专线小包特货A",
        "sheetName": "加拿大专线小包",
        "dateLookup": "加拿大专线小包特货A",
        "cargoType": "特货A",
        "defaultCountry": "加拿大",
        "minimumWeightKg": 0.05,
        "volumeDivisor": 8000,
    },
    {
        "key": "one_yifan_au_special_a",
        "name": "壹号澳大利亚特货A",
        "fullName": "壹号-澳大利亚专线小包特货A",
        "sourceName": "澳大利亚专线小包特货A",
        "sheetName": "澳大利亚专线小包",
        "dateLookup": "澳大利亚专线小包特货A",
        "cargoType": "特货A",
        "minimumWeightKg": 0.01,
        "volumeDivisor": 8000,
        "layout": "australia",
    },
    {
        "key": "one_yifan_us_special_swd",
        "name": "壹号美国特货SWD",
        "fullName": "壹号-美国专线小包特货SWD",
        "sourceName": "美国专线小包特货SWD",
        "sheetName": "WD渠道",
        "dateLookup": "WD渠道",
        "cargoType": "特货SWD",
        "defaultCountry": "美国",
        "minimumWeightKg": 0.05,
        "volumeDivisor": 8000,
    },
]

UBI_MAIN_CHANNEL_DEFINITIONS = [
    {
        "key": "ubi_au_post_general",
        "name": "UBI澳邮普货",
        "fullName": "全球专线（普货）澳大利亚-澳邮专线",
        "sheetName": "全球专线（普货）澳大利亚-澳邮专线",
        "country": "澳大利亚",
        "cargoType": "普货",
        "layout": "australia",
    },
    {
        "key": "ubi_au_post_battery",
        "name": "UBI澳邮带电",
        "fullName": "全球专线（带电）澳大利亚-澳邮专线",
        "sheetName": "全球专线（带电）澳大利亚-澳邮专线",
        "country": "澳大利亚",
        "cargoType": "带电",
        "layout": "australia",
    },
    {
        "key": "ubi_nz_general",
        "name": "UBI新西兰普货",
        "fullName": "全球专线（普货）-新西兰",
        "sheetName": "全球专线（普货）",
        "country": "新西兰",
        "cargoType": "普货",
        "layout": "country",
    },
    {
        "key": "ubi_nz_battery",
        "name": "UBI新西兰带电",
        "fullName": "全球专线（带电）-新西兰",
        "sheetName": "全球专线（带电）",
        "country": "新西兰",
        "cargoType": "带电",
        "layout": "country",
    },
]

UBI_CANADA_CHANNEL_DEFINITIONS = [
    {
        "key": "ubi_ca_special_general",
        "name": "UBI加拿大特价普货",
        "fullName": "UBI加拿大特价-华南普货（上门揽收）",
        "sheetName": "价格表-华南普货",
        "cargoType": "普货",
    },
    {
        "key": "ubi_ca_special_battery",
        "name": "UBI加拿大特价带电",
        "fullName": "UBI加拿大特价-华南带电（上门揽收）",
        "sheetName": "价格表-华南带电",
        "cargoType": "带电",
    },
]

YUANPENG_CHANNEL_DEFINITIONS = [
    {
        "key": "yp_standard_general",
        "name": "远朋普货小包",
        "fullName": "普货小包专线",
        "sheetName": "普货小包专线",
        "cargoType": "普货",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_standard_special",
        "name": "远朋特货小包",
        "fullName": "特货小包专线",
        "sheetName": "特货小包专线",
        "cargoType": "内电/膏体/化妆品",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_standard_general_f",
        "name": "远朋普F小包",
        "fullName": "普F小包专线",
        "sheetName": "普F小包专线",
        "cargoType": "F类普货",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_standard_special_f",
        "name": "远朋特F小包",
        "fullName": "特F小包专线",
        "sheetName": "特F小包专线",
        "cargoType": "F类特货",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_standard_battery",
        "name": "远朋纯电小包",
        "fullName": "纯电小包专线",
        "sheetName": "纯电小包专线",
        "cargoType": "纯电/香水",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_standard_sensitive",
        "name": "远朋特敏感小包",
        "fullName": "特敏感小包专线",
        "sheetName": "特敏感小包专线",
        "cargoType": "敏感货/食品",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_us_food",
        "name": "远朋美国食品小包",
        "fullName": "美国食品小包专线",
        "sheetName": "美国食品小包专线",
        "cargoType": "食品/保健品",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_nz_remote",
        "name": "远朋新西兰偏远",
        "fullName": "远朋新西兰偏远专线",
        "sheetName": "远朋新西兰偏远专线",
        "cargoType": "综合敏感货",
        "minimumWeightKg": 0.05,
    },
    {
        "key": "yp_fujian_eub_special",
        "name": "远朋福建E邮宝特货",
        "fullName": "福建E邮宝特货",
        "sheetName": "福建E邮宝特货",
        "cargoType": "纯电/敏感货",
        "minimumWeightKg": 0,
        "eubMinimums": True,
        "transitColumn": 0,
    },
    {
        "key": "yp_fujian_eub_us_special",
        "name": "远朋福建E邮宝美国特货",
        "fullName": "福建E邮宝美国特货",
        "sheetName": "福建E邮宝美国特货",
        "cargoType": "美国敏感货",
        "minimumWeightKg": 0,
        "eubMinimums": True,
        "transitColumn": 0,
    },
    {
        "key": "yp_guangzhou_eub_special",
        "name": "远朋广州E邮宝特货",
        "fullName": "广州E邮宝特货",
        "sheetName": "广州E邮宝特货",
        "cargoType": "内电/化妆品",
        "minimumWeightKg": 0,
        "eubMinimums": True,
        "transitColumn": 0,
    },
    {
        "key": "yp_uk_royal_sensitive",
        "name": "远朋英国皇家特敏感",
        "fullName": "远朋英国皇家特敏感",
        "sheetName": "特敏感小包专线",
        "dateLookup": "特敏感小包专线",
        "cargoType": "英国敏感货",
        "minimumWeightKg": 0.05,
        "countryFilter": {"英国"},
    },
]

YANWEN_CHANNEL_DEFINITIONS = [
    {
        "key": "yw_tracking_general",
        "name": "燕文专线追踪普货",
        "fullName": "南昌燕文-燕文专线追踪-普货",
        "sheetName": "燕文专线追踪-普货",
        "cargoType": "普货",
    },
    {
        "key": "yw_tracking_special",
        "name": "燕文专线追踪特货",
        "fullName": "南昌燕文-燕文专线追踪-特货",
        "sheetName": "燕文专线追踪-特货",
        "cargoType": "特货",
    },
    {
        "key": "yw_cosmetics",
        "name": "燕文化妆品专线",
        "fullName": "南昌燕文-燕文化妆品专线",
        "sheetName": "燕文化妆品专线",
        "cargoType": "化妆品",
    },
    {
        "key": "yw_air_registered_general",
        "name": "燕文航空挂号普货",
        "fullName": "南昌燕文-燕文航空挂号-普货",
        "sheetName": "燕文航空挂号-普货",
        "cargoType": "普货",
    },
    {
        "key": "yw_air_registered_special",
        "name": "燕文航空挂号特货",
        "fullName": "南昌燕文-燕文航空挂号-特货",
        "sheetName": "燕文航空挂号-特货",
        "cargoType": "特货",
    },
    {
        "key": "yw_small_light",
        "name": "燕文轻小件专线",
        "fullName": "南昌燕文-轻小件专线",
        "sheetName": "轻小件专线",
        "cargoType": "普货",
    },
]

COUNTRY_ALIASES = {
    "捷克共和国": "捷克",
    "斯洛伐克共和国": "斯洛伐克",
    "马尔他": "马耳他",
    "阿联酋": "阿拉伯联合酋长国",
}


class ImportValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("；".join(errors))
        self.errors = errors


def _column_number(reference: str) -> int:
    match = CELL_RE.fullmatch(reference)
    if not match:
        return 0
    number = 0
    for char in match.group(1):
        number = number * 26 + ord(char) - 64
    return number


def _clean_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _load_shared_strings(book: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in book.namelist():
        return []
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        strings.append(
            "".join(text.text or "" for text in item.iter(f"{{{MAIN_NS}}}t"))
        )
    return strings


def _sheet_paths(book: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    relationships = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall(f"{{{REL_NS}}}Relationship")
    }
    result = {}
    for sheet in workbook.findall(".//m:sheets/m:sheet", NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
        target = rel_targets[rel_id].lstrip("/")
        result[name] = target if target.startswith("xl/") else f"xl/{target}"
    return result


def _read_sheet(
    book: zipfile.ZipFile, shared: list[str], sheet_path: str
) -> list[tuple[int, dict[int, str]]]:
    root = ET.fromstring(book.read(sheet_path))
    result = []
    for row in root.findall(".//m:sheetData/m:row", NS):
        values: dict[int, str] = {}
        for cell in row.findall("m:c", NS):
            reference = cell.attrib.get("r", "")
            cell_type = cell.attrib.get("t")
            value_node = cell.find("m:v", NS)
            inline_node = cell.find("m:is", NS)
            value = ""
            if inline_node is not None:
                value = "".join(
                    text.text or ""
                    for text in inline_node.iterfind(".//m:t", NS)
                )
            elif value_node is not None:
                raw = value_node.text or ""
                value = shared[int(raw)] if cell_type == "s" and raw else raw
            if value:
                values[_column_number(reference)] = value
        result.append((int(row.attrib["r"]), values))
    return result


def _extract_effective_date(rows: list[tuple[int, dict[int, str]]]) -> str:
    for row_number, values in rows:
        if row_number > 4:
            break
        for value in values.values():
            match = re.search(r"生效时间[：:]\s*(\d{4}-\d{2}-\d{2})", value)
            if match:
                return match.group(1)
    return "未识别"


def _validate_header(
    definition: dict[str, str], rows: list[tuple[int, dict[int, str]]]
) -> list[str]:
    row_map = {row_number: values for row_number, values in rows}
    header = row_map.get(4, {})
    required = {
        2: "国家/地区",
        5: "重量",
        8: "运费",
        9: "挂号费",
    }
    errors = []
    for column, expected in required.items():
        if expected not in header.get(column, ""):
            errors.append(
                f"{definition['name']}：第4行第{column}列未识别为“{expected}”"
            )
    return errors


def _extract_channel(
    definition: dict[str, str],
    rows: list[tuple[int, dict[int, str]]],
) -> tuple[dict[str, Any], list[str]]:
    errors = _validate_header(definition, rows)
    rates = []
    suspicious_rows = []
    for source_row, values in rows:
        country = values.get(2, "").strip()
        weight_text = values.get(5, "").strip()
        price_text = values.get(8, "").strip()
        fee_text = values.get(9, "").strip()
        weight_match = WEIGHT_RE.match(weight_text)
        numeric_price_fee = False
        try:
            price = float(price_text)
            fee = float(fee_text)
            numeric_price_fee = True
        except ValueError:
            price = fee = 0.0
        if country and numeric_price_fee and weight_text and not weight_match:
            suspicious_rows.append(source_row)
            continue
        if not country or not weight_match or not numeric_price_fee:
            continue
        try:
            increment = float(values[6]) if values.get(6, "").strip() else 0.0
            minimum = float(values[7]) if values.get(7, "").strip() else 0.0
        except ValueError:
            errors.append(f"{definition['name']}：第 {source_row} 行进位制或最低计费重不是数字")
            continue
        rates.append(
            {
                "country": country,
                "zone": values.get(4, "").strip(),
                "transitTime": values.get(3, "").strip(),
                "minKg": _clean_number(float(weight_match.group(1))),
                "maxKg": _clean_number(float(weight_match.group(2))),
                "incrementKg": _clean_number(increment),
                "minimumWeightKg": _clean_number(minimum),
                "pricePerKg": _clean_number(price),
                "registrationFee": _clean_number(fee),
                "sourceSheet": definition["fullName"],
                "sourceRow": source_row,
            }
        )
    if suspicious_rows:
        errors.append(
            f"{definition['name']}：第 {', '.join(map(str, suspicious_rows[:10]))} "
            "行重量档位无法识别"
        )
    if not rates:
        errors.append(f"{definition['name']}：没有读取到有效费率")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    keys = set()
    for rate in rates:
        key = (
            rate["country"],
            rate["zone"],
            rate["minKg"],
            rate["maxKg"],
        )
        if key in keys:
            errors.append(
                f"{definition['name']}：{rate['country']} {rate['zone']} "
                f"{rate['minKg']}-{rate['maxKg']}kg 档位重复"
            )
        keys.add(key)
        groups[(rate["country"], rate["zone"])].append(rate)

    normalized = []
    for (country, zone), group in groups.items():
        minimums = {
            float(item["minimumWeightKg"])
            for item in group
            if float(item["minimumWeightKg"]) > 0
        }
        if len(minimums) > 1:
            errors.append(
                f"{definition['name']}：{country} {zone} 出现多个最低计费重"
            )
        minimum = next(iter(minimums), 0.0)
        sorted_group = sorted(group, key=lambda item: (item["minKg"], item["maxKg"]))
        for previous, current in zip(sorted_group, sorted_group[1:]):
            if float(current["minKg"]) < float(previous["maxKg"]):
                errors.append(
                    f"{definition['name']}：{country} {zone} "
                    f"{current['sourceRow']} 行与上一档重叠"
                )
        for item in sorted_group:
            item["minimumWeightKg"] = _clean_number(minimum)
            normalized.append(item)

    return (
        {
            "key": definition["key"],
            "company": definition.get("company", "云途"),
            **(
                {"parentCompany": definition["parentCompany"]}
                if definition.get("parentCompany")
                else {}
            ),
            "name": definition["name"],
            "fullName": definition["fullName"],
            "cargoType": definition["cargoType"],
            "effectiveDate": _extract_effective_date(rows),
            "rates": normalized,
        },
        errors,
    )


def parse_yuntu_workbook(content: bytes) -> list[dict[str, Any]]:
    errors = []
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportValidationError(["文件不是有效的 .xlsx 工作簿"]) from exc
    with book:
        try:
            paths = _sheet_paths(book)
            shared = _load_shared_strings(book)
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
        missing = [
            definition["fullName"]
            for definition in CHANNEL_DEFINITIONS
            if definition["fullName"] not in paths
        ]
        if missing:
            raise ImportValidationError(
                ["缺少工作表：" + "、".join(missing)]
            )
        channels = []
        for definition in CHANNEL_DEFINITIONS:
            rows = _read_sheet(book, shared, paths[definition["fullName"]])
            channel, channel_errors = _extract_channel(definition, rows)
            channels.append(channel)
            errors.extend(channel_errors)
    if errors:
        raise ImportValidationError(errors)
    return channels


def parse_shangpai_workbook(content: bytes) -> list[dict[str, Any]]:
    errors = []
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportValidationError(["文件不是有效的 .xlsx 工作簿"]) from exc
    with book:
        try:
            paths = _sheet_paths(book)
            shared = _load_shared_strings(book)
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
        missing = [
            definition["fullName"]
            for definition in SHANGPAI_CHANNEL_DEFINITIONS
            if definition["fullName"] not in paths
        ]
        if missing:
            raise ImportValidationError(["缺少工作表：" + "、".join(missing)])
        channels = []
        for base_definition in SHANGPAI_CHANNEL_DEFINITIONS:
            definition = {
                **base_definition,
                "company": "云途商派",
                "parentCompany": "云途",
            }
            rows = _read_sheet(book, shared, paths[definition["fullName"]])
            channel, channel_errors = _extract_channel(definition, rows)
            channels.append(channel)
            errors.extend(channel_errors)
    if errors:
        raise ImportValidationError(errors)
    return channels


def _one_effective_dates(
    rows: list[tuple[int, dict[int, str]]],
) -> dict[str, str]:
    dates = {}
    for _, values in rows:
        lookup = values.get(3, "").strip()
        match = ONE_DATE_RE.search(values.get(7, ""))
        if lookup and match:
            dates[lookup] = (
                f"{int(match.group(1)):04d}-"
                f"{int(match.group(2)):02d}-"
                f"{int(match.group(3)):02d}"
            )
    return dates


def _validate_one_header(
    definition: dict[str, Any],
    rows: list[tuple[int, dict[int, str]]],
) -> list[str]:
    header = dict(rows).get(7, {})
    if definition.get("defaultCountry"):
        required = {2: "对接代码", 3: "重量", 4: "运费", 5: "处理费"}
    else:
        required = {
            2: "对接代码",
            3: "国家",
            4: "重量",
            5: "运费",
            6: "处理费",
        }
    errors = []
    for column, expected in required.items():
        if expected not in header.get(column, ""):
            errors.append(
                f"{definition['name']}：{definition['sheetName']}第7行"
                f"第{column}列未识别为“{expected}”"
            )
    return errors


def _extract_one_australia_channel(
    definition: dict[str, Any],
    rows: list[tuple[int, dict[int, str]]],
    effective_dates: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    errors = []
    header = dict(rows).get(7, {})
    required = {2: "对接代码", 3: "国家", 4: "分区", 5: "重量", 6: "运费", 7: "挂号费"}
    for column, expected in required.items():
        if expected not in header.get(column, ""):
            errors.append(
                f"{definition['name']}：{definition['sheetName']}第7行"
                f"第{column}列未识别为“{expected}”"
            )

    row_map = {row_number: values for row_number, values in rows}
    source_name = definition.get("sourceName", definition["fullName"])
    start_rows = [
        row_number
        for row_number, values in rows
        if values.get(2, "").strip() == source_name
    ]
    if len(start_rows) != 1:
        errors.append(
            f"{definition['name']}：应找到1个渠道区块，实际找到{len(start_rows)}个"
        )
        return (
            {
                "key": definition["key"],
                "company": "壹号物流",
                "name": definition["name"],
                "fullName": definition["fullName"],
                "cargoType": definition["cargoType"],
                "effectiveDate": effective_dates.get(definition["dateLookup"], "未识别"),
                "volumeDivisor": definition["volumeDivisor"],
                "rates": [],
            },
            errors,
        )

    start_row = start_rows[0]
    end_row = max(row_map, default=start_row)
    for row_number in range(start_row + 1, end_row + 1):
        if row_map.get(row_number, {}).get(2, "").strip():
            end_row = row_number - 1
            break

    zone_aliases = {
        "邮编一区": "1区",
        "邮编二区": "2区",
        "邮编三区": "3区",
        "邮编四区": "4区",
    }
    current_country = "澳大利亚"
    current_zone = ""
    raw_rates = []
    suspicious_rows = []
    for source_row in range(start_row, end_row + 1):
        values = row_map.get(source_row, {})
        if values.get(3, "").strip():
            raw_country = values[3].strip()
            current_country = COUNTRY_ALIASES.get(raw_country, raw_country)
        if values.get(4, "").strip():
            current_zone = zone_aliases.get(values[4].strip(), values[4].strip())
        weight_text = values.get(5, "").strip()
        weight_match = ONE_WEIGHT_RE.match(weight_text)
        try:
            price = float(values.get(6, "").strip())
            fee = float(values.get(7, "").strip())
            numeric_price_fee = True
        except ValueError:
            price = fee = 0.0
            numeric_price_fee = False
        if weight_text and numeric_price_fee and not weight_match:
            suspicious_rows.append(source_row)
            continue
        if not current_zone or not weight_match or not numeric_price_fee:
            continue
        raw_rates.append(
            {
                "country": current_country,
                "zone": current_zone,
                "transitTime": values.get(8, "").strip(),
                "rawMinKg": float(weight_match.group(1)),
                "maxKg": float(weight_match.group(2)),
                "pricePerKg": price,
                "registrationFee": fee,
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
            }
        )

    if suspicious_rows:
        errors.append(
            f"{definition['name']}：第 {', '.join(map(str, suspicious_rows[:10]))}"
            " 行重量档位无法识别"
        )
    if not raw_rates:
        errors.append(f"{definition['name']}：没有读取到有效费率")

    rates = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rate in raw_rates:
        grouped[(rate["country"], rate["zone"])].append(rate)
    for (country, zone), group in grouped.items():
        sorted_group = sorted(group, key=lambda item: (item["rawMinKg"], item["maxKg"]))
        transit_time = next(
            (item["transitTime"] for item in sorted_group if item["transitTime"]),
            "",
        )
        previous_max = None
        for item in sorted_group:
            raw_min = item.pop("rawMinKg")
            min_kg = raw_min if previous_max is None else previous_max
            max_kg = item["maxKg"]
            if max_kg <= min_kg:
                errors.append(
                    f"{definition['name']}：{country}{zone}第{item['sourceRow']}行"
                    "重量上限不大于下限"
                )
                continue
            item.update(
                {
                    "transitTime": item["transitTime"] or transit_time,
                    "minKg": _clean_number(min_kg),
                    "maxKg": _clean_number(max_kg),
                    "incrementKg": 0.001,
                    "minimumWeightKg": _clean_number(float(definition["minimumWeightKg"])),
                    "pricePerKg": _clean_number(item["pricePerKg"]),
                    "registrationFee": _clean_number(item["registrationFee"]),
                }
            )
            previous_max = max_kg
            rates.append(item)

    effective_date = effective_dates.get(definition["dateLookup"], "未识别")
    if effective_date == "未识别":
        errors.append(f"{definition['name']}：目录中未识别到生效日期")
    return (
        {
            "key": definition["key"],
            "company": "壹号物流",
            "name": definition["name"],
            "fullName": definition["fullName"],
            "cargoType": definition["cargoType"],
            "effectiveDate": effective_date,
            "volumeDivisor": definition["volumeDivisor"],
            "rates": rates,
        },
        errors,
    )


def _extract_one_channel(
    definition: dict[str, Any],
    rows: list[tuple[int, dict[int, str]]],
    effective_dates: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    if definition.get("layout") == "australia":
        return _extract_one_australia_channel(definition, rows, effective_dates)
    errors = _validate_one_header(definition, rows)
    row_map = {row_number: values for row_number, values in rows}
    source_name = definition.get("sourceName", definition["fullName"])
    start_rows = [
        row_number
        for row_number, values in rows
        if values.get(2, "").strip() == source_name
    ]
    if len(start_rows) != 1:
        errors.append(
            f"{definition['name']}：应找到1个渠道区块，实际找到{len(start_rows)}个"
        )
        return (
            {
                "key": definition["key"],
                "company": "壹号物流",
                "name": definition["name"],
                "fullName": definition["fullName"],
                "cargoType": definition["cargoType"],
                "effectiveDate": effective_dates.get(
                    definition["dateLookup"], "未识别"
                ),
                "volumeDivisor": definition["volumeDivisor"],
                "rates": [],
            },
            errors,
        )

    start_row = start_rows[0]
    end_row = max(row_map, default=start_row)
    for row_number in range(start_row + 1, end_row + 1):
        if row_map.get(row_number, {}).get(2, "").strip():
            end_row = row_number - 1
            break

    default_country = definition.get("defaultCountry", "")
    country_column = 0 if default_country else 3
    weight_column = 3 if default_country else 4
    price_column = 4 if default_country else 5
    fee_column = 5 if default_country else 6
    transit_column = 7 if default_country else 8
    current_country = default_country
    raw_rates = []
    suspicious_rows = []

    for source_row in range(start_row, end_row + 1):
        values = row_map.get(source_row, {})
        if country_column and values.get(country_column, "").strip():
            current_country = COUNTRY_ALIASES.get(
                values[country_column].strip(), values[country_column].strip()
            )
        weight_text = values.get(weight_column, "").strip()
        price_text = values.get(price_column, "").strip()
        fee_text = values.get(fee_column, "").strip()
        weight_match = ONE_WEIGHT_RE.match(weight_text)
        try:
            price = float(price_text)
            fee = float(fee_text)
            numeric_price_fee = True
        except ValueError:
            price = fee = 0.0
            numeric_price_fee = False
        if weight_text and numeric_price_fee and not weight_match:
            suspicious_rows.append(source_row)
            continue
        if not current_country or not weight_match or not numeric_price_fee:
            continue
        raw_rates.append(
            {
                "country": current_country,
                "zone": "",
                "transitTime": values.get(transit_column, "").strip(),
                "rawMinKg": float(weight_match.group(1)),
                "maxKg": float(weight_match.group(2)),
                "pricePerKg": price,
                "registrationFee": fee,
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
            }
        )

    if suspicious_rows:
        errors.append(
            f"{definition['name']}：第 {', '.join(map(str, suspicious_rows[:10]))}"
            " 行重量档位无法识别"
        )
    if not raw_rates:
        errors.append(f"{definition['name']}：没有读取到有效费率")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rate in raw_rates:
        groups[rate["country"]].append(rate)

    rates = []
    for country, group in groups.items():
        sorted_group = sorted(
            group, key=lambda item: (item["rawMinKg"], item["maxKg"])
        )
        transit_time = next(
            (
                item["transitTime"]
                for item in sorted_group
                if item["transitTime"]
            ),
            "",
        )
        previous_max = None
        for item in sorted_group:
            raw_min = item.pop("rawMinKg")
            min_kg = raw_min if previous_max is None else previous_max
            max_kg = item["maxKg"]
            if max_kg <= min_kg:
                errors.append(
                    f"{definition['name']}：{country}第{item['sourceRow']}行"
                    "重量上限不大于下限"
                )
                continue
            increment = 1.0 if default_country and max_kg > 5 else 0.001
            item.update(
                {
                    "transitTime": item["transitTime"] or transit_time,
                    "minKg": _clean_number(min_kg),
                    "maxKg": _clean_number(max_kg),
                    "incrementKg": _clean_number(increment),
                    "minimumWeightKg": _clean_number(
                        float(definition["minimumWeightKg"])
                    ),
                    "pricePerKg": _clean_number(item["pricePerKg"]),
                    "registrationFee": _clean_number(item["registrationFee"]),
                }
            )
            previous_max = max_kg
            rates.append(item)

    effective_date = effective_dates.get(definition["dateLookup"], "未识别")
    if effective_date == "未识别":
        errors.append(f"{definition['name']}：目录中未识别到生效日期")

    return (
        {
            "key": definition["key"],
            "company": "壹号物流",
            "name": definition["name"],
            "fullName": definition["fullName"],
            "cargoType": definition["cargoType"],
            "effectiveDate": effective_date,
            "volumeDivisor": definition["volumeDivisor"],
            "rates": rates,
        },
        errors,
    )


def parse_one_workbook(content: bytes) -> list[dict[str, Any]]:
    errors = []
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportValidationError(["文件不是有效的 .xlsx 工作簿"]) from exc
    with book:
        try:
            paths = _sheet_paths(book)
            shared = _load_shared_strings(book)
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
        required_sheets = {
            "目录",
            *(definition["sheetName"] for definition in ONE_CHANNEL_DEFINITIONS),
        }
        missing = sorted(required_sheets - paths.keys())
        if missing:
            raise ImportValidationError(["缺少工作表：" + "、".join(missing)])
        effective_dates = _one_effective_dates(
            _read_sheet(book, shared, paths["目录"])
        )
        rows_by_sheet = {
            sheet_name: _read_sheet(book, shared, paths[sheet_name])
            for sheet_name in required_sheets
            if sheet_name != "目录"
        }
        channels = []
        for definition in ONE_CHANNEL_DEFINITIONS:
            channel, channel_errors = _extract_one_channel(
                definition,
                rows_by_sheet[definition["sheetName"]],
                effective_dates,
            )
            channels.append(channel)
            errors.extend(channel_errors)
    if errors:
        raise ImportValidationError(errors)
    return channels


def _yuanpeng_directory_metadata(
    rows: list[tuple[int, dict[int, str]]],
) -> dict[str, dict[str, str]]:
    metadata = {}
    for _, values in rows:
        channel_name = values.get(3, "").strip()
        date_match = ONE_DATE_RE.search(values.get(6, ""))
        if not channel_name:
            continue
        metadata[channel_name] = {
            "effectiveDate": (
                f"{int(date_match.group(1)):04d}-"
                f"{int(date_match.group(2)):02d}-"
                f"{int(date_match.group(3)):02d}"
                if date_match
                else "未识别"
            ),
            "transitTime": values.get(4, "").strip(),
        }
    return metadata


def _normalize_yuanpeng_country(raw_country: str) -> tuple[str, str]:
    zone_match = re.fullmatch(r"(?:澳洲|澳大利亚)([一二三四])区", raw_country)
    if zone_match:
        zone_number = {"一": "1区", "二": "2区", "三": "3区", "四": "4区"}
        return "澳大利亚", zone_number[zone_match.group(1)]
    return COUNTRY_ALIASES.get(raw_country, raw_country), ""


def _yuanpeng_minimum_weight(
    definition: dict[str, Any], country: str, first_min_kg: float
) -> float:
    configured = float(definition.get("minimumWeightKg", 0))
    if definition.get("eubMinimums"):
        if country in {"新西兰", "巴西", "日本", "哈萨克斯坦"}:
            configured = 0.05
        elif country == "乌克兰":
            configured = 0.01
    return max(configured, first_min_kg)


def _validate_yuanpeng_header(
    definition: dict[str, Any], rows: list[tuple[int, dict[int, str]]]
) -> list[str]:
    header = dict(rows).get(3, {})
    required = {2: "国家", 3: "限重", 4: "运费", 5: "挂号费"}
    errors = []
    for column, expected in required.items():
        if expected not in header.get(column, ""):
            errors.append(
                f"{definition['name']}：{definition['sheetName']}第3行"
                f"第{column}列未识别为“{expected}”"
            )
    return errors


def _extract_yuanpeng_channel(
    definition: dict[str, Any],
    rows: list[tuple[int, dict[int, str]]],
    directory_metadata: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], list[str]]:
    errors = _validate_yuanpeng_header(definition, rows)
    lookup = definition.get("dateLookup", definition["fullName"])
    metadata = directory_metadata.get(lookup, {})
    default_transit = metadata.get("transitTime", "")
    current_country = ""
    current_zone = ""
    raw_rates = []
    suspicious_rows = []
    continuation_countries = {"罗马尼亚", "斯洛文尼亚", "克罗地亚"}

    for source_row, values in rows:
        weight_text = values.get(3, "").strip()
        price_text = values.get(4, "").strip()
        fee_text = values.get(5, "").strip()
        weight_match = ONE_WEIGHT_RE.match(weight_text)
        try:
            price = float(price_text)
            fee = float(fee_text)
            numeric_price_fee = True
        except ValueError:
            price = fee = 0.0
            numeric_price_fee = False
        if weight_text and numeric_price_fee and not weight_match:
            suspicious_rows.append(source_row)
            continue
        if not weight_match or not numeric_price_fee:
            continue

        raw_min = float(weight_match.group(1))
        raw_country = values.get(2, "").strip()
        is_mislabeled_continuation = (
            raw_country == "爱尔兰"
            and raw_min >= 2
            and current_country in continuation_countries
            and definition["sheetName"] in {
                "普货小包专线",
                "特货小包专线",
                "普F小包专线",
                "特F小包专线",
                "纯电小包专线",
                "特敏感小包专线",
            }
        )
        if raw_country and not is_mislabeled_continuation:
            current_country, current_zone = _normalize_yuanpeng_country(raw_country)
        if not current_country:
            errors.append(f"{definition['name']}：第{source_row}行未识别国家")
            continue
        country_filter = definition.get("countryFilter")
        if country_filter and current_country not in country_filter:
            continue
        raw_rates.append(
            {
                "country": current_country,
                "zone": current_zone,
                "transitTime": values.get(
                    int(definition.get("transitColumn", 6)), ""
                ).strip(),
                "rawMinKg": raw_min,
                "maxKg": float(weight_match.group(2)),
                "pricePerKg": price,
                "registrationFee": fee,
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
            }
        )

    if suspicious_rows:
        errors.append(
            f"{definition['name']}：第 {', '.join(map(str, suspicious_rows[:10]))}"
            " 行重量档位无法识别"
        )
    if not raw_rates:
        errors.append(f"{definition['name']}：没有读取到有效费率")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rate in raw_rates:
        groups[(rate["country"], rate["zone"])].append(rate)

    rates = []
    for (country, zone), group in groups.items():
        sorted_group = sorted(
            group, key=lambda item: (item["rawMinKg"], item["maxKg"])
        )
        transit_time = next(
            (item["transitTime"] for item in sorted_group if item["transitTime"]),
            default_transit,
        )
        minimum_weight = _yuanpeng_minimum_weight(
            definition, country, sorted_group[0]["rawMinKg"]
        )
        previous_max = None
        for item in sorted_group:
            raw_min = item.pop("rawMinKg")
            min_kg = raw_min if previous_max is None else previous_max
            max_kg = item["maxKg"]
            if max_kg <= min_kg:
                errors.append(
                    f"{definition['name']}：{country}{zone}第{item['sourceRow']}行"
                    "重量上限不大于下限"
                )
                continue
            item.update(
                {
                    "transitTime": item["transitTime"] or transit_time,
                    "minKg": _clean_number(min_kg),
                    "maxKg": _clean_number(max_kg),
                    "incrementKg": 0.001,
                    "minimumWeightKg": _clean_number(minimum_weight),
                    "pricePerKg": _clean_number(item["pricePerKg"]),
                    "registrationFee": _clean_number(item["registrationFee"]),
                }
            )
            previous_max = max_kg
            rates.append(item)

    effective_date = metadata.get("effectiveDate", "未识别")
    if effective_date == "未识别":
        errors.append(f"{definition['name']}：目录中未识别到生效日期")
    return (
        {
            "key": definition["key"],
            "company": "远朋物流",
            "name": definition["name"],
            "fullName": definition["fullName"],
            "cargoType": definition["cargoType"],
            "effectiveDate": effective_date,
            "rates": rates,
        },
        errors,
    )


def parse_yuanpeng_workbook(content: bytes) -> list[dict[str, Any]]:
    errors = []
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportValidationError(["文件不是有效的 .xlsx 工作簿"]) from exc
    with book:
        try:
            paths = _sheet_paths(book)
            shared = _load_shared_strings(book)
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
        required_sheets = {
            "目录",
            *(definition["sheetName"] for definition in YUANPENG_CHANNEL_DEFINITIONS),
        }
        missing = sorted(required_sheets - paths.keys())
        if missing:
            raise ImportValidationError(["缺少工作表：" + "、".join(missing)])
        directory_metadata = _yuanpeng_directory_metadata(
            _read_sheet(book, shared, paths["目录"])
        )
        rows_by_sheet = {
            sheet_name: _read_sheet(book, shared, paths[sheet_name])
            for sheet_name in required_sheets
            if sheet_name != "目录"
        }
        channels = []
        for definition in YUANPENG_CHANNEL_DEFINITIONS:
            channel, channel_errors = _extract_yuanpeng_channel(
                definition,
                rows_by_sheet[definition["sheetName"]],
                directory_metadata,
            )
            channels.append(channel)
            errors.extend(channel_errors)
    if errors:
        raise ImportValidationError(errors)
    return channels


def _yanwen_effective_date(
    rows: list[tuple[int, dict[int, str]]],
) -> str:
    value = dict(rows).get(2, {}).get(2, "").strip()
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if not match:
        return "未识别"
    return (
        f"{int(match.group(1)):04d}-"
        f"{int(match.group(2)):02d}-"
        f"{int(match.group(3)):02d}"
    )


def _yanwen_transit_times(
    rows: list[tuple[int, dict[int, str]]],
) -> dict[str, str]:
    result = {}
    for _, values in rows:
        country = values.get(2, "").strip()
        transit = values.get(4, "").strip()
        if country and "工作日" in transit:
            result[COUNTRY_ALIASES.get(country, country)] = transit
    return result


def _validate_yanwen_header(
    definition: dict[str, Any], rows: list[tuple[int, dict[int, str]]]
) -> list[str]:
    header = dict(rows).get(4, {})
    required = {
        2: "国家",
        4: "公斤运费",
        5: "处理费",
        6: "重量段",
        7: "最小计费重量",
    }
    errors = []
    for column, expected in required.items():
        if expected not in header.get(column, ""):
            errors.append(
                f"{definition['name']}：{definition['sheetName']}第4行"
                f"第{column}列未识别为“{expected}”"
            )
    return errors


def _normalize_yanwen_country(
    raw_country: str, country_code: str
) -> tuple[str, str]:
    zone = country_code if re.fullmatch(r"[一二三四1234]区", country_code) else ""
    if zone and zone[0] in "一二三四":
        zone = {"一": "1区", "二": "2区", "三": "3区", "四": "4区"}[
            zone[0]
        ]
    return COUNTRY_ALIASES.get(raw_country, raw_country), zone


def _extract_yanwen_channel(
    definition: dict[str, Any],
    rows: list[tuple[int, dict[int, str]]],
) -> tuple[dict[str, Any], list[str]]:
    errors = _validate_yanwen_header(definition, rows)
    transit_times = _yanwen_transit_times(rows)
    raw_rates = []
    suspicious_rows = []

    for source_row, values in rows:
        if source_row < 5:
            continue
        country_text = values.get(2, "").strip()
        weight_text = values.get(6, "").strip()
        weight_match = ONE_WEIGHT_RE.match(weight_text)
        try:
            price = float(values.get(4, "").strip())
            fee = float(values.get(5, "").strip())
            minimum = float(values.get(7, "").strip())
            numeric_rate = True
        except ValueError:
            price = fee = minimum = 0.0
            numeric_rate = False
        if country_text and weight_text and numeric_rate and not weight_match:
            suspicious_rows.append(source_row)
            continue
        if not country_text or not weight_match or not numeric_rate:
            continue
        country, zone = _normalize_yanwen_country(
            country_text, values.get(3, "").strip()
        )
        raw_rates.append(
            {
                "country": country,
                "zone": zone,
                "transitTime": transit_times.get(country, ""),
                "rawMinKg": float(weight_match.group(1)),
                "maxKg": float(weight_match.group(2)),
                "incrementKg": 0.001,
                "minimumWeightKg": minimum,
                "pricePerKg": price,
                "registrationFee": fee,
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
            }
        )

    # Several Yanwen products quote Japan as first-weight/continued-weight.
    # Convert that affine fee into the pricing engine's kg-rate + fixed-fee model.
    for source_row, values in rows:
        if source_row < 5:
            continue
        country_text = values.get(2, "").strip()
        weight_text = values.get(4, "").strip()
        weight_match = ONE_WEIGHT_RE.match(weight_text)
        try:
            first_weight = float(values.get(5, "").strip())
            first_price = float(values.get(6, "").strip())
            continued_weight = float(values.get(7, "").strip())
            continued_price = float(values.get(8, "").strip())
            handling_fee = float(values.get(9, "").strip())
            numeric_step_rate = True
        except ValueError:
            first_weight = first_price = continued_weight = 0.0
            continued_price = handling_fee = 0.0
            numeric_step_rate = False
        if not country_text or not weight_match or not numeric_step_rate:
            continue
        if first_weight <= 0 or continued_weight <= 0:
            errors.append(f"{definition['name']}：第{source_row}行首重或续重必须大于0")
            continue
        country, zone = _normalize_yanwen_country(
            country_text, values.get(3, "").strip()
        )
        price_per_kg = continued_price / continued_weight
        fixed_fee = handling_fee + first_price - price_per_kg * first_weight
        raw_rates.append(
            {
                "country": country,
                "zone": zone,
                "transitTime": transit_times.get(country, ""),
                "rawMinKg": float(weight_match.group(1)),
                "maxKg": float(weight_match.group(2)),
                "incrementKg": continued_weight,
                "minimumWeightKg": first_weight,
                "pricePerKg": price_per_kg,
                "registrationFee": fixed_fee,
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
            }
        )

    if suspicious_rows:
        errors.append(
            f"{definition['name']}：第 {', '.join(map(str, suspicious_rows[:10]))}"
            " 行重量档位无法识别"
        )
    if not raw_rates:
        errors.append(f"{definition['name']}：没有读取到有效费率")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rate in raw_rates:
        groups[(rate["country"], rate["zone"])].append(rate)

    rates = []
    for (country, zone), group in groups.items():
        sorted_group = sorted(
            group, key=lambda item: (item["rawMinKg"], item["maxKg"])
        )
        previous_max = None
        for item in sorted_group:
            raw_min = item.pop("rawMinKg")
            min_kg = raw_min if previous_max is None else previous_max
            max_kg = item["maxKg"]
            if max_kg <= min_kg:
                errors.append(
                    f"{definition['name']}：{country}{zone}第{item['sourceRow']}行"
                    "重量上限不大于下限"
                )
                continue
            item.update(
                {
                    "minKg": _clean_number(min_kg),
                    "maxKg": _clean_number(max_kg),
                    "incrementKg": _clean_number(float(item["incrementKg"])),
                    "minimumWeightKg": _clean_number(
                        float(item["minimumWeightKg"])
                    ),
                    "pricePerKg": _clean_number(float(item["pricePerKg"])),
                    "registrationFee": _clean_number(
                        float(item["registrationFee"])
                    ),
                }
            )
            previous_max = max_kg
            rates.append(item)

    effective_date = _yanwen_effective_date(rows)
    if effective_date == "未识别":
        errors.append(f"{definition['name']}：未识别到生效日期")
    return (
        {
            "key": definition["key"],
            "company": "燕文物流",
            "name": definition["name"],
            "fullName": definition["fullName"],
            "cargoType": definition["cargoType"],
            "effectiveDate": effective_date,
            "rates": rates,
        },
        errors,
    )


def parse_yanwen_workbook(content: bytes) -> list[dict[str, Any]]:
    errors = []
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportValidationError(["文件不是有效的 .xlsx 工作簿"]) from exc
    with book:
        try:
            paths = _sheet_paths(book)
            shared = _load_shared_strings(book)
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
        required_sheets = {
            definition["sheetName"] for definition in YANWEN_CHANNEL_DEFINITIONS
        }
        missing = sorted(required_sheets - paths.keys())
        if missing:
            raise ImportValidationError(["缺少工作表：" + "、".join(missing)])
        channels = []
        for definition in YANWEN_CHANNEL_DEFINITIONS:
            rows = _read_sheet(book, shared, paths[definition["sheetName"]])
            channel, channel_errors = _extract_yanwen_channel(definition, rows)
            channels.append(channel)
            errors.extend(channel_errors)
    if errors:
        raise ImportValidationError(errors)
    return channels


def _parse_ubi_date(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    if match:
        return (
            f"{int(match.group(1)):04d}-"
            f"{int(match.group(2)):02d}-"
            f"{int(match.group(3)):02d}"
        )
    try:
        serial = float(text)
    except ValueError:
        return "未识别"
    if serial < 1:
        return "未识别"
    return (datetime(1899, 12, 30) + timedelta(days=serial)).strftime("%Y-%m-%d")


def _validate_ubi_main_header(
    definition: dict[str, Any], rows: list[tuple[int, dict[int, str]]]
) -> list[str]:
    row_map = dict(rows)
    errors = []
    if row_map.get(2, {}).get(2, "").strip() != "大陆":
        errors.append(f"{definition['name']}：第2行未识别为大陆价格表")
    if row_map.get(2, {}).get(7, "").strip() != "上门揽收":
        errors.append(f"{definition['name']}：第2行未识别到上门揽收价格")
    header = row_map.get(3, {})
    required = {5: "公斤", 7: "操作费", 8: "每公斤"}
    for column, expected in required.items():
        if expected not in header.get(column, ""):
            errors.append(
                f"{definition['name']}：第3行第{column}列未识别为“{expected}”"
            )
    return errors


def _ubi_channel_payload(
    definition: dict[str, Any], rates: list[dict[str, Any]], effective_date: str
) -> dict[str, Any]:
    return {
        "key": definition["key"],
        "company": "UBI",
        "name": definition["name"],
        "fullName": definition["fullName"],
        "cargoType": definition["cargoType"],
        "effectiveDate": effective_date,
        "rates": rates,
    }


def _extract_ubi_australia_channel(
    definition: dict[str, Any], rows: list[tuple[int, dict[int, str]]]
) -> tuple[dict[str, Any], list[str]]:
    errors = _validate_ubi_main_header(definition, rows)
    zone_aliases = {"一区": "1区", "二区": "2区", "三区": "3区", "四区": "4区"}
    current_zone = ""
    current_transit = ""
    raw_rates = []
    effective_date = "未识别"
    for source_row, values in rows:
        origin = values.get(2, "").strip()
        if source_row > 3 and origin in {"香港", "备注"}:
            break
        if source_row <= 3:
            continue
        if values.get(4, "").strip():
            current_zone = zone_aliases.get(
                values[4].strip(), values[4].strip()
            )
        if values.get(11, "").strip():
            current_transit = values[11].strip()
        try:
            raw_min = float(values.get(5, "").strip())
            max_kg = float(values.get(6, "").strip())
            registration_fee = float(values.get(7, "").strip())
            price_per_kg = float(values.get(8, "").strip())
        except ValueError:
            continue
        if not current_zone:
            errors.append(f"{definition['name']}：第{source_row}行未识别澳大利亚分区")
            continue
        row_date = _parse_ubi_date(values.get(12, ""))
        if effective_date == "未识别" and row_date != "未识别":
            effective_date = row_date
        raw_rates.append(
            {
                "country": definition["country"],
                "zone": current_zone,
                "transitTime": current_transit,
                "rawMinKg": raw_min,
                "maxKg": max_kg,
                "pricePerKg": price_per_kg,
                "registrationFee": registration_fee,
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rate in raw_rates:
        grouped[rate["zone"]].append(rate)
    if set(grouped) != {"1区", "2区", "3区", "4区"}:
        errors.append(
            f"{definition['name']}：澳大利亚应包含1至4区，实际为"
            + "、".join(sorted(grouped))
        )
    rates = []
    for zone, group in grouped.items():
        previous_max = None
        for item in sorted(group, key=lambda rate: (rate["rawMinKg"], rate["maxKg"])):
            raw_min = item.pop("rawMinKg")
            min_kg = raw_min if previous_max is None else previous_max
            max_kg = float(item["maxKg"])
            if max_kg <= min_kg:
                errors.append(
                    f"{definition['name']}：{zone}第{item['sourceRow']}行重量档位异常"
                )
                continue
            item.update(
                {
                    "minKg": _clean_number(min_kg),
                    "maxKg": _clean_number(max_kg),
                    "incrementKg": 0.001,
                    "minimumWeightKg": 0.001,
                    "pricePerKg": _clean_number(float(item["pricePerKg"])),
                    "registrationFee": _clean_number(
                        float(item["registrationFee"])
                    ),
                }
            )
            rates.append(item)
            previous_max = max_kg
    if not rates:
        errors.append(f"{definition['name']}：没有读取到有效费率")
    if effective_date == "未识别":
        errors.append(f"{definition['name']}：未识别到生效日期")
    return _ubi_channel_payload(definition, rates, effective_date), errors


def _extract_ubi_country_channel(
    definition: dict[str, Any], rows: list[tuple[int, dict[int, str]]]
) -> tuple[dict[str, Any], list[str]]:
    errors = _validate_ubi_main_header(definition, rows)
    candidates = []
    current_origin = ""
    for source_row, values in rows:
        country_or_origin = values.get(2, "").strip()
        if country_or_origin in {"大陆", "香港"}:
            current_origin = country_or_origin
            continue
        if (
            current_origin != "大陆"
            or country_or_origin != definition["country"]
        ):
            continue
        try:
            min_kg = float(values.get(5, "").strip())
            max_kg = float(values.get(6, "").strip())
            registration_fee = float(values.get(7, "").strip())
            price_per_kg = float(values.get(8, "").strip())
        except ValueError:
            continue
        candidates.append(
            {
                "country": definition["country"],
                "zone": "",
                "transitTime": values.get(11, "").strip(),
                "minKg": _clean_number(min_kg),
                "maxKg": _clean_number(max_kg),
                "incrementKg": 0.001,
                "minimumWeightKg": 0.001,
                "pricePerKg": _clean_number(price_per_kg),
                "registrationFee": _clean_number(registration_fee),
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
                "effectiveDate": _parse_ubi_date(values.get(12, "")),
            }
        )
    if len(candidates) != 1:
        errors.append(
            f"{definition['name']}：大陆价格表应找到1条{definition['country']}费率，"
            f"实际找到{len(candidates)}条"
        )
    rates = []
    effective_date = "未识别"
    if candidates:
        rate = candidates[0]
        effective_date = rate.pop("effectiveDate")
        rates.append(rate)
    if effective_date == "未识别":
        errors.append(f"{definition['name']}：未识别到生效日期")
    return _ubi_channel_payload(definition, rates, effective_date), errors


def parse_ubi_main_workbook(content: bytes) -> list[dict[str, Any]]:
    errors = []
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportValidationError(["文件不是有效的 .xlsx 工作簿"]) from exc
    with book:
        try:
            paths = _sheet_paths(book)
            shared = _load_shared_strings(book)
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
        required_sheets = {
            definition["sheetName"] for definition in UBI_MAIN_CHANNEL_DEFINITIONS
        }
        missing = sorted(required_sheets - paths.keys())
        if missing:
            raise ImportValidationError(["缺少工作表：" + "、".join(missing)])
        channels = []
        rows_by_sheet = {
            sheet_name: _read_sheet(book, shared, paths[sheet_name])
            for sheet_name in required_sheets
        }
        for definition in UBI_MAIN_CHANNEL_DEFINITIONS:
            rows = rows_by_sheet[definition["sheetName"]]
            if definition["layout"] == "australia":
                channel, channel_errors = _extract_ubi_australia_channel(
                    definition, rows
                )
            else:
                channel, channel_errors = _extract_ubi_country_channel(
                    definition, rows
                )
            channels.append(channel)
            errors.extend(channel_errors)
    if errors:
        raise ImportValidationError(errors)
    return channels


def _extract_ubi_canada_channel(
    definition: dict[str, Any],
    rows: list[tuple[int, dict[int, str]]],
    effective_date: str,
) -> tuple[dict[str, Any], list[str]]:
    row_map = dict(rows)
    errors = []
    if row_map.get(3, {}).get(2, "").strip() != "大陆":
        errors.append(f"{definition['name']}：第3行未识别为大陆价格表")
    if row_map.get(3, {}).get(4, "").strip() != "上门揽收":
        errors.append(f"{definition['name']}：第3行未识别到上门揽收价格")
    header = row_map.get(4, {})
    required = {2: "From", 3: "To", 4: "Per Item", 5: "Per Kg"}
    for column, expected in required.items():
        if expected not in header.get(column, ""):
            errors.append(
                f"{definition['name']}：第4行第{column}列未识别为“{expected}”"
            )

    raw_rates = []
    for source_row, values in rows:
        if source_row <= 4:
            continue
        try:
            raw_min = float(values.get(2, "").strip())
            max_kg = float(values.get(3, "").strip())
            registration_fee = float(values.get(4, "").strip())
            price_per_kg = float(values.get(5, "").strip())
        except ValueError:
            if raw_rates:
                break
            continue
        raw_rates.append(
            {
                "country": "加拿大",
                "zone": "",
                "transitTime": "",
                "rawMinKg": raw_min,
                "maxKg": max_kg,
                "pricePerKg": price_per_kg,
                "registrationFee": registration_fee,
                "sourceSheet": definition["sheetName"],
                "sourceRow": source_row,
            }
        )

    rates = []
    previous_max = None
    for item in raw_rates:
        raw_min = item.pop("rawMinKg")
        min_kg = raw_min if previous_max is None else previous_max
        max_kg = float(item["maxKg"])
        if max_kg <= min_kg:
            errors.append(
                f"{definition['name']}：第{item['sourceRow']}行重量档位异常"
            )
            continue
        item.update(
            {
                "minKg": _clean_number(min_kg),
                "maxKg": _clean_number(max_kg),
                "incrementKg": 0.001,
                "minimumWeightKg": 0.001,
                "pricePerKg": _clean_number(float(item["pricePerKg"])),
                "registrationFee": _clean_number(float(item["registrationFee"])),
            }
        )
        rates.append(item)
        previous_max = max_kg
    if not rates:
        errors.append(f"{definition['name']}：没有读取到有效费率")
    if effective_date == "未识别":
        errors.append(f"{definition['name']}：目录中未识别到生效日期")
    return (
        {
            "key": definition["key"],
            "company": "UBI加拿大特价",
            "parentCompany": "UBI",
            "name": definition["name"],
            "fullName": definition["fullName"],
            "cargoType": definition["cargoType"],
            "effectiveDate": effective_date,
            "rates": rates,
        },
        errors,
    )


def parse_ubi_canada_workbook(content: bytes) -> list[dict[str, Any]]:
    errors = []
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportValidationError(["文件不是有效的 .xlsx 工作簿"]) from exc
    with book:
        try:
            paths = _sheet_paths(book)
            shared = _load_shared_strings(book)
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
        required_sheets = {
            definition["sheetName"] for definition in UBI_CANADA_CHANNEL_DEFINITIONS
        }
        missing = sorted(required_sheets - paths.keys())
        if missing:
            raise ImportValidationError(["缺少工作表：" + "、".join(missing)])
        directory_name = next(
            (name for name in paths if name.strip() == "目录"), ""
        )
        if not directory_name:
            raise ImportValidationError(["缺少工作表：目录"])
        directory_rows = _read_sheet(book, shared, paths[directory_name])
        effective_date = next(
            (
                parsed
                for _, values in directory_rows
                for parsed in [_parse_ubi_date(values.get(7, ""))]
                if parsed != "未识别"
            ),
            "未识别",
        )
        channels = []
        for definition in UBI_CANADA_CHANNEL_DEFINITIONS:
            rows = _read_sheet(book, shared, paths[definition["sheetName"]])
            channel, channel_errors = _extract_ubi_canada_channel(
                definition, rows, effective_date
            )
            channels.append(channel)
            errors.extend(channel_errors)
    if errors:
        raise ImportValidationError(errors)
    return channels


def parse_price_workbook(content: bytes) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as book:
            paths = _sheet_paths(book)
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise ImportValidationError(["无法读取 Excel 工作簿结构"]) from exc
    yuntu_sheets = {definition["fullName"] for definition in CHANNEL_DEFINITIONS}
    shangpai_sheets = {
        definition["fullName"] for definition in SHANGPAI_CHANNEL_DEFINITIONS
    }
    one_sheets = {
        "目录",
        *(definition["sheetName"] for definition in ONE_CHANNEL_DEFINITIONS),
    }
    yuanpeng_sheets = {
        "目录",
        *(definition["sheetName"] for definition in YUANPENG_CHANNEL_DEFINITIONS),
    }
    yanwen_sheets = {
        definition["sheetName"] for definition in YANWEN_CHANNEL_DEFINITIONS
    }
    ubi_main_sheets = {
        definition["sheetName"] for definition in UBI_MAIN_CHANNEL_DEFINITIONS
    }
    ubi_canada_sheets = {
        definition["sheetName"] for definition in UBI_CANADA_CHANNEL_DEFINITIONS
    }
    if yuntu_sheets.issubset(paths):
        return parse_yuntu_workbook(content)
    if shangpai_sheets.issubset(paths):
        return parse_shangpai_workbook(content)
    if one_sheets.issubset(paths):
        return parse_one_workbook(content)
    if yuanpeng_sheets.issubset(paths):
        return parse_yuanpeng_workbook(content)
    if yanwen_sheets.issubset(paths):
        return parse_yanwen_workbook(content)
    if ubi_main_sheets.issubset(paths):
        return parse_ubi_main_workbook(content)
    if ubi_canada_sheets.issubset(paths):
        return parse_ubi_canada_workbook(content)
    raise ImportValidationError(
        ["无法识别物流公司：当前只支持云途、云途商派、壹号、远朋、燕文或UBI物流价格表"]
    )


def merge_company_channels(
    current: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    companies = {channel["company"] for channel in incoming}
    if len(companies) != 1:
        raise ImportValidationError(["单次更新只能包含一家物流公司"])
    company = next(iter(companies))
    first_index = next(
        (
            index
            for index, channel in enumerate(current)
            if channel.get("company") == company
        ),
        len(current),
    )
    retained = [
        channel for channel in current if channel.get("company") != company
    ]
    insertion_index = min(first_index, len(retained))
    return retained[:insertion_index] + incoming + retained[insertion_index:]


def _rate_key(channel_key: str, rate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        channel_key,
        rate["country"],
        rate["zone"],
        rate["minKg"],
        rate["maxKg"],
    )


def compare_channels(
    current: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> dict[str, Any]:
    current_map = {
        _rate_key(channel["key"], rate): (channel, rate)
        for channel in current
        for rate in channel["rates"]
    }
    incoming_map = {
        _rate_key(channel["key"], rate): (channel, rate)
        for channel in incoming
        for rate in channel["rates"]
    }
    added_keys = incoming_map.keys() - current_map.keys()
    removed_keys = current_map.keys() - incoming_map.keys()
    common_keys = current_map.keys() & incoming_map.keys()
    compared_fields = [
        "pricePerKg",
        "registrationFee",
        "incrementKg",
        "minimumWeightKg",
        "transitTime",
    ]
    changed_keys = [
        key
        for key in common_keys
        if any(
            current_map[key][1].get(field) != incoming_map[key][1].get(field)
            for field in compared_fields
        )
    ]
    unchanged = len(common_keys) - len(changed_keys)

    details = []
    for change_type, keys, source in [
        ("新增", sorted(added_keys), incoming_map),
        ("删除", sorted(removed_keys), current_map),
        ("变更", sorted(changed_keys), incoming_map),
    ]:
        for key in keys[:200]:
            channel, rate = source[key]
            current_rate = current_map.get(key, (None, None))[1]
            incoming_rate = incoming_map.get(key, (None, None))[1]
            differences = []
            if change_type == "变更":
                for field in compared_fields:
                    old = current_rate.get(field)
                    new = incoming_rate.get(field)
                    if old != new:
                        differences.append(
                            {"field": field, "old": old, "new": new}
                        )
            details.append(
                {
                    "type": change_type,
                    "channel": channel["name"],
                    "country": rate["country"],
                    "zone": rate["zone"],
                    "tier": f"{rate['minKg']}＜W≤{rate['maxKg']} kg",
                    "differences": differences,
                }
            )
    return {
        "summary": {
            "added": len(added_keys),
            "removed": len(removed_keys),
            "changed": len(changed_keys),
            "unchanged": unchanged,
            "totalIncoming": len(incoming_map),
        },
        "details": details,
        "detailsTruncated": (
            len(added_keys) + len(removed_keys) + len(changed_keys) > len(details)
        ),
        "channelSummaries": [
            {
                "name": channel["name"],
                "effectiveDate": channel["effectiveDate"],
                "rateCount": len(channel["rates"]),
                "countryCount": len({rate["country"] for rate in channel["rates"]}),
            }
            for channel in incoming
        ],
    }


class PriceStore:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.data_dir = project_root / "data"
        self.versions_dir = self.data_dir / "versions"
        self.current_path = self.data_dir / "current-prices.json"
        self.history_path = self.data_dir / "version-history.json"
        self.js_path = project_root / "channel-data.js"
        self.data_dir.mkdir(exist_ok=True)
        self.versions_dir.mkdir(exist_ok=True)
        self._ensure_initialized()

    def _atomic_json(self, path: Path, value: Any) -> None:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            temp_path = Path(handle.name)
        temp_path.replace(path)

    def _write_js(self, channels: list[dict[str, Any]]) -> None:
        payload = json.dumps(channels, ensure_ascii=False, separators=(",", ":"))
        content = (
            '(function(root){"use strict";root.LOGISTICS_CHANNELS='
            + payload
            + ";root.YUNTU_CHANNELS=root.LOGISTICS_CHANNELS"
            + ';})(typeof globalThis!=="undefined"?globalThis:this);\n'
        )
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.root, delete=False
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        temp_path.replace(self.js_path)

    def _channels_from_js(self) -> list[dict[str, Any]]:
        content = self.js_path.read_text(encoding="utf-8")
        marker = (
            "root.LOGISTICS_CHANNELS="
            if "root.LOGISTICS_CHANNELS=" in content
            else "root.YUNTU_CHANNELS="
        )
        start = content.index(marker) + len(marker)
        end_marker = (
            ";root.YUNTU_CHANNELS=root.LOGISTICS_CHANNELS"
            if marker == "root.LOGISTICS_CHANNELS="
            else ";})(typeof"
        )
        end = content.index(end_marker, start)
        return json.loads(content[start:end])

    def _ensure_initialized(self) -> None:
        if not self.current_path.exists():
            self._atomic_json(self.current_path, self._channels_from_js())
        if not self.history_path.exists():
            current = self.load_current()
            version_id = "initial-" + datetime.now().strftime("%Y%m%d-%H%M%S")
            self._atomic_json(self.versions_dir / f"{version_id}.json", current)
            self._atomic_json(
                self.history_path,
                {
                    "activeVersionId": version_id,
                    "versions": [
                        {
                            "id": version_id,
                            "appliedAt": datetime.now(timezone.utc).isoformat(),
                            "sourceFile": "当前物流价格快照",
                            "effectiveDates": sorted(
                                {channel["effectiveDate"] for channel in current}
                            ),
                            "rateCount": sum(
                                len(channel["rates"]) for channel in current
                            ),
                            "action": "初始化",
                        }
                    ],
                },
            )

    def load_current(self) -> list[dict[str, Any]]:
        return json.loads(self.current_path.read_text(encoding="utf-8"))

    def history(self) -> dict[str, Any]:
        return json.loads(self.history_path.read_text(encoding="utf-8"))

    def _load_version(self, version_id: str) -> list[dict[str, Any]]:
        path = self.versions_dir / f"{version_id}.json"
        if not path.exists():
            raise ImportValidationError(["找不到价格版本快照"])
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _company_channels(
        channels: list[dict[str, Any]], company: str
    ) -> list[dict[str, Any]]:
        return [
            channel for channel in channels if channel.get("company") == company
        ]

    @staticmethod
    def _company_summary(
        channels: list[dict[str, Any]], company: str
    ) -> dict[str, Any]:
        company_channels = PriceStore._company_channels(channels, company)
        parent_companies = {
            channel.get("parentCompany")
            for channel in company_channels
            if channel.get("parentCompany")
        }
        summary = {
            "company": company,
            "channelCount": len(company_channels),
            "rateCount": sum(
                len(channel["rates"]) for channel in company_channels
            ),
            "effectiveDates": sorted(
                {channel["effectiveDate"] for channel in company_channels}
            ),
        }
        if len(parent_companies) == 1:
            summary["parentCompany"] = next(iter(parent_companies))
        return summary

    def version_overview(self) -> dict[str, Any]:
        history = self.history()
        previous_channels: list[dict[str, Any]] = []
        enriched = []
        snapshots: dict[str, list[dict[str, Any]]] = {}
        for entry in history["versions"]:
            snapshot = self._load_version(entry["id"])
            snapshots[entry["id"]] = snapshot
            companies = list(
                dict.fromkeys(
                    [channel.get("company", "未识别") for channel in previous_channels]
                    + [channel.get("company", "未识别") for channel in snapshot]
                )
            )
            detected_changes = [
                company
                for company in companies
                if self._company_channels(previous_channels, company)
                != self._company_channels(snapshot, company)
            ]
            changed_companies = entry.get("updatedCompanies") or detected_changes
            enriched_entry = dict(entry)
            enriched_entry["changedCompanies"] = changed_companies
            enriched_entry["companySummaries"] = [
                self._company_summary(snapshot, company)
                for company in changed_companies
                if self._company_channels(snapshot, company)
            ]
            enriched.append(enriched_entry)
            previous_channels = snapshot

        current = self.load_current()
        current_companies = list(
            dict.fromkeys(channel.get("company", "未识别") for channel in current)
        )
        statuses = []
        for company in current_companies:
            current_company_channels = self._company_channels(current, company)
            source_entry = None
            for entry in reversed(enriched):
                if company not in entry["changedCompanies"]:
                    continue
                snapshot = snapshots[entry["id"]]
                if (
                    self._company_channels(snapshot, company)
                    == current_company_channels
                ):
                    source_entry = entry
                    break
            summary = self._company_summary(current, company)
            statuses.append(
                {
                    **summary,
                    "versionId": source_entry["id"] if source_entry else "",
                    "sourceFile": (
                        source_entry["sourceFile"]
                        if source_entry
                        else "当前价格快照"
                    ),
                    "appliedAt": (
                        source_entry["appliedAt"] if source_entry else ""
                    ),
                }
            )

        return {
            "activeVersionId": history["activeVersionId"],
            "companyStatuses": statuses,
            "versions": list(reversed(enriched)),
        }

    def _activate(
        self,
        channels: list[dict[str, Any]],
        source_file: str,
        action: str,
        updated_companies: list[str],
    ) -> dict[str, Any]:
        version_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self._atomic_json(self.versions_dir / f"{version_id}.json", channels)
        self._atomic_json(self.current_path, channels)
        self._write_js(channels)
        history = self.history()
        entry = {
            "id": version_id,
            "appliedAt": datetime.now(timezone.utc).isoformat(),
            "sourceFile": source_file,
            "effectiveDates": sorted(
                {channel["effectiveDate"] for channel in channels}
            ),
            "rateCount": sum(len(channel["rates"]) for channel in channels),
            "action": action,
            "updatedCompanies": updated_companies,
        }
        history["activeVersionId"] = version_id
        history["versions"].append(entry)
        self._atomic_json(self.history_path, history)
        return entry

    def apply(
        self,
        channels: list[dict[str, Any]],
        source_file: str,
        updated_company: str,
    ) -> dict[str, Any]:
        return self._activate(
            channels, source_file, "导入", [updated_company]
        )

    def rollback(
        self, target_version_id: str, company: str
    ) -> dict[str, Any]:
        target_channels = self._load_version(target_version_id)
        target_company_channels = self._company_channels(
            target_channels, company
        )
        if not target_company_channels:
            raise ImportValidationError(
                [f"该历史版本中没有{company}价格"]
            )
        channels = merge_company_channels(
            self.load_current(), target_company_channels
        )
        return self._activate(
            channels,
            f"{company}恢复至 {target_version_id}",
            "恢复",
            [company],
        )
