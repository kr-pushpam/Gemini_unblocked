# Requirements Document: Gemini Unblocked

## 1. Overview

Build a full-stack multimodal AI application that provides Gemini-like capabilities (chat, image analysis, document analysis, image generation, grounded search) through a custom interface. The application bypasses direct Gemini API restrictions by routing all LLM calls through **Vertex AI** on GCP.

**Phase 1** (this document): Build and test in GitHub Codespaces, authenticated to GCP via Workload Identity Federation (WIF) — no service account keys.

**Phase 2** (future): Deploy to Cloud Run with production-grade configuration.

---

## 2. Constraints & Assumptions

| Constraint | Detail |
|-----------|--------|
| Corporate block | Direct `generativelanguage.googleapis.com` (Gemini API) is blocked |
| Allowed access | GCP Cloud Console and Vertex AI endpoints are reachable |
| No tokens/keys in code | Authentication uses Workload Identity Federation or `gcloud` CLI — never JSON key files committed to repo |
| Dev environment | GitHub Codespaces (Python 3.12) |
| No deployment code yet | Phase 1 produces no Dockerfiles, Cloud Run configs, or CI/CD pipelines |

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Streamlit | User-facing UI for all features |
| Backend | FastAPI | API layer, business logic, streaming |
| LLM | Vertex AI Gemini 2.0 Flash / Pro | Text, multimodal, grounding |
| Image Gen | Vertex AI Imagen 3 | Text-to-image generation |
| Storage | Firestore | Chat session persistence |
| Auth | Workload Identity Federation / gcloud ADC | Keyless GCP authentication from Codespace |
| Dev Env | GitHub Codespaces | Development and testing |
| Python | 3.12 | Runtime |

---

## 4. Authentication Strategy

### 4.1 Approach: Workload Identity Federation (WIF)

Connect the GitHub Codespace to GCP without service account key files.

**How it works:**
1. Create a **Workload Identity Pool** in GCP
2. Add a **GitHub OIDC Provider** to the pool
3. Grant the pool's identities access to a **GCP Service Account**
4. The Service Account has roles: `Vertex AI User`, `Firestore User`
5. In the Codespace, use `gcloud auth login --cred-file=<wif-config>.json` or `gcloud auth application-default login` to obtain short-lived credentials

### 4.2 Fallback: gcloud CLI ADC (for quick local testing)

```bash
gcloud auth application-default login
```

This opens a browser flow and stores ADC credentials locally. Works in Codespace when port forwarding is available.

### 4.3 What gets stored in repo

- A **credential configuration JSON** (not a key — just tells the SDK where to get tokens)
- Or nothing at all if using `gcloud auth application-default login`

---

## 5. Functional Requirements

### FR-1: Multi-turn Chat with Streaming

| ID | Requirement |
|----|-------------|
| FR-1.1 | User can send text messages and receive responses from Gemini |
| FR-1.2 | Responses stream token-by-token via Server-Sent Events (SSE) |
| FR-1.3 | Conversation history is maintained within a session |
| FR-1.4 | User can start a new chat session |
| FR-1.5 | Chat sessions are persisted to Firestore |

### FR-2: File / PDF Upload & Analysis

| ID | Requirement |
|----|-------------|
| FR-2.1 | User can upload files: PDF, images (JPEG/PNG/GIF/WebP), TXT, CSV, DOCX, XLSX |
| FR-2.2 | User provides a text prompt alongside the file |
| FR-2.3 | Gemini analyzes the file content and returns a response |
| FR-2.4 | Response can be streamed |
| FR-2.5 | File size limit: 20MB (Vertex AI limit for inline data) |

### FR-3: Image Generation

| ID | Requirement |
|----|-------------|
| FR-3.1 | User provides a text prompt describing desired image |
| FR-3.2 | System generates 1–4 images using Imagen 3 on Vertex AI |
| FR-3.3 | User can select aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4) |
| FR-3.4 | Generated images are displayed in the UI |
| FR-3.5 | User can download generated images |

### FR-4: Google Search Grounding

| ID | Requirement |
|----|-------------|
| FR-4.1 | User can ask factual/current questions |
| FR-4.2 | Gemini uses Google Search to ground its response with real-time data |
| FR-4.3 | Source citations (URLs, titles) are displayed alongside the response |
| FR-4.4 | Response can be streamed |

### FR-5: Session Management

| ID | Requirement |
|----|-------------|
| FR-5.1 | Chat sessions stored in Firestore with timestamps |
| FR-5.2 | User can view list of previous sessions |
| FR-5.3 | User can resume a previous session |
| FR-5.4 | User can delete a session |

---

## 6. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Backend responds within 2s for non-streaming requests (excluding LLM latency) |
| NFR-2 | Streaming starts delivering tokens within 1s of request |
| NFR-3 | No secrets or credentials committed to the repository |
| NFR-4 | Code structured for future Cloud Run deployment (modular, env-driven config) |
| NFR-5 | Frontend usable on desktop browsers (Chrome, Firefox, Safari) |
| NFR-6 | Error messages are user-friendly, not raw stack traces |

---

## 7. Architecture (Phase 1 — Codespace)

```
┌──────────────────────────────────────────────────────┐
│  GitHub Codespace                                     │
│                                                       │
│  ┌─────────────┐         ┌─────────────┐            │
│  │  Streamlit  │──HTTP──▶│   FastAPI   │            │
│  │  (port 8501)│◀────────│  (port 8000)│            │
│  └─────────────┘         └──────┬──────┘            │
│                                  │                    │
│                    ADC / WIF credentials              │
└──────────────────────────────────┼────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
           ┌──────────────┐ ┌──────────┐ ┌────────────┐
           │  Vertex AI   │ │ Imagen 3 │ │ Firestore  │
           │  Gemini API  │ │          │ │            │
           └──────────────┘ └──────────┘ └────────────┘
```

---

## 8. Project Structure

```
6.gemini-vertex-multimodal/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings from env vars
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat.py             # Chat + streaming endpoints
│   │   ├── multimodal.py       # File analysis, imagen, grounding
│   │   └── health.py           # Health check
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_service.py   # Vertex AI Gemini operations
│   │   ├── imagen_service.py   # Image generation
│   │   └── firestore_service.py# Chat persistence
│   └── models/
│       ├── __init__.py
│       └── schemas.py          # Pydantic models
├── frontend/
│   ├── app.py                  # Streamlit main page
│   └── pages/
│       ├── 1_Chat.py           # Streaming chat UI
│       ├── 2_Documents.py      # File upload UI
│       ├── 3_Image_Gen.py      # Image generation UI
│       └── 4_Grounded_Search.py# Grounded search UI
├── scripts/
│   └── setup_wif.sh            # WIF setup helper (GCP admin runs once)
├── .devcontainer/
│   └── devcontainer.json       # Codespace configuration
├── .env.example                # Template for env vars
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 9. GCP Services Required

| Service | Purpose | Required Role |
|---------|---------|---------------|
| Vertex AI API | Gemini text/multimodal, Imagen | `roles/aiplatform.user` |
| Firestore | Chat session storage | `roles/datastore.user` |
| IAM | Workload Identity Federation | `roles/iam.workloadIdentityPoolAdmin` (admin setup only) |

---

## 10. Setup Steps (One-time GCP Admin)

1. Enable APIs: Vertex AI, Firestore, IAM Credentials
2. Create Workload Identity Pool: `github-codespace-pool`
3. Add OIDC Provider (GitHub): issuer `https://token.actions.githubusercontent.com`
4. Create Service Account: `gemini-app-sa@<project>.iam.gserviceaccount.com`
5. Grant SA roles: Vertex AI User, Firestore User
6. Bind WIF pool to SA with attribute condition on repo
7. Create Firestore database in Native mode (region: `europe-west2`)

---

## 11. Environment Variables

```
GCP_PROJECT_ID=<your-project-id>
GCP_LOCATION=europe-west2
MODEL_NAME=gemini-2.0-flash
FIRESTORE_DATABASE=(default)
BACKEND_URL=http://localhost:8000
```

---

## 12. Out of Scope (Phase 1)

- Dockerfile / Cloud Run deployment
- CI/CD pipelines
- User authentication (login/signup)
- Rate limiting / quotas management
- Audio/video input
- ADK agents with tools/function calling
- Production monitoring/logging

---

## 13. Success Criteria

- [ ] Backend starts in Codespace and responds to `/health`
- [ ] Chat endpoint streams responses from Gemini via Vertex AI
- [ ] PDF upload returns analysis from Gemini
- [ ] Image generation returns base64 images from Imagen 3
- [ ] Grounded search returns response with source citations
- [ ] Chat history persists across page reloads (Firestore)
- [ ] No service account keys in the repository
- [ ] Streamlit UI is functional for all 4 features
