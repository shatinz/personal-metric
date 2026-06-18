"""
ai_evaluator.py
===============
Uses the Google Antigravity SDK to spawn an AI agent that:
  1. Reads the latest clustering + NLP analysis output from the database
  2. Reviews the mathematical correctness of the pipeline
  3. Identifies new patterns, anomalies, and insights
  4. Returns a structured Markdown report

Falls back to a rule-based heuristic evaluation if the SDK is unavailable.
"""

import sqlite3
import json
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DATA COLLECTION
# ─────────────────────────────────────────────────────────────────────────────

def collect_analysis_snapshot(db_path: str) -> dict:
    """
    Gathers the latest analysis data from the DB into a structured snapshot
    that will be sent to the AI for evaluation.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Overall stats
    cursor.execute("SELECT COUNT(*) as n FROM notes")
    total_notes = cursor.fetchone()['n']

    cursor.execute("SELECT COUNT(*) as n FROM note_analysis")
    analyzed_notes = cursor.fetchone()['n']

    # Metric averages and trends
    cursor.execute("""
        SELECT 
            AVG(word_count) as avg_words,
            AVG(word_diversity) as avg_diversity,
            AVG(sentiment_polarity) as avg_sentiment,
            AVG(creativity_score) as avg_creativity,
            AVG(grammatical_correctness_score) as avg_grammar,
            AVG(emotion_joy) as avg_joy,
            AVG(emotion_sadness) as avg_sadness,
            AVG(emotion_fear) as avg_fear,
            AVG(emotion_diversity) as avg_emotion_diversity,
            MIN(date) as earliest_date,
            MAX(date) as latest_date
        FROM note_analysis
    """)
    aggregate = dict(cursor.fetchone())

    # Latest clustering run
    cursor.execute("""
        SELECT * FROM clustering_runs 
        ORDER BY run_timestamp DESC 
        LIMIT 2
    """)
    latest_runs = [dict(r) for r in cursor.fetchall()]
    for run in latest_runs:
        if 'cluster_summary' in run and run['cluster_summary']:
            run['cluster_summary'] = json.loads(run['cluster_summary'])

    # Strong correlations from latest runs
    if latest_runs:
        run_ids = tuple(r['run_id'] for r in latest_runs)
        placeholders = ','.join('?' * len(run_ids))
        cursor.execute(f"""
            SELECT metric_name, cluster_id, correlation_coefficient, p_value
            FROM cluster_correlations
            WHERE run_id IN ({placeholders})
              AND ABS(correlation_coefficient) > 0.3
              AND p_value < 0.05
            ORDER BY ABS(correlation_coefficient) DESC
            LIMIT 20
        """, run_ids)
        strong_corrs = [dict(r) for r in cursor.fetchall()]
    else:
        strong_corrs = []

    # Recent 5 entries (for context)
    cursor.execute("""
        SELECT n.date, n.content, na.sentiment_polarity, na.creativity_score,
               na.word_count, na.emotion_diversity
        FROM notes n
        INNER JOIN note_analysis na ON n.id = na.note_id
        ORDER BY n.date DESC
        LIMIT 5
    """)
    recent_entries = [dict(r) for r in cursor.fetchall()]
    # Truncate content for the AI context
    for e in recent_entries:
        e['content'] = e['content'][:200] + '...' if len(e.get('content', '')) > 200 else e.get('content', '')

    conn.close()

    agg_metrics = {}
    for k, v in aggregate.items():
        if k in ('earliest_date', 'latest_date'):
            agg_metrics[k] = v
        else:
            agg_metrics[k] = round(float(v), 4) if v is not None else None

    return {
        'total_notes': total_notes,
        'analyzed_notes': analyzed_notes,
        'aggregate_metrics': agg_metrics,
        'latest_clustering_runs': latest_runs,
        'strong_correlations': strong_corrs,
        'recent_entries': recent_entries
    }


# ─────────────────────────────────────────────────────────────────────────────
# ANTIGRAVITY SDK EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

async def _run_antigravity_evaluation(snapshot: dict) -> str:
    """
    Uses the Google Antigravity SDK to spawn an AI analysis agent.
    """
    try:
        from google.antigravity import Agent, LocalAgentConfig
    except ImportError:
        raise ImportError(
            "google-antigravity SDK not installed. "
            "Run: pip install google-antigravity"
        )

    snapshot_json = json.dumps(snapshot, indent=2, default=str)

    system_prompt = """You are an expert data scientist and clinical psychologist specializing in 
computational psycholinguistics. You review statistical outputs from personal diary NLP analyses.

Your job is to:
1. Evaluate the mathematical correctness and validity of the metrics and clustering.
2. Identify meaningful psychological or behavioral patterns from the data.
3. Flag any anomalies, outliers, or potential data quality issues.
4. Provide concrete, actionable insights the diary author should be aware of.

Format your response in Markdown with clear sections."""

    user_prompt = f"""Please evaluate the following diary NLP analysis pipeline output.

## Analysis Snapshot
```json
{snapshot_json}
```

Please provide:

### 1. Mathematical Validation
- Are the metric ranges what you would expect? (e.g., sentiment -1 to 1, diversity 0-1)
- Are the clustering results statistically valid (silhouette scores)?
- Are there any red flags in the correlations (spurious, multicollinearity)?

### 2. Psychological Pattern Analysis
- What patterns emerge from the cluster summaries?
- What do the strong correlations tell us about the author's psychological state?
- How do emotion diversity and sentiment polarity relate?

### 3. Notable Observations
- Any concerning trends (e.g., declining sentiment, increasing fear scores)?
- Any positive trends worth noting?

### 4. Data Quality Issues
- Any entries or metrics that seem like outliers or errors?

### 5. Recommendations
- What should the author focus on for self-development?
- What additional analyses would be valuable?
"""

    config = LocalAgentConfig(
        system_instructions=system_prompt,
    )

    async with Agent(config) as agent:
        response = await agent.chat(user_prompt)
        return await response.text()


def _rule_based_evaluation(snapshot: dict) -> str:
    """
    Fallback evaluation using deterministic rules when the SDK is unavailable.
    """
    agg = snapshot.get('aggregate_metrics', {})
    runs = snapshot.get('latest_clustering_runs', [])
    corrs = snapshot.get('strong_correlations', [])

    lines = ["# Diary Analysis Evaluation Report\n", 
             f"*Generated: rule-based fallback (Antigravity SDK not available)*\n"]

    # Math validation
    lines.append("## Mathematical Validation\n")
    issues = []
    if agg.get('avg_sentiment') is not None:
        s = agg['avg_sentiment']
        if -1 <= s <= 1:
            lines.append(f"✅ Average sentiment polarity: **{s:.3f}** (valid range -1 to 1)")
        else:
            issues.append(f"⚠️ Sentiment out of range: {s}")

    if agg.get('avg_diversity') is not None:
        d = agg['avg_diversity']
        if 0 <= d <= 1:
            lines.append(f"✅ Average word diversity (TTR): **{d:.3f}** (valid range 0 to 1)")
        else:
            issues.append(f"⚠️ Word diversity out of range: {d}")

    for run in runs:
        sil = run.get('silhouette_score', 0)
        alg = run.get('algorithm', '?')
        k = run.get('n_clusters', 0)
        if sil > 0.5:
            lines.append(f"✅ {alg.upper()} silhouette score: **{sil:.3f}** (excellent, K={k})")
        elif sil > 0.25:
            lines.append(f"🟡 {alg.upper()} silhouette score: **{sil:.3f}** (moderate, K={k})")
        else:
            lines.append(f"⚠️ {alg.upper()} silhouette score: **{sil:.3f}** (weak, clusters may not be meaningful)")

    if issues:
        lines.extend(issues)

    # Patterns
    lines.append("\n## Pattern Analysis\n")
    if agg.get('avg_sentiment') is not None:
        s = agg['avg_sentiment']
        if s > 0.2:
            lines.append(f"- 😊 Overall diary tone is **positive** (avg sentiment: {s:.2f})")
        elif s < -0.1:
            lines.append(f"- 😔 Overall diary tone is **negative** (avg sentiment: {s:.2f})")
        else:
            lines.append(f"- 😐 Overall diary tone is **neutral** (avg sentiment: {s:.2f})")

    if corrs:
        lines.append("\n**Strongest metric correlations with clusters:**")
        for c in corrs[:5]:
            direction = "↑ positively" if c['correlation_coefficient'] > 0 else "↓ negatively"
            lines.append(
                f"- `{c['metric_name']}` is {direction} correlated "
                f"with cluster {c['cluster_id']} "
                f"(r={c['correlation_coefficient']:.2f}, p={c['p_value']:.3f})"
            )

    lines.append("\n## Recommendations\n")
    lines.append("- Run this evaluation regularly to track longitudinal trends.")
    lines.append("- As more entries accumulate, clustering quality will improve.")
    lines.append("- Consider reviewing entries from clusters with lowest sentiment for self-reflection.")

    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def run_ai_evaluation(db_path: str) -> str:
    """
    Main entry point. Collects snapshot and runs AI or fallback evaluation.
    Returns a Markdown report string.
    """
    logger.info("Collecting analysis snapshot from database...")
    snapshot = collect_analysis_snapshot(db_path)

    # Try Antigravity SDK first
    try:
        logger.info("Attempting Antigravity SDK evaluation...")
        report = asyncio.run(_run_antigravity_evaluation(snapshot))
        logger.info("Antigravity SDK evaluation complete.")
        return report
    except ImportError:
        logger.warning("Antigravity SDK not available. Using rule-based fallback.")
    except Exception as e:
        logger.warning(f"Antigravity SDK evaluation failed: {e}. Using rule-based fallback.")

    # Fallback to rule-based
    return _rule_based_evaluation(snapshot)


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    report = run_ai_evaluation('personal_metric.db')
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(report)
