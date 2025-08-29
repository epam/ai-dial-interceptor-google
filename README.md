# Google Model Armor interceptor

This interceptor streamlines work with Google Cloud DLP—handling PII detection, de‑identification, and re‑identification—while supporting asynchronous workflows. Blocking RPC calls are delegated to the event loop’s default executor, making the design well‑suited for modern async Python applications.

## Key Capabilities:

- PII Detection: Identifies sensitive information within text and images.
- De-identification: Transforms sensitive data (e.g., masking, redacting, tokenizing) to protect privacy.
- Re-identification (for tokenized data): Reverses the de-identification process for specific tokenized data, allowing controlled access to original PII when necessary
- Asynchronous Operations: Integrates seamlessly into asyncio applications.


A step‑by‑step guide to spinning up **Google Cloud Model Armor** — complete with Compute Engine dependencies, **KMS encryption**, and four ready‑to‑use templates (**basic filter · inspect · de‑identify · re‑identify**) — using nothing but the **gcloud CLI**.

## 1.  Prerequisites

Model Armor relies on Google Cloud APIs that require billing and authentication. The service account is necessary to automate deployment and API calls.

| Tool / Resource                  | Version / Role | Notes |
|---------------------------------|----------------|-------|
| **gcloud CLI**                  | ≥ 460          | `gcloud version` |
| **openssl**                     | any            | Generate AES key |
| **Service‑account JSON key**    | Project Owner  | Activate via `gcloud auth` |
| **Billing Account**             | Billing Admin  | Needed for new project |

## 2. Environment Variables

Add following variables to main:

|Variable|Description|
|---|---|
|GOOGLE_PROJECT|GCP project name|
|GOOGLE_REGION|GCP region|
|GOOGLE_INSPECT_TEMPLATE|inspect template|
|GOOGLE_DEIDENTIFY_TEMPLATE|PII deidentify template name|
|GOOGLE_KMS_KEY_NAME|PATH to DLP key|
|GOOGLE_KMS_WRAPPED_KEY|KMS wrapped key base64|
|GOOGLE_SURROGATE_INFO_TYPE|Surrogate token name in re-identify template|
|GOOGLE_APPLICATION_CREDENTIALS|Local path to credentials file|
|DIAL_URL|URL where dial core is running|

## 3.  Authenticate

Activate the service account and set it as the active one

```bash
gcloud auth activate-service-account --key-file=./secret/xxx-key.json
gcloud config set account "$(jq -r .client_email < ./secret/xxx-key.json)"
```

## 4.  Create & Fund the Project

A project is the security + billing boundary for Model Armor.
Without billing, the Model Armor API refuses to enable.

```bash
# Create the project
gcloud projects create "$PROJECT_ID" \
  --name="Model Armor Demo"
# Link to a billing account
gcloud billing projects link "$PROJECT_ID" \
  --billing-account "$BILLING_ACCOUNT_ID"
```

## 5.  Enable Required APIs

```bash
# Point gcloud at the regional Model Armor endpoint
gcloud config set api_endpoint_overrides/modelarmor \
  "https://modelarmor.${LOCATION_ID}.rep.googleapis.com/"

# Enable the required services
gcloud services enable compute.googleapis.com     --project "$PROJECT_ID"
gcloud services enable modelarmor.googleapis.com  --project "$PROJECT_ID"
gcloud services enable cloudkms.googleapis.com    --project "$PROJECT_ID"
```

## 6.  Create Model Armor Templates

Model Armor controls are template‑driven – each template is an immutable set of rules that the interceptor references by name.

### 6.1  Basic Filter Template

```bash
gcloud model-armor templates create "$BASIC_TEMPLATE_ID" \
  --location "$REGION" \
  --basic-config-filter-enforcement=enabled
```

### 6.2  Inspect Template (custom infoTypes)

Adds structured findings so downstream logic can decide to redact, log, or allow.

```bash
cat > inspect-config.json <<'EOF'
{
  "inspectConfig": {
    "infoTypes": [
      { "name": "EMAIL_ADDRESS" },
      { "name": "PHONE_NUMBER" },
      { "name": "CREDIT_CARD_NUMBER" }
    ],
    "includeQuote": true
  }
}
EOF

# Создаём template в Model Armor
gcloud model-armor templates create "$INSPECT_TEMPLATE_ID" \
  --location "$REGION" \
  --inspect-config=@inspect-config.json
```

### 6.3  De‑identify Template (strip findings)

De-identification templates specify the rules and methods for transforming sensitive data (e.g., PII, financial details) to protect privacy while still allowing for data analysis or model training.

```bash
cat > deidentify-config.json <<'EOF'
{
  "transformationConfigs": [
    {
      "primitiveTransform": {
        "removeFindings": true
      }
    }
  ]
}
EOF

gcloud model-armor templates create "$DEID_TEMPLATE_ID" \
  --location="$REGION" \
  --deidentify-config=@deidentify-config.json
```

### 6.4  Re‑identify Template (surrogate tokens)

Turns PII_TOKEN placeholders back into real data after the LLM responds.

```bash
cat > reidentify-config.json <<'EOF'
{
  "reidentifyConfig": {
    "surrogateInfoType": {
      "name": "PII-TOKEN"
    }
  }
}
EOF

gcloud model-armor templates create "$REID_TEMPLATE_ID" \
  --location "$REGION" \
  --reidentify-config=@reidentify-config.json
```

### 6.5  Verify

```bash
gcloud model-armor templates list --location "$LOCATION_ID"
# Should list: basic‑guard, inspect‑guard, deid‑guard, reid‑guard
```

## 7.  Provision Cloud KMS

```bash
# Create a key ring
gcloud kms keyrings create "dlp-keyring" \
  --location global \
  --project "$PROJECT_ID"

# Create a key inside the key ring
gcloud kms keys create "dlp-key" \
  --location global \
  --keyring dlp-keyring \
  --purpose encryption \
  --project "$PROJECT_ID"
```

## 8.  Generate & Wrap a Data‑Encryption Key (DEK)

```bash
# Generate 256‑bit AES key
openssl rand -out ./aes_key.bin 32

# Base‑64 encode
PLAINTEXT_KEY=$(base64 -i ./aes_key.bin)

# Wrap using Cloud KMS
gcloud kms encrypt \
  --location=global \
  --keyring=dlp-keyring \
  --key=dlp-key \
  --plaintext-file=<(echo "$PLAINTEXT_KEY") \
  --ciphertext-file=wrapped_key.b64 \
  --project="$PROJECT_ID"

export WRAPPED_KEY=$(cat wrapped_key.b64)

# Persist to env
printf "\nWRAPPED_KEY=%s\n" "$WRAPPED_KEY" >> .env
```

## 9.  Validate

```bash
# List templates
gcloud model-armor templates list --location "$REGION"

# Dry‑run an inspect call
gcloud model-armor templates inspect-user-prompt \
  --location "$REGION" \
  --template "$INSPECT_TEMPLATE_ID" \
  --user-prompt-data-text "Hi, my SSN is 123‑45‑6789"
```

## 10.  Configuring the Interceptor in DIAL Core

### 10.1  Enable the interceptor in DIAL Core

Edit the config.json file located at:

```bash
$DIAL-CORE-SDK/dial-docker-compose/application/core/config.json
```

### 10.2  Declare the interceptor endpoint

Add the interceptor under the interceptors section:

```json
"INTERCEPTOR_NAME": {
  "endpoint": "http://INTERCEPTOR_HOST:INTERCEPTOR_PORT/openai/deployments/INTERCEPTOR_NAME/chat/completions"
}
```

Replace:

INTERCEPTOR_NAME → the name of your interceptor.

INTERCEPTOR_HOST and INTERCEPTOR_PORT → the host and port where the interceptor service is running.

### 10.3  Register the interceptor in the application section

Include your interceptor in the application’s interceptor list:

```json
"interceptors": [
  "google-ma-anonimyzer"
]
```

This ensures that all requests pass through the interceptor before reaching the model.
