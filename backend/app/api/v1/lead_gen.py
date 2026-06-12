"""
AI 短影音獲客系統 - Lead Generation API
======================================
接收產業主題 → 呼叫 Claude AI → 回傳爆款腳本

POST /api/v1/lead-gen/script   生成短影音腳本
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
# Schemas
# ---------------------------------------------------------------------------

class ScriptRequest(BaseModel):
    industry: str = Field(..., description="目標產業，例如：醫美、建築、宗教、餐飲")
    cta_type: Literal["line", "trial", "consult"] = Field(
        default="line",
        description="行動呼籲類型：line=加LINE、trial=免費試用、consult=預約諮詢"
    )
    duration_sec: int = Field(default=60, ge=15, le=120, description="影片長度（秒）")
    language: str = Field(default="zh-TW", description="腳本語言")
    brand_name: Optional[str] = Field(default="瞬影科技", description="品牌/公司名稱")
    line_id: Optional[str] = Field(default=None, description="LINE ID 或連結（放入 CTA）")


class ScriptResponse(BaseModel):
    industry: str
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

CTA_TEMPLATES = {
    "line": "現在加 LINE {line_id} 免費諮詢，前 10 名送價值 NT$3,000 的 AI 影片製作",
    "trial": "點擊連結免費試用 7 天，不滿意全額退款，零風險",
    "consult": "掃描 QR Code 預約 30 分鐘免費顧問，名額有限",
}

SCRIPT_SYSTEM_PROMPT = """你是台灣頂級 B2B 短影音行銷文案師。
你寫的腳本專門讓台灣中小企業主看完立刻想行動。
風格：口語化、有共鳴、像朋友在說話，不像廣告稿。
重要：絕對不要說「我們很厲害」，只說「客戶得到什麼結果」。"""


def _build_script_prompt(req: ScriptRequest) -> str:
    cta_line = CTA_TEMPLATES.get(req.cta_type, CTA_TEMPLATES["line"])
    if req.line_id:
        cta_line = cta_line.replace("{line_id}", req.line_id)
    else:
        cta_line = cta_line.replace(" {line_id}", "")

    word_count = int(req.duration_sec * 2.5)

    return f"""請幫我寫一支針對【{req.industry}】產業的 B2B 短影音腳本。

品牌名稱：{req.brand_name}
影片長度：{req.duration_sec}秒（約 {word_count} 字）
目標觀眾：台灣{req.industry}產業的企業主、行銷主管
行動呼籲：{cta_line}

請用以下 JSON 格式輸出（不要加其他說明，只輸出 JSON）：

{{
  "hook": "前 3 秒的開場白，一句讓人停止滑手機的話（用數字、問句、或反常識）",
  "pain": "10秒痛點描述，說出他們每天遇到的具體困境（讓他們點頭說對就是這樣）",
  "solution": "30秒解決方案，用 3 個具體結果說明 {req.brand_name} 能帶來什麼改變",
  "cta": "最後 10 秒的行動呼籲，帶有緊迫感",
  "full_script": "完整連貫的腳本文字，可以直接念出來",
  "video_prompt": "用英文描述這支影片的畫面風格，給 AI 影片生成工具用（例如：professional Taiwan business owner, modern office, confident presentation, 9:16 vertical）",
  "hashtags": ["5個中文hashtag", "不含#符號", "適合台灣受眾"]
}}"""


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
    輸入產業主題，AI 自動生成具備行銷轉換力的短影音腳本。

    **使用說明（給 n8n 呼叫）：**
    - 需要 Bearer Token（VidGo 登入後取得）
    - 回傳 JSON 包含 hook / pain / solution / cta / full_script / video_prompt
    - full_script 可直接傳給影片生成工具
    - video_prompt 可傳給 MoneyPrinterTurbo 或 VidGo short_video
    """
    prompt = _build_script_prompt(req)
    result = await _call_claude(prompt)

    word_count = len(result.get("full_script", ""))
    estimated_sec = max(15, min(120, int(word_count / 2.5)))

    return ScriptResponse(
        industry=req.industry,
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
