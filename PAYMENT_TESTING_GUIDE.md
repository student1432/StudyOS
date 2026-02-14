# Testing Guide: Institution Payment Integration

This guide provides the steps to verify the payment gateway integration for the Sclera Institutional Module.

## Prerequisites
1.  **Stripe Test Mode:** Ensure your Stripe API keys are in "Test Mode".
2.  **Test Account:** Use a fresh email address for each signup test.

## Test Scenario 1: New Admin Signup & Payment Redirection
1.  Navigate to `/signup/admin`.
2.  Fill out the form and click "Register".
3.  **Expected Result:** You should be redirected to the `/institution/checkout` page (or directly to Stripe Checkout).
4.  **Database Check:** Open Firestore and verify that the new institution document has `status: "pending_payment"`.

## Test Scenario 2: Accessing Dashboard Without Payment
1.  While in the `pending_payment` state, try to navigate directly to `/institution/admin/dashboard`.
2.  **Expected Result:** The system should automatically redirect you back to the checkout page.

## Test Scenario 3: Successful Payment
1.  On the Stripe Checkout page, use a test card (e.g., `4242 4242 4242 4242`).
2.  Complete the payment.
3.  **Expected Result:** You should be redirected to `/institution/payment-success` and then to the Admin Dashboard.
4.  **Database Check:**
    *   The institution's `status` should now be `"active"`.
    *   The `plan` should be `"Premium"`.
    *   A `payment_id` should be recorded.

## Test Scenario 4: Failed/Cancelled Payment
1.  On the Stripe Checkout page, click the "Back" or "Cancel" button.
2.  **Expected Result:** You should be returned to the Sclera checkout page with an information message (e.g., "Payment cancelled. Please try again to activate your account.").
3.  **Access Check:** Verify that you still cannot access the Admin Dashboard.

## Test Scenario 5: Session Persistence
1.  Log out and log back in as the Admin who just paid.
2.  **Expected Result:** You should be taken directly to the Admin Dashboard without seeing the checkout page again.

## Tools for Verification
*   **Stripe Dashboard:** Check the "Payments" tab to see successful and failed transactions.
*   **Firestore Console:** Monitor real-time updates to the `institutions` and `institution_admins` collections.
*   **Browser Network Tab:** Verify that the API calls to `/api/create-checkout-session` are returning `200 OK` with a valid URL.
