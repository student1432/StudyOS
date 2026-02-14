# Guide: Implementing Payment for Institution Setup

This guide outlines the steps required to transition the Sclera Institutional Module from a free signup to a paid subscription model.

## 1. Modify the Admin Signup Flow
In `app.py`, update the `signup_admin` function to set the initial status to `pending_payment` instead of `active`.

**Current State:**
```python
db.collection(INSTITUTIONS_COL).document(institution_id).set({
    'status': 'active',
    'plan': 'Free'
})
```

**Recommended Change:**
```python
db.collection(INSTITUTIONS_COL).document(institution_id).set({
    'status': 'pending_payment',
    'plan': 'Premium_Pending'
})
```

## 2. Implement a Payment Gateway (e.g., Stripe)
1.  **Add Dependencies:** Add `stripe` to `requirements.txt`.
2.  **Configuration:** Add `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` to `.env` and `config.py`.
3.  **Create Checkout Route:** Implement a new route `/institution/checkout` that creates a Stripe Checkout Session.

## 3. Create the Payment Success Handler
Implement a webhook or a success redirect route (e.g., `/institution/payment-success`) that:
1.  Verifies the payment status.
2.  Retrieves the `institution_id` from the session or payment metadata.
3.  Updates the Firestore document:
    *   Set `status` to `active`.
    *   Set `plan` to `Pro` or `Premium`.
    *   Record `payment_id` and `expiry_date`.

## 4. Protect Admin Routes
Update the `require_admin_v2` decorator or add a check in `institution_admin_dashboard` to redirect users with `pending_payment` status back to the checkout page.

```python
if profile.get('status') == 'pending_payment':
    return redirect(url_for('institution_checkout'))
```

## 5. UI Updates
1.  **Signup Page:** Inform the user that a setup fee/subscription is required.
2.  **Checkout Page:** A clean page showing the plan details and a "Pay Now" button.
3.  **Success Page:** A professional confirmation page that redirects to the dashboard after 5 seconds.

## 6. Business Logic Considerations
*   **Trial Period:** Decide if you want to offer a 7-day trial before requiring payment.
*   **Pricing Tiers:** Implement different prices based on the number of students or teachers.
*   **Invoicing:** Ensure the system generates a receipt/invoice for the institution's records.
