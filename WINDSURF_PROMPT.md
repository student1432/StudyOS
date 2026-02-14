# Windsurf Implementation Prompt: Institution Payment Flow

Copy and paste the following prompt into Windsurf to implement the paid institution setup:

---

**Task: Implement Stripe Payment Requirement for Institution Setup**

**Context:**
Currently, Sclera allows anyone to sign up as an Institution Admin for free. We need to gate the Institutional Dashboard behind a payment requirement.

**Required Changes:**

1.  **Backend (`app.py`):**
    *   Modify `signup_admin` to set the new institution's `status` to `'pending_payment'` and `plan` to `'Premium'`.
    *   Create a new route `@app.route('/institution/checkout')` that renders a checkout page.
    *   Implement `@app.route('/api/create-checkout-session', methods=['POST'])` to integrate with the Stripe API.
    *   Implement `@app.route('/institution/payment-success')` to handle the return from Stripe. This route should update the Firestore `institutions` collection, setting the status to `'active'` and recording the payment details.
    *   Update the `institution_admin_dashboard` route to check if the `admin_profile`'s institution status is `'active'`. If it's `'pending_payment'`, redirect to `/institution/checkout`.

2.  **Configuration (`config.py` & `.env`):**
    *   Add placeholders for `STRIPE_PUBLIC_KEY` and `STRIPE_SECRET_KEY`.

3.  **Frontend:**
    *   Create `templates/institution_checkout.html` using the existing "Dark Academic" CSS. It should clearly display the subscription price and have a "Pay Now" button.
    *   Create a simple `templates/payment_success.html` with a success animation and a button to "Go to Dashboard".

4.  **Security:**
    *   Ensure the payment success route validates the Stripe session ID before updating the database.

**Instructions:**
Please use `app.py` as the primary file for route implementation. Refer to `static/styles.css` for consistent styling. Use the `db` (Firestore) instance already initialized in the project.

---
