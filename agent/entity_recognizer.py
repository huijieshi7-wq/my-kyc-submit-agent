"""Entity Recognizer module.

Takes the structured OCR output from agent/ocr.py and produces standardized
entity classification: company type mapping, ISO country code, region, risk
tags, and the required KYC review tier.
"""

import json
import os
import re
import time
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# 环境初始化
# ---------------------------------------------------------------------------
load_dotenv()

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """懒加载 DeepSeek 兼容客户端。"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            timeout=30.0,
        )
    return _client


# ---------------------------------------------------------------------------
# 硬编码规则列表（高风险司法区 & 离岸地，不依赖 LLM 判断）
# ---------------------------------------------------------------------------

# 联合国/OFAC 全面制裁国家 — 直接 BLOCKED
_HIGH_RISK_COUNTRIES: set[str] = {
    "IR",  # 伊朗
    "KP",  # 朝鲜
    "SY",  # 叙利亚
    "MM",  # 缅甸
    "CU",  # 古巴
}

# 常见离岸金融中心 — PRIVATE_LIMITED 注册在此类地区触发 REQUIRES_UBO
_OFFSHORE_JURISDICTIONS: set[str] = {
    "KY",  # 开曼群岛
    "VG",  # 英属维尔京群岛 (BVI)
    "BM",  # 百慕大
    "BS",  # 巴哈马
    "BZ",  # 伯利兹
    "CK",  # 库克群岛
    "GI",  # 直布罗陀
    "MH",  # 马绍尔群岛
    "MU",  # 毛里求斯
    "PA",  # 巴拿马
    "SC",  # 塞舌尔
    "VC",  # 圣文森特
    "WS",  # 萨摩亚
    "VU",  # 瓦努阿图
}


# ===================================================================
# 公共函数：analyze_entity
# ===================================================================

def analyze_entity(ocr_result: dict) -> dict:
    """对 OCR 提取结果做实体标准化和风险初判。

    处理流程：
    1. 用 DeepSeek 把 raw 字段映射为标准枚举值（类型、国家代码、区域）。
    2. 用硬编码规则叠加风险标签（高风险司法区、复杂结构、离岸 UBO）。
    3. 由风险标签推导 KYC 审核级别。

    Args:
        ocr_result: agent/ocr.py extract_certificate_info 的返回字典，至少包含
                    company_name, company_type, registration_country。

    Returns:
        dict:
          - "company_type_standard": str   Corporate / Limited_Liability_Company /
                                          Partnership / Sole_Proprietor / UNKNOWN
          - "country_code": str | None     ISO 3166-1 alpha-2
          - "region": str                  APAC / EU / US / CN / OTHER
          - "risk_tags": list[str]         风险标签列表
          - "kyc_tier": str                STANDARD / ENHANCED / BLOCKED
    """
    # 防御：ocr_result 为 None 或缺少关键字段时直接返回安全兜底
    if not ocr_result or not isinstance(ocr_result, dict):
        return _default_result()

    # ---- 第1步：LLM 分类 ---------------------------------------------------
    llm_result = _call_llm_classify(ocr_result)

    # ---- 第2步：硬编码规则叠加风险标签 -------------------------------------
    risk_tags = _compute_risk_tags(
        company_type_standard=llm_result.get("company_type_standard", "UNKNOWN"),
        country_code=llm_result.get("country_code"),
        raw_company_type=ocr_result.get("company_type", ""),
    )

    # ---- 第3步：推导审核级别 -------------------------------------------------
    kyc_tier = _derive_kyc_tier(risk_tags)

    return {
        "company_type_standard": llm_result.get("company_type_standard", "UNKNOWN"),
        "country_code": llm_result.get("country_code"),
        "region": llm_result.get("region", "OTHER"),
        "risk_tags": risk_tags,
        "kyc_tier": kyc_tier,
    }


# ===================================================================
# 内部辅助：LLM 分类
# ===================================================================

_SYSTEM_PROMPT = """你是一个企业注册信息标准化专家。
给定一份企业 OCR 提取结果（JSON），请输出标准化分类。

严格按照以下 JSON 格式返回，不要输出任何额外文字或 markdown 标记：

{
  "company_type_standard": "Corporate | Limited_Liability_Company | Partnership | Sole_Proprietor | UNKNOWN",
  "country_code": "ISO 3166-1 alpha-2 代码，如 SG、HK、GB、US；无法判断填 null",
  "region": "APAC | EU | US | CN | OTHER"
}

分类依据：
1. company_type_standard 映射规则：
   - Corporate: 大型股份公司、公众公司、Berhad、Public Company、AG、SA、PLC
   - Limited_Liability_Company: 私人有限公司、Private Limited、Sdn Bhd、GmbH、Sarl、LLC
   - Partnership: 合伙制、Partnership、LLP
   - Sole_Proprietor: 独资经营、个体工商户、Sole Proprietorship
   - UNKNOWN: 无法从原始文字判断

2. country_code: 从 registration_country 字段推断 ISO alpha-2 代码。
   常见映射：Singapore → SG, Malaysia → MY, Hong Kong → HK,
   China → CN, United States → US, United Kingdom → GB,
   Japan → JP, South Korea → KR, Thailand → TH, Vietnam → VN,
   Indonesia → ID, India → IN, Germany → DE, France → FR,
   Cayman Islands → KY, British Virgin Islands → VG

3. region:
   - APAC: SG, MY, HK, JP, KR, TH, VN, ID, IN, AU, NZ, PH, TW 等亚太
   - EU: 欧盟/欧洲经济区成员国
   - US: 美国
   - CN: 中国大陆
   - OTHER: 以上均不匹配
"""


def _call_llm_classify(ocr_result: dict) -> dict:
    """调用 DeepSeek 对 OCR 结果做标准化分类。"""
    print("开始调用 DeepSeek 进行实体分类...")
    client = _get_client()

    # 只传相关字段，减少 token 消耗
    context = {
        "company_name": ocr_result.get("company_name"),
        "company_type": ocr_result.get("company_type"),
        "registration_country": ocr_result.get("registration_country"),
        "registration_number": ocr_result.get("registration_number"),
    }

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"请对以下 OCR 结果做标准化分类：\n\n{json.dumps(context, ensure_ascii=False, indent=2)}",
        },
    ]

    for attempt in range(3):  # 1 + 2 次重试
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=messages,
                temperature=0.0,  # 分类任务用最低温度
                max_tokens=256,
            )
            raw_text = response.choices[0].message.content.strip()
            parsed = _parse_json(raw_text)
            if parsed:
                print("实体分类完成")
                return parsed

        except Exception as e:
            print(f"  实体分类 API 失败 (第 {attempt + 1} 次): {str(e)[:120]}")
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))

    # 全部失败，返回兜底
    print("实体分类全部重试失败，使用兜底值")
    return {"company_type_standard": "UNKNOWN", "country_code": None, "region": "OTHER"}


def _parse_json(raw_text: str) -> Optional[dict]:
    """从 LLM 回复中解析 JSON（三级 fallback）。"""
    # 直接解析
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    # ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 第一个 { ... }
    m = re.search(r"\{[\s\S]*\}", raw_text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ===================================================================
# 内部辅助：风险标签 & 审核级别（硬编码规则）
# ===================================================================

def _compute_risk_tags(
    company_type_standard: str,
    country_code: Optional[str],
    raw_company_type: str,
) -> list[str]:
    """根据硬编码规则计算风险标签列表。

    HIGH_RISK_JURISDICTION — 国家在制裁名单中（硬编码，不依赖 LLM）
    COMPLEX_STRUCTURE      — 分支/公众公司等复杂结构
    REQUIRES_UBO           — 离岸地注册的私人有限公司需核查最终受益人
    STANDARD               — 以上条件均不满足
    """
    tags: list[str] = []

    # 规则1：高风险司法区 —— 硬编码国家列表
    if country_code and country_code.upper() in _HIGH_RISK_COUNTRIES:
        tags.append("HIGH_RISK_JURISDICTION")

    # 规则2：复杂企业结构 —— 检查标准化类型 + 原始文字关键词
    type_upper = company_type_standard.upper()
    raw_upper = raw_company_type.upper()
    if "PUBLIC" in type_upper or "BRANCH" in type_upper:
        tags.append("COMPLEX_STRUCTURE")
    elif "PUBLIC" in raw_upper or "BRANCH" in raw_upper or "BERHAD" in raw_upper:
        tags.append("COMPLEX_STRUCTURE")

    # 规则3：离岸 + 私人有限公司 → 需要核查 UBO
    if (
        country_code
        and country_code.upper() in _OFFSHORE_JURISDICTIONS
        and (
            "LIMITED_LIABILITY" in type_upper
            or "PRIVATE LIMITED" in raw_upper
            or "SDN BHD" in raw_upper
            or "LLC" in raw_upper
        )
    ):
        tags.append("REQUIRES_UBO")

    # 规则4：无特殊风险
    if not tags:
        tags.append("STANDARD")

    return tags


def _derive_kyc_tier(risk_tags: list[str]) -> str:
    """由风险标签推导 KYC 审核级别。

    BLOCKED  = HIGH_RISK_JURISDICTION  → 直接拒绝
    ENHANCED = COMPLEX_STRUCTURE 或 REQUIRES_UBO → 增强审核
    STANDARD = 其他（仅 STANDARD 标签或空）
    """
    if "HIGH_RISK_JURISDICTION" in risk_tags:
        return "BLOCKED"
    if "COMPLEX_STRUCTURE" in risk_tags or "REQUIRES_UBO" in risk_tags:
        return "ENHANCED"
    return "STANDARD"


def _default_result() -> dict:
    """OCR 结果无效时的安全兜底。"""
    return {
        "company_type_standard": "UNKNOWN",
        "country_code": None,
        "region": "OTHER",
        "risk_tags": ["STANDARD"],
        "kyc_tier": "STANDARD",
    }


# ===================================================================
# 以下为骨架阶段的函数签名（后续逐步实现）
# ===================================================================

def extract_company_name(text: str) -> Optional[str]:
    """Extract the registered company name from business-license text."""
    pass


def extract_person_name(text: str) -> Optional[str]:
    """Extract a natural person's full name from identity-document text."""
    pass


def extract_id_number(text: str, doc_type: str = "passport") -> Optional[str]:
    """Extract a government-issued identification number."""
    pass


def extract_address(text: str) -> Optional[str]:
    """Extract a physical or registered address from document text."""
    pass


def extract_date_of_birth(text: str) -> Optional[str]:
    """Extract date of birth from identity-document text."""
    pass


def extract_registration_number(text: str) -> Optional[str]:
    """Extract the business registration / tax ID number."""
    pass


# ===================================================================
# 测试块
# ===================================================================

if __name__ == "__main__":
    import sys

    # ---- 确保项目根目录在 sys.path 中 ---------------------------------------
    _proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj_root not in sys.path:
        sys.path.insert(0, _proj_root)

    # ---- 解析命令行参数 ----------------------------------------------------
    # 支持格式：python agent/entity_recognizer.py file_path=test_certificates/test_cert_01.pdf
    cli_args = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, _, value = arg.partition("=")
            cli_args[key.strip()] = value.strip()

    # ---- 传入 file_path：OCR → Entity 完整流水线 ---------------------------
    if "file_path" in cli_args:
        print("=" * 60)
        print(f"完整流水线测试（OCR → Entity）: {cli_args['file_path']}")
        from agent.ocr import extract_certificate_info

        ocr_result = extract_certificate_info(file_path=cli_args["file_path"])
        print()
        print("OCR 结果：")
        for k, v in ocr_result.items():
            print(f"  {k}: {v}")

        print()
        print("实体识别结果：")
        result = analyze_entity(ocr_result)
        for k, v in result.items():
            print(f"  {k}: {v}")
        sys.exit(0)

    # ---- 默认：跑硬编码测试用例 --------------------------------------------

    print("未传入文件，运行默认测试用例...")

    # 模拟 OCR 输出：新加坡私人有限公司
    mock_ocr_sg = {
        "company_name": "ABC Trading Pte. Ltd.",
        "registration_country": "Singapore",
        "company_type": "Private Limited Company",
        "registration_date": "2021-03-15",
        "registration_number": "202312345K",
        "directors_or_shareholders": ["John Tan", "Mary Lee"],
        "raw_confidence": "HIGH",
    }

    # 模拟 OCR 输出：BVI 离岸公司
    mock_ocr_bvi = {
        "company_name": "Ocean Holdings Ltd.",
        "registration_country": "British Virgin Islands",
        "company_type": "Private Limited Company",
        "registration_date": "2019-07-01",
        "registration_number": "BVI-1882345",
        "directors_or_shareholders": ["James Smith"],
        "raw_confidence": "MEDIUM",
    }

    # 模拟 OCR 输出：伊朗公司（应触发 BLOCKED）
    mock_ocr_ir = {
        "company_name": "Tehran Trade Group",
        "registration_country": "Iran",
        "company_type": "Private Limited Company",
        "registration_date": "2018-01-20",
        "registration_number": "IR-998877",
        "directors_or_shareholders": ["Ali Rezaei"],
        "raw_confidence": "MEDIUM",
    }

    print("=" * 60)
    print("测试1：新加坡私人有限公司")
    result1 = analyze_entity(mock_ocr_sg)
    for k, v in result1.items():
        print(f"  {k}: {v}")

    print()
    print("=" * 60)
    print("测试2：BVI 离岸公司（应触发 REQUIRES_UBO + ENHANCED）")
    result2 = analyze_entity(mock_ocr_bvi)
    for k, v in result2.items():
        print(f"  {k}: {v}")

    print()
    print("=" * 60)
    print("测试3：伊朗公司（应触发 HIGH_RISK_JURISDICTION + BLOCKED）")
    result3 = analyze_entity(mock_ocr_ir)
    for k, v in result3.items():
        print(f"  {k}: {v}")
