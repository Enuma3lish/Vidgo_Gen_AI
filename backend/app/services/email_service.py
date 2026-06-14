"""
Email Service for sending verification and notification emails.
"""
import html
import smtplib
import logging
import ssl
import time
import traceback as _traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails."""

    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME
        self.use_tls = settings.SMTP_TLS
        self.use_ssl = settings.SMTP_SSL
        self.smtp_timeout = settings.SMTP_TIMEOUT_SECONDS
        self.frontend_url = settings.FRONTEND_URL

    def _normalize_language(self, language: Optional[str] = None) -> str:
        lang = (language or "en").split(",", 1)[0].strip().lower()
        return "zh-TW" if lang.startswith("zh") else "en"

    def _is_configured(self) -> bool:
        """Check if SMTP is configured."""
        # Only require host - user/password optional for local dev (Mailpit)
        return bool(self.smtp_host)

    def _create_message(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> MIMEMultipart:
        """Create an email message."""
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = to_email

        # Plain text fallback
        if text_content:
            part1 = MIMEText(text_content, "plain")
            message.attach(part1)

        # HTML content
        part2 = MIMEText(html_content, "html")
        message.attach(part2)

        return message

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email."""
        if not self._is_configured():
            logger.warning(f"SMTP not configured. Would send email to {to_email}: {subject}")
            # In development, log the email instead of sending
            if settings.DEBUG:
                logger.info(f"Email content:\n{text_content or html_content}")
                return True
            return False

        try:
            message = self._create_message(to_email, subject, html_content, text_content)

            if self.smtp_host.lower() == "smtp.gmail.com" and self.smtp_user:
                if self.from_email.lower() != self.smtp_user.lower():
                    logger.warning(
                        "Gmail SMTP usually expects SMTP_FROM_EMAIL to match SMTP_USER "
                        "or a verified Gmail alias. Current from=%s smtp_user=%s",
                        self.from_email,
                        self.smtp_user,
                    )

            ssl_context = ssl.create_default_context()

            if self.use_ssl:
                with smtplib.SMTP_SSL(
                    self.smtp_host,
                    self.smtp_port,
                    timeout=self.smtp_timeout,
                    context=ssl_context,
                ) as server:
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)

                    server.sendmail(self.from_email, to_email, message.as_string())
            else:
                with smtplib.SMTP(
                    self.smtp_host,
                    self.smtp_port,
                    timeout=self.smtp_timeout,
                ) as server:
                    server.ehlo()
                    if self.use_tls:
                        server.starttls(context=ssl_context)
                        server.ehlo()

                    # Only login if credentials are provided
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)

                    server.sendmail(self.from_email, to_email, message.as_string())

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def get_admin_recipients(self) -> List[str]:
        """Return configured administrator email recipients."""
        recipients: List[str] = []

        primary_admin = (settings.ADMIN_ACCOUNT or "").strip()
        if primary_admin:
            recipients.append(primary_admin)

        for account in (settings.ADMIN_EXTRA_ACCOUNTS or "").split(","):
            account = account.strip()
            if not account:
                continue

            email = account.split(":", 1)[0].strip()
            if email and email not in recipients:
                recipients.append(email)

        return recipients

    async def send_provider_failure_alert(
        self,
        provider_name: str,
        task_type: str,
        error: str,
        fallback_provider: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Notify administrators that a provider failed, went unhealthy, or ran out of credits."""
        recipients = self.get_admin_recipients()
        if not recipients:
            logger.warning("No admin recipients configured for provider failure alerts.")
            return False

        request_params = request_params or {}
        task_label = task_type.replace("_", " ").title()
        model_name = str(request_params.get("model") or "").strip() or "n/a"
        prompt_preview = str(
            request_params.get("prompt")
            or request_params.get("script")
            or request_params.get("text")
            or ""
        ).strip()[:240]
        fallback_label = fallback_provider or "none available"
        issue_summary = (
            "VidGo detected a provider issue and switched to the next fallback provider."
            if fallback_provider
            else "VidGo detected a provider issue during health monitoring or without an available fallback."
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 640px; margin: 0 auto; padding: 24px; }}
                .header {{ background: #111827; color: white; padding: 20px 24px; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 24px; border-radius: 0 0 10px 10px; }}
                .meta {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 16px 0; }}
                .error {{ color: #b91c1c; white-space: pre-wrap; word-break: break-word; }}
                .muted {{ color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Provider Failure Alert</h2>
                </div>
                <div class="content">
                    <p>{html.escape(issue_summary)}</p>
                    <div class="meta">
                        <p><strong>Provider:</strong> {html.escape(provider_name)}</p>
                        <p><strong>Task:</strong> {html.escape(task_label)}</p>
                        <p><strong>Fallback:</strong> {html.escape(fallback_label)}</p>
                        <p><strong>Model:</strong> {html.escape(model_name)}</p>
                        <p><strong>Error:</strong></p>
                        <div class="error">{html.escape(error)}</div>
                    </div>
                    <p><strong>Prompt preview:</strong> {html.escape(prompt_preview or 'n/a')}</p>
                    <p class="muted">This alert is rate-limited to avoid duplicate emails during an outage.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = (
            f"Provider failure alert\n\n"
            f"Provider: {provider_name}\n"
            f"Task: {task_label}\n"
            f"Fallback: {fallback_label}\n"
            f"Model: {model_name}\n"
            f"Error: {error}\n"
            f"Prompt preview: {prompt_preview or 'n/a'}\n"
        )

        sent = False
        subject = f"[VidGo] Provider issue: {provider_name} ({task_label})"
        for recipient in recipients:
            delivered = await self.send_email(
                recipient,
                subject,
                html_content,
                text_content,
            )
            sent = sent or delivered

        return sent

    async def send_verification_email(self, to_email: str, token: str, username: Optional[str] = None) -> bool:
        """Send email verification link."""
        verification_url = f"{self.frontend_url}?verify_email={token}"

        subject = "Verify your VidGo account"

        greeting = f"Hi {username}," if username else "Hi,"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #6366f1; color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
                .button:hover {{ background: #4f46e5; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎬 Welcome to VidGo!</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>Thank you for registering with VidGo - AI Video Generation Platform!</p>
                    <p>Please verify your email address by clicking the button below:</p>
                    <p style="text-align: center;">
                        <a href="{verification_url}" class="button">Verify Email Address</a>
                    </p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p style="word-break: break-all; color: #6366f1;">{verification_url}</p>
                    <p>This link will expire in {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} hours.</p>
                    <p>If you didn't create an account with VidGo, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2024 VidGo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
{greeting}

Thank you for registering with VidGo - AI Video Generation Platform!

Please verify your email address by clicking the link below:
{verification_url}

This link will expire in {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} hours.

If you didn't create an account with VidGo, please ignore this email.

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_verification_code_email(
        self,
        to_email: str,
        code: str,
        username: Optional[str] = None,
        language: str = "en",
    ) -> bool:
        """Send 6-digit verification code email."""
        lang = self._normalize_language(language)
        is_zh = lang.startswith("zh")
        subject = "VidGo 電子郵件驗證碼" if is_zh else "Your VidGo verification code"

        greeting = f"{username} 您好：" if (is_zh and username) else ("您好：" if is_zh else (f"Hi {username}," if username else "Hi,"))
        header = "VidGo 驗證碼" if is_zh else "VidGo Verification Code"
        intro = "感謝您註冊 VidGo AI 視覺生成平台。" if is_zh else "Thank you for registering with VidGo - AI Video Generation Platform!"
        code_label = "您的驗證碼是：" if is_zh else "Your verification code is:"
        instruction = "請在 VidGo 輸入此驗證碼完成電子郵件驗證。" if is_zh else "Enter this code in the app to verify your email address."
        expiry = "此驗證碼將於 15 分鐘後失效。" if is_zh else "This code will expire in 15 minutes."
        ignore = "如果您沒有建立 VidGo 帳戶，請忽略此信。" if is_zh else "If you didn't create an account with VidGo, please ignore this email."

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .code-box {{ background: #1f2937; color: #ffffff; font-size: 36px; font-weight: bold; letter-spacing: 8px; padding: 20px 40px; border-radius: 12px; text-align: center; margin: 30px 0; font-family: 'Courier New', monospace; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{header}</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>{intro}</p>
                    <p>{code_label}</p>
                    <div class="code-box">{code}</div>
                    <p style="text-align: center; color: #6b7280;">{instruction}</p>
                    <p style="color: #ef4444; font-size: 14px;">{expiry}</p>
                    <p>{ignore}</p>
                </div>
                <div class="footer">
                    <p>© 2024 VidGo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
{greeting}

{intro}

{code_label} {code}

{instruction}

{expiry}

{ignore}

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_password_reset_email(
        self,
        to_email: str,
        token: str,
        username: Optional[str] = None,
        language: str = "en",
    ) -> bool:
        """Send password reset link."""
        reset_url = f"{self.frontend_url.rstrip('/')}/auth/reset-password?token={token}"

        lang = self._normalize_language(language)
        is_zh = lang.startswith("zh")
        subject = "重設您的 VidGo 密碼" if is_zh else "Reset your VidGo password"

        greeting = f"{username} 您好：" if (is_zh and username) else ("您好：" if is_zh else (f"Hi {username}," if username else "Hi,"))
        header = "密碼重設" if is_zh else "Password Reset"
        intro = "我們收到重設您 VidGo 帳戶密碼的請求。" if is_zh else "We received a request to reset your VidGo account password."
        action = "重設密碼" if is_zh else "Reset Password"
        copy = "請點擊下方按鈕重設密碼：" if is_zh else "Click the button below to reset your password:"
        paste = "或複製以下連結並貼到瀏覽器：" if is_zh else "Or copy and paste this link in your browser:"
        expiry = "此連結將於 1 小時後失效。" if is_zh else "This link will expire in 1 hour."
        ignore = "如果您沒有要求重設密碼，請忽略此信；若有疑慮請聯絡客服。" if is_zh else "If you didn't request a password reset, please ignore this email or contact support if you have concerns."

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #6366f1; color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{header}</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>{intro}</p>
                    <p>{copy}</p>
                    <p style="text-align: center;">
                        <a href="{reset_url}" class="button">{action}</a>
                    </p>
                    <p>{paste}</p>
                    <p style="word-break: break-all; color: #6366f1;">{reset_url}</p>
                    <p>{expiry}</p>
                    <p>{ignore}</p>
                </div>
                <div class="footer">
                    <p>© 2024 VidGo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
{greeting}

{intro}

{copy}
{reset_url}

{expiry}

{ignore}

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_welcome_email(self, to_email: str, username: Optional[str] = None, language: str = "en") -> bool:
        """Send welcome email after successful verification."""
        lang = self._normalize_language(language)
        is_zh = lang.startswith("zh")
        subject = "歡迎使用 VidGo" if is_zh else "Welcome to VidGo!"

        greeting = f"{username} 您好！" if (is_zh and username) else ("您好！" if is_zh else (f"Hi {username}!" if username else "Hi there!"))
        header = "歡迎使用 VidGo" if is_zh else "Welcome to VidGo!"
        activated = "您的電子郵件已驗證完成，帳戶已啟用。" if is_zh else "Your email has been verified and your account is now active!"
        start_label = "開始創作" if is_zh else "Start Creating"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .feature {{ padding: 15px; margin: 10px 0; background: white; border-radius: 8px; border-left: 4px solid #6366f1; }}
                .button {{ display: inline-block; background: #6366f1; color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{header}</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>{activated}</p>
                    <p>{'您可以使用 VidGo 完成以下工作：' if is_zh else "Here's what you can do with VidGo:"}</p>
                    <div class="feature">
                        <strong>{'AI 商品與服飾視覺' if is_zh else 'AI Product and Fashion Visuals'}</strong><br>
                        {'用 AI 製作商品場景、模特試穿與商業素材。' if is_zh else 'Create product scenes, try-on visuals, and commercial assets with AI.'}
                    </div>
                    <div class="feature">
                        <strong>{'去背與高清放大' if is_zh else 'Background Removal and HD Upscale'}</strong><br>
                        {'快速整理商品圖並輸出可下載素材。' if is_zh else 'Clean product images quickly and export downloadable assets.'}
                    </div>
                    <div class="feature">
                        <strong>{'短影音與數位人' if is_zh else 'Short Video and Avatar'}</strong><br>
                        {'把圖片變成短影片，或製作可用於行銷的數位人影片。' if is_zh else 'Turn images into short videos or create marketing-ready avatar clips.'}
                    </div>
                    <p style="text-align: center;">
                        <a href="{self.frontend_url}" class="button">{start_label}</a>
                    </p>
                </div>
                <div class="footer">
                    <p>© 2024 VidGo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
{greeting}

{activated}

{'您可以使用 VidGo 完成以下工作：' if is_zh else "Here's what you can do with VidGo:"}

- {'AI 商品與服飾視覺：製作商品場景、模特試穿與商業素材。' if is_zh else 'AI Product and Fashion Visuals: Create product scenes, try-on visuals, and commercial assets.'}
- {'去背與高清放大：快速整理商品圖並輸出可下載素材。' if is_zh else 'Background Removal and HD Upscale: Clean product images and export downloadable assets.'}
- {'短影音與數位人：把圖片變成短影片，或製作行銷數位人影片。' if is_zh else 'Short Video and Avatar: Turn images into short videos or create avatar clips.'}

Get started at: {self.frontend_url}

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_promotion_code_used_email(
        self,
        to_email: str,
        new_user_email: str,
        promotion_code: str,
        reward_credits: int,
        username: Optional[str] = None,
    ) -> bool:
        """Notify a promoter when someone registers with their promotion code."""
        subject = "[VidGo] Your promotion code was used"
        greeting = f"Hi {username}," if username else "Hi,"
        safe_user_email = html.escape(new_user_email)
        safe_code = html.escape(promotion_code)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .notice {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin: 20px 0; }}
                .credits {{ color: #4f46e5; font-weight: bold; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Promotion Code Used</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <div class="notice">
                        <p><strong>User:</strong> {safe_user_email} used your promotion code <strong>{safe_code}</strong>.</p>
                        <p>You received <span class="credits">{reward_credits} bonus credits</span>.</p>
                    </div>
                    <p>You can view your referral stats from your VidGo dashboard.</p>
                </div>
                <div class="footer">
                    <p>© 2024 VidGo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""{greeting}

User: {new_user_email} used your promotion code {promotion_code}.
You received {reward_credits} bonus credits.

You can view your referral stats from your VidGo dashboard.

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_invoice_email(
        self,
        to_email: str,
        invoice_number: str,
        amount: float,
        currency: str,
        plan_name: str,
        pdf_url: str,
        username: Optional[str] = None
    ) -> bool:
        """Send invoice email with PDF download link."""
        subject = f"Your VidGo Invoice #{invoice_number}"

        greeting = f"Hi {username}," if username else "Hi,"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .invoice-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #e5e7eb; }}
                .invoice-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f3f4f6; }}
                .invoice-total {{ font-size: 24px; font-weight: bold; color: #6366f1; }}
                .button {{ display: inline-block; background: #6366f1; color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🧾 Invoice</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>Thank you for your subscription to VidGo!</p>

                    <div class="invoice-box">
                        <div class="invoice-row">
                            <span>Invoice Number</span>
                            <span><strong>{invoice_number}</strong></span>
                        </div>
                        <div class="invoice-row">
                            <span>Plan</span>
                            <span>{plan_name}</span>
                        </div>
                        <div class="invoice-row">
                            <span>Amount</span>
                            <span class="invoice-total">{currency} {amount:.2f}</span>
                        </div>
                    </div>

                    <p style="text-align: center;">
                        <a href="{pdf_url}" class="button">📄 Download PDF Invoice</a>
                    </p>
                    <p style="color: #6b7280; font-size: 12px; text-align: center;">
                        Note: This download link expires in 1 hour.
                    </p>
                </div>
                <div class="footer">
                    <p>© 2024 VidGo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
{greeting}

Thank you for your subscription to VidGo!

Invoice Number: {invoice_number}
Plan: {plan_name}
Amount: {currency} {amount:.2f}

Download your PDF invoice: {pdf_url}

Note: This download link expires in 1 hour.

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_refund_notification(
        self,
        to_email: str,
        order_number: str,
        refund_amount: float,
        currency: str = "TWD",
        requires_manual: bool = False,
        username: Optional[str] = None,
    ) -> bool:
        """Send refund notification email."""
        subject = f"VidGo Refund Confirmation — Order {order_number}"

        greeting = f"Hi {username}," if username else "Hi,"

        if requires_manual:
            processing_note = "Your refund is being processed manually and will be completed within <strong>3-5 business days</strong>."
        else:
            processing_note = "Your refund has been processed and should appear in your account within <strong>5-10 business days</strong>."

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
                .refund-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #e5e7eb; }}
                .refund-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f3f4f6; }}
                .refund-amount {{ font-size: 24px; font-weight: bold; color: #10b981; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Refund Confirmation</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>Your subscription refund has been confirmed.</p>

                    <div class="refund-box">
                        <div class="refund-row">
                            <span>Order Number</span>
                            <span><strong>{order_number}</strong></span>
                        </div>
                        <div class="refund-row">
                            <span>Refund Amount</span>
                            <span class="refund-amount">{currency} {refund_amount:,.0f}</span>
                        </div>
                    </div>

                    <p>{processing_note}</p>
                    <p>Your subscription has been cancelled and all associated credits have been removed from your account.</p>
                    <p>If you have any questions, please contact our support team.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 VidGo. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""{greeting}

Your subscription refund has been confirmed.

Order Number: {order_number}
Refund Amount: {currency} {refund_amount:,.0f}

{"Your refund is being processed manually and will be completed within 3-5 business days." if requires_manual else "Your refund has been processed and should appear in your account within 5-10 business days."}

Your subscription has been cancelled and all associated credits have been removed from your account.

If you have any questions, please contact our support team.

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)


# In-memory rate limiter for admin tool-failure alerts
# Key: (tool_name, error_signature) -> last sent timestamp (epoch seconds)
_TOOL_FAILURE_ALERT_LAST_SENT: Dict[str, float] = {}
_TOOL_FAILURE_ALERT_INTERVAL_SECONDS = 60.0


# Singleton instance
email_service = EmailService()


async def send_admin_tool_failure_email(
    tool_name: str,
    user_email: Optional[str],
    error: BaseException,
    request_id: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> bool:
    """Notify admins that an internal tool/api failed for a user.

    Rate-limited per (tool_name, error_class) at most once per minute to
    avoid an email storm during outages. Failures here are swallowed so a
    broken mail pipeline never affects user-facing requests.
    """
    try:
        error_class = type(error).__name__
        error_summary = str(error)[:500] or error_class
        rate_key = f"{tool_name}::{error_class}"
        now = time.monotonic()
        last = _TOOL_FAILURE_ALERT_LAST_SENT.get(rate_key, 0.0)
        if now - last < _TOOL_FAILURE_ALERT_INTERVAL_SECONDS:
            logger.info(
                "Suppressing duplicate admin tool-failure alert for %s (%s)",
                tool_name,
                error_class,
            )
            return False
        _TOOL_FAILURE_ALERT_LAST_SENT[rate_key] = now

        recipients = email_service.get_admin_recipients()
        if not recipients:
            logger.warning("No admin recipients configured for tool-failure alerts.")
            return False

        traceback_excerpt = ""
        try:
            tb = _traceback.format_exception(type(error), error, error.__traceback__)
            traceback_excerpt = "".join(tb)[-2000:]
        except Exception:
            traceback_excerpt = ""

        context_lines = []
        if request_id:
            context_lines.append(f"Request ID: {request_id}")
        if user_email:
            context_lines.append(f"User: {user_email}")
        if extra_context:
            for k, v in extra_context.items():
                context_lines.append(f"{k}: {str(v)[:200]}")
        context_block = "\n".join(context_lines) or "(no additional context)"

        subject = f"[VidGo] Tool failure: {tool_name} ({error_class})"

        html_body = f"""
        <!DOCTYPE html><html><body style="font-family: Arial, sans-serif; line-height: 1.55; color: #111;">
            <h2 style="color:#b91c1c;">Tool failure: {html.escape(tool_name)}</h2>
            <p>An internal tool raised an unhandled exception while serving a user request.</p>
            <h3>Context</h3>
            <pre style="background:#f3f4f6;padding:12px;border-radius:6px;white-space:pre-wrap;">{html.escape(context_block)}</pre>
            <h3>Error</h3>
            <pre style="background:#fef2f2;padding:12px;border-radius:6px;white-space:pre-wrap;color:#b91c1c;">{html.escape(error_class)}: {html.escape(error_summary)}</pre>
            <h3>Traceback</h3>
            <pre style="background:#f9fafb;padding:12px;border-radius:6px;white-space:pre-wrap;font-size:12px;">{html.escape(traceback_excerpt or '(unavailable)')}</pre>
            <p style="color:#6b7280;font-size:12px;">Alerts are rate-limited to one per minute per error class.</p>
        </body></html>
        """

        text_body = (
            f"Tool failure: {tool_name}\n"
            f"Error: {error_class}: {error_summary}\n\n"
            f"Context:\n{context_block}\n\n"
            f"Traceback:\n{traceback_excerpt or '(unavailable)'}\n"
        )

        sent_any = False
        for recipient in recipients:
            try:
                delivered = await email_service.send_email(
                    recipient, subject, html_body, text_body
                )
                sent_any = sent_any or delivered
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Failed to send admin tool-failure alert: %s", exc)
        return sent_any
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("send_admin_tool_failure_email crashed: %s", exc)
        return False
