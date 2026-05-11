# 📊  Regulatory Monitoring Dashboard

A Python and SQL pipeline that automatically retrieves, processes, and displays EU regulatory documents relevant to BNPL businesses — surfacing legislative proposals, public consultations, and EBA guidelines in a prioritised, searchable dashboard.

🔗 [Web App](#) · [GitHub Repo](#)

---

## Overview

The system follows a three-stage pipeline: **retrieval → processing → display**.

Regulatory documents are pulled from two authoritative sources, enriched with AI-generated summaries and domain classifications, then scored by urgency and presented through a hosted dashboard.

---

## Architecture

### 1. Data Retrieval

Documents are sourced from two providers chosen for their retrieval infrastructure and relevance to BNPL businesses:

**European Commission**
- The [Cellar API](https://op.europa.eu/en/web/cellar) queries the EU Publications Office for legislative proposals, filtered by EuroVoc concept numbers relevant to BNPL (e.g. `4491` for financial transactions).
- RSS feeds are used to retrieve public consultations, filtered by keyword search.

**EBA (European Banking Authority)**
- The EBA website HTML is parsed to extract RTS and Guidelines.
- Filtering uses EBA-specific topic numbers embedded in page URLs (e.g. `237` for AML).

> **Limitations:** Keyword filters lack semantic context and may over-penalise documents. Topic-based filtering assumes documents belong to a single domain. There is currently no ground truth to validate retrieval completeness.

---

### 2. Data Processing

Each retrieved document is enriched through three steps:

| Step | Method |
|---|---|
| **Summarisation** | Locally deployed LLM (`gemma3`) generates a concise summary of the document text |
| **Domain Classification** | The same LLM categorises the regulatory domain, cross-validated against a keyword-based classifier |
| **Urgency Scoring** | Each item is scored 1–100 based on relevance (keyword count), data confidence (AI vs keyword classifier agreement), and urgency (deadline proximity, status, publication date) |

> **Limitations:** The scoring system and LLM model selection are not yet validated. Scoring logic is currently uniform across document types rather than tailored to each type's specific importance signals.

---

### 3. Display

The dashboard is hosted on **HuggingFace** (free, public). It includes:

- A **summary home page** with an overview of recent activity
- Filtered views by **urgency score**, **document source**, and **document type**

> **Limitations:** End-user feedback has not yet been incorporated to refine the feature set.

---

## Regulatory Perimeter Assumptions

Two sets of assumptions underpin the filtering logic:

1. **Keywords** — Derived from the task description. These are unlikely to be exhaustive, so some relevant documents may be missed.
2. **EuroVoc & EBA topic codes** — Topics were selected if listed in the task description or related to digital finance, financial services, or credit. This selection should be reviewed with the compliance team against the full list of available topics.

---

## Roadmap

- [ ] Validate scoring system and LLM model selection
- [ ] Develop document-type-specific scoring models
- [ ] Implement version control for safe, regular data updates
- [ ] Link related documents by relationship
- [ ] More granular information extraction from document text
- [ ] Incorporate end-user feedback on dashboard features
- [ ] Expand regulatory perimeter in collaboration with the compliance team

---

## Author

**Omar Mukhtar**