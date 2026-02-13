"""
SRE Meeting Hub - Knowledge Base Chatbot
Provides intelligent search and conversational routing to KB articles.
Uses fuzzy keyword matching and category-aware ranking.
"""

from database import search_kb_articles, get_all_kb_articles
from difflib import SequenceMatcher
from typing import List, Dict


# ──────────────────────────────────────────────
# INTENT MAPPING - Maps natural language to SRE domains
# ──────────────────────────────────────────────

INTENT_MAP = {
    "incident": ["incident", "outage", "P1", "P2", "sev1", "sev2", "alert", "page", "fire",
                  "escalat", "on-call", "oncall", "respond", "triage"],
    "monitoring": ["monitor", "observ", "metric", "dashboard", "grafana", "dynatrace",
                   "prometheus", "alert", "SLO", "SLI", "SLA", "error budget", "APM", "RUM",
                   "synthetic", "trace", "log"],
    "deployment": ["deploy", "pipeline", "CI/CD", "harness", "canary", "rollback", "release",
                   "build", "artifact", "helm", "docker"],
    "infrastructure": ["kubernetes", "k8s", "terraform", "pod", "container", "node", "cluster",
                       "AWS", "cloud", "IaC", "infra", "scaling", "load balanc"],
    "reliability": ["chaos", "fault", "resilience", "DR", "disaster", "recovery", "failover",
                    "RTO", "RPO", "redundan", "availability", "SRE", "toil"],
    "postmortem": ["postmortem", "post-mortem", "RCA", "root cause", "blameless", "retrospect",
                   "lessons learned", "action item"],
}

# Greeting patterns
GREETINGS = {"hello", "hi", "hey", "good morning", "good afternoon", "howdy", "sup", "what's up"}

# Help patterns
HELP_PATTERNS = {"help", "what can you do", "how does this work", "commands", "guide me"}


def classify_intent(query: str) -> List[str]:
    """Classify user query into one or more SRE domains."""
    query_lower = query.lower()
    matched = []
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                matched.append(intent)
                break
    return matched


def fuzzy_score(query: str, text: str) -> float:
    """Compute a combined relevance score using substring + sequence matching."""
    query_lower = query.lower()
    text_lower = text.lower()

    # Direct substring bonus
    substring_score = 0
    for word in query_lower.split():
        if word in text_lower:
            substring_score += 0.3

    # Sequence similarity
    seq_score = SequenceMatcher(None, query_lower, text_lower).ratio()

    return min(1.0, substring_score + seq_score)


def rank_articles(query: str, articles: List[Dict]) -> List[Dict]:
    """Rank articles by relevance to the query using multi-signal scoring."""
    scored = []
    for article in articles:
        # Score across multiple fields
        title_score = fuzzy_score(query, article.get("title", "")) * 2.0  # Title weighted 2x
        desc_score = fuzzy_score(query, article.get("description", "")) * 1.5
        tag_score = fuzzy_score(query, article.get("tags", "")) * 1.8
        cat_score = fuzzy_score(query, article.get("category", "")) * 1.2

        total = title_score + desc_score + tag_score + cat_score
        scored.append((total, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored if item[0] > 0.5]


def chatbot_response(user_input: str) -> Dict:
    """
    Process user input and return a structured response.

    Returns:
        {
            "message": str,         # Response text
            "articles": List[Dict], # Matching KB articles
            "suggestions": List[str] # Follow-up suggestions
        }
    """
    query = user_input.strip()

    # Handle empty input
    if not query:
        return {
            "message": "Please type a question or topic — I'll find the most relevant SRE resources for you.",
            "articles": [],
            "suggestions": ["incident response", "monitoring setup", "chaos engineering"]
        }

    # Handle greetings
    if query.lower() in GREETINGS or any(g in query.lower() for g in GREETINGS):
        return {
            "message": (
                "👋 Hey there! I'm the SRE Knowledge Base assistant. "
                "Ask me about any SRE topic and I'll point you to the right Confluence page or external resource.\n\n"
                "**Try asking about:**"
            ),
            "articles": [],
            "suggestions": [
                "How do I respond to a P1 incident?",
                "Show me chaos engineering resources",
                "Where's the Dynatrace setup guide?",
                "What are our SLO standards?",
                "Kubernetes troubleshooting help"
            ]
        }

    # Handle help requests
    if any(h in query.lower() for h in HELP_PATTERNS):
        return {
            "message": (
                "🔍 **I can help you find SRE resources!**\n\n"
                "Just describe what you need in plain language. I search across:\n"
                "- 📘 Internal Confluence pages\n"
                "- 🌐 External SRE resources\n"
                "- 🏷️ Tags, categories, and descriptions\n\n"
                "**Example queries:**"
            ),
            "articles": [],
            "suggestions": [
                "incident runbook",
                "Grafana dashboard setup",
                "disaster recovery plan",
                "terraform standards",
                "on-call rotation policy"
            ]
        }

    # Search KB articles
    db_results = search_kb_articles(query)

    # Also get all articles for fuzzy ranking
    all_articles = get_all_kb_articles()
    ranked = rank_articles(query, all_articles)

    # Merge: DB results first (exact matches), then ranked fuzzy matches
    seen_ids = set()
    merged = []
    for article in db_results + ranked:
        if article["id"] not in seen_ids:
            seen_ids.add(article["id"])
            merged.append(article)

    # Limit to top 5
    top_results = merged[:5]

    # Classify intent for suggestions
    intents = classify_intent(query)

    # Build response message
    if top_results:
        source_types = set(a.get("source_type", "") for a in top_results)
        source_label = ""
        if "confluence" in source_types and "external" in source_types:
            source_label = "Confluence pages and external resources"
        elif "confluence" in source_types:
            source_label = "Confluence pages"
        else:
            source_label = "external resources"

        message = f"📚 Found **{len(top_results)}** relevant {source_label} for *\"{query}\"*:"
    else:
        message = (
            f"🤔 I couldn't find articles matching *\"{query}\"*. "
            "Try different keywords or browse the suggestions below."
        )

    # Generate contextual suggestions
    suggestions = _generate_suggestions(query, intents, top_results)

    return {
        "message": message,
        "articles": top_results,
        "suggestions": suggestions
    }


def _generate_suggestions(query: str, intents: List[str], results: List[Dict]) -> List[str]:
    """Generate contextual follow-up suggestions based on the query and results."""
    suggestions = []

    # Intent-based suggestions
    intent_suggestions = {
        "incident": ["postmortem template", "on-call escalation policy", "PagerDuty operations guide"],
        "monitoring": ["SLO/SLI definitions", "Grafana dashboards", "Dynatrace RUM setup"],
        "deployment": ["canary deployment strategy", "rollback procedures", "Harness pipeline guide"],
        "infrastructure": ["Kubernetes troubleshooting", "Terraform IaC standards", "AWS reliability pillar"],
        "reliability": ["chaos engineering playbook", "disaster recovery plan", "error budget policy"],
        "postmortem": ["incident response runbook", "blameless postmortem guide", "action item tracking"],
    }

    for intent in intents:
        if intent in intent_suggestions:
            suggestions.extend(intent_suggestions[intent])

    # If no intents matched, offer general suggestions
    if not suggestions:
        suggestions = [
            "incident management",
            "observability tools",
            "infrastructure automation",
            "reliability testing"
        ]

    # Remove suggestions that are too similar to the query
    query_lower = query.lower()
    suggestions = [s for s in suggestions if query_lower not in s.lower()]

    return suggestions[:4]
