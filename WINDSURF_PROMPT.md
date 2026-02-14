# Master Implementation Prompt: Paid Institution Tiers

Use this prompt in Windsurf for an automated, high-fidelity implementation of the payment gateway.

---

**Task: Implement Stripe Gateway for Institutional Onboarding**

**Objective:**
Convert the current free institution setup into a paid subscription flow. Gating the `institution_admin_dashboard` behind a Stripe payment.

**Exact Implementation Steps:**

1.  **Dependency Addition:**
    *   Add `stripe` to `requirements.txt`.

2.  **Configuration Overhaul:**
    *   In `config.py`, add `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, and `STRIPE_PRICE_ID` to the `Config` class.
    *   Add placeholders for these in `.env`.

3.  **Routing & Logic (`app.py`):**
    *   **Signup Logic:** Update `@app.route('/signup/admin')`. When a new institution is created, set its `status` to `'pending_payment'` in the `institutions` collection.
    *   **Checkout Route:** Create `@app.route('/institution/checkout')`. This should render a new template `institution_checkout.html`. Pass `config.STRIPE_PUBLIC_KEY` to the template.
    *   **Session API:** Create `@app.route('/api/create-checkout-session', methods=['POST'])`.
        *   It must use `stripe.checkout.Session.create`.
        *   Include `metadata={'institution_id': institution_id}`.
        *   Set `success_url` to redirect to `/institution/payment-success?session_id={CHECKOUT_SESSION_ID}`.
    *   **Success Handler:** Create `@app.route('/institution/payment-success')`.
        *   Retrieve the session using `stripe.checkout.Session.retrieve(request.args.get('session_id'))`.
        *   If `payment_status == 'paid'`, update the Firestore document for that `institution_id`: set `status` to `'active'`, `plan` to `'Pro'`, and store the `subscription_id`.
    *   **Middleware Enforcement:** In `@app.route('/institution/admin/dashboard')`, fetch the institution document. If `status != 'active'`, redirect the user to `url_for('institution_checkout')`.

4.  **Template Creation:**
    *   **`templates/institution_checkout.html`**:
        *   Use the "Dark Academic" shell (`_admin_sidebar.html`).
        *   Add a "Pricing" section showing $29/month (or your choice).
        *   Include a `<button id="checkout-button">Pay with Stripe</button>`.
        *   Implement the JavaScript to handle the click: fetch `/api/create-checkout-session` and then use `stripe.redirectToCheckout({ sessionId: data.id })`.
    *   **`templates/payment_success.html`**:
        *   Show a professional success message.
        *   Add a script: `setTimeout(() => { window.location.href = "/institution/admin/dashboard"; }, 5000);`.

**Constraints:**
*   Maintain the current "Dark Academic" aesthetic (Black/Dark Gray theme with sharp borders).
*   Use `flash()` messages for payment status feedback.
*   Ensure the `require_admin_v2` decorator is applied to all new payment routes.

**Database References:**
*   Collection: `institutions`
*   Status Field: `status` (values: `'pending_payment'`, `'active'`)
*   Plan Field: `plan` (values: `'Pro'`)

---
