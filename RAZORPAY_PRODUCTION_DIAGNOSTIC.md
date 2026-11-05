# Razorpay Production Diagnostic

## Root cause

**CONFIRMED ISSUE** — The production Compose service does not pass the Razorpay credentials into the backend container. The backend reads `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`, but `docker-compose.prod.yml` originally omitted both. Its environment mapping is explicit, so having credentials in the shell, in a developer's `backend/.env`, or in Jenkins does not make them available in the running production container.

The request fails in `_razorpay_configured()` at `backend/portal_api.py:45-50`. If either variable is absent or empty, that helper raises HTTP 503 with the exact response in the report. Order creation checks configuration at `backend/portal_api.py:2749-2761`; no request is made to Razorpay in this failure path.

## Framework and configuration path

**CONFIRMED ISSUE** — Backend is a Python 3.12 FastAPI modular monolith, built as one backend image (`backend/Dockerfile`) with routers split by domain. The endpoint is registered by `backend/portal_api.py` under `/api/portal` and is called as `POST /api/portal/student/fees/razorpay/order`.

**CONFIRMED ISSUE** — `backend/main.py:18` imports `load_dotenv`, and `backend/main.py:54` calls it before serving the application. This loads a local `backend/.env` when present. Local `docker-compose.yml:3-4` explicitly passes `./backend/.env` with `env_file`, which explains why local Compose can work.

**CONFIRMED ISSUE** — `docker-compose.prod.yml` specifies backend variables individually and did not include the two Razorpay variables. Jenkins deploys using that Compose file (`Jenkinsfile`, deployment stage); it neither copies `backend/.env` nor adds Razorpay credentials to the container. `backend/.env` exists locally and contains nonempty values for both expected variable names; secret values were not read into this report. It is gitignored. No `.env.example` existed before this change.

## Configuration findings

- **CONFIRMED ISSUE** — Required variable names are `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`; they are read directly by `backend/portal_api.py:46-47`.
- **CONFIRMED ISSUE** — Production must inject both variables into the backend container. Added explicit variable mappings to `docker-compose.prod.yml`.
- **NOT AN ISSUE** — No alternate Razorpay flag such as `PAYMENTS_ENABLED` gates these routes in the code. `ICMS_ENVIRONMENT=production` does not disable payments.
- **NOT AN ISSUE** — The local Compose service passes `backend/.env`; the backend also calls `load_dotenv()`. A bare local process can therefore use that file, while production Compose needs its own injection.
- **POSSIBLE ISSUE** — Whether the live EC2 host has values named `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `/opt/icms/.env` cannot be inspected from this repository. Confirm them on the host without printing values. The reported 503 confirms at least one variable is missing or empty inside the serving process at request time.
- **POSSIBLE ISSUE** — Test versus live mode cannot be inferred from presence. Ensure the key ID and secret are a matching pair for the intended Razorpay account/mode. Both test and live credentials use the same variable names.
- **NOT AN ISSUE** — The Dockerfile does not bake credentials into the image, which is correct. `python-dotenv` is installed, and no missing Razorpay SDK dependency exists because the backend uses Python standard-library HTTP and HMAC.

## Payment flow review

1. **CONFIRMED ISSUE** — `frontend/src/personas/StudentViews.tsx:2686-2700` validates the user-entered amount, requests an order, loads Razorpay Checkout JS, and opens the checkout using the returned public `key_id` and `order_id`. The API wrapper is `frontend/src/api.ts:916-917`.
2. **NOT AN ISSUE** — Student order validation checks invoice ownership and outstanding balance (`backend/portal_api.py:2749-2758`). Amount is interpreted as rupees, 18% GST is added, and the total is converted to integer paise (`:2756-2759`). Currency is INR.
3. **NOT AN ISSUE** — The Razorpay order ID is stored in `RazorpayOrder` after the remote order is created (`backend/portal_api.py:2760-2762`, model `backend/domain_models.py:1600-1611`). The database column is unique.
4. **NOT AN ISSUE** — Student verification scopes the order to invoice and authenticated student, checks the HMAC SHA-256 signature with the server secret using constant-time comparison, then records and allocates the payment (`backend/portal_api.py:2770-2792`). Already-paid orders return early. Invoice allocation is idempotent via `PaymentAllocation` (`backend/portal_api.py:133-149`). No verification bypass was found.
5. **POSSIBLE ISSUE** — There is no Razorpay webhook route in this project. The current flow relies on Checkout's handler posting the signed response to `/verify`; handling a browser close after successful payment requires operational reconciliation or adding a verified webhook as separate work.
6. **POSSIBLE ISSUE** — Verification records a checkout payment ID after signature verification but does not fetch payment status from Razorpay. Signature verification authenticates the order/payment identifiers; if the application needs additional server confirmation that the capture is settled, add a server-side status/capture check before invoice allocation. This is separate from the observed 503.
7. **POSSIBLE ISSUE** — Parent payment routes have equivalent create/verify flows (`backend/portal_api.py:4411-4429`). Parent verification is also signature checked and scoped to the linked ward.

## Changes made

- Added `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` variable injection to the backend service in `docker-compose.prod.yml`. Values come from the host deployment environment; no credentials are committed or baked into images.
- Added safe error logging in `backend/portal_api.py:45-56`, recording only whether each variable is present. It never logs values.
- Added `backend/.env.example` showing the required local variable names with placeholders. The existing `.gitignore` permits `.env.example` and ignores real env files.
- Kept the 503 response text and API response structure unchanged.

## Production server configuration and deployment

On the production host, create or edit `/opt/icms/.env` (the file next to `docker-compose.prod.yml`) with the real matching credentials, accessible only to the deployment administrator:

```dotenv
RAZORPAY_KEY_ID=your_matching_key_id
RAZORPAY_KEY_SECRET=your_matching_key_secret
```

Do not put credentials in the frontend build, source control, image, or Jenkinsfile. Then deploy/recreate the backend so Compose injects the new values:

```bash
cd /opt/icms
chmod 600 .env
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' icms-backend \
  | sed -E 's/^(RAZORPAY_KEY_(ID|SECRET))=.*/\1=<set>/' \
  | grep '^RAZORPAY_KEY_'
docker inspect --format '{{.State.Health.Status}}' icms-backend
```

The inspect command masks values before output. Expect both names as `<set>` and container status `healthy`. If Jenkins deployment is used, it will consume `/opt/icms/.env` during `docker compose` after the Compose change is included in the deployed repository. Never pass secrets as command-line arguments.

## Verification procedure

1. Confirm the two masked environment names appear inside the recreated `icms-backend` container.
2. Check backend logs for `razorpay_configuration_missing`. After configuration is fixed, that event should stop appearing on order attempts. Do not use logs or environment dumps that reveal values.
3. Sign in as a student with an unpaid invoice and make a small test-mode order. Call the endpoint through the UI; expect HTTP 200 with `key_id`, `order_id`, integer `amount` in paise, `currency: INR`, student prefill, and description. Confirm Checkout opens.
4. Use Razorpay test credentials/payment methods only. Complete a test payment and confirm `/verify` returns success and the invoice/payment allocation updates once.
5. Cancel or fail a test checkout and confirm the invoice remains unpaid. Replay a completed verification request and confirm it does not allocate a second payment.
6. Repeat the UI initialization and verification checks in the production deployment configured with the intended mode's credentials. Do not perform a real financial transaction.

## Testing status

No tests or frontend checks were run in this diagnostic step. No real payment was attempted.
