"""OCR (Optical Character Recognition) module.

Extracts structured text from uploaded KYC documents (passports, business
licenses, bank statements, etc.) and returns normalized text blocks keyed by
document type.
"""

import json
import os
import re
import sys
import time
from typing import Optional

import fitz  # PyMuPDF — PDF text extraction
import pytesseract  # OCR 引擎 — 从图片中提取文字
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image  # 图片加载，配合 pytesseract 使用

# 注意：pytesseract 需要系统安装 tesseract-ocr 才能工作
#   Mac:  brew install tesseract
#   Linux: apt-get install tesseract-ocr
#   同时建议安装中文语言包：brew install tesseract-lang
#   如未安装 tesseract，图片 OCR 路径会返回错误提示

# ---------------------------------------------------------------------------
# 环境初始化：加载 .env 并创建 DeepSeek 客户端
# ---------------------------------------------------------------------------
load_dotenv()

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """懒加载 DeepSeek 兼容客户端（OpenAI SDK）。"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            timeout=30.0,  # 30 秒超时，避免网络抖动时无限 hang
        )
    return _client


# ---------------------------------------------------------------------------
# 文件扩展名分类
# ---------------------------------------------------------------------------
_SUPPORTED_PDF_EXTS = {".pdf"}
_SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


# ===================================================================
# 公共函数：extract_certificate_info
# ===================================================================

def extract_certificate_info(
    file_path: Optional[str] = None,
    text_content: Optional[str] = None,
) -> dict:
    """从企业注册证书中提取关键工商信息。

    支持三种输入模式（优先级从高到低）：
    1. text_content — 纯文本，直接发给 DeepSeek 分析。
    2. file_path 指向 PDF — 用 PyMuPDF 提取前3页文字发给 DeepSeek。
    3. file_path 指向图片 — 用 pytesseract OCR 提取文字后发给 DeepSeek。

    Args:
        file_path: 证书文件路径（PDF 或图片）。
        text_content: 文字描述，传此参数时跳过文件读取。

    Returns:
        dict:
          - "company_name": str | None           企业名称
          - "registration_country": str | None   注册国家/地区（英文全称）
          - "company_type": str | None           企业类型（原始文字）
          - "registration_date": str | None      注册日期 YYYY-MM-DD
          - "registration_number": str | None    注册编号
          - "directors_or_shareholders": list | None  法定代表人或股东名称（最多3个）
          - "raw_confidence": str                HIGH / MEDIUM / LOW
    """
    # ---- 参数校验 ----------------------------------------------------------
    if not file_path and not text_content:
        return _error_dict("请提供 file_path 或 text_content 至少一个参数。")

    # ---- 模式1：纯文字输入（优先级最高）------------------------------------
    if text_content:
        return _call_llm_with_text(text_content)

    # ---- 模式2/3：文件路径 -------------------------------------------------
    ext = os.path.splitext(file_path)[1].lower()

    # 不支持的文件格式
    if ext not in _SUPPORTED_PDF_EXTS and ext not in _SUPPORTED_IMAGE_EXTS:
        return _error_dict(
            f"不支持的文件格式 '{ext}'。"
            f"支持的格式：{sorted(_SUPPORTED_PDF_EXTS | _SUPPORTED_IMAGE_EXTS)}"
        )

    # 文件存在性检查
    if not os.path.exists(file_path):
        return _error_dict(f"文件不存在: {file_path}")

    # 图片分支：pytesseract OCR → DeepSeek 分析
    if ext in _SUPPORTED_IMAGE_EXTS:
        try:
            ocr_text = _ocr_image(file_path)
        except Exception as e:
            return _error_dict(f"图片 OCR 失败: {str(e)}")

        if not ocr_text or not ocr_text.strip():
            return _error_dict("图片 OCR 未识别到文字内容")

        return _call_llm_with_text(ocr_text)

    # PDF 分支：提取文字 → DeepSeek 分析
    try:
        pdf_text = _extract_pdf_text(file_path, max_pages=3)
    except Exception as e:
        return _error_dict(f"PDF 解析失败: {str(e)}")

    if not pdf_text or not pdf_text.strip():
        return _error_dict(
            "PDF 无可提取的文字内容（可能是扫描件图片，请使用可选中文字的 PDF）"
        )

    return _call_llm_with_text(pdf_text)


# ===================================================================
# 内部辅助：PDF 文字提取
# ===================================================================

def _extract_pdf_text(file_path: str, max_pages: int = 3) -> str:
    """用 PyMuPDF 直接提取 PDF 前 N 页的文字内容。

    不做 OCR，只提取 PDF 中嵌入的可选中文字层。
    扫描件（纯图片 PDF）将返回空字符串。

    Args:
        file_path: PDF 文件路径。
        max_pages: 最多提取页数（注册证书通常在前几页）。

    Returns:
        提取到的全部文字，多页之间用换行分隔。
    """
    print(f"开始提取 PDF 文字: {file_path}")
    doc = fitz.open(file_path)
    total_pages = len(doc)
    pages_to_extract = min(total_pages, max_pages)
    print(f"PDF 共 {total_pages} 页，提取前 {pages_to_extract} 页")

    text_parts = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        print(f"  正在提取第 {i + 1} 页...")
        page_text = page.get_text()
        text_parts.append(page_text)
        print(f"  第 {i + 1} 页提取到 {len(page_text)} 个字符")

    doc.close()
    full_text = "\n".join(text_parts)
    print(f"PDF 文字提取完毕，共 {len(full_text)} 个字符")
    return full_text


# ===================================================================
# 内部辅助：图片 OCR
# ===================================================================

def _ocr_image(file_path: str) -> str:
    """用 pytesseract 对图片进行 OCR，提取文字内容。

    需要系统安装 tesseract-ocr：
        Mac:  brew install tesseract
        Linux: apt-get install tesseract-ocr

    Args:
        file_path: 图片文件路径（.jpg / .png / .bmp / .tiff）。

    Returns:
        OCR 识别到的文字字符串。

    Raises:
        RuntimeError: tesseract 未安装时给出安装提示。
    """
    print(f"开始 OCR 识别图片: {file_path}")
    try:
        image = Image.open(file_path)
    except Exception as e:
        raise RuntimeError(f"无法打开图片文件: {str(e)}") from e

    # 检查 tesseract 是否可用
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "未检测到 tesseract-ocr。请先安装：\n"
            "  Mac:  brew install tesseract\n"
            "  Linux: apt-get install tesseract-ocr\n"
            "多语言支持（可选）：brew install tesseract-lang"
        )

    # 执行 OCR（中英文混合识别）
    text = pytesseract.image_to_string(image, lang="eng+chi_sim")
    print(f"OCR 识别完毕，共 {len(text)} 个字符")
    return text


# ===================================================================
# 内部辅助：LLM 调用
# ===================================================================

# 系统提示词：指导模型按结构化 JSON 提取字段
_SYSTEM_PROMPT = """你是一个专业的 KYC（了解你的客户）文档审核助手。
你的任务是从企业注册证书（Business Registration Certificate）中提取关键工商信息。

请严格按照以下 JSON 格式返回，不要输出任何额外的文字、解释或 markdown 标记：

{
  "company_name": "企业全称（英文优先；如原件为其他语种，也请提取原文）",
  "registration_country": "注册国家/地区英文全称，如 Singapore",
  "company_type": "企业类型原文，如 Private Limited Company",
  "registration_date": "注册日期，格式 YYYY-MM-DD；无法识别则填 null",
  "registration_number": "注册编号/统一社会信用代码",
  "directors_or_shareholders": ["法定代表人/股东1", "股东2", "股东3"],
  "raw_confidence": "HIGH 或 MEDIUM 或 LOW"
}

注意事项：
1. 日期统一为 YYYY-MM-DD 格式。如果原文是 "15 March 2021"，应输出 "2021-03-15"。
2. directors_or_shareholders 最多返回3个，找不到任何信息时返回空数组 []。
3. 任何字段无法识别时，字符串填 null，数组填 []。
4. raw_confidence 的判定标准：
   - HIGH：所有关键字段（公司名、注册号、日期）都清晰可读。
   - MEDIUM：部分字段模糊或需要推断。
   - LOW：文字质量差，大部分信息不可读。
5. 优先提取英文信息；如果证书上没有英文，则提取原文（中文、越南文、泰文等）。
"""


def _call_llm_with_text(text: str) -> dict:
    """将文字发送给 DeepSeek API 提取结构化字段。

    所有路径（text_content、PDF 文字提取）最终都汇聚到此函数。
    """
    print("开始调用 DeepSeek API 分析...")
    client = _get_client()
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "请从以下企业证书文字内容中提取关键信息：\n\n"
                f"{text}"
            ),
        },
    ]
    return _llm_api_call_with_retry(client, messages)


def _llm_api_call_with_retry(client: OpenAI, messages: list[dict]) -> dict:
    """带重试机制的 LLM API 调用（最多重试2次）。

    同时处理：
    - 网络错误 / 超时
    - 返回内容非 JSON 时的 fallback 解析
    """
    last_error = None
    for attempt in range(3):  # 1 次原始 + 2 次重试
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=messages,
                temperature=0.1,  # 低温度保证提取稳定性
                max_tokens=1024,
            )
            raw_text = response.choices[0].message.content.strip()

            # 尝试提取 JSON（模型可能在 JSON 外包裹 ``` 标记）
            parsed = _parse_json_from_response(raw_text)
            if parsed:
                print("API 返回结果解析成功")
                return _normalize_result(parsed)

            # 非 JSON 内容则记录错误
            last_error = f"模型返回非 JSON 内容: {raw_text[:200]}"

        except Exception as e:
            last_error = str(e)
            print(f"  API 调用失败 (第 {attempt + 1} 次): {last_error[:120]}")

        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))  # 指数退避：1.5s → 3s

    return _error_dict(f"API 调用失败（已重试2次）: {last_error}")


# ===================================================================
# 内部辅助：结果解析 & 规范化
# ===================================================================

def _parse_json_from_response(raw_text: str) -> Optional[dict]:
    """从模型返回的原始文本中解析 JSON。

    模型可能返回纯 JSON 或 ```json ... ``` 包裹的代码块。
    """
    # 方式1：直接解析
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # 方式2：提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 方式3：尝试匹配第一个 { ... } 对象
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _normalize_result(raw: dict) -> dict:
    """将 LLM 返回的原始 dict 规范化为统一字段格式。

    - 确保所有必需字段存在
    - 将 null / "null" / "None" 统一为 Python None
    - registration_date 校验 YYYY-MM-DD 格式
    - directors_or_shareholders 保证是 list
    - raw_confidence 兜底 LOW
    """
    result = {
        "company_name": raw.get("company_name"),
        "registration_country": raw.get("registration_country"),
        "company_type": raw.get("company_type"),
        "registration_date": raw.get("registration_date"),
        "registration_number": raw.get("registration_number"),
        "directors_or_shareholders": raw.get("directors_or_shareholders", []),
        "raw_confidence": raw.get("raw_confidence", "LOW"),
    }

    # 统一 null 字符串 → None
    for key in (
        "company_name",
        "registration_country",
        "company_type",
        "registration_date",
        "registration_number",
    ):
        if isinstance(result[key], str) and result[key].lower() in ("null", "none", ""):
            result[key] = None

    # 日期格式校验：非 YYYY-MM-DD 的尝试转换，无法转换则置 None
    if result["registration_date"] is not None:
        result["registration_date"] = _normalize_date(result["registration_date"])

    # directors_or_shareholders 保底
    if not isinstance(result["directors_or_shareholders"], list):
        result["directors_or_shareholders"] = []
    # 去空、最多3个
    result["directors_or_shareholders"] = [
        d for d in result["directors_or_shareholders"]
        if isinstance(d, str) and d.strip() and d.strip().lower() not in ("null", "none")
    ][:3]

    # confidence 标准化
    conf = str(result["raw_confidence"]).upper()
    if conf not in ("HIGH", "MEDIUM", "LOW"):
        conf = "LOW"
    result["raw_confidence"] = conf

    return result


def _normalize_date(date_str: str) -> Optional[str]:
    """尝试将各种日期格式转为 YYYY-MM-DD，失败返回 None。

    支持示例：
    - "15 March 2021"
    - "2021-03-15"
    - "03/15/2021"
    - "2021年3月15日"
    """
    # 已经是标准格式
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        try:
            from datetime import date
            date.fromisoformat(date_str)
            return date_str
        except ValueError:
            return None

    # 中文格式：2021年3月15日
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 英文格式：15 March 2021 / March 15, 2021
    for fmt in (
        "%d %B %Y",      # 15 March 2021
        "%B %d, %Y",     # March 15, 2021
        "%d %b %Y",      # 15 Mar 2021
        "%b %d, %Y",     # Mar 15, 2021
        "%m/%d/%Y",      # 03/15/2021
        "%d/%m/%Y",      # 15/03/2021
        "%Y/%m/%d",      # 2021/03/15
    ):
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _error_dict(message: str) -> dict:
    """统一的错误返回格式。"""
    return {
        "company_name": None,
        "registration_country": None,
        "company_type": None,
        "registration_date": None,
        "registration_number": None,
        "directors_or_shareholders": None,
        "raw_confidence": "LOW",
        "error": message,
    }


# ===================================================================
# 以下为骨架阶段的函数签名（后续逐步实现）
# ===================================================================

def extract_text_from_image(image_path: str, lang: str = "eng") -> str:
    """Extract raw text from a single image file using OCR."""
    pass


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text page-by-page from a PDF document."""
    pass


def preprocess_document(file_path: str) -> bytes:
    """Apply preprocessing (grayscale, deskew, threshold) to improve OCR accuracy."""
    pass


def classify_document_type(text: str) -> Optional[str]:
    """Guess the KYC document type from its OCR text content."""
    pass


# ===================================================================
# 测试块
# ===================================================================

if __name__ == "__main__":
    # ---- 解析命令行参数 ----------------------------------------------------
    # 支持格式：python agent/ocr.py file_path=test_certificates/test_cert_01.pdf
    #           python agent/ocr.py text=xxx
    cli_args = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, _, value = arg.partition("=")
            cli_args[key.strip()] = value.strip()

    # ---- 如果传了 file_path 或 text，只跑指定模式 -------------------------
    if "file_path" in cli_args:
        print("=" * 60)
        print(f"命令行文件测试: {cli_args['file_path']}")
        result = extract_certificate_info(file_path=cli_args["file_path"])
        for k, v in result.items():
            print(f"  {k}: {v}")
        sys.exit(0)

    if "text" in cli_args:
        print("=" * 60)
        print("命令行文字测试：")
        result = extract_certificate_info(text_content=cli_args["text"])
        for k, v in result.items():
            print(f"  {k}: {v}")
        sys.exit(0)

    # ---- 默认：跑全部内置测试 ------------------------------------------------

    # 方式1：文字模拟测试（不依赖真实文件）
    test_text = """
    Company Name: ABC Trading Pte. Ltd.
    Registration Number: 202312345K
    Country: Singapore
    Company Type: Private Limited Company
    Date of Incorporation: 15 March 2021
    Directors: John Tan, Mary Lee
    """
    print("=" * 60)
    print("文字输入测试：")
    result = extract_certificate_info(text_content=test_text)
    for k, v in result.items():
        print(f"  {k}: {v}")

    # 方式2：测试不支持的文件格式
    print()
    print("=" * 60)
    print("不支持格式测试：")
    result2 = extract_certificate_info(file_path="test.xyz")
    for k, v in result2.items():
        print(f"  {k}: {v}")

    # 方式3：图片 OCR 模拟测试（用虚构 OCR 输出模拟 pytesseract 识别结果）
    print()
    print("=" * 60)
    print("图片 OCR 模拟测试：")
    # 模拟 pytesseract 从一张图片中识别到的文字（OCR 输出通常有噪声和格式错乱）
    mock_ocr_text = """
    BUSINESS REGISTRATION CERTIFICATE

    Company Name: GLOBAL MERCHANT SOLUTIONS SDN. BHD.
    Registration No: 202101234567 (1234567-A)
    Date of Incorporation: 22 January 2021
    Type: Private Limited Company
    Registered Office: Level 15, Menara Exchange, 50450 Kuala Lumpur, Malaysia

    Director(s):
    - Nurul Amira Binti Razali
    - Lee Chong Wei

    This is to certify that the above company is duly registered under
    the Companies Act 2016.
    """
    result3 = extract_certificate_info(text_content=mock_ocr_text)
    for k, v in result3.items():
        print(f"  {k}: {v}")

    # 方式4：真实 PDF 文字提取测试（如果文件存在）
    print()
    print("=" * 60)
    test_pdf = "test_certificates/test_cert_01.pdf"
    if os.path.exists(test_pdf):
        print(f"PDF 文字提取测试: {test_pdf}")
        result4 = extract_certificate_info(file_path=test_pdf)
        for k, v in result4.items():
            print(f"  {k}: {v}")
    else:
        print(f"PDF 测试跳过（文件不存在: {test_pdf}）")
        print("提示：将 PDF 文件放到 test_certificates/ 目录下即可自动测试")
