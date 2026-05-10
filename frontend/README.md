---
title: Regulatory Monitoring Dashboard
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.35.0"
app_file: app.py
pinned: false
---

# Regulatory Monitoring Dashboard

A Streamlit dashboard for monitoring EU regulatory developments relevant to Scalapay’s business perimeter, including payment services, BNPL and consumer credit, AML/CFT, operational resilience, and data/AI regulation.

The app aggregates regulatory items into a searchable dashboard and allows users to explore items by type, urgency, source, status, and impact area.

## Dashboard Structure

The homepage contains two interactive ring charts:

- **Regulatory Type Summary**  
  Shows how many items exist for each regulatory type.

- **Urgency Summary**  
  Shows how many items fall into each urgency level.

Clicking on a chart segment opens a filtered database view for that specific type or urgency level.

A **See Whole Database** button allows users to access the complete regulatory database.

## Features

- Interactive Streamlit frontend
- Ring chart summaries for type and urgency
- Click-through filtering from charts to database views
- Full database table view
- Search and filtering functionality
- Relevance and urgency indicators
- Source links for regulatory items
- SQLite-backed data storage

## Data Sources

The prototype focuses on regulatory information from selected EU regulatory sources, including:

- European Banking Authority
- European Commission

The database contains normalized regulatory records with fields such as:

- Title
- Source
- Publication date
- Status
- Type
- Summary
- Impact area
- Relevance score
- Urgency level
- Consultation deadline, where available
- Source URL

## Relevance Logic

Items are categorized and prioritized according to their relevance to Scalapay’s regulatory perimeter.

The main impact areas considered are:

- Payment services
- BNPL and consumer credit
- AML/CFT
- Operational resilience
- Data protection and AI

The filtering logic is rule-based and relies on keywords, regulatory category mapping, and scoring fields stored in the SQLite database.

## Repository Structure

```text
.
├── app.py
├── eu_regulatory_data.db
├── requirements.txt
└── README.md