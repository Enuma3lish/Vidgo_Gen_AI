"""
Email Service for sending verification and notification emails.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
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
        self.frontend_url = settings.FRONTEND_URL

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

            if self.use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                # For local development (Mailpit) or SSL
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)

            # Only login if credentials are provided
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.from_email, to_email, message.as_string())
            server.quit()

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

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

    async def send_verification_code_email(self, to_email: str, code: str, username: Optional[str] = None) -> bool:
        """Send 6-digit verification code email."""
        subject = "Your VidGo verification code"

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
                .code-box {{ background: #1f2937; color: #ffffff; font-size: 36px; font-weight: bold; letter-spacing: 8px; padding: 20px 40px; border-radius: 12px; text-align: center; margin: 30px 0; font-family: 'Courier New', monospace; }}
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎬 VidGo Verification Code</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>Thank you for registering with VidGo - AI Video Generation Platform!</p>
                    <p>Your verification code is:</p>
                    <div class="code-box">{code}</div>
                    <p style="text-align: center; color: #6b7280;">Enter this code in the app to verify your email address.</p>
                    <p style="color: #ef4444; font-size: 14px;">⏰ This code will expire in 15 minutes.</p>
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

Your verification code is: {code}

Enter this code in the app to verify your email address.

This code will expire in 15 minutes.

If you didn't create an account with VidGo, please ignore this email.

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_password_reset_email(self, to_email: str, token: str, username: Optional[str] = None) -> bool:
        """Send password reset link."""
        reset_url = f"{self.frontend_url}?reset_password={token}"

        subject = "Reset your VidGo password"

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
                .footer {{ text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>We received a request to reset your VidGo account password.</p>
                    <p>Click the button below to reset your password:</p>
                    <p style="text-align: center;">
                        <a href="{reset_url}" class="button">Reset Password</a>
                    </p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p style="word-break: break-all; color: #6366f1;">{reset_url}</p>
                    <p>This link will expire in 1 hour.</p>
                    <p>If you didn't request a password reset, please ignore this email or contact support if you have concerns.</p>
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

We received a request to reset your VidGo account password.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email.

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_welcome_email(self, to_email: str, username: Optional[str] = None) -> bool:
        """Send welcome email after successful verification."""
        subject = "Welcome to VidGo! 🎬"

        greeting = f"Hi {username}!" if username else "Hi there!"

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
                    <h1>🎉 Welcome to VidGo!</h1>
                </div>
                <div class="content">
                    <p>{greeting}</p>
                    <p>Your email has been verified and your account is now active!</p>
                    <p>Here's what you can do with VidGo:</p>
                    <div class="feature">
                        <strong>👗 AI Clothing Transform</strong><br>
                        Transform your photos with stunning AI-generated clothing styles.
                    </div>
                    <div class="feature">
                        <strong>✨ Special Effects</strong><br>
                        Enhance your images with professional-grade AI effects.
                    </div>
                    <div class="feature">
                        <strong>🎬 Video Generation</strong><br>
                        Create amazing videos from your images with AI.
                    </div>
                    <p style="text-align: center;">
                        <a href="{self.frontend_url}" class="button">Start Creating</a>
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

Your email has been verified and your account is now active!

Here's what you can do with VidGo:

- AI Clothing Transform: Transform your photos with stunning AI-generated clothing styles.
- Special Effects: Enhance your images with professional-grade AI effects.
- Video Generation: Create amazing videos from your images with AI.

Get started at: {self.frontend_url}

© 2024 VidGo. All rights reserved.
        """

        return await self.send_email(to_email, subject, html_content, text_content)


# Singleton instance
email_service = EmailService()
