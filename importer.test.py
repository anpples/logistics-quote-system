from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from importer import (
    PriceStore,
    compare_channels,
    merge_company_channels,
    parse_one_workbook,
    parse_price_workbook,
    parse_shangpai_workbook,
    parse_ubi_canada_workbook,
    parse_ubi_main_workbook,
    parse_yanwen_workbook,
    parse_yuanpeng_workbook,
    parse_yuntu_workbook,
)


def passed(name: str, detail: str = "") -> None:
    print(f"通过：{name}")
    if detail:
        print(f"  {detail}")


current = json.loads(
    (PROJECT_ROOT / "data/current-prices.json").read_text(encoding="utf-8")
)
assert len(current) == 55
assert sum(len(channel["rates"]) for channel in current) == 2898
passed("当前价格版本完整", "7个物流服务组、55个渠道，共2898条费率")

live_store = PriceStore(PROJECT_ROOT)
overview = live_store.version_overview()
statuses = {item["company"]: item for item in overview["companyStatuses"]}
assert set(statuses) == {
    "云途", "云途商派", "壹号物流", "远朋物流", "燕文物流",
    "UBI", "UBI加拿大特价",
}
assert len({item["sourceFile"] for item in statuses.values()}) == 7
assert statuses["云途"]["rateCount"] == 990
assert statuses["壹号物流"]["rateCount"] == 227
assert statuses["远朋物流"]["rateCount"] == 612
assert statuses["云途商派"]["rateCount"] == 67
assert statuses["燕文物流"]["rateCount"] == 886
assert statuses["UBI"]["rateCount"] == 90
assert statuses["UBI加拿大特价"]["rateCount"] == 26
assert statuses["云途商派"]["parentCompany"] == "云途"
assert statuses["UBI加拿大特价"]["parentCompany"] == "UBI"
passed(
    "按物流服务组识别当前价格来源",
    "云途商派和UBI加拿大特价均与各自主价格表分开显示",
)

source_workbook = Path("/Users/anan/Documents") / statuses["云途"]["sourceFile"]
if source_workbook.exists():
    parsed = parse_yuntu_workbook(source_workbook.read_bytes())
    assert len(parsed) == 10
    assert sum(len(channel["rates"]) for channel in parsed) == 990
    assert parse_price_workbook(source_workbook.read_bytes()) == parsed
    yuntu_current = [channel for channel in current if channel["company"] == "云途"]
    assert compare_channels(yuntu_current, parsed)["summary"] == {
        "added": 0,
        "removed": 0,
        "changed": 0,
        "unchanged": 990,
        "totalIncoming": 990,
    }
    parsed_by_key = {channel["key"]: channel for channel in parsed}
    assert len(parsed_by_key["yt_eu_amz_general"]["rates"]) == 58
    assert len(parsed_by_key["yt_eu_amz_battery"]["rates"]) == 72
    assert len(parsed_by_key["yt_eu_amz_cosmetics"]["rates"]) == 41
    assert len(parsed_by_key["yt_selected_general"]["rates"]) == 93
    assert len(parsed_by_key["yt_selected_battery"]["rates"]) == 94
    passed("云途原始工作簿可重复解析", "10个渠道、990条费率完全一致")
else:
    print("跳过：原始云途工作簿当前不在Documents目录")

one_workbook = Path("/Users/anan/Documents") / statuses["壹号物流"]["sourceFile"]
if one_workbook.exists():
    parsed_one = parse_one_workbook(one_workbook.read_bytes())
    assert len(parsed_one) == 12
    assert sum(len(channel["rates"]) for channel in parsed_one) == 227
    assert parse_price_workbook(one_workbook.read_bytes()) == parsed_one
    one_current = [
        channel for channel in current if channel["company"] == "壹号物流"
    ]
    comparison = compare_channels(one_current, parsed_one)
    assert comparison["summary"] == {
        "added": 0,
        "removed": 0,
        "changed": 0,
        "unchanged": 227,
        "totalIncoming": 227,
    }
    parsed_by_key = {channel["key"]: channel for channel in parsed_one}
    assert len(parsed_by_key["one_yifan_uk_special_a"]["rates"]) == 4
    assert len(parsed_by_key["one_yifan_eu_special_a"]["rates"]) == 56
    assert len(parsed_by_key["one_yifan_ca_special_a"]["rates"]) == 6
    assert len(parsed_by_key["one_yifan_au_special_a"]["rates"]) == 12
    assert len(parsed_by_key["one_yifan_us_special_swd"]["rates"]) == 6
    assert {
        rate["zone"] for rate in parsed_by_key["one_yifan_au_special_a"]["rates"]
    } == {"1区", "2区", "3区", "4区"}
    merged = merge_company_channels(current, parsed_one)
    assert len(merged) == 55
    passed("壹号原始工作簿可重复解析", "12个渠道、227条费率完全一致")
else:
    print("跳过：壹号物流原始工作簿当前不在Documents目录")

yuanpeng_workbook = Path("/Users/anan/Documents/远朋07.20生效.xlsx")
if yuanpeng_workbook.exists():
    parsed_yuanpeng = parse_yuanpeng_workbook(yuanpeng_workbook.read_bytes())
    assert len(parsed_yuanpeng) == 12
    assert sum(len(channel["rates"]) for channel in parsed_yuanpeng) == 612
    assert parse_price_workbook(yuanpeng_workbook.read_bytes()) == parsed_yuanpeng
    yuanpeng_current = [
        channel for channel in current if channel["company"] == "远朋物流"
    ]
    comparison = compare_channels(yuanpeng_current, parsed_yuanpeng)
    assert comparison["summary"] == {
        "added": 0,
        "removed": 0,
        "changed": 0,
        "unchanged": 612,
        "totalIncoming": 612,
    }
    parsed_by_key = {channel["key"]: channel for channel in parsed_yuanpeng}
    standard_general = parsed_by_key["yp_standard_general"]
    for country in ["罗马尼亚", "斯洛文尼亚", "克罗地亚"]:
        country_rates = [
            rate for rate in standard_general["rates"]
            if rate["country"] == country
        ]
        assert max(rate["maxKg"] for rate in country_rates) == 5
    royal = parsed_by_key["yp_uk_royal_sensitive"]
    assert {rate["country"] for rate in royal["rates"]} == {"英国"}
    assert len(royal["rates"]) == 4
    passed(
        "远朋原始工作簿可重复解析",
        "12个渠道、612条费率完全一致，模板错标续档已正确归属",
    )
else:
    print("跳过：远朋物流原始工作簿当前不在Documents目录")

shangpai_workbook = Path("/Users/anan/Documents/云途商派20260720.xlsx")
if shangpai_workbook.exists():
    parsed_shangpai = parse_shangpai_workbook(shangpai_workbook.read_bytes())
    assert len(parsed_shangpai) == 9
    assert sum(len(channel["rates"]) for channel in parsed_shangpai) == 67
    assert parse_price_workbook(shangpai_workbook.read_bytes()) == parsed_shangpai
    assert {channel["company"] for channel in parsed_shangpai} == {"云途商派"}
    assert {channel.get("parentCompany") for channel in parsed_shangpai} == {"云途"}
    shangpai_current = [
        channel for channel in current if channel["company"] == "云途商派"
    ]
    comparison = compare_channels(shangpai_current, parsed_shangpai)
    assert comparison["summary"] == {
        "added": 0,
        "removed": 0,
        "changed": 0,
        "unchanged": 67,
        "totalIncoming": 67,
    }
    merged = merge_company_channels(current, parsed_shangpai)
    assert len(merged) == 55
    passed(
        "云途商派原始工作簿可重复解析",
        "快速4条、经济5条，共9个渠道、67条费率完全一致",
    )
else:
    print("跳过：云途商派原始工作簿当前不在Documents目录")

yanwen_workbook = Path("/Users/anan/Documents/南昌燕文报价单20260724版.xlsx")
if yanwen_workbook.exists():
    parsed_yanwen = parse_yanwen_workbook(yanwen_workbook.read_bytes())
    assert len(parsed_yanwen) == 6
    assert sum(len(channel["rates"]) for channel in parsed_yanwen) == 886
    assert parse_price_workbook(yanwen_workbook.read_bytes()) == parsed_yanwen
    assert {channel["company"] for channel in parsed_yanwen} == {"燕文物流"}
    yanwen_current = [
        channel for channel in current if channel["company"] == "燕文物流"
    ]
    comparison = compare_channels(yanwen_current, parsed_yanwen)
    assert comparison["summary"] == {
        "added": 0,
        "removed": 0,
        "changed": 0,
        "unchanged": 886,
        "totalIncoming": 886,
    }
    parsed_by_key = {channel["key"]: channel for channel in parsed_yanwen}
    assert len(parsed_by_key["yw_tracking_general"]["rates"]) == 206
    assert len(parsed_by_key["yw_tracking_special"]["rates"]) == 209
    assert len(parsed_by_key["yw_cosmetics"]["rates"]) == 118
    assert len(parsed_by_key["yw_air_registered_general"]["rates"]) == 189
    assert len(parsed_by_key["yw_air_registered_special"]["rates"]) == 156
    assert len(parsed_by_key["yw_small_light"]["rates"]) == 8
    japan_rates = [
        rate for rate in parsed_by_key["yw_small_light"]["rates"]
        if rate["country"] == "日本"
    ]
    assert len(japan_rates) == 2
    assert japan_rates[0]["incrementKg"] == 0.1
    assert japan_rates[0]["minimumWeightKg"] == 0.1
    australia_zones = {
        rate["zone"]
        for rate in parsed_by_key["yw_tracking_general"]["rates"]
        if rate["country"] == "澳大利亚"
    }
    assert australia_zones == {"1区", "2区", "3区", "4区"}
    passed(
        "燕文原始工作簿可重复解析",
        "仅接入指定6个渠道、886条费率，日本首续重与澳大利亚四区均已识别",
    )
else:
    print("跳过：燕文物流原始工作簿当前不在Documents目录")

new_yanwen_workbook = Path("/Users/anan/Downloads/南昌燕文报价单20260929版.xlsx")
if new_yanwen_workbook.exists():
    parsed_new_yanwen = parse_yanwen_workbook(new_yanwen_workbook.read_bytes())
    assert len(parsed_new_yanwen) == 6
    assert sum(len(channel["rates"]) for channel in parsed_new_yanwen) == 907
    assert parse_price_workbook(new_yanwen_workbook.read_bytes()) == parsed_new_yanwen
    parsed_new_by_key = {
        channel["key"]: channel for channel in parsed_new_yanwen
    }
    assert {
        channel["effectiveDate"] for channel in parsed_new_yanwen
    } == {"2026-09-29"}
    assert {
        key: len(parsed_new_by_key[key]["rates"])
        for key in parsed_new_by_key
    } == {
        "yw_tracking_general": 206,
        "yw_tracking_special": 210,
        "yw_cosmetics": 118,
        "yw_air_registered_general": 200,
        "yw_air_registered_special": 164,
        "yw_small_light": 9,
    }
    us_200g = next(
        rate
        for rate in parsed_new_by_key["yw_tracking_general"]["rates"]
        if rate["country"] == "美国" and rate["maxKg"] == 0.2
    )
    assert us_200g["pricePerKg"] == 138
    assert us_200g["registrationFee"] == 18
    assert us_200g["transitTime"] == "6-12"
    canada_zones = {
        rate["zone"]
        for rate in parsed_new_by_key["yw_air_registered_general"]["rates"]
        if rate["country"] == "加拿大"
    }
    assert canada_zones == {f"{zone}区" for zone in range(1, 8)}
    assert {
        rate["sourceSheet"]
        for rate in parsed_new_by_key["yw_small_light"]["rates"]
    } == {"轻小件专线-普货"}
    passed(
        "燕文2026年9月新版工作簿可识别",
        "保留指定6个渠道、读取907条费率，并兼容新版列位和轻小件工作表名称",
    )
else:
    print("跳过：燕文2026年9月新版工作簿当前不在Downloads目录")

ubi_workbook = Path("/Users/anan/Documents") / statuses["UBI"]["sourceFile"]
if ubi_workbook.exists():
    parsed_ubi = parse_ubi_main_workbook(ubi_workbook.read_bytes())
    assert len(parsed_ubi) == 4
    assert sum(len(channel["rates"]) for channel in parsed_ubi) == 90
    assert parse_price_workbook(ubi_workbook.read_bytes()) == parsed_ubi
    ubi_current = [channel for channel in current if channel["company"] == "UBI"]
    assert compare_channels(ubi_current, parsed_ubi)["summary"] == {
        "added": 0,
        "removed": 0,
        "changed": 0,
        "unchanged": 90,
        "totalIncoming": 90,
    }
    parsed_by_key = {channel["key"]: channel for channel in parsed_ubi}
    assert len(parsed_by_key["ubi_au_post_general"]["rates"]) == 44
    assert len(parsed_by_key["ubi_au_post_battery"]["rates"]) == 44
    assert len(parsed_by_key["ubi_nz_general"]["rates"]) == 1
    assert len(parsed_by_key["ubi_nz_battery"]["rates"]) == 1
    for key in ["ubi_au_post_general", "ubi_au_post_battery"]:
        assert {rate["zone"] for rate in parsed_by_key[key]["rates"]} == {
            "1区", "2区", "3区", "4区"
        }
    passed(
        "UBI总价格表可重复解析",
        "仅读取大陆上门揽收的澳邮普货/带电与新西兰普货/带电，共90条费率",
    )
else:
    print("跳过：UBI总价格表当前不在Documents目录")

ubi_canada_workbook = (
    Path("/Users/anan/Documents") / statuses["UBI加拿大特价"]["sourceFile"]
)
if ubi_canada_workbook.exists():
    parsed_ubi_canada = parse_ubi_canada_workbook(ubi_canada_workbook.read_bytes())
    assert len(parsed_ubi_canada) == 2
    assert sum(len(channel["rates"]) for channel in parsed_ubi_canada) == 26
    assert parse_price_workbook(ubi_canada_workbook.read_bytes()) == parsed_ubi_canada
    ubi_canada_current = [
        channel for channel in current if channel["company"] == "UBI加拿大特价"
    ]
    assert compare_channels(ubi_canada_current, parsed_ubi_canada)["summary"] == {
        "added": 0,
        "removed": 0,
        "changed": 0,
        "unchanged": 26,
        "totalIncoming": 26,
    }
    assert {channel.get("parentCompany") for channel in parsed_ubi_canada} == {
        "UBI"
    }
    assert all(
        channel["effectiveDate"] == "2026-07-06"
        for channel in parsed_ubi_canada
    )
    passed(
        "UBI加拿大特价表可重复解析",
        "仅读取华南普货与华南带电的上门揽收价格，共26条费率",
    )
else:
    print("跳过：UBI加拿大特价表当前不在Documents目录")

with tempfile.TemporaryDirectory() as temporary:
    temp_root = Path(temporary)
    shutil.copy2(PROJECT_ROOT / "channel-data.js", temp_root / "channel-data.js")
    store = PriceStore(temp_root)
    original_history = store.history()
    original_version = original_history["activeVersionId"]
    modified = copy.deepcopy(store.load_current())
    modified[0]["rates"][0]["pricePerKg"] += 1
    preview = compare_channels(store.load_current(), modified)
    assert preview["summary"]["changed"] == 1
    applied = store.apply(modified, "自动测试.xlsx", "云途")
    assert store.history()["activeVersionId"] == applied["id"]
    assert store.load_current()[0]["rates"][0]["pricePerKg"] == modified[0]["rates"][0]["pricePerKg"]
    restored = store.rollback(original_version, "云途")
    assert store.history()["activeVersionId"] == restored["id"]
    assert store.load_current() == current
    overview = store.version_overview()
    assert len(overview["companyStatuses"]) == 7
    assert any(
        status["company"] == "云途商派"
        and status["parentCompany"] == "云途"
        for status in overview["companyStatuses"]
    )
    assert any(
        status["company"] == "UBI加拿大特价"
        and status["parentCompany"] == "UBI"
        for status in overview["companyStatuses"]
    )
    passed(
        "服务组级版本启用与恢复安全",
        "恢复云途主价格不会改变云途商派、壹号、远朋、燕文与UBI价格",
    )

print("\n价格更新功能测试全部通过。")
