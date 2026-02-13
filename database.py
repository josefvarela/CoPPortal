"""
SRE Meeting Hub - Database Layer
Handles all CRUD operations for meetings, notes, KB articles using SQLite.
"""

import sqlite3
import json
import os
from datetime import datetime, date
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "sre_meeting_hub.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database schema with all required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_date DATE NOT NULL,
            meeting_time TEXT NOT NULL,
            topic TEXT NOT NULL,
            presenter TEXT NOT NULL,
            description TEXT,
            url_name TEXT,
            url TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS meeting_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            notes TEXT,
            attendee_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            item_type TEXT NOT NULL CHECK(item_type IN ('todo', 'action_item')),
            description TEXT NOT NULL,
            assignee TEXT,
            due_date DATE,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'in_progress', 'completed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_data BLOB,
            file_type TEXT,
            file_size INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS meeting_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            url_name TEXT NOT NULL,
            url TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS kb_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            url TEXT NOT NULL,
            source_type TEXT DEFAULT 'confluence' CHECK(source_type IN ('confluence', 'external')),
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_meetings_date ON meetings(meeting_date);
        CREATE INDEX IF NOT EXISTS idx_action_items_meeting ON action_items(meeting_id);
        CREATE INDEX IF NOT EXISTS idx_kb_tags ON kb_articles(tags);
    """)

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# MEETING CRUD
# ──────────────────────────────────────────────

def create_meeting(meeting_date, meeting_time, topic, presenter,
                   description="", url_name="", url=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO meetings (meeting_date, meeting_time, topic, presenter,
                              description, url_name, url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (meeting_date, meeting_time, topic, presenter, description, url_name, url))
    meeting_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return meeting_id


def get_all_meetings():
    conn = get_connection()
    rows = conn.execute("""
        SELECT m.*,
               mn.notes, mn.attendee_count,
               mn.id as notes_id
        FROM meetings m
        LEFT JOIN meeting_notes mn ON m.id = mn.meeting_id
        ORDER BY m.meeting_date DESC, m.meeting_time DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_meeting(meeting_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_meeting(meeting_id, **kwargs):
    conn = get_connection()
    allowed = {"meeting_date", "meeting_time", "topic", "presenter",
               "description", "url_name", "url", "status"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [meeting_id]
    conn.execute(f"UPDATE meetings SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_meeting(meeting_id):
    conn = get_connection()
    conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# MEETING NOTES CRUD
# ──────────────────────────────────────────────

def upsert_meeting_notes(meeting_id, notes="", attendee_count=0):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM meeting_notes WHERE meeting_id = ?", (meeting_id,)
    ).fetchone()
    if existing:
        conn.execute("""
            UPDATE meeting_notes
            SET notes = ?, attendee_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE meeting_id = ?
        """, (notes, attendee_count, meeting_id))
    else:
        conn.execute("""
            INSERT INTO meeting_notes (meeting_id, notes, attendee_count)
            VALUES (?, ?, ?)
        """, (meeting_id, notes, attendee_count))
    conn.commit()
    conn.close()


def get_meeting_notes(meeting_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM meeting_notes WHERE meeting_id = ?", (meeting_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ──────────────────────────────────────────────
# ACTION ITEMS / TODOS
# ──────────────────────────────────────────────

def add_action_item(meeting_id, item_type, description, assignee="", due_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO action_items (meeting_id, item_type, description, assignee, due_date)
        VALUES (?, ?, ?, ?, ?)
    """, (meeting_id, item_type, description, assignee, due_date))
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id


def get_action_items(meeting_id, item_type=None):
    conn = get_connection()
    if item_type:
        rows = conn.execute(
            "SELECT * FROM action_items WHERE meeting_id = ? AND item_type = ? ORDER BY id",
            (meeting_id, item_type)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM action_items WHERE meeting_id = ? ORDER BY item_type, id",
            (meeting_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_action_item_status(item_id, status):
    conn = get_connection()
    conn.execute("UPDATE action_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    conn.close()


def delete_action_item(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM action_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# ATTACHMENTS
# ──────────────────────────────────────────────

def save_attachment(meeting_id, file_name, file_data, file_type, file_size):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attachments (meeting_id, file_name, file_data, file_type, file_size)
        VALUES (?, ?, ?, ?, ?)
    """, (meeting_id, file_name, file_data, file_type, file_size))
    att_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return att_id


def get_attachments(meeting_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, meeting_id, file_name, file_type, file_size, uploaded_at FROM attachments WHERE meeting_id = ?",
        (meeting_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attachment_data(attachment_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT file_name, file_data, file_type FROM attachments WHERE id = ?",
        (attachment_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_attachment(attachment_id):
    conn = get_connection()
    conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# MEETING URLS (additional URLs in notes)
# ──────────────────────────────────────────────

def add_meeting_url(meeting_id, url_name, url):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO meeting_urls (meeting_id, url_name, url) VALUES (?, ?, ?)
    """, (meeting_id, url_name, url))
    url_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return url_id


def get_meeting_urls(meeting_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM meeting_urls WHERE meeting_id = ?", (meeting_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_meeting_url(url_id):
    conn = get_connection()
    conn.execute("DELETE FROM meeting_urls WHERE id = ?", (url_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# KNOWLEDGE BASE ARTICLES
# ──────────────────────────────────────────────

def add_kb_article(title, category, description, url, source_type="confluence", tags=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO kb_articles (title, category, description, url, source_type, tags)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, category, description, url, source_type, tags))
    article_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return article_id


def get_all_kb_articles():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM kb_articles ORDER BY category, title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_kb_articles(query):
    """Keyword search across title, description, tags, and category."""
    conn = get_connection()
    terms = query.lower().split()
    if not terms:
        return get_all_kb_articles()

    conditions = []
    params = []
    for term in terms:
        conditions.append(
            "(LOWER(title) LIKE ? OR LOWER(description) LIKE ? "
            "OR LOWER(tags) LIKE ? OR LOWER(category) LIKE ?)"
        )
        wildcard = f"%{term}%"
        params.extend([wildcard] * 4)

    where = " OR ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM kb_articles WHERE {where} ORDER BY category, title", params
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_kb_article(article_id):
    conn = get_connection()
    conn.execute("DELETE FROM kb_articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()


def update_kb_article(article_id, **kwargs):
    conn = get_connection()
    allowed = {"title", "category", "description", "url", "source_type", "tags"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [article_id]
    conn.execute(f"UPDATE kb_articles SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# SEED DATA
# ──────────────────────────────────────────────

def seed_kb_articles():
    """Pre-populate KB with common SRE resources if table is empty."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM kb_articles").fetchone()[0]
    if count > 0:
        conn.close()
        return

    articles = [
        ("Incident Response Runbook", "Incident Management",
         "Step-by-step guide for P1/P2 incident response including escalation paths and communication templates.",
         "https://confluence.internal/sre/incident-runbook", "confluence",
         "incident,runbook,P1,P2,escalation,on-call"),
        ("Chaos Engineering Playbook", "Reliability Testing",
         "Framework for designing and executing chaos experiments using AWS FIS and custom fault injection.",
         "https://confluence.internal/sre/chaos-engineering", "confluence",
         "chaos,engineering,fault-injection,FIS,resilience,testing"),
        ("SLO/SLI Definition Guide", "Observability",
         "How to define, measure, and alert on Service Level Objectives and Indicators across the platform.",
         "https://confluence.internal/sre/slo-sli-guide", "confluence",
         "SLO,SLI,SLA,observability,alerting,error-budget"),
        ("Dynatrace Monitoring Setup", "Observability",
         "Configuration guide for Dynatrace real user monitoring, synthetic monitors, and custom dashboards.",
         "https://confluence.internal/sre/dynatrace-setup", "confluence",
         "dynatrace,monitoring,RUM,synthetic,dashboard,APM"),
        ("Harness CI/CD Pipeline Guide", "Deployment",
         "Best practices for configuring Harness pipelines with canary deployments and automated rollback.",
         "https://confluence.internal/sre/harness-pipelines", "confluence",
         "harness,CI/CD,pipeline,canary,deployment,rollback"),
        ("Kubernetes Troubleshooting", "Infrastructure",
         "Common K8s issues and resolution steps including pod failures, resource limits, and networking.",
         "https://confluence.internal/sre/k8s-troubleshooting", "confluence",
         "kubernetes,k8s,pods,troubleshooting,networking,OOM"),
        ("Disaster Recovery Plan", "Business Continuity",
         "DR procedures including RTO/RPO targets, failover automation, and recovery validation.",
         "https://confluence.internal/sre/disaster-recovery", "confluence",
         "DR,disaster,recovery,failover,RTO,RPO,business-continuity"),
        ("Terraform IaC Standards", "Infrastructure",
         "Infrastructure as Code standards, module conventions, and state management best practices.",
         "https://confluence.internal/sre/terraform-standards", "confluence",
         "terraform,IaC,infrastructure,modules,state,automation"),
        ("Google SRE Book", "External Resources",
         "Google's comprehensive guide to Site Reliability Engineering principles and practices.",
         "https://sre.google/sre-book/table-of-contents/", "external",
         "SRE,google,reliability,principles,toil,error-budget"),
        ("Prometheus Monitoring Guide", "External Resources",
         "Official Prometheus documentation for metrics collection, PromQL, and alerting.",
         "https://prometheus.io/docs/introduction/overview/", "external",
         "prometheus,metrics,PromQL,alerting,monitoring,TSDB"),
        ("PagerDuty Incident Ops Guide", "External Resources",
         "PagerDuty's guide to incident operations including on-call best practices and postmortems.",
         "https://response.pagerduty.com/", "external",
         "pagerduty,incident,on-call,postmortem,operations"),
        ("AWS Well-Architected Reliability", "External Resources",
         "AWS reliability pillar covering fault tolerance, disaster recovery, and scaling strategies.",
         "https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/", "external",
         "AWS,reliability,well-architected,fault-tolerance,scaling"),
        ("Grafana Dashboard Best Practices", "Observability",
         "Guidelines for creating effective Grafana dashboards with proper panel organization and alerting.",
         "https://confluence.internal/sre/grafana-dashboards", "confluence",
         "grafana,dashboard,visualization,alerting,panels"),
        ("On-Call Rotation & Escalation Policy", "Incident Management",
         "On-call scheduling, escalation tiers, and handoff procedures for the SRE team.",
         "https://confluence.internal/sre/on-call-policy", "confluence",
         "on-call,rotation,escalation,schedule,handoff,PagerDuty"),
        ("Postmortem Template & Process", "Incident Management",
         "Blameless postmortem template with timeline, root cause analysis, and action item tracking.",
         "https://confluence.internal/sre/postmortem-template", "confluence",
         "postmortem,blameless,RCA,root-cause,timeline,action-items"),
    ]

    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO kb_articles (title, category, description, url, source_type, tags)
        VALUES (?, ?, ?, ?, ?, ?)
    """, articles)
    conn.commit()
    conn.close()
