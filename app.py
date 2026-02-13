"""
SRE Meeting Hub - Main Streamlit Application
─────────────────────────────────────────────
A comprehensive meeting management platform with:
  • Meeting Agenda CRUD with collapsible monthly grouping
  • Meeting Notes with TO DOs, Action Items, Attachments, URLs
  • AI-powered Knowledge Base Chatbot for SRE resources
"""

import streamlit as st
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import calendar
import base64

from database import (
    init_db, seed_kb_articles,
    create_meeting, get_all_meetings, get_meeting, update_meeting, delete_meeting,
    upsert_meeting_notes, get_meeting_notes,
    add_action_item, get_action_items, update_action_item_status, delete_action_item,
    save_attachment, get_attachments, get_attachment_data, delete_attachment,
    add_meeting_url, get_meeting_urls, delete_meeting_url,
    get_all_kb_articles, add_kb_article, delete_kb_article, update_kb_article,
)
from chatbot import chatbot_response

# ──────────────────────────────────────────────
# PAGE CONFIG & INIT
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="SRE Meeting Hub",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
seed_kb_articles()

# ──────────────────────────────────────────────
# CUSTOM CSS
# ──────────────────────────────────────────────

st.markdown("""
<style>
    /* Global */
    .block-container { padding-top: 1rem; }

    /* Header */
    .hub-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .hub-header h1 { margin: 0; font-size: 1.8rem; }
    .hub-header p { margin: 0.3rem 0 0 0; opacity: 0.85; font-size: 0.95rem; }

    /* Cards */
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        border-left: 4px solid;
        margin-bottom: 0.5rem;
    }
    .metric-card h3 { margin: 0; font-size: 1.5rem; }
    .metric-card p { margin: 0; font-size: 0.85rem; color: #666; }

    /* Status badges */
    .status-open { color: #d63031; font-weight: 600; }
    .status-in_progress { color: #e17055; font-weight: 600; }
    .status-completed { color: #00b894; font-weight: 600; }

    /* KB Article cards */
    .kb-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.8rem;
        transition: box-shadow 0.2s;
    }
    .kb-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
    .kb-tag {
        display: inline-block;
        background: #e3f2fd;
        color: #1565c0;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        margin: 2px;
    }
    .confluence-badge {
        background: #e8f5e9; color: #2e7d32;
        padding: 2px 10px; border-radius: 12px;
        font-size: 0.75rem; font-weight: 600;
    }
    .external-badge {
        background: #fff3e0; color: #e65100;
        padding: 2px 10px; border-radius: 12px;
        font-size: 0.75rem; font-weight: 600;
    }

    /* Chat */
    .chat-user {
        background: #e3f2fd;
        padding: 0.6rem 1rem;
        border-radius: 12px 12px 4px 12px;
        margin: 0.4rem 0;
        max-width: 80%;
        margin-left: auto;
    }
    .chat-bot {
        background: #f5f5f5;
        padding: 0.6rem 1rem;
        border-radius: 12px 12px 12px 4px;
        margin: 0.4rem 0;
        max-width: 80%;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #e0e0e0; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "editing_meeting_id" not in st.session_state:
    st.session_state.editing_meeting_id = None
if "show_create_form" not in st.session_state:
    st.session_state.show_create_form = False
if "active_notes_meeting" not in st.session_state:
    st.session_state.active_notes_meeting = None


# ──────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🛡️ SRE Meeting Hub")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["📋 Meeting Agendas", "📖 Knowledge Base", "💬 KB Chatbot", "📊 Dashboard"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#888'>Built for SRE Community of Practice</small>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════
# PAGE: MEETING AGENDAS
# ══════════════════════════════════════════════

if page == "📋 Meeting Agendas":

    # Header
    st.markdown("""
    <div class="hub-header">
        <h1>📋 Meeting Agendas</h1>
        <p>Create, manage, and track SRE community meetings with notes, action items, and attachments</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Create / Edit Meeting Form ──
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("➕ New Meeting", type="primary", use_container_width=True):
            st.session_state.show_create_form = not st.session_state.show_create_form
            st.session_state.editing_meeting_id = None

    # CREATE FORM
    if st.session_state.show_create_form and st.session_state.editing_meeting_id is None:
        with st.expander("🆕 Create New Meeting", expanded=True):
            with st.form("create_meeting_form", clear_on_submit=True):
                st.subheader("Meeting Details")
                fc1, fc2 = st.columns(2)
                with fc1:
                    m_date = st.date_input("📅 Date", value=date.today())
                    m_topic = st.text_input("📌 Topic *", placeholder="e.g., Chaos Engineering Review")
                    m_url_name = st.text_input("🔗 URL Label", placeholder="e.g., Slide Deck")
                with fc2:
                    m_time = st.time_input("🕐 Time", value=time(10, 0))
                    m_presenter = st.text_input("🎤 Presenter *", placeholder="e.g., Jose Recalde")
                    m_url = st.text_input("🌐 URL", placeholder="https://...")
                m_desc = st.text_area("📝 Brief Description", height=80,
                                      placeholder="What will be covered in this meeting?")

                submitted = st.form_submit_button("✅ Create Meeting", type="primary")
                if submitted:
                    if not m_topic or not m_presenter:
                        st.error("Topic and Presenter are required.")
                    else:
                        create_meeting(
                            meeting_date=m_date.isoformat(),
                            meeting_time=m_time.strftime("%I:%M %p"),
                            topic=m_topic,
                            presenter=m_presenter,
                            description=m_desc,
                            url_name=m_url_name,
                            url=m_url,
                        )
                        st.success(f"✅ Meeting '{m_topic}' created!")
                        st.session_state.show_create_form = False
                        st.rerun()

    # EDIT FORM
    if st.session_state.editing_meeting_id is not None:
        meeting = get_meeting(st.session_state.editing_meeting_id)
        if meeting:
            with st.expander(f"✏️ Editing: {meeting['topic']}", expanded=True):
                with st.form("edit_meeting_form"):
                    st.subheader("Edit Meeting Details")
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_date = st.date_input("📅 Date", value=date.fromisoformat(meeting["meeting_date"]))
                        e_topic = st.text_input("📌 Topic", value=meeting["topic"])
                        e_url_name = st.text_input("🔗 URL Label", value=meeting.get("url_name", ""))
                    with ec2:
                        try:
                            parsed_time = datetime.strptime(meeting["meeting_time"], "%I:%M %p").time()
                        except ValueError:
                            parsed_time = time(10, 0)
                        e_time = st.time_input("🕐 Time", value=parsed_time)
                        e_presenter = st.text_input("🎤 Presenter", value=meeting["presenter"])
                        e_url = st.text_input("🌐 URL", value=meeting.get("url", ""))
                    e_desc = st.text_area("📝 Description", value=meeting.get("description", ""), height=80)
                    e_status = st.selectbox("Status", ["scheduled", "completed", "cancelled"],
                                            index=["scheduled", "completed", "cancelled"].index(
                                                meeting.get("status", "scheduled")))

                    ec_save, ec_cancel = st.columns(2)
                    with ec_save:
                        save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                    with ec_cancel:
                        cancel_btn = st.form_submit_button("❌ Cancel")

                    if save_btn:
                        update_meeting(
                            st.session_state.editing_meeting_id,
                            meeting_date=e_date.isoformat(),
                            meeting_time=e_time.strftime("%I:%M %p"),
                            topic=e_topic,
                            presenter=e_presenter,
                            description=e_desc,
                            url_name=e_url_name,
                            url=e_url,
                            status=e_status,
                        )
                        st.success("✅ Meeting updated!")
                        st.session_state.editing_meeting_id = None
                        st.rerun()
                    if cancel_btn:
                        st.session_state.editing_meeting_id = None
                        st.rerun()

    # ── Display Meetings Grouped by Month ──
    st.markdown("---")
    meetings = get_all_meetings()

    if not meetings:
        st.info("📭 No meetings yet. Click **➕ New Meeting** to get started!")
    else:
        # Group by month
        monthly = defaultdict(list)
        for m in meetings:
            try:
                d = date.fromisoformat(m["meeting_date"])
                key = f"{calendar.month_name[d.month]} {d.year}"
            except (ValueError, TypeError):
                key = "Unknown Date"
            monthly[key].append(m)

        for month_label, month_meetings in monthly.items():
            with st.expander(f"📅 **{month_label}** — {len(month_meetings)} meeting(s)", expanded=True):
                for mtg in month_meetings:
                    _render_meeting_card(mtg)


def _render_meeting_card(mtg):
    """Render a single meeting card with notes, action items, attachments."""
    meeting_id = mtg["id"]
    status_emoji = {"scheduled": "🟡", "completed": "🟢", "cancelled": "🔴"}.get(mtg.get("status", ""), "⚪")

    with st.container(border=True):
        # Header row
        hc1, hc2, hc3 = st.columns([4, 2, 2])
        with hc1:
            st.markdown(f"### {status_emoji} {mtg['topic']}")
        with hc2:
            st.markdown(f"**📅** {mtg['meeting_date']}  •  **🕐** {mtg['meeting_time']}")
        with hc3:
            st.markdown(f"**🎤** {mtg['presenter']}")

        if mtg.get("description"):
            st.markdown(f"_{mtg['description']}_")

        if mtg.get("url") and mtg.get("url_name"):
            st.markdown(f"🔗 [{mtg['url_name']}]({mtg['url']})")
        elif mtg.get("url"):
            st.markdown(f"🔗 [Link]({mtg['url']})")

        # Action buttons
        bc1, bc2, bc3, bc4 = st.columns(4)
        with bc1:
            if st.button("✏️ Edit", key=f"edit_{meeting_id}"):
                st.session_state.editing_meeting_id = meeting_id
                st.session_state.show_create_form = False
                st.rerun()
        with bc2:
            if st.button("🗑️ Delete", key=f"del_{meeting_id}"):
                delete_meeting(meeting_id)
                st.rerun()
        with bc3:
            notes_key = f"notes_{meeting_id}"
            if st.button("📝 Notes", key=notes_key):
                if st.session_state.active_notes_meeting == meeting_id:
                    st.session_state.active_notes_meeting = None
                else:
                    st.session_state.active_notes_meeting = meeting_id
                st.rerun()
        with bc4:
            status_toggle = "completed" if mtg.get("status") != "completed" else "scheduled"
            label = "✅ Mark Done" if status_toggle == "completed" else "🔄 Reopen"
            if st.button(label, key=f"status_{meeting_id}"):
                update_meeting(meeting_id, status=status_toggle)
                st.rerun()

        # ── NOTES PANEL ──
        if st.session_state.active_notes_meeting == meeting_id:
            _render_notes_panel(meeting_id)


def _render_notes_panel(meeting_id):
    """Render the notes, TODOs, action items, attachments, and URLs panel."""
    st.markdown("---")
    notes_tab, todo_tab, attach_tab, urls_tab = st.tabs(
        ["📝 Meeting Notes", "☑️ TODOs & Action Items", "📎 Attachments", "🔗 URLs"]
    )

    # ── Meeting Notes Tab ──
    with notes_tab:
        existing_notes = get_meeting_notes(meeting_id)
        with st.form(f"notes_form_{meeting_id}"):
            notes_text = st.text_area(
                "Meeting Notes",
                value=existing_notes.get("notes", "") if existing_notes else "",
                height=200,
                placeholder="Capture key discussion points, decisions, and insights...",
            )
            attendee_count = st.number_input(
                "👥 Number of Attendees",
                min_value=0, max_value=500,
                value=existing_notes.get("attendee_count", 0) if existing_notes else 0,
            )
            if st.form_submit_button("💾 Save Notes", type="primary"):
                upsert_meeting_notes(meeting_id, notes_text, attendee_count)
                st.success("Notes saved!")
                st.rerun()

    # ── TODOs & Action Items Tab ──
    with todo_tab:
        tc1, tc2 = st.columns(2)

        with tc1:
            st.markdown("**📋 TO DOs**")
            todos = get_action_items(meeting_id, "todo")
            for item in todos:
                ic1, ic2, ic3 = st.columns([4, 2, 1])
                with ic1:
                    status_class = f"status-{item['status']}"
                    st.markdown(
                        f"<span class='{status_class}'>●</span> {item['description']}"
                        + (f" — *{item['assignee']}*" if item.get("assignee") else ""),
                        unsafe_allow_html=True,
                    )
                with ic2:
                    new_status = st.selectbox(
                        "Status", ["open", "in_progress", "completed"],
                        index=["open", "in_progress", "completed"].index(item["status"]),
                        key=f"todo_status_{item['id']}",
                        label_visibility="collapsed",
                    )
                    if new_status != item["status"]:
                        update_action_item_status(item["id"], new_status)
                        st.rerun()
                with ic3:
                    if st.button("🗑️", key=f"del_todo_{item['id']}"):
                        delete_action_item(item["id"])
                        st.rerun()

            with st.form(f"add_todo_{meeting_id}"):
                st.markdown("**Add TO DO**")
                td_desc = st.text_input("Description", key=f"td_desc_{meeting_id}",
                                        placeholder="What needs to be done?")
                td_assignee = st.text_input("Assignee", key=f"td_assign_{meeting_id}",
                                            placeholder="Who's responsible?")
                if st.form_submit_button("➕ Add TO DO"):
                    if td_desc:
                        add_action_item(meeting_id, "todo", td_desc, td_assignee)
                        st.rerun()

        with tc2:
            st.markdown("**🎯 Action Items**")
            actions = get_action_items(meeting_id, "action_item")
            for item in actions:
                ac1, ac2, ac3 = st.columns([4, 2, 1])
                with ac1:
                    status_class = f"status-{item['status']}"
                    due = f" (Due: {item['due_date']})" if item.get("due_date") else ""
                    st.markdown(
                        f"<span class='{status_class}'>●</span> {item['description']}"
                        + (f" — *{item['assignee']}*" if item.get("assignee") else "")
                        + due,
                        unsafe_allow_html=True,
                    )
                with ac2:
                    new_status = st.selectbox(
                        "Status", ["open", "in_progress", "completed"],
                        index=["open", "in_progress", "completed"].index(item["status"]),
                        key=f"ai_status_{item['id']}",
                        label_visibility="collapsed",
                    )
                    if new_status != item["status"]:
                        update_action_item_status(item["id"], new_status)
                        st.rerun()
                with ac3:
                    if st.button("🗑️", key=f"del_ai_{item['id']}"):
                        delete_action_item(item["id"])
                        st.rerun()

            with st.form(f"add_action_{meeting_id}"):
                st.markdown("**Add Action Item**")
                ai_desc = st.text_input("Description", key=f"ai_desc_{meeting_id}",
                                        placeholder="Action to be taken")
                ai_c1, ai_c2 = st.columns(2)
                with ai_c1:
                    ai_assignee = st.text_input("Assignee", key=f"ai_assign_{meeting_id}")
                with ai_c2:
                    ai_due = st.date_input("Due Date", key=f"ai_due_{meeting_id}",
                                           value=date.today() + timedelta(days=7))
                if st.form_submit_button("➕ Add Action Item"):
                    if ai_desc:
                        add_action_item(meeting_id, "action_item", ai_desc,
                                        ai_assignee, ai_due.isoformat())
                        st.rerun()

    # ── Attachments Tab ──
    with attach_tab:
        existing_attachments = get_attachments(meeting_id)
        if existing_attachments:
            for att in existing_attachments:
                att_c1, att_c2, att_c3 = st.columns([4, 2, 1])
                with att_c1:
                    st.markdown(f"📎 **{att['file_name']}**")
                with att_c2:
                    size_kb = (att.get("file_size", 0) or 0) / 1024
                    st.markdown(f"_{size_kb:.1f} KB_ • {att.get('file_type', 'N/A')}")
                with att_c3:
                    # Download button
                    att_data = get_attachment_data(att["id"])
                    if att_data and att_data.get("file_data"):
                        st.download_button(
                            "⬇️", data=att_data["file_data"],
                            file_name=att_data["file_name"],
                            mime=att_data.get("file_type", "application/octet-stream"),
                            key=f"dl_att_{att['id']}",
                        )

        uploaded = st.file_uploader(
            "Upload Attachment", key=f"upload_{meeting_id}",
            accept_multiple_files=True,
            help="Upload documents, images, or any relevant files."
        )
        if uploaded:
            for f in uploaded:
                save_attachment(meeting_id, f.name, f.read(), f.type, f.size)
            st.success(f"Uploaded {len(uploaded)} file(s)!")
            st.rerun()

    # ── URLs Tab ──
    with urls_tab:
        existing_urls = get_meeting_urls(meeting_id)
        for u in existing_urls:
            uc1, uc2 = st.columns([5, 1])
            with uc1:
                st.markdown(f"🔗 [{u['url_name']}]({u['url']})")
            with uc2:
                if st.button("🗑️", key=f"del_url_{u['id']}"):
                    delete_meeting_url(u["id"])
                    st.rerun()

        with st.form(f"add_url_{meeting_id}"):
            url_c1, url_c2 = st.columns(2)
            with url_c1:
                new_url_name = st.text_input("URL Label", placeholder="e.g., Recording Link")
            with url_c2:
                new_url = st.text_input("URL", placeholder="https://...")
            if st.form_submit_button("➕ Add URL"):
                if new_url_name and new_url:
                    add_meeting_url(meeting_id, new_url_name, new_url)
                    st.rerun()


# ══════════════════════════════════════════════
# PAGE: KNOWLEDGE BASE
# ══════════════════════════════════════════════

elif page == "📖 Knowledge Base":

    st.markdown("""
    <div class="hub-header">
        <h1>📖 Knowledge Base</h1>
        <p>Internal Confluence pages and external SRE resources — searchable and organized by category</p>
    </div>
    """, unsafe_allow_html=True)

    # Search bar
    kb_search = st.text_input("🔍 Search articles...", placeholder="e.g., incident, kubernetes, monitoring")

    # Add new article
    with st.expander("➕ Add New KB Article"):
        with st.form("add_kb_form", clear_on_submit=True):
            kb_c1, kb_c2 = st.columns(2)
            with kb_c1:
                kb_title = st.text_input("Title *")
                kb_category = st.selectbox("Category", [
                    "Incident Management", "Observability", "Deployment",
                    "Infrastructure", "Reliability Testing", "Business Continuity",
                    "External Resources", "Other"
                ])
                kb_source = st.selectbox("Source Type", ["confluence", "external"])
            with kb_c2:
                kb_url = st.text_input("URL *")
                kb_tags = st.text_input("Tags (comma-separated)", placeholder="e.g., incident,runbook,P1")
            kb_desc = st.text_area("Description", height=80)

            if st.form_submit_button("✅ Add Article", type="primary"):
                if kb_title and kb_url:
                    add_kb_article(kb_title, kb_category, kb_desc, kb_url, kb_source, kb_tags)
                    st.success(f"Added: {kb_title}")
                    st.rerun()
                else:
                    st.error("Title and URL are required.")

    # Display articles
    articles = get_all_kb_articles()
    if kb_search:
        from chatbot import search_kb_articles
        articles = search_kb_articles(kb_search)

    # Group by category
    by_category = defaultdict(list)
    for a in articles:
        by_category[a["category"]].append(a)

    for cat, cat_articles in sorted(by_category.items()):
        st.markdown(f"### 📂 {cat}")
        for article in cat_articles:
            with st.container(border=True):
                ac1, ac2 = st.columns([5, 1])
                with ac1:
                    badge_class = "confluence-badge" if article["source_type"] == "confluence" else "external-badge"
                    badge_label = "📘 Confluence" if article["source_type"] == "confluence" else "🌐 External"
                    st.markdown(
                        f"**[{article['title']}]({article['url']})** "
                        f"<span class='{badge_class}'>{badge_label}</span>",
                        unsafe_allow_html=True,
                    )
                    if article.get("description"):
                        st.markdown(f"_{article['description']}_")
                    if article.get("tags"):
                        tags_html = " ".join(
                            f"<span class='kb-tag'>{t.strip()}</span>"
                            for t in article["tags"].split(",")
                        )
                        st.markdown(tags_html, unsafe_allow_html=True)
                with ac2:
                    if st.button("🗑️", key=f"del_kb_{article['id']}"):
                        delete_kb_article(article["id"])
                        st.rerun()


# ══════════════════════════════════════════════
# PAGE: KB CHATBOT
# ══════════════════════════════════════════════

elif page == "💬 KB Chatbot":

    st.markdown("""
    <div class="hub-header">
        <h1>💬 SRE Knowledge Assistant</h1>
        <p>Ask questions in plain language — I'll find the right Confluence page or resource for you</p>
    </div>
    """, unsafe_allow_html=True)

    # Chat history display
    chat_container = st.container(height=450)
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown("""
            **👋 Welcome to the SRE Knowledge Assistant!**

            I can help you find internal Confluence pages and external SRE resources.
            Try asking things like:
            - *"How do I respond to a P1 incident?"*
            - *"Where's our chaos engineering playbook?"*
            - *"Show me Kubernetes troubleshooting guides"*
            """)

        for entry in st.session_state.chat_history:
            if entry["role"] == "user":
                st.markdown(
                    f"<div class='chat-user'>🧑 {entry['content']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='chat-bot'>🤖 {entry['message']}</div>",
                    unsafe_allow_html=True,
                )
                # Display articles
                for article in entry.get("articles", []):
                    badge = "📘" if article.get("source_type") == "confluence" else "🌐"
                    st.markdown(f"  {badge} **[{article['title']}]({article['url']})**")
                    if article.get("description"):
                        st.markdown(f"  _{article['description'][:120]}..._" if len(article.get("description", "")) > 120 else f"  _{article['description']}_")

                # Display suggestions
                if entry.get("suggestions"):
                    st.markdown("**💡 Related searches:**")
                    suggestion_cols = st.columns(min(len(entry["suggestions"]), 4))
                    for idx, sug in enumerate(entry["suggestions"][:4]):
                        with suggestion_cols[idx]:
                            if st.button(f"🔍 {sug}", key=f"sug_{len(st.session_state.chat_history)}_{idx}"):
                                _process_chat(sug)
                                st.rerun()

    # Input
    user_input = st.chat_input("Ask about any SRE topic...")
    if user_input:
        _process_chat(user_input)
        st.rerun()

    # Clear chat
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()


def _process_chat(user_input):
    """Process a chat message and get bot response."""
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    response = chatbot_response(user_input)
    st.session_state.chat_history.append({
        "role": "bot",
        "message": response["message"],
        "articles": response["articles"],
        "suggestions": response["suggestions"],
    })


# ══════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════

elif page == "📊 Dashboard":

    st.markdown("""
    <div class="hub-header">
        <h1>📊 Dashboard</h1>
        <p>At-a-glance metrics for your SRE meetings, action items, and knowledge base</p>
    </div>
    """, unsafe_allow_html=True)

    meetings = get_all_meetings()
    all_articles = get_all_kb_articles()

    # Summary metrics
    total_meetings = len(meetings)
    completed = sum(1 for m in meetings if m.get("status") == "completed")
    scheduled = sum(1 for m in meetings if m.get("status") == "scheduled")

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.markdown(f"""
        <div class="metric-card" style="border-color: #0984e3;">
            <h3>{total_meetings}</h3><p>Total Meetings</p>
        </div>""", unsafe_allow_html=True)
    with mc2:
        st.markdown(f"""
        <div class="metric-card" style="border-color: #00b894;">
            <h3>{completed}</h3><p>Completed</p>
        </div>""", unsafe_allow_html=True)
    with mc3:
        st.markdown(f"""
        <div class="metric-card" style="border-color: #fdcb6e;">
            <h3>{scheduled}</h3><p>Scheduled</p>
        </div>""", unsafe_allow_html=True)
    with mc4:
        st.markdown(f"""
        <div class="metric-card" style="border-color: #6c5ce7;">
            <h3>{len(all_articles)}</h3><p>KB Articles</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Open action items across all meetings
    st.subheader("🎯 Open Action Items Across All Meetings")
    has_open = False
    for mtg in meetings:
        items = get_action_items(mtg["id"])
        open_items = [i for i in items if i["status"] != "completed"]
        if open_items:
            has_open = True
            st.markdown(f"**{mtg['topic']}** ({mtg['meeting_date']})")
            for item in open_items:
                status_emoji = "🔴" if item["status"] == "open" else "🟠"
                assignee = f" → {item['assignee']}" if item.get("assignee") else ""
                due = f" (Due: {item['due_date']})" if item.get("due_date") else ""
                st.markdown(f"  {status_emoji} {item['description']}{assignee}{due}")
    if not has_open:
        st.success("🎉 No open action items — everything is on track!")

    st.markdown("---")

    # Upcoming meetings
    st.subheader("📅 Upcoming Meetings")
    today = date.today().isoformat()
    upcoming = [m for m in meetings if m.get("meeting_date", "") >= today and m.get("status") == "scheduled"]
    if upcoming:
        for m in upcoming[:5]:
            st.markdown(f"• **{m['topic']}** — {m['meeting_date']} at {m['meeting_time']} (🎤 {m['presenter']})")
    else:
        st.info("No upcoming meetings scheduled.")

    # KB coverage
    st.markdown("---")
    st.subheader("📚 Knowledge Base Coverage")
    by_cat = defaultdict(int)
    for a in all_articles:
        by_cat[a["category"]] += 1
    if by_cat:
        import pandas as pd
        df = pd.DataFrame(list(by_cat.items()), columns=["Category", "Articles"])
        st.bar_chart(df.set_index("Category"))
