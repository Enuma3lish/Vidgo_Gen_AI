"""
AI 短影音獲客系統 - Lead Generation API
======================================
接收產業主題 + 推廣產品 → 呼叫 Claude AI → 回傳爆款腳本

POST /api/v1/lead-gen/script   生成短影音腳本（支援 MOLTI AI / VidGo 兩個產品）
GET  /api/v1/lead-gen/health   檢查服務狀態
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Literal
import httpx
import logging

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# ---------------------------------------------------------------------------
# 產品設定：MOLTI AI 和 VidGo 瞬影科技
# ---------------------------------------------------------------------------

PRODUCT_CONFIGS = {
    "moltiai": {
        "name": "MOLTI AI",
        "url": "www.moltiai.com",
        "tagline": "AI 無程式碼自動化銷售系統",
        "features": [
            "AI 自動回覆 LINE / IG / FB 詢問，24小時不漏單",
            "三步驟自動追蹤潛在客戶，成交率提升 3 倍不用靠人催",
            "零程式碼整合 CRM、報表、LINE官方帳號，一個人頂三個業務",
        ],
        "pricing": "月租方案，7 天免費試用",
        "cta_templates": {
            "line": "現在加 LINE {line_id} 領取 7 天免費試用資格，限前 20 名",
            "trial": "到 moltiai.com 立即免費試用，不滿意 7 天全額退款",
            "consult": "預約 30 分鐘免費顧問，了解 AI 如何讓你的業績翻倍",
        },
    },
    "vidgo": {
        "name": "VidGo 瞬影科技",
        "url": "www.vidgo.co",
        "tagline": "AI 視覺內容生成平台",
        "features": [
            "30 秒生成專業電商產品圖，不用攝影棚、不用設計師",
            "AI 自動生成短影音，一天產出 10 支影片一個人搞定",
            "月費 NT$399 起，比請設計師便宜 50 倍，品質不打折",
        ],
        "pricing": "NT$399/月起，前 7 天免費試用",
        "cta_templates": {
            "line": "加 LINE {line_id} 立即領取免費試用，名額限 10 名",
            "trial": "到 vidgo.co 免費試用 7 天，親自體驗 AI 生成效果",
            "consult": "預約 Demo，30 分鐘看懂 AI 怎麼幫你省下設計費",
        },
    },
}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScriptRequest(BaseModel):
    industry: str = Field(..., description="目標產業，例如：醫美、建築、宗教、餐飲")
    product: Literal["moltiai", "vidgo"] = Field(
        default="vidgo",
        description="推廣產品：moltiai=MOLTI AI 自動化系統、vidgo=VidGo 瞬影科技"
    )
    cta_type: Literal["line", "trial", "consult"] = Field(
        default="line",
        description="行動呼籲類型：line=加LINE、trial=免費試用、consult=預約諮詢"
    )
    duration_sec: int = Field(default=60, ge=15, le=120, description="影片長度（秒）")
    language: str = Field(default="zh-TW", description="腳本語言")
    line_id: Optional[str] = Field(default=None, description="LINE ID 或連結（放入 CTA）")


class ScriptResponse(BaseModel):
    industry: str
    product: str
    product_name: str
    hook: str
    pain: str
    solution: str
    cta: str
    full_script: str
    video_prompt: str
    hashtags: list[str]
    estimated_duration_sec: int


# ---------------------------------------------------------------------------
# Claude API helper
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

SCRIPT_SYSTEM_PROMPT = """你是台灣頂級 B2B 短影音行銷文案師，專門寫讓台灣中小企業主看完立刻行動的腳本。
風格：口語化、有共鳴、像朋友在說話，不像廣告稿。
重要規則：絕對不說「我們很厲害」，只說「客戶得到什麼具體結果」。
格式：直接輸出 JSON，不加任何解釋文字。"""


def _build_script_prompt(req: ScriptRequest) -> str:
    cfg = PRODUCT_CONFIGS.get(req.product, PRODUCT_CONFIGS["vidgo"])
    cta_line = cfg["cta_templates"].get(req.cta_type, cfg["cta_templates"]["line"])
    if req.line_id:
        cta_line = cta_line.replace("{line_id}", req.line_id)
    else:
        cta_line = cta_line.replace(" {line_id}", "").replace("{line_id}", cfg["url"])

    word_count = int(req.duration_sec * 2.5)
    features_text = "\n".join(f"  - {f}" for f in cfg["features"])

    return f"""請幫我寫一支針對【{req.industry}】產業的 B2B 短影音腳本，推廣產品是「{cfg["name"]}」。

產品名稱：{cfg["name"]}（{cfg["tagline"]}）
產品特色：
{features_text}
定價方案：{cfg["pricing"]}
影片長度：{req.duration_sec}秒（約 {word_count} 字）
目標觀眾：台灣{req.industry}產業的企業主、決策者、行銷主管
行動呼籲：{cta_line}

請用以下 JSON 格式輸出（只輸出 JSON，不加說明）：

{{
  "hook": "前3秒開場白：一句讓{req.industry}業主停止滑手機的話（用數字、問句、或反常識說法）",
  "pain": "10秒痛點：說出{req.industry}業主每天遇到的具體困境，讓他們點頭說「對！就是這樣！」",
  "solution": "30秒解決方案：用{cfg['name']}的3個具體功能結果說明能帶來什麼改變（不說功能說結果）",
  "cta": "最後10秒行動呼籲：帶有緊迫感，包含限時或限量",
  "full_script": "完整連貫腳本，可以直接念出來，語氣自然口語",
  "video_prompt": "English description of video visuals for AI generation: professional Taiwan {req.industry} business setting, confident entrepreneur, modern aesthetic, 9:16 vertical format, warm lighting",
  "hashtags": ["5個中文hashtag不含#號", "適合台灣{req.industry}受眾搜尋"]
}}


async def _call_claude(prompt: str) -> dict:
    """呼叫 Anthropic Claude API 生成腳本"""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY 未設定，請聯繫管理員"
        )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": SCRIPT_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Claude API error: {e.response.status_code} {e.response.text}")
            raise HTTPException(status_code=502, detail="AI 腳本生成服務暫時無法使用，請稍後再試")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI 服務回應超時，請稍後再試")

    data = resp.json()
    raw_text = data["content"][0]["text"].strip()

    # 解析 JSON 回應（Claude 可能包在 ```json ``` 裡）
    import json, re
    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if not json_match:
        raise HTTPException(status_code=502, detail="AI 回應格式錯誤，請重試")

    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="AI 回應解析失敗，請重試")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/script", response_model=ScriptResponse, summary="生成短影音爆款腳本")
async def generate_script(
    req: ScriptRequest,
    current_user: User = Depends(get_current_user),
):
    """
    輸入產業主題 + 推廣產品，AI 自動生成具備行銷轉換力的短影音腳本。

    **支援產品：**
    - product=moltiai → MOLTI AI 無程式碼自動化銷售系統腳本
    - product=vidgo   → VidGo 瞬影科技 AI 視覺內容生成腳本

    **給 Make.com / n8n 呼叫：**
    - 先呼叫 POST /api/v1/auth/login/form 取得 access_token
    - Header 加入 Authorization: Bearer {access_token}
    - 回傳 hook / pain / solution / cta / full_script / video_prompt
    """
    cfg = PRODUCT_CONFIGS.get(req.product, PRODUCT_CONFIGS["vidgo"])
    prompt = _build_script_prompt(req)
    result = await _call_claude(prompt)

    word_count = len(result.get("full_script", ""))
    estimated_sec = max(15, min(120, int(word_count / 2.5)))

    return ScriptResponse(
        industry=req.industry,
        product=req.product,
        product_name=cfg["name"],
        hook=result.get("hook", ""),
        pain=result.get("pain", ""),
        solution=result.get("solution", ""),
        cta=result.get("cta", ""),
        full_script=result.get("full_script", ""),
        video_prompt=result.get("video_prompt", ""),
        hashtags=result.get("hashtags", []),
        estimated_duration_sec=estimated_sec,
    )


@router.get("/health", summary="檢查 Lead Gen 服務狀態")
async def health_check():
    """快速確認服務是否正常運作，以及 Anthropic API Key 是否已設定。"""
    return {
        "status": "ok",
        "anthropic_configured": bool(settings.ANTHROPIC_API_KEY),
        "message": "AI 獲客腳本服務正常運作" if settings.ANTHROPIC_API_KEY else "請設定 ANTHROPIC_API_KEY 環境變數",
    }
