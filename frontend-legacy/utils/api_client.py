"""
API Client for backend communication
"""
import requests
import streamlit as st
import hashlib
from typing import Optional, Dict, Any
from config import *


def hash_password_client(password: str, salt: str = "vidgo_salt_2024") -> str:
    """
    Hash password on client side before sending to server.
    This provides an extra layer of security in addition to HTTPS.
    The server will hash it again with bcrypt.
    """
    # Create a salted hash
    salted = f"{salt}{password}{salt}"
    return hashlib.sha256(salted.encode()).hexdigest()


class APIClient:
    """API Client for communicating with backend services"""

    def __init__(self):
        self.backend_url = BACKEND_URL
        self.payment_url = PAYMENT_SERVICE_URL
        
        # Error message translations (Chinese to English)
        self.error_translations = {
            '此欄位不可為空白。': 'This field cannot be blank.',
            '此為必需欄位。': 'This field is required.',
            '請輸入有效的電子郵件地址。': 'Please enter a valid email address.',
            '這個密碼過短。請至少使用 8 個字元。': 'This password is too short. It must contain at least 8 characters.',
            '這個密碼太普通。': 'This password is too common.',
            '這個密碼只包含數字。': 'This password is entirely numeric.',
            '一個相同名稱的使用者已經存在。': 'A user with that username already exists.',
            '這個 電子信箱 在 使用者 已經存在。': 'A user with that email already exists.',
        }
        
        # Pattern-based translations
        self.error_patterns = [
            (r'"(.+)" 不是有效的選擇。', r'"\1" is not a valid choice.'),
        ]

    def translate_error(self, error_msg: str) -> str:
        """Translate Chinese error messages to English"""
        import re
        
        # First try direct translation
        if error_msg in self.error_translations:
            return self.error_translations[error_msg]
        
        # Then try pattern-based translation
        for pattern, replacement in self.error_patterns:
            if re.search(pattern, error_msg):
                return re.sub(pattern, replacement, error_msg)
        
        return error_msg

    def get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Get request headers with authentication token"""
        headers = {
            'Content-Type': 'application/json',
        }

        if include_auth and SESSION_ACCESS_TOKEN in st.session_state:
            headers['Authorization'] = f"Bearer {st.session_state[SESSION_ACCESS_TOKEN]}"

        return headers

    def handle_response(self, response: requests.Response) -> Optional[Dict[str, Any]]:
        """Handle API response"""
        if response.status_code == 401:
            # Token expired, try to refresh
            if self.refresh_token():
                return None  # Retry the request
            else:
                st.session_state.clear()
                st.error("Session expired. Please login again.")
                return None

        if response.status_code >= 400:
            try:
                error_data = response.json()
                
                # Handle validation errors (field-specific errors)
                if isinstance(error_data, dict):
                    error_messages = []
                    for field, errors in error_data.items():
                        if isinstance(errors, list):
                            for error in errors:
                                if isinstance(error, dict) and 'string' in error:
                                    translated = self.translate_error(error['string'])
                                    error_messages.append(f"**{field.replace('_', ' ').title()}**: {translated}")
                                elif isinstance(error, str):
                                    translated = self.translate_error(error)
                                    error_messages.append(f"**{field.replace('_', ' ').title()}**: {translated}")
                        elif isinstance(errors, str):
                            translated = self.translate_error(errors)
                            error_messages.append(f"**{field.replace('_', ' ').title()}**: {translated}")
                    
                    if error_messages:
                        st.error("❌ Validation errors:\n\n" + "\n\n".join(error_messages))
                    elif 'detail' in error_data:
                        st.error(f"Error: {error_data['detail']}")
                    else:
                        st.error(f"Error: {error_data}")
                else:
                    st.error(f"Error: {error_data.get('detail', 'Unknown error')}")
            except:
                st.error(f"Error: {response.status_code}")
            return None

        return response.json()

    def refresh_token(self) -> bool:
        """Refresh access token"""
        if SESSION_REFRESH_TOKEN not in st.session_state:
            return False

        try:
            response = requests.post(
                API_AUTH_REFRESH,
                json={'refresh': st.session_state[SESSION_REFRESH_TOKEN]}
            )

            if response.status_code == 200:
                data = response.json()
                st.session_state[SESSION_ACCESS_TOKEN] = data['access']
                return True
        except:
            pass

        return False

    def register(self, username: str, email: str, password: str, full_name: str = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Register a new user.
        Returns a message response - user must verify email before logging in.
        Password is hashed client-side before transmission for extra security.
        """
        try:
            # Hash password before sending (extra security layer)
            hashed_password = hash_password_client(password)

            payload = {
                'username': username,
                'email': email,
                'password': hashed_password,
                'password_confirm': hashed_password,
            }
            if full_name:
                payload['full_name'] = full_name

            response = requests.post(API_AUTH_REGISTER, json=payload)

            if response.status_code == 200:
                data = response.json()
                return data
            else:
                return self.handle_response(response)
        except Exception as e:
            st.error(f"Registration failed: {str(e)}")
            return None

    def verify_email(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify email using token from verification link"""
        try:
            from config import API_AUTH_VERIFY_EMAIL
            response = requests.post(
                API_AUTH_VERIFY_EMAIL,
                json={'token': token}
            )
            if response.status_code == 200:
                return response.json()
            else:
                return self.handle_response(response)
        except Exception as e:
            st.error(f"Email verification failed: {str(e)}")
            return None

    def resend_verification(self, email: str) -> Optional[Dict[str, Any]]:
        """Resend verification email"""
        try:
            from config import API_AUTH_RESEND_VERIFICATION
            response = requests.post(
                API_AUTH_RESEND_VERIFICATION,
                json={'email': email}
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                st.warning("Please wait before requesting another verification email.")
                return None
            else:
                return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to resend verification: {str(e)}")
            return None

    def forgot_password(self, email: str) -> Optional[Dict[str, Any]]:
        """Request password reset email"""
        try:
            from config import API_AUTH_FORGOT_PASSWORD
            response = requests.post(
                API_AUTH_FORGOT_PASSWORD,
                json={'email': email}
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                st.warning("Please wait before requesting another password reset.")
                return None
            else:
                return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to request password reset: {str(e)}")
            return None

    def reset_password(self, token: str, new_password: str) -> Optional[Dict[str, Any]]:
        """
        Reset password using token from email.
        Password is hashed client-side before transmission.
        """
        try:
            from config import API_AUTH_RESET_PASSWORD
            # Hash password before sending
            hashed_password = hash_password_client(new_password)

            response = requests.post(
                API_AUTH_RESET_PASSWORD,
                json={'token': token, 'new_password': hashed_password}
            )
            if response.status_code == 200:
                return response.json()
            else:
                return self.handle_response(response)
        except Exception as e:
            st.error(f"Password reset failed: {str(e)}")
            return None

    def login(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Login user.
        Password is hashed client-side before transmission for extra security.
        """
        try:
            # Hash password before sending (must match registration hash)
            hashed_password = hash_password_client(password)

            response = requests.post(
                API_AUTH_LOGIN,
                json={'email': email, 'password': hashed_password}
            )

            if response.status_code == 200:
                data = response.json()

                # Save to session state
                st.session_state[SESSION_USER] = data['user']
                st.session_state[SESSION_ACCESS_TOKEN] = data['tokens']['access']
                st.session_state[SESSION_REFRESH_TOKEN] = data['tokens']['refresh']

                return data
            else:
                return self.handle_response(response)

        except Exception as e:
            st.error(f"Login failed: {str(e)}")
            return None

    def logout(self) -> bool:
        """Logout user"""
        try:
            requests.post(API_AUTH_LOGOUT, headers=self.get_headers())
            st.session_state.clear()
            return True
        except:
            st.session_state.clear()
            return False

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current user details"""
        try:
            response = requests.get(API_USERS_ME, headers=self.get_headers())
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to get user: {str(e)}")
            return None

    def get_plans(self) -> Optional[list]:
        """Get all available plans"""
        try:
            response = requests.get(API_PLANS, headers=self.get_headers(include_auth=False))
            if response.status_code == 200:
                data = response.json()
                # New API returns list directly, not paginated
                return data if isinstance(data, list) else data.get('results', [])
            return self.handle_response(response) or []
        except Exception as e:
            st.error(f"Failed to get plans: {str(e)}")
            return []

    def get_current_subscription(self) -> Optional[Dict[str, Any]]:
        """Get current user's subscription"""
        try:
            from config import API_PLANS_CURRENT
            response = requests.get(API_PLANS_CURRENT, headers=self.get_headers())
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None  # No subscription
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to get subscription: {str(e)}")
            return None

    def get_plans_with_subscription(self) -> Optional[Dict[str, Any]]:
        """Get all plans with current subscription info"""
        try:
            from config import API_PLANS_WITH_SUBSCRIPTION
            response = requests.get(API_PLANS_WITH_SUBSCRIPTION, headers=self.get_headers())
            if response.status_code == 200:
                return response.json()
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to get plans: {str(e)}")
            return None

    def get_subscriptions(self) -> Optional[list]:
        """Get user subscriptions"""
        try:
            response = requests.get(API_SUBSCRIPTIONS, headers=self.get_headers())
            data = self.handle_response(response)
            return data.get('results', []) if data else []
        except Exception as e:
            st.error(f"Failed to get subscriptions: {str(e)}")
            return []

    def create_subscription(self, plan_id: str, auto_renew: bool = True) -> Optional[Dict[str, Any]]:
        """Create a new subscription"""
        try:
            response = requests.post(
                API_SUBSCRIPTIONS,
                json={'plan_id': plan_id, 'auto_renew': auto_renew},
                headers=self.get_headers()
            )
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to create subscription: {str(e)}")
            return None

    def update_subscription_status(self, subscription_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Update subscription status"""
        try:
            response = requests.patch(
                f"{API_SUBSCRIPTIONS}{subscription_id}/update_status/",
                json={'status': status},
                headers=self.get_headers()
            )
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to update subscription: {str(e)}")
            return None

    def get_orders(self) -> Optional[list]:
        """Get user orders"""
        try:
            response = requests.get(API_ORDERS, headers=self.get_headers())
            data = self.handle_response(response)
            return data.get('results', []) if data else []
        except Exception as e:
            st.error(f"Failed to get orders: {str(e)}")
            return []

    def create_order(self, plan_id: str, payment_method: str, notes: str = "") -> Optional[Dict[str, Any]]:
        """Create a new order"""
        try:
            response = requests.post(
                API_ORDERS,
                json={
                    'plan_id': plan_id,
                    'payment_method': payment_method,
                    'notes': notes
                },
                headers=self.get_headers()
            )
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to create order: {str(e)}")
            return None

    def cancel_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Cancel an order"""
        try:
            response = requests.patch(
                f"{API_ORDERS}{order_id}/cancel/",
                headers=self.get_headers()
            )
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to cancel order: {str(e)}")
            return None

    def delete_order(self, order_id: str) -> bool:
        """Delete a cancelled order"""
        try:
            response = requests.delete(
                f"{API_ORDERS}{order_id}/",
                headers=self.get_headers()
            )
            if response.status_code == 204:
                return True
            return self.handle_response(response) is not None
        except Exception as e:
            st.error(f"Failed to delete order: {str(e)}")
            return False

    def create_payment(self, order_id: str, order_number: str, amount: int, item_name: str, payment_method: str) -> Optional[Dict[str, Any]]:
        """Create payment with ECPay"""
        try:
            # Map payment methods to ECPay format
            payment_method_map = {
                'credit_card': 'Credit',
                'atm': 'ATM',
                'cvs': 'CVS',
                'barcode': 'BARCODE'
            }
            ecpay_payment_method = payment_method_map.get(payment_method, 'Credit')

            response = requests.post(
                API_PAYMENT_CREATE,
                json={
                    'order_id': order_id,
                    'order_number': order_number,
                    'amount': amount,
                    'item_name': item_name,
                    'payment_method': ecpay_payment_method
                },
                headers=self.get_headers()
            )
            return self.handle_response(response)
        except Exception as e:
            st.error(f"Failed to create payment: {str(e)}")
            return None

    def get_invoices(self) -> Optional[list]:
        """Get user invoices"""
        try:
            response = requests.get(API_INVOICES, headers=self.get_headers())
            data = self.handle_response(response)
            return data.get('results', []) if data else []
        except Exception as e:
            st.error(f"Failed to get invoices: {str(e)}")
            return []

    def delete_account(self, password: str) -> bool:
        """Delete user account"""
        try:
            response = requests.delete(
                f"{API_USERS_ME.replace('/me/', '/delete_account/')}",
                json={'password': password},
                headers=self.get_headers()
            )
            if response.status_code == 200:
                return True
            else:
                self.handle_response(response)
                return False
        except Exception as e:
            st.error(f"Failed to delete account: {str(e)}")
            return False

    # ==========================================================================
    # Demo API Methods
    # ==========================================================================

    def demo_search(self, prompt: str, style: str = None, category: str = None,
                    generate_if_not_found: bool = True) -> Optional[Dict[str, Any]]:
        """
        Search for matching demo or generate new one.
        Supports multi-language prompts.
        """
        try:
            payload = {
                "prompt": prompt,
                "generate_if_not_found": generate_if_not_found
            }
            if style:
                payload["style"] = style
            if category:
                payload["category"] = category

            response = requests.post(
                API_DEMO_SEARCH,
                json=payload,
                headers=self.get_headers(include_auth=False)
            )

            if response.status_code == 400:
                # Content moderation blocked
                data = response.json()
                return {"error": True, "detail": data.get("detail", "Content not allowed")}

            return self.handle_response(response)
        except Exception as e:
            return {"error": True, "detail": str(e)}

    def demo_get_random(self, category: str = None, style: str = None) -> Optional[Dict[str, Any]]:
        """Get a random demo for display"""
        try:
            params = {}
            if category:
                params["category"] = category
            if style:
                params["style"] = style

            response = requests.get(
                API_DEMO_RANDOM,
                params=params,
                headers=self.get_headers(include_auth=False)
            )
            return self.handle_response(response)
        except Exception as e:
            return None

    def demo_analyze_prompt(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Analyze a prompt without generating a demo"""
        try:
            response = requests.post(
                API_DEMO_ANALYZE,
                params={"prompt": prompt},
                headers=self.get_headers(include_auth=False)
            )
            return self.handle_response(response)
        except Exception as e:
            return None

    def demo_get_styles(self) -> list:
        """Get all available transformation styles"""
        try:
            response = requests.get(
                API_DEMO_STYLES,
                headers=self.get_headers(include_auth=False)
            )
            data = self.handle_response(response)
            return data if data else []
        except Exception as e:
            return []

    def demo_get_categories(self) -> list:
        """Get all demo categories"""
        try:
            response = requests.get(
                API_DEMO_CATEGORIES,
                headers=self.get_headers(include_auth=False)
            )
            data = self.handle_response(response)
            return data if data else []
        except Exception as e:
            return []

    def demo_moderate_prompt(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Check if a prompt passes content moderation"""
        try:
            response = requests.post(
                API_DEMO_MODERATE,
                params={"prompt": prompt},
                headers=self.get_headers(include_auth=False)
            )
            return self.handle_response(response)
        except Exception as e:
            return {"is_safe": False, "reason": str(e)}

    def demo_get_block_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get block cache statistics"""
        try:
            response = requests.get(
                API_DEMO_BLOCK_CACHE_STATS,
                headers=self.get_headers(include_auth=False)
            )
            return self.handle_response(response)
        except Exception as e:
            return None

    def demo_check_block_cache(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Check if prompt is in block cache"""
        try:
            response = requests.post(
                API_DEMO_BLOCK_CACHE_CHECK,
                params={"prompt": prompt},
                headers=self.get_headers(include_auth=False)
            )
            return self.handle_response(response)
        except Exception as e:
            return None

    def demo_get_category_videos(self, category: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Get videos for a specific category"""
        try:
            response = requests.get(
                f"{self.backend_url}/api/v1/demo/videos/{category}",
                params={"limit": limit},
                headers=self.get_headers(include_auth=False)
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None

    def demo_get_random_category_videos(self, category: str, count: int = 3) -> Optional[Dict[str, Any]]:
        """
        Get random videos for a category (for Explore Categories display).
        Returns specified number of random videos for auto-play carousel.
        """
        try:
            response = requests.get(
                f"{self.backend_url}/api/v1/demo/videos/{category}/random",
                params={"count": count},
                headers=self.get_headers(include_auth=False)
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None

    def demo_get_category_video_count(self, category: str) -> Optional[Dict[str, Any]]:
        """Get count of videos for a category"""
        try:
            response = requests.get(
                f"{self.backend_url}/api/v1/demo/videos/{category}/count",
                headers=self.get_headers(include_auth=False)
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None

    def demo_generate_image(
        self,
        prompt: str,
        style: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate demo image only (with watermark).
        This is the "Generate Demo" feature - Step 1.

        Uses GoEnhance Nano Banana for text-to-image generation.
        Processing time: ~30-60 seconds.

        Args:
            prompt: User's text prompt
            style: Optional style slug for image generation

        Returns:
            Dict with success, image_url, style_name
        """
        try:
            payload = {"prompt": prompt}
            if style:
                payload["style"] = style

            response = requests.post(
                f"{self.backend_url}/api/v1/demo/generate-image",
                json=payload,
                headers=self.get_headers(include_auth=False),
                timeout=180  # 3 minute timeout
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                data = response.json()
                return {"success": False, "error": data.get("detail", "Content not allowed")}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except requests.Timeout:
            return {"success": False, "error": "Request timed out (>3 minutes)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def demo_generate_video(
        self,
        prompt: str,
        image_url: str,
        style: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate video from an existing image.
        This is the "See It In Action" feature - Step 2.

        Uses Pollo AI Pixverse for image-to-video generation.
        Processing time: ~1-3 minutes.

        Args:
            prompt: User's text prompt (for video motion)
            image_url: Pre-generated image URL from Step 1
            style: Optional style slug

        Returns:
            Dict with success, video_url
        """
        try:
            payload = {
                "prompt": prompt,
                "image_url": image_url,
                "skip_v2v": True  # V2V disabled for current version
            }
            if style:
                payload["style"] = style

            response = requests.post(
                f"{self.backend_url}/api/v1/demo/generate-realtime",
                json=payload,
                headers=self.get_headers(include_auth=False),
                timeout=360  # 6 minute timeout
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                data = response.json()
                return {"success": False, "error": data.get("detail", "Content not allowed")}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except requests.Timeout:
            return {"success": False, "error": "Request timed out (>6 minutes)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def demo_generate_realtime(
        self,
        prompt: str,
        style: str = None,
        skip_v2v: bool = True,
        image_url: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate demo in real-time (legacy method for backward compatibility).
        If image_url is provided, uses that image; otherwise generates new image first.

        NOTE: This can take 3-10 minutes to complete.

        Args:
            prompt: User's text prompt
            style: Optional style slug
            skip_v2v: Skip V2V enhancement (default True)
            image_url: Optional pre-generated image URL

        Returns:
            Dict with image_url, video_url
        """
        try:
            payload = {
                "prompt": prompt,
                "skip_v2v": skip_v2v
            }
            if style:
                payload["style"] = style
            if image_url:
                payload["image_url"] = image_url

            response = requests.post(
                f"{self.backend_url}/api/v1/demo/generate-realtime",
                json=payload,
                headers=self.get_headers(include_auth=False),
                timeout=600  # 10 minute timeout
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                data = response.json()
                return {"success": False, "error": data.get("detail", "Content not allowed")}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except requests.Timeout:
            return {"success": False, "error": "Request timed out (>10 minutes)"}
        except Exception as e:
            return {"success": False, "error": str(e)}
