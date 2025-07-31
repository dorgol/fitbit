## Fitbit Conversational AI POC - Technical Design Document

### 1. High-Level Architecture

The core philosophy behind this design is **memory-centric orchestration**. The primary goal is to ensure that every relevant piece of context—metrics, trends, preferences, and environment—is surfaced and available to the LLM **before** it generates a response.

* **Frontend Layer**: Streamlit interface provides chat, health data visualizations, and transparency into what the AI "knows."
* **Orchestration Layer**: LangGraph drives the conversational loop, managing turn-taking, state transitions, and stop conditions.
* **Memory Layer** (central concept):

  * **Raw Data**: Mock time-series data simulates Fitbit sensor metrics (steps, heart rate, sleep).
  * **Insights**: Precomputed batch analysis of raw data, surfacing trends and correlations. This reduces latency and ensures structured domain understanding. Over time, insights evolve to reflect broader patterns rather than ephemeral details.
  * **Highlights**: LLM-extracted memory from past conversations — captures user context not available via sensors (e.g., allergies, stress sources). Highlights fade in granularity over time.
  * **External Context**: Live and mock integrations (e.g., weather, air quality). Extensible to include local events, yoga recommendations, etc.
  * **Knowledge Base**: Decouples "knowing" from "talking" — allows batch research or user-specific enrichment that is injected into the prompt without needing the LLM to have it memorized.
  * **System Prompt**: Final assembly of memory + behavioral rules into a single payload, modularly constructed from prompt templates ("Lego bricks").

This layered memory approach enables flexible experimentation, prompt tuning, and insight control — each section can be tested, swapped, or upgraded independently.

### 2. LLM Orchestration Framework

**Framework: LangGraph**

* Declarative node-based architecture: `load_context → build_prompt → get_response → update_memory → check_stop`
* Uses conditional edges to control loop behavior
* Conversation stops after 10 messages or if user ends explicitly ("bye", etc.) — mock logic for the POC, easily extendable.
* Supports fallback paths and retry logic

### 3. Data Storage & Simulation

* **PostgreSQL** is recommended for production with separate `messages` and `conversations` tables
* Each message should be stored as a separate row with `role`, `content`, `timestamp`, and optional `metadata`
* **Vector Database Integration**: Use `pgvector` (Postgres extension) or external vector DB (e.g., Pinecone, Qdrant, Weaviate) to store semantic embeddings of messages for retrieval-augmented generation (RAG), memory search, or personalization
* **SQLite** is used for POC simplicity; mock data engine populates the database with realistic user profiles, health trends, and conversational history

### 4. Prompt Strategy & Agent Behavior

**Goal**: Guide the LLM with complete, pre-assembled context, ensuring:

* Personalization
* Actionable insights (not raw reporting)
* Behavioral alignment (transparency, empathy, accuracy)

**Prompt Construction**:

* Modular template sections: base character, insights, raw data, highlights, external context, knowledge, behavioral guidelines
* Dynamically generated per turn
* Safe fallback sections if data is missing

**Agent Behavior**:

* Responds with awareness of context, not just user message
* Leverages prior conversations (via highlights)
* Injects nudges, suggestions, or clarifications based on memory
* Avoids robotic recitation of stats in favor of informed guidance

### 5. UX Philosophy

While the current frontend is a functional web-based chat, the envisioned experience is more immersive:

* **Conversational Tone**: Like speaking to a trusted health coach or professional who *knows you*, not a stats reader.
* **Memory Design Reflects UX**: Recency influences granularity — recent conversations preserve detail, older ones distill into lasting insights. This principle drove the **insights layer**.
* **Future Direction**: Incorporate a **vocal UI** — a talking head or voice avatar — to avoid the sterile feeling of typical chatbots and promote natural interaction.

### 6. Evaluation & Monitoring Strategy

**Current Testing**:

* Unit-level tests for memory loading, insight generation, external APIs
* End-to-end LangGraph flow tested in CLI and web
* Manual walkthrough of multiple user personas

**Observability** (Planned):

* Logging at all stages (prompt build, LLM response, DB writes)
* Placeholder for structured logging and metrics
* Highlight summaries help debug memory and extract UX signals

---

### 7. Productionization Plan

#### Infrastructure Setup

* Migrate from SQLite to managed PostgreSQL with connection pooling
* Deploy the LangGraph orchestration backend using containerized services (e.g., AWS ECS, GCP Cloud Run)
* Secure secrets with tools like AWS Secrets Manager
* Set up Redis or similar caching layer if needed for session memory or rate limiting

#### Storage Enhancements

* Normalize conversations and messages into separate tables for analytics and scalability
* Add pgvector or connect to an external vector database (e.g., Pinecone) to store semantic message embeddings and support context search or memory recall
* Introduce row-level encryption for sensitive content if clinical context is expanded

#### Observability & Monitoring

* Implement structured logging with unique request/session IDs
* Use metrics and traces for latency, throughput, and LLM performance
* Add error alerting (e.g., via Sentry or CloudWatch)

#### Frontend Transition

* Move from Streamlit to production-grade frontend (e.g., React or Flutter)
* Integrate optional voice interface or avatar component to match desired UX
* Implement authentication and user onboarding flow

#### API and Security

* Expose REST or GraphQL API with authentication for frontend-to-backend communication
* Implement abuse throttling and fallback paths for unavailable components
* Enforce user data access control per account/session

This plan prepares the system for real-world usage with a scalable, secure, and extensible architecture. Testing and long-term improvement loops will follow in the next phase.

---

### 8. Testing & Continuous Improvement Loop

#### Testing Framework

**Layer 1: Automated Testing**

* Safety validation (no dangerous or medical advice)
* Integration correctness (user data included)
* Tone and engagement scoring
* Prompt boundary adherence

**Layer 2: Human Expert Review**

* Certified wellness coach review of sampled conversations
* Validation of health advice, motivational tone, and goal relevance
* Boundary assessment between wellness and medical domains

**Layer 3: User Experience Testing**

* A/B tests for tone, prompt depth, and personalization variations
* Metrics: conversation completion, re-engagement, motivation impact
* Collection of user feedback and behavioral engagement tracking

#### Continuous Improvement Loop

**Daily Checks**

* Automated safety scans and prompt regression tests
* Monitoring of context freshness and performance stats

**Weekly Cycles**

1. Conversation pattern review
2. Prompt and insight tuning
3. Deployment of winning A/B variants
4. Handling flagged content from QA

**Monthly Strategy Review**

* Expert feedback integration
* Knowledge base and insight content refresh
* System updates based on long-term user engagement trends

#### Risk Mitigation

* Boundaries: Avoid medical advice, surface disclaimers, handle edge language
* Escalation: Trigger alerts on certain user intents or keywords
* Expert guardrails: Validate system output against wellness guidelines

#### Success Indicators

* User satisfaction and engagement trends
* Expert-approved coaching strategies
* High-quality, personalized conversation feedback
* Safe and effective use of user data in recommendations

---

### 9. How to Use This Repo

#### ✅ Prerequisites

* Python 3.9 or later
* pip (Python package manager)
* `virtualenv` (recommended)

#### 🛠️ Setup Steps

1. **Clone the repository:**

   ```bash
   git clone https://github.com/dorgol/fitbit
   cd fitbit
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables (if needed):**
   Create a `.env` file or export them directly in your shell:

   ```bash
   export CLAUDE_API_KEY=your_api_key_here
   export OPENWEATHER_API_KEY=your_api_key_here
   ```

5. **Launch the app:**

   ```bash
   streamlit run app/main.py
   ```

6. **Access in your browser:**
   Open [http://localhost:8501](http://localhost:8501)

#### 🧪 Troubleshooting

* Restart the app using:

  ```bash
  streamlit run app/main.py --server.headless true
  ```
* If using Jupyter or VSCode, manually open the printed URL in your browser.

---

This concludes the technical design and implementation documentation for the Fitbit AI Assistant.
