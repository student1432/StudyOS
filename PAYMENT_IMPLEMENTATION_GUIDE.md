# Deep Dive: Implementing Payment for Institution Setup

This guide provides the exact technical steps and code logic required to transition the Sclera Institutional Module to a paid subscription model using Stripe.

---

## 1. Environment & Config Setup
Add the following to your `.env` file:
```env
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRICE_ID=price_... # Monthly or Setup fee ID
```

Update `config.py` to include these variables:
```python
class Config:
    # ... existing config ...
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID')
```

## 2. Database Schema Shift
Modify the `signup_admin` function in `app.py`. We must ensure the institution is created in a "Locked" state.

**File: `app.py`**
```python
# Inside signup_admin POST handler
db.collection(INSTITUTIONS_COL).document(institution_id).set({
    'name': institution_name,
    'created_at': now,
    'created_by': uid,
    'status': 'pending_payment', # Changed from 'active'
    'plan': 'Premium_Pending'
})
```

## 3. The Stripe Integration Logic
Install the dependency: `pip install stripe`.

### A. Create Checkout Session
Create a new endpoint to initiate the payment.

```python
import stripe
stripe.api_key = app.config['STRIPE_SECRET_KEY']

@app.route('/api/create-checkout-session', methods=['POST'])
@require_admin_v2
def create_checkout_session():
    uid = session.get('uid')
    admin_profile = _get_admin_profile(uid)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': app.config['STRIPE_PRICE_ID'],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('institution_checkout', _external=True),
            metadata={
                'institution_id': admin_profile.get('institution_id'),
                'admin_uid': uid
            }
        )
        return jsonify({'id': checkout_session.id})
    except Exception as e:
        return jsonify(error=str(e)), 403
```

### B. Success Handling & Activation
Implement the success route. **Note:** In production, use Webhooks for reliability. This example uses the Redirect Success URL for simplicity.

```python
@app.route('/institution/payment-success')
@require_admin_v2
def payment_success():
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('institution_checkout'))

    # Verify the session with Stripe
    stripe_session = stripe.checkout.Session.retrieve(session_id)
    institution_id = stripe_session.metadata.get('institution_id')

    if stripe_session.payment_status == 'paid':
        # Activate the Institution
        db.collection(INSTITUTIONS_COL).document(institution_id).update({
            'status': 'active',
            'plan': 'Pro',
            'subscription_id': stripe_session.subscription,
            'activated_at': datetime.utcnow().isoformat()
        })
        flash('Payment successful! Your institution is now active.', 'success')
        return render_template('payment_success.html')

    return redirect(url_for('institution_checkout'))
```

## 4. Middleware: The Gatekeeper
Update the `institution_admin_dashboard` to prevent access to unpaid accounts.

```python
@app.route('/institution/admin/dashboard')
@require_admin_v2
def institution_admin_dashboard():
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')

    # Check activation status
    inst_doc = db.collection(INSTITUTIONS_COL).document(institution_id).get()
    inst_data = inst_doc.to_dict() if inst_doc.exists else {}

    if inst_data.get('status') == 'pending_payment':
        return redirect(url_for('institution_checkout'))

    # ... rest of the existing dashboard logic ...
```

## 5. User Interface requirements
*   **Checkout Page (`institution_checkout.html`):** Must include the Stripe.js library and a script to call the `/api/create-checkout-session` endpoint when the "Pay Now" button is clicked.
*   **Success Page (`payment_success.html`):** Use a meta-refresh tag to redirect the user to the dashboard after 5 seconds: `<meta http-equiv="refresh" content="5;url=/institution/admin/dashboard">`.

---

## Technical Summary of Steps
1.  **Status Lock:** Ensure `status` is `pending_payment` on signup.
2.  **Session Creation:** Use Stripe API to create a secure checkout.
3.  **Metadata Passing:** Pass `institution_id` in Stripe metadata to link the payment back to the user.
4.  **Enforcement:** Redirect any `pending_payment` admin to the checkout page.
5.  **Atomic Update:** Update the Firestore document only after verifying the Stripe session status.
