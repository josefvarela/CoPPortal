# 🛡️ SRE Meeting Hub

A comprehensive meeting management platform built for SRE Communities of Practice, featuring intelligent knowledge base search, meeting lifecycle management, and an AI-powered chatbot.

---

## Architecture

```
sre_meeting_hub/
├── app.py            # Streamlit frontend (4 pages: Agendas, KB, Chatbot, Dashboard)
├── database.py       # SQLite persistence layer with full CRUD operations
├── chatbot.py        # KB chatbot with fuzzy matching & intent classification
├── requirements.txt  # Python dependencies
└── README.md
```

## Features

### 📋 Meeting Agendas
- **Full CRUD** — Create, read, update, and delete meetings
- **Fields**: Date, Time, Topic, Presenter, Brief Description, URL Name, URL
- **Collapsible monthly grouping** — meetings organized under expandable month headers
- **Status tracking** — Scheduled → Completed → Cancelled with one-click toggling

### 📝 Meeting Notes & Tracking
- **Rich notes editor** attached to each meeting agenda
- **TO DOs** with assignees and status tracking (Open / In Progress / Completed)
- **Action Items** with assignees, due dates, and status management
- **Attendee count** tracking per meeting
- **File attachments** — upload and download any file type
- **Additional URLs** — link recordings, slides, or external references

### 📖 Knowledge Base
- **Pre-seeded with 15 SRE articles** covering Incident Management, Observability, Deployment, Infrastructure, Reliability Testing, and Business Continuity
- **Dual source types**: Internal Confluence pages (📘) and External resources (🌐)
- **Category-organized** with tag-based filtering
- **Full CRUD** for managing articles

### 💬 KB Chatbot
- **Natural language search** — ask questions like "How do I respond to a P1 incident?"
- **Multi-signal ranking** — scores results across title (2x weight), tags (1.8x), description (1.5x), category (1.2x)
- **Intent classification** — maps queries to SRE domains (incident, monitoring, deployment, etc.)
- **Contextual suggestions** — follow-up queries based on detected intent
- **Conversation history** with clickable suggestion buttons

### 📊 Dashboard
- **At-a-glance metrics**: Total meetings, completed, scheduled, KB article count
- **Cross-meeting open action items** tracker
- **Upcoming meetings** summary
- **KB coverage chart** by category

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

The app launches at `http://localhost:8501` with a pre-seeded knowledge base ready to use.

---

## Data Storage

- **SQLite** database (`sre_meeting_hub.db`) created automatically on first run
- **WAL mode** enabled for concurrent read performance
- **Foreign keys** enforced with cascading deletes (deleting a meeting removes all associated notes, items, attachments, and URLs)
- **Indexed** on meeting dates and action item relationships

---

## Innovative Differentiators

| Feature | Traditional Approach | SRE Meeting Hub |
|---------|---------------------|-----------------|
| KB Search | Keyword-only | Multi-signal fuzzy ranking with intent classification |
| Meeting Notes | Separate tool | Integrated tabs directly within each meeting card |
| Action Tracking | Spreadsheet | Status-tracked items with assignees and due dates inline |
| Resource Discovery | Manual browsing | Conversational chatbot with contextual suggestions |
| Monthly Organization | Flat list or calendar | Collapsible month groups with meeting counts |
| Attachments | Email or shared drive | Directly attached to meeting records with download |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (Python) |
| Database | SQLite with WAL mode |
| Search | Custom fuzzy matching + SequenceMatcher |
| Chatbot | Intent classification + multi-signal ranking |
| Styling | Custom CSS with gradient headers and status badges |
