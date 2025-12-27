"""
Streamlit Frontend - Main Application
VidGo - AI Video Generation Platform

Features:
- Demo page with AI Clothing Transform & Special Effects
- User authentication and subscription management
- Multi-language support (EN, ZH-TW, JA, KO, ES)
"""
import streamlit as st
from streamlit_option_menu import option_menu
from config import PAGE_TITLE, PAGE_ICON, LAYOUT
from utils.api_client import APIClient
from utils.auth import is_authenticated, get_current_user
from components.demo import show_demo_page

# Page configuration
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="expanded"
)

# Initialize API client
api_client = APIClient()

# Custom CSS - High Contrast Theme
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 900;
        text-align: center;
        margin-bottom: 2rem;
        color: #FFFFFF;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        border: 3px solid #FFFFFF;
    }

    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .main-header {
            color: #FFFFFF;
            border-color: #FFFFFF;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.9);
        }
    }

    /* Light mode support */
    @media (prefers-color-scheme: light) {
        .main-header {
            color: #FFFFFF;
            border-color: #4B5563;
            background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        }
    }

    .plan-card {
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .plan-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        border-color: #667eea;
    }
    .popular-badge {
        background-color: #ffd700;
        color: #000;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


def show_login_page():
    """Login page"""
    st.markdown('<h1 class="main-header">🎨 Fluxus Imago Fabrica</h1>', unsafe_allow_html=True)

    # Show success message if redirected from registration
    if 'registration_success' in st.session_state and st.session_state['registration_success']:
        st.success("✅ Registration successful! Please login with your new account.")
        del st.session_state['registration_success']

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            st.subheader("Login to your account")
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="your@email.com")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login", use_container_width=True)

                if submit:
                    if not email or not password:
                        st.error("Please fill in all fields")
                    else:
                        with st.spinner("Logging in..."):
                            result = api_client.login(email, password)
                            if result:
                                st.success("Login successful! Redirecting to dashboard...")
                                # Clear any lingering query params and go to dashboard
                                st.query_params.clear()
                                import time
                                time.sleep(0.5)
                                st.rerun()

        with tab2:
            st.subheader("Create a new account")
            with st.form("register_form"):
                username = st.text_input("Username", placeholder="username")
                email = st.text_input("Email", placeholder="your@email.com")
                password = st.text_input("Password", type="password")
                password_confirm = st.text_input("Confirm Password", type="password")
                first_name = st.text_input("First Name", placeholder="First Name")
                last_name = st.text_input("Last Name", placeholder="Last Name")

                submit = st.form_submit_button("Register", use_container_width=True)

                if submit:
                    if not username or not email or not password:
                        st.error("Please fill in all required fields")
                    elif password != password_confirm:
                        st.error("Passwords don't match")
                    else:
                        with st.spinner("Creating account..."):
                            result = api_client.register(
                                username=username,
                                email=email,
                                password=password,
                                password_confirm=password_confirm,
                                first_name=first_name,
                                last_name=last_name
                            )
                            if result:
                                # Set flag to show success message on next page load
                                st.session_state['registration_success'] = True
                                st.rerun()


def show_dashboard():
    """Main dashboard"""
    user = get_current_user()

    st.markdown(f'<h1 class="main-header">Welcome, {user["username"]}! 👋</h1>', unsafe_allow_html=True)

    # Get user data
    subscriptions = api_client.get_subscriptions()
    orders = api_client.get_orders()

    # Dashboard metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Active Subscriptions", len([s for s in subscriptions if s['status'] == 'active']))

    with col2:
        st.metric("Total Orders", len(orders))

    with col3:
        completed_orders = len([o for o in orders if o['status'] == 'completed'])
        st.metric("Completed Payments", completed_orders)

    with col4:
        total_spent = sum([float(o['amount']) for o in orders if o['status'] == 'completed'])
        st.metric("Total Spent", f"${total_spent:.2f}")

    st.divider()

    # Recent subscriptions
    st.subheader("📋 Your Subscriptions")
    # Filter out cancelled subscriptions
    active_subscriptions = [sub for sub in subscriptions if sub['status'] != 'cancelled']
    if active_subscriptions:
        for sub in active_subscriptions[:5]:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                with col1:
                    st.write(f"**{sub['plan']['name']}**")
                with col2:
                    st.write(f"Status: **{sub['status'].upper()}**")
                with col3:
                    st.write(f"${sub['plan']['price']}/{sub['plan']['billing_cycle']}")
                with col4:
                    if sub['status'] == 'active':
                        if st.button("❌ Cancel", key=f"cancel_{sub['id']}", help="Cancel this subscription"):
                            # Show confirmation in session state
                            st.session_state[f'confirm_cancel_sub_{sub["id"]}'] = True
                            st.rerun()

                        # Check if confirmation is needed
                        if st.session_state.get(f'confirm_cancel_sub_{sub["id"]}'):
                            st.warning("⚠️ Are you sure? Click Cancel again to confirm.")
                            if st.button("✅ Confirm Cancel", key=f"confirm_cancel_{sub['id']}", type="primary"):
                                result = api_client.update_subscription_status(sub['id'], 'cancelled')
                                if result:
                                    st.success("Subscription cancelled successfully!")
                                    st.session_state.pop(f'confirm_cancel_sub_{sub["id"]}', None)
                                    st.rerun()
                            if st.button("↩️ Keep Subscription", key=f"keep_sub_{sub['id']}"):
                                st.session_state.pop(f'confirm_cancel_sub_{sub["id"]}', None)
                                st.rerun()
                st.divider()
    else:
        st.info("No active subscriptions. Browse plans to get started!")

    st.divider()

    # Recent orders and subscriptions
    st.subheader("💳 Recent Orders & Subscriptions")

    # Combine orders and subscriptions with type indicator
    combined_items = []
    if orders:
        for order in orders[:5]:
            combined_items.append({
                'type': 'order',
                'id': order['id'],
                'number': order['order_number'],
                'status': order['status'],
                'amount': order['amount'],
                'date': order['created_at'][:10],
                'plan_name': order.get('plan', {}).get('name', 'N/A') if order.get('plan') else 'N/A',
                'data': order
            })

    if subscriptions:
        for sub in subscriptions[:5]:
            combined_items.append({
                'type': 'subscription',
                'id': sub['id'],
                'number': f"SUB-{sub['id'][:8]}",
                'status': sub['status'],
                'amount': sub['plan']['price'],
                'date': sub['created_at'][:10],
                'plan_name': sub['plan']['name'],
                'data': sub
            })

    # Sort by date
    combined_items.sort(key=lambda x: x['date'], reverse=True)

    if combined_items:
        for item in combined_items[:10]:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
                with col1:
                    icon = "📦" if item['type'] == 'order' else "💎"
                    st.write(f"{icon} **{item['number']}**")
                    st.caption(item['plan_name'])
                with col2:
                    status_color = {
                        'pending': '🟡',
                        'processing': '🔵',
                        'completed': '🟢',
                        'active': '🟢',
                        'failed': '🔴',
                        'cancelled': '⚫',
                        'expired': '⚫'
                    }
                    status_display = 'ACHIEVED' if item['status'] == 'completed' else item['status'].upper()
                    st.write(f"{status_color.get(item['status'], '⚪')} {status_display}")
                with col3:
                    st.write(f"${item['amount']}")
                with col4:
                    st.write(item['date'])
                with col5:
                    # Show appropriate action buttons based on type and status
                    if item['type'] == 'order':
                        order = item['data']
                        if order['status'] == 'pending':
                            # For pending orders, show "Pay Now" button
                            if st.button("💳 Pay", key=f"pay_order_{order['id']}", help="Continue to payment"):
                                # Get plan details for payment
                                if order.get('plan'):
                                    payment = api_client.create_payment(
                                        order_id=order['id'],
                                        order_number=order['order_number'],
                                        amount=int(float(order['amount'])),
                                        item_name=order['plan']['name'],
                                        payment_method=order.get('payment_method', 'credit_card')
                                    )
                                    if payment and payment.get('success'):
                                        st.session_state['payment_data'] = payment
                                        st.session_state['order'] = order
                                        st.session_state['show_payment_form'] = True
                                        st.rerun()
                        elif order['status'] in ['pending', 'processing', 'failed']:
                            # For pending/processing/failed orders, show cancel button
                            if st.button("❌", key=f"cancel_order_{order['id']}", help="Cancel order"):
                                result = api_client.cancel_order(order['id'])
                                if result:
                                    st.success("Order cancelled")
                                    st.rerun()
                    elif item['type'] == 'subscription':
                        sub = item['data']
                        if sub['status'] == 'active':
                            if st.button("❌ Cancel", key=f"cancel_sub_dash_{sub['id']}", help="Cancel subscription"):
                                result = api_client.update_subscription_status(sub['id'], 'cancelled')
                                if result:
                                    st.success("Subscription cancelled!")
                                    st.rerun()
                st.divider()
    else:
        st.info("No orders yet")


def show_plans_page():
    """Plans and pricing page"""
    st.markdown('<h1 class="main-header">💎 Choose Your Plan</h1>', unsafe_allow_html=True)

    plans = api_client.get_plans()

    if not plans:
        st.info("Loading plans...")
        return

    # Get current subscription
    current_sub = api_client.get_current_subscription()
    current_plan_id = current_sub.get('plan_id') if current_sub else None

    # Display plans in columns
    num_cols = min(len(plans), 4)
    cols = st.columns(num_cols)

    for idx, plan in enumerate(plans):
        with cols[idx % num_cols]:
            with st.container():
                # Featured/current badge
                if str(plan.get('id')) == str(current_plan_id):
                    st.markdown('<span class="popular-badge">✓ CURRENT</span>', unsafe_allow_html=True)
                elif plan.get('is_featured'):
                    st.markdown('<span class="popular-badge">⭐ RECOMMENDED</span>', unsafe_allow_html=True)

                st.markdown(f"### {plan['name']}")

                # Pricing
                if plan.get('price_monthly', 0) == 0:
                    st.markdown("## Free")
                else:
                    st.markdown(f"## ${plan['price_monthly']}/mo")
                    st.caption(f"or ${plan['price_yearly']}/year")

                st.markdown(f"*{plan.get('description', '')}*")

                st.markdown("---")

                # Features
                st.markdown(f"✓ {plan['credits_per_month']} credits/month")
                st.markdown(f"✓ Max {plan['max_video_length']}s videos")
                st.markdown(f"✓ {plan['max_resolution']} resolution")

                if not plan.get('watermark'):
                    st.markdown("✓ No watermark")
                if plan.get('priority_queue'):
                    st.markdown("✓ Priority queue")
                if plan.get('api_access'):
                    st.markdown("✓ API access")

                # Feature flags
                if plan.get('feature_clothing_transform'):
                    st.markdown("✓ AI Clothing Transform")
                if plan.get('feature_goenhance'):
                    st.markdown("✓ Special Effects")
                if plan.get('feature_video_gen'):
                    st.markdown("✓ Video Generation")
                if plan.get('feature_batch_processing'):
                    st.markdown("✓ Batch Processing")

                st.markdown("---")

                if str(plan.get('id')) == str(current_plan_id):
                    st.button("Current Plan", key=f"plan_{plan['id']}", use_container_width=True, disabled=True)
                elif plan.get('price_monthly', 0) == 0:
                    st.button("Free Plan", key=f"plan_{plan['id']}", use_container_width=True, disabled=True)
                else:
                    if st.button("Subscribe", key=f"plan_{plan['id']}", use_container_width=True, type="primary" if plan.get('is_featured') else "secondary"):
                        st.session_state['selected_plan'] = plan
                        st.session_state['page'] = 'checkout'
                        st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)


def show_checkout_page():
    """Checkout page"""
    if 'selected_plan' not in st.session_state:
        st.warning("Please select a plan first")
        if st.button("← Back to Plans"):
            st.session_state.pop('page', None)
            st.rerun()
        return

    plan = st.session_state['selected_plan']

    st.markdown('<h1 class="main-header">🛒 Checkout</h1>', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back to Plans"):
        st.session_state.pop('page', None)
        st.session_state.pop('selected_plan', None)
        st.rerun()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Order Summary")
        st.write(f"**Plan:** {plan['name']}")
        st.write(f"**Price:** ${plan['price']}")
        st.write(f"**Billing Cycle:** {plan['billing_cycle']}")

        if plan.get('description'):
            st.write(f"**Description:** {plan['description']}")

        st.divider()

        st.subheader("Payment Method")
        payment_method = st.selectbox(
            "Select Payment Method",
            options=["credit_card", "atm", "cvs", "barcode"],
            format_func=lambda x: {
                "credit_card": "💳 Credit Card",
                "atm": "🏦 ATM Transfer",
                "cvs": "🏪 Convenience Store",
                "barcode": "📊 Barcode"
            }[x]
        )

        notes = st.text_area("Notes (Optional)", placeholder="Add any notes here...")

    with col2:
        st.subheader("Price Details")
        st.write(f"Plan Price: ${plan['price']}")
        st.write(f"Tax (5%): ${float(plan['price']) * 0.05:.2f}")
        st.write("---")
        total = float(plan['price']) * 1.05
        st.write(f"**Total: ${total:.2f}**")

    st.divider()

    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:
        if st.button("Proceed to Payment", use_container_width=True, type="primary"):
            with st.spinner("Creating order..."):
                # Create order
                order = api_client.create_order(
                    plan_id=plan['id'],
                    payment_method=payment_method,
                    notes=notes
                )

                if not order:
                    st.error("Failed to create order. Please check if the backend service is running and try again.")
                elif 'id' not in order:
                    st.error("Order created but missing ID. Please contact support.")
                elif 'order_number' not in order:
                    st.error("Order created but missing order number. Please contact support.")
                elif order and 'id' in order and 'order_number' in order:
                    # Create payment
                    payment = api_client.create_payment(
                        order_id=order['id'],
                        order_number=order['order_number'],
                        amount=int(float(plan['price'])),
                        item_name=plan['name'],
                        payment_method=payment_method
                    )

                    if payment and payment.get('success'):
                        # Store payment info in session
                        st.session_state['payment_data'] = payment
                        st.session_state['order'] = order
                        st.session_state['show_payment_form'] = True
                        st.rerun()
                    else:
                        st.error("Failed to create payment. Please try again.")


def show_payment_form():
    """Display ECPay payment form and auto-submit"""
    if 'payment_data' not in st.session_state or 'order' not in st.session_state:
        st.error("Payment data not found. Please try again.")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("← Back to Dashboard", use_container_width=True):
                st.session_state.pop('show_payment_form', None)
                st.session_state.pop('payment_data', None)
                st.session_state.pop('order', None)
                st.rerun()
        return

    payment = st.session_state['payment_data']
    order = st.session_state['order']

    st.markdown('<h1 class="main-header">🔄 Redirecting to Payment Gateway</h1>', unsafe_allow_html=True)

    # Add cancel button at the top
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("✕ Cancel", help="Cancel and return to dashboard"):
            st.session_state.pop('show_payment_form', None)
            st.session_state.pop('payment_data', None)
            st.session_state.pop('order', None)
            st.rerun()

    st.success(f"✅ Order #{order['order_number']} created successfully!")

    st.divider()

    st.subheader("📱 Proceed to Payment")
    st.write("Click the button below to open ECPay payment gateway in a new window.")
    st.info("💡 **Tip**: If the window doesn't open, please allow pop-ups for this site.")

    # Generate ECPay form that opens in new window
    form_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 20px;
            }}
            .payment-button {{
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 20px 50px;
                font-size: 18px;
                font-weight: bold;
                border-radius: 10px;
                cursor: pointer;
                margin: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.2);
                transition: all 0.3s;
            }}
            .payment-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 8px rgba(0,0,0,0.3);
            }}
            .info {{
                color: #666;
                margin-top: 20px;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <form id="ecpay_form" method="post" action="{payment['payment_url']}" target="_blank">
    """

    for key, value in payment['form_data'].items():
        form_html += f'<input type="hidden" name="{key}" value="{value}">\n'

    form_html += """
            <button type="submit" class="payment-button" onclick="showMessage()">
                💳 Open ECPay Payment Gateway
            </button>
        </form>
        <div class="info" id="message"></div>

        <script>
            function showMessage() {
                document.getElementById('message').innerHTML = '✅ Payment window opened! Please complete the payment in the new window.';
            }
        </script>
    </body>
    </html>
    """

    st.components.v1.html(form_html, height=200, scrolling=False)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Dashboard", use_container_width=True):
            st.session_state.pop('show_payment_form', None)
            st.session_state.pop('payment_data', None)
            st.session_state.pop('order', None)
            st.rerun()
    with col2:
        if st.button("🔄 Regenerate Payment Link", use_container_width=True):
            st.rerun()


def show_subscriptions_page():
    """Subscriptions management page"""
    st.markdown('<h1 class="main-header">💎 My Subscriptions</h1>', unsafe_allow_html=True)

    subscriptions = api_client.get_subscriptions()

    if not subscriptions:
        st.info("You don't have any subscriptions yet. Browse plans to get started!")

        if st.button("💎 Browse Plans", use_container_width=True, type="primary"):
            st.session_state['selected_page'] = 'Plans'
            st.rerun()
        return

    # Filter options
    col1, col2 = st.columns([3, 1])
    with col1:
        status_filter = st.selectbox(
            "Filter by status",
            options=["All", "Active", "Cancelled", "Expired"],
            index=0
        )

    # Filter subscriptions
    if status_filter != "All":
        filtered_subs = [s for s in subscriptions if s['status'] == status_filter.lower()]
    else:
        filtered_subs = subscriptions

    # Count active subscriptions
    active_subs = [s for s in subscriptions if s['status'] == 'active']

    # Display stats
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Total Subscriptions:** {len(filtered_subs)}")
    with col2:
        st.write(f"**Active Subscriptions:** {len(active_subs)}")

    st.divider()

    # Display subscriptions
    for sub in filtered_subs:
        with st.expander(f"💎 {sub['plan']['name']} - {sub['status'].upper()}", expanded=sub['status'] == 'active'):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Plan:** {sub['plan']['name']}")
                st.write(f"**Status:** {sub['status'].upper()}")
                st.write(f"**Price:** ${sub['plan']['price']}/{sub['plan']['billing_cycle']}")
                st.write(f"**Start Date:** {sub['start_date'][:10]}")
                if sub.get('end_date'):
                    st.write(f"**End Date:** {sub['end_date'][:10]}")

            with col2:
                if sub['plan'].get('description'):
                    st.write(f"**Description:**")
                    st.write(sub['plan']['description'])

                # Show features if available
                if sub['plan'].get('features'):
                    st.write(f"**Features:**")
                    for feature in sub['plan']['features']:
                        st.write(f"✓ {feature}")

            st.divider()

            # Action buttons
            if sub['status'] == 'active':
                col1, col2, col3 = st.columns([1, 1, 2])

                with col1:
                    if st.button("❌ Cancel Subscription", key=f"cancel_sub_page_{sub['id']}", use_container_width=True):
                        st.session_state[f'confirm_cancel_subscription_{sub["id"]}'] = True
                        st.rerun()

                # Confirmation dialog
                if st.session_state.get(f'confirm_cancel_subscription_{sub["id"]}'):
                    st.warning("⚠️ **Are you sure you want to cancel this subscription?**")
                    st.write("You will lose access to the plan benefits.")

                    ccol1, ccol2, ccol3 = st.columns([1, 1, 2])
                    with ccol1:
                        if st.button("✅ Yes, Cancel", key=f"confirm_yes_{sub['id']}", type="primary", use_container_width=True):
                            result = api_client.update_subscription_status(sub['id'], 'cancelled')
                            if result:
                                st.success("✅ Subscription cancelled successfully!")
                                st.session_state.pop(f'confirm_cancel_subscription_{sub["id"]}', None)
                                # Redirect to dashboard
                                st.session_state['selected_page'] = 'Dashboard'
                                import time
                                time.sleep(1)
                                st.rerun()
                    with ccol2:
                        if st.button("↩️ Keep Subscription", key=f"confirm_no_{sub['id']}", use_container_width=True):
                            st.session_state.pop(f'confirm_cancel_subscription_{sub["id"]}', None)
                            st.rerun()


def show_orders_page():
    """Orders management page"""
    st.markdown('<h1 class="main-header">📦 My Orders</h1>', unsafe_allow_html=True)

    orders = api_client.get_orders()

    if not orders:
        st.info("No orders yet. Browse plans to get started!")
        return

    # Filter options and bulk actions
    col1, col2 = st.columns([3, 1])
    with col1:
        status_filter = st.selectbox(
            "Filter by status",
            options=["All", "Pending", "Processing", "Completed", "Failed", "Cancelled"],
            index=0
        )

    # Filter orders
    if status_filter != "All":
        filtered_orders = [o for o in orders if o['status'] == status_filter.lower()]
    else:
        filtered_orders = orders

    # Count cancelled orders
    cancelled_orders = [o for o in orders if o['status'] == 'cancelled']

    # Display stats and bulk delete button
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.write(f"**Total Orders:** {len(filtered_orders)}")
    with col2:
        st.write(f"**Cancelled Orders:** {len(cancelled_orders)}")
    with col3:
        if len(cancelled_orders) > 0:
            if st.button("🗑️ Clear All", help="Delete all cancelled orders", type="secondary"):
                if st.session_state.get('confirm_bulk_delete'):
                    # Perform bulk delete
                    deleted_count = 0
                    for order in cancelled_orders:
                        if api_client.delete_order(order['id']):
                            deleted_count += 1
                    st.session_state.pop('confirm_bulk_delete', None)
                    st.success(f"✅ Successfully deleted {deleted_count} cancelled order(s)!")
                    st.rerun()
                else:
                    st.session_state['confirm_bulk_delete'] = True
                    st.warning(f"⚠️ This will delete {len(cancelled_orders)} cancelled order(s). Click again to confirm.")
                    st.rerun()

    st.divider()

    # Display orders
    for order in filtered_orders:
        with st.expander(f"Order #{order['order_number']} - {order['status'].upper()}", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Order Number:** {order['order_number']}")
                st.write(f"**Status:** {order['status'].upper()}")
                st.write(f"**Amount:** ${order['amount']}")
                st.write(f"**Created:** {order['created_at'][:16].replace('T', ' ')}")
                if order.get('payment_method'):
                    method_display = {
                        'credit_card': '💳 Credit Card',
                        'atm': '🏦 ATM Transfer',
                        'cvs': '🏪 Convenience Store',
                        'barcode': '📊 Barcode'
                    }
                    st.write(f"**Payment Method:** {method_display.get(order['payment_method'], order['payment_method'])}")

            with col2:
                if order.get('plan'):
                    st.write(f"**Plan:** {order['plan']['name']}")
                    st.write(f"**Plan Price:** ${order['plan']['price']}")
                    st.write(f"**Billing Cycle:** {order['plan']['billing_cycle']}")
                if order.get('notes'):
                    st.write(f"**Notes:** {order['notes']}")

            st.divider()

            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 3])

            with col1:
                if order['status'] == 'pending':
                    if st.button("💳 Pay Now", key=f"pay_order_page_{order['id']}", use_container_width=True):
                        if order.get('plan'):
                            payment = api_client.create_payment(
                                order_id=order['id'],
                                order_number=order['order_number'],
                                amount=int(float(order['amount'])),
                                item_name=order['plan']['name'],
                                payment_method=order.get('payment_method', 'credit_card')
                            )
                            if payment and payment.get('success'):
                                st.session_state['payment_data'] = payment
                                st.session_state['order'] = order
                                st.session_state['show_payment_form'] = True
                                st.rerun()

            with col2:
                if order['status'] in ['pending', 'processing', 'failed']:
                    if st.button("❌ Cancel", key=f"cancel_order_page_{order['id']}", use_container_width=True):
                        result = api_client.cancel_order(order['id'])
                        if result:
                            st.success("Order cancelled successfully!")
                            st.rerun()
                elif order['status'] == 'cancelled':
                    if st.button("🗑️ Delete", key=f"delete_order_page_{order['id']}", use_container_width=True, type="secondary"):
                        if st.session_state.get(f'confirm_delete_{order["id"]}'):
                            if api_client.delete_order(order['id']):
                                st.success("Order deleted successfully!")
                                st.session_state.pop(f'confirm_delete_{order["id"]}', None)
                                st.rerun()
                        else:
                            st.session_state[f'confirm_delete_{order["id"]}'] = True
                            st.warning("⚠️ Click Delete again to confirm")
                            st.rerun()


def show_invoices_page():
    """Invoices page"""
    st.markdown('<h1 class="main-header">📄 Invoices</h1>', unsafe_allow_html=True)

    invoices = api_client.get_invoices()

    if not invoices:
        st.info("No invoices yet")
        return

    for invoice in invoices:
        with st.expander(f"Invoice {invoice['invoice_number']} - ${invoice['total_amount']}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Invoice Number:** {invoice['invoice_number']}")
                st.write(f"**Amount:** ${invoice['amount']}")
                st.write(f"**Tax:** ${invoice['tax_amount']}")
                st.write(f"**Total:** ${invoice['total_amount']}")

            with col2:
                st.write(f"**Issued:** {invoice['issued_at'][:10]}")
                if invoice.get('paid_at'):
                    st.write(f"**Paid:** {invoice['paid_at'][:10]}")
                st.write(f"**Currency:** {invoice['currency']}")

            if invoice.get('pdf_url'):
                st.link_button("Download PDF", invoice['pdf_url'])


def show_payment_result():
    """Payment result page (shown after ECPay redirect) - No authentication required"""
    st.markdown('<h1 class="main-header">💳 Payment Result</h1>', unsafe_allow_html=True)

    # Get query parameters from URL
    query_params = st.query_params

    # Check authentication status once at the beginning
    is_logged_in = is_authenticated()

    # Check if we have payment result info
    if 'RtnCode' in query_params or 'status' in query_params:
        # ECPay returns with RtnCode parameter
        rtn_code = query_params.get('RtnCode', ['0'])[0] if isinstance(query_params.get('RtnCode', '0'), list) else query_params.get('RtnCode', '0')

        if rtn_code == '1':
            st.success("✅ Payment Successful!")
            st.balloons()

            st.write("Your payment has been processed successfully.")
            st.write("Thank you for your purchase!")

            # Show order details if available
            if 'MerchantTradeNo' in query_params:
                order_no = query_params.get('MerchantTradeNo', [''])[0] if isinstance(query_params.get('MerchantTradeNo', ''), list) else query_params.get('MerchantTradeNo', '')
                st.info(f"📦 Order Number: {order_no}")

            st.divider()

            # Check authentication status
            if is_logged_in:
                # User is authenticated, auto-redirect to dashboard
                st.success("🎉 You're logged in! Redirecting to your dashboard...")

                placeholder = st.empty()

                import time
                for seconds in range(3, 0, -1):
                    placeholder.info(f"⏱️ Redirecting to Dashboard in {seconds} second{'s' if seconds > 1 else ''}...")
                    time.sleep(1)

                placeholder.success("✨ Redirecting now...")
                st.query_params.clear()
                time.sleep(0.5)
                st.rerun()
            else:
                # User not authenticated, show login prompt (and skip bottom section)
                st.warning("⚠️ Please login to view your order details and access your dashboard.")
                st.info("💡 Your payment was successful and your order has been recorded.")

                # Show inline login form for convenience
                st.divider()
                st.subheader("🔐 Quick Login")

                with st.form("quick_login_form"):
                    email = st.text_input("Email", placeholder="your@email.com")
                    password = st.text_input("Password", type="password")
                    submit = st.form_submit_button("Login & View Dashboard", use_container_width=True, type="primary")

                    if submit:
                        if not email or not password:
                            st.error("Please fill in all fields")
                        else:
                            with st.spinner("Logging in..."):
                                result = api_client.login(email, password)
                                if result:
                                    st.success("✅ Login successful! Redirecting to dashboard...")
                                    st.query_params.clear()
                                    import time
                                    time.sleep(0.5)
                                    st.rerun()
                return  # Exit early, don't show bottom navigation section
        else:
            st.error("❌ Payment Failed")
            st.write("Unfortunately, your payment could not be processed.")

            # Show error message if available
            if 'RtnMsg' in query_params:
                rtn_msg = query_params.get('RtnMsg', [''])[0] if isinstance(query_params.get('RtnMsg', ''), list) else query_params.get('RtnMsg', '')
                st.warning(f"Error: {rtn_msg}")
    else:
        # Generic payment result page
        st.info("🔄 Payment completed!")
        st.write("Your payment has been processed.")
        st.write("Please login to check your orders and subscription status.")

    st.divider()

    # Show navigation buttons or login prompt
    if is_logged_in:
        # Show navigation buttons for authenticated users
        st.subheader("📍 What's Next?")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("📦 View Orders", key="view_orders_nav", use_container_width=True):
                st.query_params.clear()
                st.session_state['selected_page'] = 'Orders'
                st.rerun()
        with col2:
            if st.button("🏠 Dashboard", key="dashboard_nav", use_container_width=True):
                st.query_params.clear()
                st.rerun()
        with col3:
            if st.button("💎 Browse Plans", key="browse_plans_nav", use_container_width=True):
                st.query_params.clear()
                st.session_state['selected_page'] = 'Plans'
                st.rerun()
    else:
        # Show login prompt for non-authenticated users
        st.warning("⚠️ Your session may have expired. Please login to view your order details.")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔐 Login to Continue", key="login_session_expired", use_container_width=True, type="primary"):
                st.query_params.clear()
                st.rerun()


def show_landing_page():
    """
    Landing page for non-authenticated users.
    Shows demo with login/register options.
    Layout like douhuiai.com - NO language buttons at top
    """
    # Initialize landing page state
    if 'landing_view' not in st.session_state:
        st.session_state['landing_view'] = 'demo'

    # Initialize language in session state
    if 'lang' not in st.session_state:
        st.session_state['lang'] = 'en'

    # Language options for dropdown
    languages = {
        "en": "🇺🇸 English",
        "zh-TW": "🇹🇼 繁體中文",
        "ja": "🇯🇵 日本語",
        "ko": "🇰🇷 한국어",
        "es": "🇪🇸 Español",
    }

    # Show selected view
    if st.session_state['landing_view'] == 'demo':
        show_demo_page(api_client)

    elif st.session_state['landing_view'] == 'login':
        show_login_form()

    elif st.session_state['landing_view'] == 'register':
        show_register_form()

    elif st.session_state['landing_view'] == 'forgot_password':
        show_forgot_password_form()

    elif st.session_state['landing_view'] == 'reset_password':
        show_reset_password_form()

    elif st.session_state['landing_view'] == 'plans':
        show_public_plans_page()


def show_login_form():
    """Show login form for landing page"""
    st.markdown('<h1 class="main-header">🔐 Login</h1>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Show success message if redirected from registration
        if 'registration_success' in st.session_state and st.session_state['registration_success']:
            st.success("✅ Registration successful! Please check your email to verify your account before logging in.")
            del st.session_state['registration_success']

        # Show email verified message
        if 'email_verified' in st.session_state and st.session_state['email_verified']:
            st.success("✅ Email verified successfully! You can now log in.")
            del st.session_state['email_verified']

        with st.form("landing_login_form"):
            st.subheader("Login to your account")
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True, type="primary")

            if submit:
                if not email or not password:
                    st.error("Please fill in all fields")
                else:
                    with st.spinner("Logging in..."):
                        result = api_client.login(email, password)
                        if result:
                            st.success("✅ Login successful!")
                            import time
                            time.sleep(0.5)
                            st.rerun()

        # Forgot password link
        st.markdown("---")
        if st.button("Forgot Password?", use_container_width=True, type="secondary"):
            st.session_state['landing_view'] = 'forgot_password'
            st.rerun()

        st.markdown("---")
        st.markdown("Don't have an account?")
        if st.button("Create Account", use_container_width=True):
            st.session_state['landing_view'] = 'register'
            st.rerun()


def show_register_form():
    """Show registration form for landing page"""
    st.markdown('<h1 class="main-header">📝 Create Account</h1>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.form("landing_register_form"):
            st.subheader("Join VidGo today")
            username = st.text_input("Username", placeholder="Choose a username")
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password", help="At least 8 characters")
            password_confirm = st.text_input("Confirm Password", type="password")

            terms = st.checkbox("I agree to the Terms of Service and Privacy Policy")

            submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")

            if submit:
                if not all([username, email, password, password_confirm]):
                    st.error("Please fill in all fields")
                elif password != password_confirm:
                    st.error("Passwords don't match")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters")
                elif not terms:
                    st.error("Please agree to the Terms of Service")
                else:
                    with st.spinner("Creating account..."):
                        result = api_client.register(username, email, password)
                        if result:
                            st.success("✅ Account created successfully!")
                            st.session_state['registration_success'] = True
                            st.session_state['landing_view'] = 'login'
                            import time
                            time.sleep(1)
                            st.rerun()

        st.markdown("---")
        st.markdown("Already have an account?")
        if st.button("Login", use_container_width=True, key="go_to_login"):
            st.session_state['landing_view'] = 'login'
            st.rerun()


def show_forgot_password_form():
    """Show forgot password form"""
    st.markdown('<h1 class="main-header">🔑 Forgot Password</h1>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.write("Enter your email address and we'll send you a link to reset your password.")

        with st.form("forgot_password_form"):
            email = st.text_input("Email", placeholder="your@email.com")
            submit = st.form_submit_button("Send Reset Link", use_container_width=True, type="primary")

            if submit:
                if not email:
                    st.error("Please enter your email address")
                else:
                    with st.spinner("Sending reset link..."):
                        result = api_client.forgot_password(email)
                        if result:
                            st.success("📧 If an account with this email exists, a password reset link has been sent.")
                            st.info("Please check your inbox and spam folder.")

        st.markdown("---")
        if st.button("← Back to Login", use_container_width=True):
            st.session_state['landing_view'] = 'login'
            st.rerun()


def show_reset_password_form():
    """Show reset password form (accessed via email link)"""
    st.markdown('<h1 class="main-header">🔐 Reset Password</h1>', unsafe_allow_html=True)

    # Get token from query params
    query_params = st.query_params
    token = query_params.get('reset_password', '')

    if not token:
        st.error("Invalid or missing reset token. Please request a new password reset.")
        if st.button("← Back to Login", use_container_width=True):
            st.session_state['landing_view'] = 'login'
            st.query_params.clear()
            st.rerun()
        return

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.form("reset_password_form"):
            st.subheader("Enter your new password")
            new_password = st.text_input("New Password", type="password", help="At least 8 characters")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Reset Password", use_container_width=True, type="primary")

            if submit:
                if not new_password or not confirm_password:
                    st.error("Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("Passwords don't match")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    with st.spinner("Resetting password..."):
                        result = api_client.reset_password(token, new_password)
                        if result:
                            st.success("✅ Password reset successfully! You can now log in with your new password.")
                            st.query_params.clear()
                            import time
                            time.sleep(2)
                            st.session_state['landing_view'] = 'login'
                            st.rerun()


def show_public_plans_page():
    """Show plans page for non-authenticated users"""
    st.markdown('<h1 class="main-header">💎 Choose Your Plan</h1>', unsafe_allow_html=True)

    plans = api_client.get_plans()

    if not plans:
        st.info("Plans loading...")
        return

    # Display plans in columns
    num_cols = min(len(plans), 4)
    cols = st.columns(num_cols)

    for idx, plan in enumerate(plans):
        with cols[idx % num_cols]:
            with st.container():
                # Featured badge
                if plan.get('is_featured'):
                    st.markdown('<span class="popular-badge">⭐ RECOMMENDED</span>', unsafe_allow_html=True)

                st.markdown(f"### {plan['name']}")

                # Pricing
                if plan['price_monthly'] == 0:
                    st.markdown("## Free")
                else:
                    st.markdown(f"## ${plan['price_monthly']}/mo")
                    st.caption(f"or ${plan['price_yearly']}/year")

                st.markdown(f"*{plan.get('description', '')}*")

                st.markdown("---")

                # Features
                st.markdown(f"✓ {plan['credits_per_month']} credits/month")
                st.markdown(f"✓ Max {plan['max_video_length']}s videos")
                st.markdown(f"✓ {plan['max_resolution']} resolution")

                if not plan.get('watermark'):
                    st.markdown("✓ No watermark")
                if plan.get('priority_queue'):
                    st.markdown("✓ Priority queue")
                if plan.get('api_access'):
                    st.markdown("✓ API access")

                # Feature flags
                if plan.get('feature_clothing_transform'):
                    st.markdown("✓ AI Clothing Transform")
                if plan.get('feature_goenhance'):
                    st.markdown("✓ Special Effects")
                if plan.get('feature_video_gen'):
                    st.markdown("✓ Video Generation")
                if plan.get('feature_batch_processing'):
                    st.markdown("✓ Batch Processing")

                st.markdown("---")

                if st.button("Get Started", key=f"plan_pub_{plan['id']}", use_container_width=True, type="primary" if plan.get('is_featured') else "secondary"):
                    st.session_state['landing_view'] = 'register'
                    st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("← Back to Demo", use_container_width=True):
        st.session_state['landing_view'] = 'demo'
        st.rerun()


def main():
    """Main application"""
    # Check query params for special actions
    query_params = st.query_params

    # Handle email verification
    if 'verify_email' in query_params:
        token = query_params.get('verify_email', '')
        if token:
            with st.spinner("Verifying email..."):
                result = api_client.verify_email(token)
                if result:
                    st.session_state['email_verified'] = True
                st.query_params.clear()
                st.session_state['landing_view'] = 'login'
                st.rerun()

    # Handle password reset (redirect to reset form)
    if 'reset_password' in query_params:
        st.session_state['landing_view'] = 'reset_password'
        # Don't clear params - the form needs the token

    # Check if we're on the payment result page (from ECPay redirect)
    if 'page' in query_params or 'RtnCode' in query_params or 'MerchantTradeNo' in query_params:
        show_payment_result()
        return

    # Check if user is authenticated
    if not is_authenticated():
        # Show landing page with demo and login options
        show_landing_page()
        return

    # Check if we need to show payment form (hide sidebar for payment page)
    if 'show_payment_form' in st.session_state and st.session_state['show_payment_form']:
        show_payment_form()
        return

    # Sidebar navigation for authenticated users
    with st.sidebar:
        user = get_current_user()
        st.write(f"👤 **{user['username']}**")
        st.write(f"📧 {user['email']}")
        st.divider()

        # Check if there's a selected page from session state
        default_idx = 0
        if 'selected_page' in st.session_state:
            options = ["Demo", "Dashboard", "Plans", "Subscriptions", "Orders", "Invoices", "Settings"]
            if st.session_state['selected_page'] in options:
                default_idx = options.index(st.session_state['selected_page'])
            st.session_state.pop('selected_page', None)

        selected = option_menu(
            menu_title="Navigation",
            options=["Demo", "Dashboard", "Plans", "Subscriptions", "Orders", "Invoices", "Settings"],
            icons=["play-circle", "speedometer2", "gem", "star", "box-seam", "file-text", "gear"],
            default_index=default_idx,
        )

        st.divider()

        if st.button("Logout", use_container_width=True):
            api_client.logout()
            st.rerun()

    # Clear checkout page state when navigating via sidebar
    if 'page' in st.session_state and st.session_state['page'] == 'checkout':
        # If user navigates away using sidebar, clear the checkout state
        if 'last_selected' in st.session_state and st.session_state['last_selected'] != selected:
            st.session_state.pop('page', None)
            st.session_state.pop('selected_plan', None)
        st.session_state['last_selected'] = selected

    # Show selected page
    if 'page' in st.session_state and st.session_state['page'] == 'checkout':
        show_checkout_page()
    elif selected == "Demo":
        show_demo_page(api_client)
    elif selected == "Dashboard":
        show_dashboard()
    elif selected == "Plans":
        show_plans_page()
    elif selected == "Subscriptions":
        show_subscriptions_page()
    elif selected == "Orders":
        show_orders_page()
    elif selected == "Invoices":
        show_invoices_page()
    elif selected == "Settings":
        st.markdown('<h1 class="main-header">⚙️ Settings</h1>', unsafe_allow_html=True)

        user = get_current_user()

        # Account Information Section
        st.subheader("👤 Account Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Username:** {user['username']}")
            st.write(f"**Email:** {user['email']}")
        with col2:
            if user.get('first_name') or user.get('last_name'):
                st.write(f"**Name:** {user.get('first_name', '')} {user.get('last_name', '')}")
            st.write(f"**Account Created:** {user['created_at'][:10]}")

        st.divider()

        # Account Actions Section
        st.subheader("🔧 Account Actions")

        # Change Password
        with st.expander("🔑 Change Password", expanded=False):
            with st.form("change_password_form"):
                old_password = st.text_input("Current Password", type="password")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")
                submit = st.form_submit_button("Change Password")

                if submit:
                    if not old_password or not new_password:
                        st.error("All fields are required")
                    elif new_password != confirm_password:
                        st.error("New passwords don't match")
                    else:
                        st.info("Password change functionality coming soon!")

        st.divider()

        # Danger Zone
        st.subheader("⚠️ Danger Zone")

        with st.expander("🗑️ Delete Account", expanded=False):
            st.warning("**Warning:** This action cannot be undone. All your data will be permanently deleted.")

            # Check for active subscriptions
            subscriptions = api_client.get_subscriptions()
            active_subs = [s for s in subscriptions if s['status'] == 'active']

            if active_subs:
                st.error(f"❌ You have {len(active_subs)} active subscription(s). Please cancel them before deleting your account.")
                st.write("**Active Subscriptions:**")
                for sub in active_subs:
                    st.write(f"- {sub['plan']['name']} ({sub['status'].upper()})")
            else:
                st.write("**Requirements:**")
                st.write("- ✅ No active subscriptions")
                st.write("- Enter your password to confirm deletion")

                with st.form("delete_account_form"):
                    st.write("**Please confirm account deletion:**")
                    confirm_email = st.text_input("Enter your email to confirm", placeholder=user['email'])
                    password = st.text_input("Enter your password", type="password")
                    confirm_delete = st.checkbox("I understand this action cannot be undone")

                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col2:
                        submit_delete = st.form_submit_button("🗑️ Delete My Account", type="primary", use_container_width=True)

                    if submit_delete:
                        if not confirm_delete:
                            st.error("Please confirm that you understand this action cannot be undone")
                        elif confirm_email != user['email']:
                            st.error("Email doesn't match. Please enter your email correctly.")
                        elif not password:
                            st.error("Password is required")
                        else:
                            # Attempt to delete account
                            if api_client.delete_account(password):
                                st.success("✅ Account deleted successfully. Redirecting...")
                                # Clear session and redirect
                                import time
                                time.sleep(2)
                                st.session_state.clear()
                                st.rerun()
                            # Error message already shown by api_client


if __name__ == "__main__":
    main()
