#!/bin/bash
# ────────────────────────────────────────────────────────────────────────────
# Workload Identity Federation Setup for GitHub Codespaces → GCP
#
# Run this ONCE from a machine where you have GCP admin access.
# It creates the trust relationship between GitHub (Codespace OIDC)
# and your GCP project so the app can authenticate without JSON keys.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated as project admin
#   - APIs enabled: Vertex AI, Firestore, IAM Credentials
# ────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration (edit these) ───────────────────────────────────────────────

PROJECT_ID="your-gcp-project-id"
REGION="europe-west2"
GITHUB_ORG="kr-pushpam"                    # Your GitHub username or org
GITHUB_REPO="Gemini_unblocked"            # Your repo name

# Names for the GCP resources
POOL_NAME="github-codespace-pool"
PROVIDER_NAME="github-oidc-provider"
SERVICE_ACCOUNT_NAME="gemini-app-sa"

# ─── Step 1: Enable required APIs ─────────────────────────────────────────────

echo "→ Enabling APIs..."
gcloud services enable \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    iamcredentials.googleapis.com \
    iam.googleapis.com \
    --project="$PROJECT_ID"

# ─── Step 2: Create Workload Identity Pool ─────────────────────────────────────

echo "→ Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create "$POOL_NAME" \
    --project="$PROJECT_ID" \
    --location="global" \
    --display-name="GitHub Codespace Pool" \
    --description="Allows GitHub Codespaces to authenticate to GCP"

# ─── Step 3: Add GitHub OIDC Provider ──────────────────────────────────────────

echo "→ Adding GitHub OIDC provider..."
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_NAME" \
    --display-name="GitHub OIDC" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
    --attribute-condition="assertion.repository == '${GITHUB_ORG}/${GITHUB_REPO}'"

# ─── Step 4: Create Service Account ───────────────────────────────────────────

echo "→ Creating service account..."
gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --project="$PROJECT_ID" \
    --display-name="Gemini Unblocked App SA" \
    --description="Used by Gemini Unblocked app to access Vertex AI and Firestore"

SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# ─── Step 5: Grant roles to the Service Account ───────────────────────────────

echo "→ Granting Vertex AI User role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"

echo "→ Granting Firestore User role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/datastore.user"

# ─── Step 6: Allow WIF pool to impersonate the SA ──────────────────────────────

echo "→ Binding WIF pool to service account..."
POOL_ID=$(gcloud iam workload-identity-pools describe "$POOL_NAME" \
    --project="$PROJECT_ID" \
    --location="global" \
    --format="value(name)")

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --project="$PROJECT_ID" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}"

# ─── Step 7: Create credential config file ────────────────────────────────────

echo "→ Generating credential config..."
gcloud iam workload-identity-pools create-cred-config \
    "${POOL_ID}/providers/${PROVIDER_NAME}" \
    --service-account="$SA_EMAIL" \
    --output-file="wif-credentials-config.json" \
    --credential-source-type="url" \
    --credential-source-url="http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"

echo ""
echo "✅ Done! Next steps:"
echo ""
echo "1. In your Codespace, set this environment variable:"
echo "   export GOOGLE_APPLICATION_CREDENTIALS=./wif-credentials-config.json"
echo ""
echo "2. Or for quick local testing, just run:"
echo "   gcloud auth application-default login"
echo ""
echo "3. Then start the app:"
echo "   uvicorn backend.main:app --port 8000"
echo "   streamlit run frontend/app.py --server.port 8501"
