# Comprehensive Testing Guide: Institutional Payment

Follow these exact steps to verify the robustness of your new payment implementation.

---

## 🛠 Setup for Testing
1.  **Stripe Keys:** Ensure you are using `sk_test_...` and `pk_test_...`.
2.  **Price ID:** Create a "Product" in your Stripe Dashboard (Test Mode) and copy the Price ID into your `.env`.

---

## 🧪 Test Suite

### 1. The "Gatekeeper" Test
*   **Action:** Create a new Admin account at `/signup/admin`.
*   **Verification:**
    *   [ ] After registration, are you immediately on `/institution/checkout`?
    *   [ ] Try to manually type `/institution/admin/dashboard` in the URL bar. Do you get redirected back to checkout?
    *   [ ] In Firestore, does the institution have `status: "pending_payment"`?

### 2. The "Stripe Handshake" Test
*   **Action:** Click the "Pay Now" button on the checkout page.
*   **Verification:**
    *   [ ] Does the browser redirect to `checkout.stripe.com`?
    *   [ ] Inspect the network tab for the POST to `/api/create-checkout-session`. Does it return a JSON object with a session ID?

### 3. The "Test Card" Success Test
*   **Action:** Use card `4242 4242 4242 4242`, any expiry in future, and any CVC.
*   **Verification:**
    *   [ ] After clicking "Pay", are you redirected to Sclera's `/institution/payment-success` page?
    *   [ ] Does the success page show a countdown or redirect you to the dashboard within 5-10 seconds?
    *   [ ] **Database check:** Does the institution now have `status: "active"`, `plan: "Pro"`, and a `subscription_id`?

### 4. The "Payment Cancelled" Test
*   **Action:** Start the checkout process, then click the "Back" arrow on the Stripe page.
*   **Verification:**
    *   [ ] Are you returned to Sclera's checkout page?
    *   [ ] Is the institution status still `pending_payment`?
    *   [ ] Try to access the dashboard again—ensure it's still locked.

### 5. The "Metadata Security" Test
*   **Action:** Verify that the `institution_id` in Stripe Metadata matches the ID in your Firestore.
*   **Verification:**
    *   [ ] Check the Stripe Dashboard -> Payments -> [Click Payment] -> Metadata section. It should contain the correct `institution_id`.

---

## 🚩 Common Failure Points to Watch For:
1.  **Missing `require_admin_v2`:** If you forget this, a student might accidentally access the checkout session API.
2.  **Wrong `success_url`:** Ensure the `success_url` in your Python code includes the `{CHECKOUT_SESSION_ID}` template tag.
3.  **Firestore Permissions:** Ensure your Firestore rules allow the Admin to update their own Institution record after payment (or perform the update server-side).
