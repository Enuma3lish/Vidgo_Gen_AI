"""
Social Media Share Service
Generates share URLs for different social media platforms.
"""
from typing import Dict, Optional
from urllib.parse import quote_plus


# Platform share URL templates
SHARE_TEMPLATES = {
    "facebook": "https://www.facebook.com/sharer/sharer.php?u={url}",
    "twitter": "https://twitter.com/intent/tweet?url={url}&text={text}",
    "line": "https://social-plugins.line.me/lineit/share?url={url}",
    "tiktok": "https://www.tiktok.com/upload?url={url}",
    "instagram": None,  # Instagram has no web share URL; copy link to clipboard
}

SUPPORTED_PLATFORMS = list(SHARE_TEMPLATES.keys())


def build_share_url(
    platform: str,
    content_url: str,
    caption: Optional[str] = None,
) -> Dict:
    """Build a platform-specific share URL."""
    if platform not in SHARE_TEMPLATES:
        return {"error": f"Unsupported platform: {platform}", "platform": platform}

    template = SHARE_TEMPLATES[platform]
    encoded_url = quote_plus(content_url)
    encoded_text = quote_plus(caption or "Check out what I created with VidGo AI!")

    if template is None:
        # Platform doesn't support web share URL (e.g., Instagram)
        return {
            "platform": platform,
            "share_url": None,
            "content_url": content_url,
            "action": "copy_link",
            "message": "Copy the link and paste it in the app"
        }

    share_url = template.format(url=encoded_url, text=encoded_text)
    return {
        "platform": platform,
        "share_url": share_url,
        "content_url": content_url,
        "action": "open_url"
    }


def get_all_share_urls(content_url: str, caption: Optional[str] = None) -> list:
    """Get share URLs for all supported platforms."""
    return [
        build_share_url(p, content_url, caption)
        for p in SUPPORTED_PLATFORMS
    ]
