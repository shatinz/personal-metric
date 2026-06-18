"""
dashboard.py
============
Streamlit Dashboard for Personal Diary NLP Analysis.

Sections:
  1. Overview — KPI cards with aggregate stats
  2. Lexical & Style Trends — word count, diversity, creativity over time
  3. Grammar Structure — POS ratios, correctness, first-person usage
  4. Emotion & Sentiment — time-series of emotions, diversity
  5. Clustering — 2D scatter plot of HDBSCAN + K-Means clusters
  6. Correlations — heatmap of significant metric-cluster correlations
  7. AI Evaluation Panel — run Antigravity AI evaluation and display report

Run with: streamlit run dashboard.py
"""

import streamlit as st
import sqlite3
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import logging
import sys
import os
import dynamic_clustering

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = 'personal_metric.db'

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Personal Diary Analytics",
    page_icon="📓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    min-height: 100vh;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: rgba(15, 12, 41, 0.95);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

/* KPI cards */
.kpi-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px 24px;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
}
.kpi-card:hover {
    background: rgba(255, 255, 255, 0.09);
    border-color: rgba(139, 92, 246, 0.5);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(139, 92, 246, 0.2);
}
.kpi-value {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, #a78bfa, #60a5fa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1;
}
.kpi-label {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.6);
    margin-top: 8px;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.kpi-delta {
    font-size: 0.8rem;
    margin-top: 4px;
}
.delta-pos { color: #34d399; }
.delta-neg { color: #f87171; }

/* Section headers */
.section-header {
    font-size: 1.3rem;
    font-weight: 600;
    color: white;
    margin: 32px 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid rgba(139, 92, 246, 0.4);
}

/* AI Evaluation panel */
.ai-panel {
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(10px);
}

/* Pills */
.cluster-pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 2px;
}

/* Info box */
.info-box {
    background: rgba(96, 165, 250, 0.1);
    border-left: 4px solid #60a5fa;
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    margin: 8px 0;
    color: rgba(255,255,255,0.85);
    font-size: 0.9rem;
}

/* Streamlit overrides */
.stButton > button {
    background: linear-gradient(135deg, #7c3aed, #4f46e5);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 28px;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    transition: all 0.3s ease;
    width: 100%;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #8b5cf6, #6366f1);
    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.4);
    transform: translateY(-1px);
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_all_data():
    """Load all analysis data from SQLite DB."""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Main analysis dataframe
        df = pd.read_sql_query("""
            SELECT 
                n.id, n.date, n.content, n.mood, n.energy, n.focus, n.source,
                na.word_count, na.unique_word_count, na.word_diversity,
                na.avg_sentence_length, na.verb_ratio, na.noun_ratio,
                na.adjective_ratio, na.adverb_ratio, na.first_person_pronoun_ratio,
                na.grammatical_error_count, na.grammatical_correctness_score,
                na.hapax_legomena_ratio, na.sentence_length_variance, na.creativity_score,
                na.sentiment_polarity, na.sentiment_subjectivity,
                na.emotion_joy, na.emotion_sadness, na.emotion_anger,
                na.emotion_fear, na.emotion_surprise, na.emotion_diversity,
                na.hdbscan_cluster_id, na.kmeans_cluster_id
            FROM notes n
            INNER JOIN note_analysis na ON n.id = na.note_id
            ORDER BY n.date
        """, conn)

        # Clustering runs
        runs_df = pd.read_sql_query(
            "SELECT * FROM clustering_runs ORDER BY run_timestamp DESC LIMIT 10", conn
        )

        # Correlations
        corr_df = pd.read_sql_query("""
            SELECT cc.*, cr.algorithm
            FROM cluster_correlations cc
            JOIN clustering_runs cr ON cc.run_id = cr.run_id
            WHERE ABS(cc.correlation_coefficient) > 0.2
            ORDER BY ABS(cc.correlation_coefficient) DESC
        """, conn)

        conn.close()

        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        return df, runs_df, corr_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=300)
def load_embeddings_2d():
    """Load 2D reduced embeddings for the cluster scatter plot."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.id, n.date, n.embedding, na.hdbscan_cluster_id, na.kmeans_cluster_id,
                   na.sentiment_polarity, na.word_count, n.content
            FROM notes n
            INNER JOIN note_analysis na ON n.id = na.note_id
            WHERE n.embedding IS NOT NULL
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return pd.DataFrame()

        note_ids, dates, embeddings, hdbscan_ids, kmeans_ids, sentiments, word_counts, contents = [], [], [], [], [], [], [], []
        for row in rows:
            blob = row[2]
            if blob is None:
                continue
            try:
                vec = np.frombuffer(blob, dtype=np.float32)
                embeddings.append(vec)
                note_ids.append(row[0])
                dates.append(row[1])
                hdbscan_ids.append(row[3])
                kmeans_ids.append(row[4])
                sentiments.append(row[5])
                word_counts.append(row[6])
                contents.append((row[7] or '')[:100] + '...')
            except Exception:
                continue

        if len(embeddings) < 4:
            return pd.DataFrame()

        matrix = np.array(embeddings, dtype=np.float32)
        
        # Reduce to 2D
        try:
            import umap.umap_ as umap
            reducer = umap.UMAP(n_components=2, n_neighbors=min(15, len(embeddings)-1),
                               metric='cosine', random_state=42)
            reduced = reducer.fit_transform(matrix)
        except Exception:
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2, random_state=42)
            reduced = pca.fit_transform(matrix)

        return pd.DataFrame({
            'note_id': note_ids,
            'date': dates,
            'x': reduced[:, 0],
            'y': reduced[:, 1],
            'hdbscan_cluster': [str(c) if c is not None else 'N/A' for c in hdbscan_ids],
            'kmeans_cluster': [str(c) if c is not None else 'N/A' for c in kmeans_ids],
            'sentiment': sentiments,
            'word_count': word_counts,
            'preview': contents
        })
    except Exception as e:
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIVE CLUSTERING PLAYGROUND HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_raw_embeddings_and_metrics():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.id, n.date, n.embedding,
                   na.word_count, na.word_diversity, na.sentiment_polarity,
                   na.sentiment_subjectivity, na.emotion_joy, na.emotion_sadness,
                   na.emotion_anger, na.emotion_fear, na.emotion_surprise,
                   na.emotion_diversity, na.creativity_score, na.verb_ratio,
                   na.noun_ratio, na.adjective_ratio, na.first_person_pronoun_ratio,
                   na.grammatical_correctness_score, na.hapax_legomena_ratio,
                   n.mood, n.energy, n.focus, n.content
            FROM notes n
            INNER JOIN note_analysis na ON n.id = na.note_id
            WHERE n.embedding IS NOT NULL
            ORDER BY n.date
        """)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None, None, None
            
        note_ids, dates, embeddings, metrics, contents = [], [], [], [], []
        for r in rows:
            blob = r[2]
            if blob is None:
                continue
            try:
                vec = np.frombuffer(blob, dtype=np.float32)
                embeddings.append(vec)
                note_ids.append(r[0])
                dates.append(r[1])
                metrics.append({
                    'word_count': r[3], 'word_diversity': r[4], 'sentiment_polarity': r[5],
                    'sentiment_subjectivity': r[6], 'emotion_joy': r[7], 'emotion_sadness': r[8],
                    'emotion_anger': r[9], 'emotion_fear': r[10], 'emotion_surprise': r[11],
                    'emotion_diversity': r[12], 'creativity_score': r[13], 'verb_ratio': r[14],
                    'noun_ratio': r[15], 'adjective_ratio': r[16], 'first_person_pronoun_ratio': r[17],
                    'grammatical_correctness_score': r[18], 'hapax_legomena_ratio': r[19],
                    'mood': r[20], 'energy': r[21], 'focus': r[22],
                    'content': r[23] or ''
                })
                contents.append((r[23] or '')[:100] + '...')
            except Exception:
                continue
                
        if not embeddings:
            return None, None, None
            
        matrix = np.array(embeddings, dtype=np.float32)
        metrics_df = pd.DataFrame(metrics)
        metrics_df['note_id'] = note_ids
        metrics_df['date'] = dates
        metrics_df['preview'] = contents
        
        return note_ids, matrix, metrics_df
    except Exception as e:
        st.error(f"Error loading raw embeddings: {e}")
        return None, None, None


@st.cache_data(ttl=600)
def get_reduced_coordinates(dr_method, umap_neighbors, umap_metric):
    res = load_raw_embeddings_and_metrics()
    if res is None or res[1] is None:
        return None, None, None
    note_ids, matrix, metrics_df = res
    
    n_samples = matrix.shape[0]
    neighbors = min(umap_neighbors, n_samples - 1)
    neighbors = max(2, neighbors)
    
    if dr_method == "UMAP":
        try:
            import umap.umap_ as umap
            reducer = umap.UMAP(
                n_components=2,
                n_neighbors=neighbors,
                metric=umap_metric,
                random_state=42
            )
            reduced = reducer.fit_transform(matrix)
        except Exception as e:
            st.warning(f"UMAP failed ({e}). Falling back to PCA.")
            from sklearn.decomposition import PCA
            pca = PCA(n_components=2, random_state=42)
            reduced = pca.fit_transform(matrix)
    else:
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2, random_state=42)
        reduced = pca.fit_transform(matrix)
        
    return reduced, note_ids, metrics_df


def run_in_memory_clustering(matrix, reduced_2d, algo_choice, space_choice, kmeans_k, auto_k, hdbscan_min_size, hdbscan_min_samples):
    # Choose clustering space
    clustering_matrix = reduced_2d if space_choice == "2D Visual Space" else matrix
    n_samples = clustering_matrix.shape[0]
    
    if algo_choice == "K-Means":
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        
        if auto_k:
            best_k = 2
            best_score = -1.0
            best_labels = None
            max_k = min(10, n_samples - 1)
            for k in range(2, max_k + 1):
                km = KMeans(n_clusters=k, n_init=10, random_state=42)
                labels = km.fit_predict(clustering_matrix)
                score = silhouette_score(clustering_matrix, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
                    best_labels = labels
            if best_labels is None:
                best_labels = np.zeros(n_samples, dtype=int)
                best_k = 1
                best_score = 0.0
            return best_labels, best_k, round(float(best_score), 4)
        else:
            k = min(kmeans_k, n_samples - 1)
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(clustering_matrix)
            score = silhouette_score(clustering_matrix, labels) if len(set(labels)) >= 2 else 0.0
            return labels, k, round(float(score), 4)
            
    else:  # HDBSCAN
        import hdbscan
        from sklearn.metrics import silhouette_score
        
        size = min(hdbscan_min_size, n_samples // 2)
        size = max(2, size)
        
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=size,
            min_samples=max(1, hdbscan_min_samples),
            metric='euclidean' if space_choice == "2D Visual Space" else 'l2'
        )
        labels = clusterer.fit_predict(clustering_matrix)
        
        valid_mask = labels != -1
        if valid_mask.sum() >= 2 and len(set(labels[valid_mask])) >= 2:
            score = silhouette_score(clustering_matrix[valid_mask], labels[valid_mask])
        else:
            score = 0.0
            
        n_clusters = len(set(labels) - {-1})
        return labels, n_clusters, round(float(score), 4)


def render_two_way_cluster_explorer(explorer_df, cluster_col):
    st.markdown('<div class="section-header">🧭 Cluster-Diary Explorer (Two-Way)</div>', unsafe_allow_html=True)
    st.markdown("Explore your clusters from both directions: analyze the portion of themes on a given date, or find all entries belonging to a specific cluster.")
    
    if explorer_df.empty:
        st.info("No data available to explore.")
        return
        
    explorer_df = explorer_df.copy()
    explorer_df['date_dt'] = pd.to_datetime(explorer_df['date'])
    
    def clean_label(c):
        if isinstance(c, (int, float, np.integer)):
            return f"Cluster {int(c)}" if c != -1 else "Noise/Unclustered"
        return str(c)
        
    tab_date_to_cluster, tab_cluster_to_diary = st.tabs([
        "📅 Date ➡️ Clusters (Portions)", 
        "🔮 Cluster ➡️ Diaries (Browse)"
    ])
    
    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1: Date -> Clusters
    # ─────────────────────────────────────────────────────────────────────────
    with tab_date_to_cluster:
        st.markdown("##### 🔍 Portions of Each Cluster on a Selected Date")
        available_dates = sorted(explorer_df['date_dt'].dt.date.unique())
        if not available_dates:
            st.info("No dates with entries found.")
        else:
            col_sel1, col_sel2 = st.columns([2, 1])
            with col_sel1:
                selected_date = st.selectbox(
                    "Select Date to Inspect", 
                    available_dates, 
                    index=len(available_dates) - 1,
                    format_func=lambda x: x.strftime('%B %d, %Y'),
                    key="explorer_date_sel"
                )
            with col_sel2:
                window_days = st.slider(
                    "Aggregation Window (Days)", 1, 30, 7, 
                    help="Number of days around the selected date to compute the cluster portions. Useful for aggregating daily logs.",
                    key="explorer_window_sel"
                )
                
            half_window = window_days // 2
            start_dt = selected_date - datetime.timedelta(days=half_window)
            end_dt = selected_date + datetime.timedelta(days=half_window)
            
            window_df = explorer_df[(explorer_df['date_dt'].dt.date >= start_dt) & (explorer_df['date_dt'].dt.date <= end_dt)]
            
            if window_df.empty:
                st.warning(f"No entries found in the {window_days}-day window around {selected_date.strftime('%B %d, %Y')}.")
            else:
                counts = window_df[cluster_col].value_counts()
                total_in_window = len(window_df)
                
                col_chart, col_entries = st.columns([2, 3])
                
                with col_chart:
                    st.markdown(f"**Cluster Mixture ({window_days}-day window)**")
                    st.caption(f"From {start_dt.strftime('%b %d')} to {end_dt.strftime('%b %d')} · {total_in_window} entries")
                    
                    portions_df = pd.DataFrame({
                        'Cluster': counts.index,
                        'Count': counts.values,
                        'Percentage': (counts.values / total_in_window) * 100
                    })
                    portions_df['Cluster Name'] = portions_df['Cluster'].apply(clean_label)
                    
                    fig = px.pie(
                        portions_df,
                        names='Cluster Name',
                        values='Count',
                        color='Cluster Name',
                        color_discrete_sequence=CLUSTER_COLORS,
                        hole=0.4,
                        hover_data=['Percentage']
                    )
                    fig.update_traces(textinfo='percent+label', marker=dict(line=dict(color='rgba(255,255,255,0.2)', width=1)))
                    fig.update_layout(showlegend=False, height=250, margin=dict(l=10, r=10, t=10, b=10))
                    apply_theme(fig)
                    st.plotly_chart(fig, use_container_width=True)
                    
                with col_entries:
                    st.markdown(f"**Entries in Window ({total_in_window})**")
                    window_df_sorted = window_df.sort_values('date_dt', ascending=False)
                    
                    for idx, row in window_df_sorted.iterrows():
                        c_label = clean_label(row[cluster_col])
                        preview = row.get('preview', '')
                        full_content = row.get('content', '')
                        if not preview and full_content:
                            preview = full_content[:100] + '...'
                        elif not preview:
                            preview = "No text available."
                            
                        sentiment = row.get('sentiment_polarity', row.get('sentiment', 0.0))
                        words = row.get('word_count', 0)
                        date_str = row['date_dt'].strftime('%b %d, %Y')
                        
                        with st.container():
                            st.markdown(f"""
                            <div style="font-size:0.85rem; color:rgba(255,255,255,0.6); margin-top:12px; display:flex; justify-content:space-between;">
                                <span>📅 <b>{date_str}</b></span>
                                <span>🏷️ <span style="color:#a78bfa; font-weight:600;">{c_label}</span></span>
                            </div>
                            """, unsafe_allow_html=True)
                            with st.expander(preview, expanded=False):
                                st.markdown(f"<div style='font-size:0.95rem; line-height:1.5; color:rgba(255,255,255,0.9); padding: 8px 0;'>{full_content}</div>", unsafe_allow_html=True)
                                st.caption(f"📏 {words} words · 😊 Sentiment: {sentiment:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2: Cluster -> Diaries
    # ─────────────────────────────────────────────────────────────────────────
    with tab_cluster_to_diary:
        st.markdown("##### 🔮 Diaries Associated with a Specific Cluster")
        
        raw_clusters = sorted(explorer_df[cluster_col].unique())
        cluster_options = {clean_label(c): c for c in raw_clusters}
        
        selected_option = st.selectbox(
            "Select Cluster", 
            list(cluster_options.keys()),
            key="explorer_cluster_sel"
        )
        target_cluster = cluster_options[selected_option]
        
        cluster_df = explorer_df[explorer_df[cluster_col] == target_cluster]
        n_cluster_entries = len(cluster_df)
        
        if cluster_df.empty:
            st.info("No entries found in this cluster.")
        else:
            col_sort1, col_sort2 = st.columns([2, 1])
            with col_sort1:
                avg_sentiment = cluster_df['sentiment_polarity'].mean() if 'sentiment_polarity' in cluster_df.columns else (cluster_df['sentiment'].mean() if 'sentiment' in cluster_df.columns else 0.0)
                avg_words = cluster_df['word_count'].mean()
                st.markdown(f"**Cluster Profile:** `{n_cluster_entries}` entries · Avg sentiment: `{avg_sentiment:.2f}` · Avg length: `{avg_words:.0f}` words")
            with col_sort2:
                sort_by = st.selectbox(
                    "Sort Entries By",
                    ["Date (Recent First)", "Date (Oldest First)", "Word Count (High to Low)", "Sentiment (Most Positive)", "Sentiment (Most Negative)"],
                    key="explorer_cluster_sort"
                )
                
            if "Date (Recent First)" in sort_by:
                cluster_df_sorted = cluster_df.sort_values('date_dt', ascending=False)
            elif "Date (Oldest First)" in sort_by:
                cluster_df_sorted = cluster_df.sort_values('date_dt', ascending=True)
            elif "Word Count (High to Low)" in sort_by:
                cluster_df_sorted = cluster_df.sort_values('word_count', ascending=False)
            elif "Sentiment (Most Positive)" in sort_by:
                col_name = 'sentiment_polarity' if 'sentiment_polarity' in cluster_df.columns else 'sentiment'
                cluster_df_sorted = cluster_df.sort_values(col_name, ascending=False)
            elif "Sentiment (Most Negative)" in sort_by:
                col_name = 'sentiment_polarity' if 'sentiment_polarity' in cluster_df.columns else 'sentiment'
                cluster_df_sorted = cluster_df.sort_values(col_name, ascending=True)
                
            st.markdown("---")
            
            for idx, row in cluster_df_sorted.iterrows():
                preview = row.get('preview', '')
                full_content = row.get('content', '')
                if not preview and full_content:
                    preview = full_content[:100] + '...'
                elif not preview:
                    preview = "No text available."
                    
                sentiment = row.get('sentiment_polarity', row.get('sentiment', 0.0))
                words = row.get('word_count', 0)
                date_str = row['date_dt'].strftime('%b %d, %Y')
                
                with st.container():
                    st.markdown(f"""
                    <div style="font-size:0.85rem; color:rgba(255,255,255,0.6); margin-top:12px;">
                        📅 <b>{date_str}</b> · 📏 {words} words · 😊 Sentiment: {sentiment:.2f}
                    </div>
                    """, unsafe_allow_html=True)
                    with st.expander(preview, expanded=False):
                        st.markdown(f"<div style='font-size:0.95rem; line-height:1.5; color:rgba(255,255,255,0.9); padding: 8px 0;'>{full_content}</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PLOTLY THEME
# ─────────────────────────────────────────────────────────────────────────────

PLOTLY_THEME = {
    'paper_bgcolor': 'rgba(0,0,0,0)',
    'plot_bgcolor': 'rgba(255,255,255,0.03)',
    'font': {'color': 'rgba(255,255,255,0.8)', 'family': 'Inter'},
    'xaxis': {'gridcolor': 'rgba(255,255,255,0.07)', 'linecolor': 'rgba(255,255,255,0.1)'},
    'yaxis': {'gridcolor': 'rgba(255,255,255,0.07)', 'linecolor': 'rgba(255,255,255,0.1)'},
    'legend': {'bgcolor': 'rgba(0,0,0,0)', 'bordercolor': 'rgba(255,255,255,0.1)'},
}

CLUSTER_COLORS = px.colors.qualitative.Vivid + px.colors.qualitative.Pastel

def apply_theme(fig):
    fig.update_layout(**PLOTLY_THEME)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("# 📓 Diary Analytics")
    st.markdown("---")

    st.markdown("### 🔧 Pipeline Controls")

    if st.button("▶ Run Full Analysis Pipeline"):
        with st.spinner("Running NLP analysis..."):
            try:
                import nlp_analysis
                import db as db_module
                db_module.init_db()
                n = nlp_analysis.run_analysis_pipeline(DB_PATH)
                st.success(f"✅ Analyzed {n} new entries!")
            except Exception as e:
                st.error(f"Error: {e}")
        st.cache_data.clear()
        st.rerun()

    if st.button("🔄 Re-run All Analysis (Force)"):
        with st.spinner("Re-analyzing all entries..."):
            try:
                import nlp_analysis
                n = nlp_analysis.run_analysis_pipeline(DB_PATH, force_rerun=True)
                st.success(f"✅ Re-analyzed {n} entries!")
            except Exception as e:
                st.error(f"Error: {e}")
        st.cache_data.clear()
        st.rerun()

    if st.button("🔮 Run Dynamic Clustering"):
        with st.spinner("Clustering embeddings..."):
            try:
                import dynamic_clustering
                result = dynamic_clustering.run_clustering_pipeline(DB_PATH)
                if result.get('status') == 'success':
                    st.success(
                        f"✅ HDBSCAN: {result['hdbscan']['n_clusters']} clusters\n"
                        f"K-Means: K={result['kmeans']['optimal_k']} (sil={result['kmeans']['silhouette_score']:.2f})"
                    )
                else:
                    st.warning(result.get('reason', 'Skipped'))
            except Exception as e:
                st.error(f"Error: {e}")
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📅 Date Filter")
    df_all, _, _ = load_all_data()
    if not df_all.empty and 'date' in df_all.columns:
        min_date = df_all['date'].min().date()
        max_date = df_all['date'].max().date()
        date_range = st.date_input(
            "Select range",
            value=(min_date, max_date),
            min_value=min_date, max_value=max_date
        )
    else:
        date_range = None

    st.markdown("---")
    st.markdown("### 📊 Metric Smoothing")
    smoothing = st.slider("Rolling window (days)", 1, 14, 3)
    
    st.markdown("---")
    st.caption("💡 Run the pipeline first if no data appears.")


# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────

df_raw, runs_df, corr_df = load_all_data()

if df_raw.empty:
    st.warning("⚠️ No analyzed data found. Use the sidebar controls to run the pipeline first.")
    st.stop()

# Apply date filter
df = df_raw.copy()
if date_range and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1])
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

if df.empty:
    st.warning("No data in selected date range.")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("# 📓 Personal Diary Analytics")
st.markdown(f"*Analyzing **{len(df)}** entries · {df['date'].min().strftime('%b %d, %Y')} to {df['date'].max().strftime('%b %d, %Y')}*")
st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: KPI OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">📊 Overview</div>', unsafe_allow_html=True)

kpi_cols = st.columns(6)

kpis = [
    ("Total Entries", len(df), None, "📝"),
    ("Avg Words/Entry", f"{df['word_count'].mean():.0f}", None, "📏"),
    ("Avg Sentiment", f"{df['sentiment_polarity'].mean():.2f}", 
     "😊 positive" if df['sentiment_polarity'].mean() > 0.1 else ("😔 negative" if df['sentiment_polarity'].mean() < -0.1 else "😐 neutral"), "💭"),
    ("Avg Creativity", f"{df['creativity_score'].mean():.2f}", None, "✨"),
    ("Avg Word Diversity", f"{df['word_diversity'].mean():.2f}", None, "📚"),
    ("Grammar Score", f"{df['grammatical_correctness_score'].mean():.2f}", None, "✅"),
]

for col, (label, value, delta, icon) in zip(kpi_cols, kpis):
    with col:
        delta_html = f'<div class="kpi-delta {"delta-pos" if delta and "pos" in str(delta).lower() else "delta-neg"}">{delta}</div>' if delta else ""
        st.markdown(f"""
        <div class="kpi-card">
            <div style="font-size:1.8rem;margin-bottom:4px">{icon}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-label">{label}</div>
            {delta_html}
        </div>
        """, unsafe_allow_html=True)

st.markdown("")  # spacer
with st.expander("❓ What do these Overview metrics mean?"):
    st.markdown("""
    * **Total Entries**: Total count of unique diary logs analyzed in your database.
    * **Avg Words/Entry**: Average number of words in your daily narrative.
    * **Avg Sentiment**: Overall emotional tone of your writing, from **-1.0 (very negative)** to **+1.0 (very positive)**. Around 0.0 is neutral.
    * **Avg Creativity**: A composite score (0 to 1) reflecting vocabulary richness (MTLD), use of rare words (Hapax Legomena), and variance in sentence length.
    * **Avg Word Diversity (MTLD)**: The Measure of Textual Lexical Diversity (MTLD). Unlike simple TTR, MTLD is mathematically robust and not biased by text length. Higher scores indicate a richer, more varied vocabulary.
    * **Grammar Score**: Assesses sentence structural completeness. Sentences without a root verb (e.g. incomplete thoughts) lower this score.
    """)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: LEXICAL & STYLE TRENDS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">📝 Lexical & Style Trends</div>', unsafe_allow_html=True)
st.markdown("Visualizes the length, richness, and complexity of your writing style over time. Use the sidebar to adjust smoothing.", help="Word count tracks length. Word diversity (MTLD) tracks unique vocabulary usage. Hapax Legomena tracks the proportion of unique words used only once (indicating vocabulary wealth). Sentence length variance tracks how much you vary sentence lengths (indicating stylistic complexity).")

col1, col2 = st.columns(2)

with col1:
    # Word count and diversity over time
    df_sorted = df.sort_values('date')
    df_sorted['word_count_smooth'] = df_sorted['word_count'].rolling(smoothing, min_periods=1).mean()
    df_sorted['word_diversity_smooth'] = df_sorted['word_diversity'].rolling(smoothing, min_periods=1).mean()

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=df_sorted['date'], y=df_sorted['word_count'],
        name='Word Count', marker_color='rgba(96,165,250,0.3)',
        showlegend=True
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['word_count_smooth'],
        name=f'Word Count ({smoothing}d avg)', 
        line=dict(color='#60a5fa', width=2.5)
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['word_diversity_smooth'],
        name=f'Word Diversity (MTLD)', 
        line=dict(color='#a78bfa', width=2.5, dash='dot')
    ), secondary_y=True)
    fig.update_layout(title="Word Count & Lexical Diversity Over Time", **PLOTLY_THEME)
    fig.update_yaxes(title_text="Word Count", secondary_y=False)
    fig.update_yaxes(title_text="Lexical Diversity (MTLD)", secondary_y=True)
    apply_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Creativity and hapax legomena
    df_sorted['creativity_smooth'] = df_sorted['creativity_score'].rolling(smoothing, min_periods=1).mean()
    df_sorted['hapax_smooth'] = df_sorted['hapax_legomena_ratio'].rolling(smoothing, min_periods=1).mean()

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['creativity_smooth'],
        name='Creativity Score', fill='tozeroy',
        fillcolor='rgba(167,139,250,0.15)', line=dict(color='#a78bfa', width=2.5)
    ))
    fig2.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['hapax_smooth'],
        name='Hapax Legomena Ratio', line=dict(color='#f472b6', width=2, dash='dot')
    ))
    fig2.update_layout(title="Creativity & Vocabulary Richness", **PLOTLY_THEME)
    apply_theme(fig2)
    st.plotly_chart(fig2, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: GRAMMATICAL STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">📐 Grammatical Structure Analysis</div>', unsafe_allow_html=True)
st.markdown("Analyzes sentence structures by tracking parts-of-speech (POS) and grammar correctness.", help="Noun ratio indicates a focus on concepts/things. Verb ratio indicates action/movement. Adjective and adverb ratios show descriptive intensity. First-person pronoun ratio ('I', 'me', 'my') indicates self-focus. Correctness checks if sentences have complete clauses with root verbs.")

col1, col2 = st.columns(2)

with col1:
    # POS Ratios Radar / Bar over time
    pos_cols = ['verb_ratio', 'noun_ratio', 'adjective_ratio', 'adverb_ratio', 'first_person_pronoun_ratio']
    pos_means = df[pos_cols].mean()
    pos_labels = ['Verbs', 'Nouns', 'Adjectives', 'Adverbs', '1st Person Pronouns']

    fig3 = go.Figure(go.Bar(
        x=pos_labels,
        y=pos_means.values,
        marker=dict(
            color=['#60a5fa', '#34d399', '#a78bfa', '#f472b6', '#fb923c'],
            opacity=0.85
        ),
        text=[f"{v:.1%}" for v in pos_means.values],
        textposition='outside'
    ))
    fig3.update_layout(title="Average POS Distribution", **PLOTLY_THEME)
    fig3.update_yaxes(tickformat='.0%')
    apply_theme(fig3)
    st.plotly_chart(fig3, use_container_width=True)

with col2:
    # Grammatical correctness & 1st person pronoun trend
    df_sorted['grammar_smooth'] = df_sorted['grammatical_correctness_score'].rolling(smoothing, min_periods=1).mean()
    df_sorted['firstperson_smooth'] = df_sorted['first_person_pronoun_ratio'].rolling(smoothing, min_periods=1).mean()

    fig4 = make_subplots(specs=[[{"secondary_y": True}]])
    fig4.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['grammar_smooth'],
        name='Grammatical Correctness', fill='tozeroy',
        fillcolor='rgba(52,211,153,0.1)', line=dict(color='#34d399', width=2.5)
    ), secondary_y=False)
    fig4.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['firstperson_smooth'],
        name='1st Person Pronoun Usage', line=dict(color='#fb923c', width=2, dash='dot')
    ), secondary_y=True)
    fig4.update_layout(title="Grammar Quality & Self-Reference Over Time", **PLOTLY_THEME)
    apply_theme(fig4)
    st.plotly_chart(fig4, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: EMOTION & SENTIMENT
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">💭 Emotion & Sentiment</div>', unsafe_allow_html=True)
st.markdown("Tracks overall sentiment polarity, discrete emotions, and emotional variety.", help="Polarity measures positive vs negative tone. Joy, Sadness, Anger, Fear, and Surprise distributions are extracted via transformer models. Emotion Diversity calculates the average distance between emotion words in the embedding space; a higher score represents a richer, more diverse spectrum of concurrent emotions.")

col1, col2 = st.columns(2)

with col1:
    # Stacked emotion area chart
    emotions = ['emotion_joy', 'emotion_sadness', 'emotion_anger', 'emotion_fear', 'emotion_surprise']
    emotion_labels = ['Joy', 'Sadness', 'Anger', 'Fear', 'Surprise']
    emotion_colors = ['#34d399', '#60a5fa', '#f87171', '#a78bfa', '#fbbf24']
    
    fig5 = go.Figure()
    for emo, label, color in zip(emotions, emotion_labels, emotion_colors):
        if emo in df_sorted.columns:
            smooth_val = df_sorted[emo].rolling(smoothing, min_periods=1).mean()
            fig5.add_trace(go.Scatter(
                x=df_sorted['date'], y=smooth_val,
                name=label, stackgroup='one',
                fillcolor=color.replace(')', ', 0.6)').replace('rgb', 'rgba') if color.startswith('rgb') else color,
                line=dict(color=color, width=1)
            ))
    fig5.update_layout(title="Emotion Distribution Over Time (Stacked)", **PLOTLY_THEME)
    apply_theme(fig5)
    st.plotly_chart(fig5, use_container_width=True)

with col2:
    # Sentiment polarity + emotion diversity
    df_sorted['sentiment_smooth'] = df_sorted['sentiment_polarity'].rolling(smoothing, min_periods=1).mean()
    df_sorted['emotion_div_smooth'] = df_sorted['emotion_diversity'].rolling(smoothing, min_periods=1).mean()

    fig6 = make_subplots(specs=[[{"secondary_y": True}]])
    # Coloured background for positive/negative sentiment
    fig6.add_hrect(y0=0, y1=1, line_width=0, fillcolor="rgba(52,211,153,0.05)", secondary_y=False)
    fig6.add_hrect(y0=-1, y1=0, line_width=0, fillcolor="rgba(248,113,113,0.05)", secondary_y=False)
    fig6.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['sentiment_smooth'],
        name='Sentiment Polarity', fill='tozeroy',
        fillcolor='rgba(96,165,250,0.1)', line=dict(color='#60a5fa', width=2.5)
    ), secondary_y=False)
    fig6.add_trace(go.Scatter(
        x=df_sorted['date'], y=df_sorted['emotion_div_smooth'],
        name='Emotion Diversity', line=dict(color='#f472b6', width=2, dash='dot')
    ), secondary_y=True)
    fig6.update_layout(title="Sentiment Polarity & Emotion Diversity", **PLOTLY_THEME)
    fig6.update_yaxes(title_text="Sentiment (-1 to 1)", secondary_y=False)
    fig6.update_yaxes(title_text="Emotion Diversity", secondary_y=True)
    apply_theme(fig6)
    st.plotly_chart(fig6, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: CLUSTERING
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">🔮 Dynamic Clustering</div>', unsafe_allow_html=True)
st.markdown("Visualizes the semantic structures of your thoughts by mapping notes in a 2D space.", help="Notes are mapped in 2D using UMAP dimensionality reduction on note embeddings. Points that are close together share highly similar semantic topics, moods, or vocabulary. HDBSCAN finds organic, dense shapes (labeling outliers as Noise). K-Means segments notes into K partitions.")

# Select clustering mode
clustering_mode = st.radio(
    "Choose how to define clusters:", 
    ["Saved Database Runs (Static) 💾", "Interactive Clustering Playground 🎮"],
    horizontal=True,
    help="Interactive Playground lets you adjust clustering algorithms, parameters, and dimensions on the fly. Database Runs shows the results of the last pipeline execution."
)

if clustering_mode == "Saved Database Runs (Static) 💾":
    # Clustering summary
    if not runs_df.empty:
        latest_runs = runs_df.head(2)
        run_cols = st.columns(len(latest_runs))
        for col, (_, run) in zip(run_cols, latest_runs.iterrows()):
            with col:
                alg = run.get('algorithm', '?').upper()
                sil = run.get('silhouette_score', 0) or 0
                sil_color = "#34d399" if sil > 0.5 else ("#fbbf24" if sil > 0.25 else "#f87171")
                st.markdown(f"""
                <div class="kpi-card">
                    <div style="font-size:1.2rem;color:rgba(255,255,255,0.6)">{alg}</div>
                    <div class="kpi-value">{run.get('n_clusters', '?')}</div>
                    <div class="kpi-label">Clusters</div>
                    <div style="color:{sil_color};font-size:0.9rem;margin-top:6px">
                        Silhouette: {sil:.3f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        cluster_view = st.radio("Color by", ["HDBSCAN", "K-Means"], horizontal=True, key="cluster_view")
    with col2:
        st.markdown("")  # spacer

    # Load 2D scatter
    with st.spinner("Preparing cluster visualization..."):
        scatter_df = load_embeddings_2d()

    if not scatter_df.empty:
        color_col = 'hdbscan_cluster' if cluster_view == "HDBSCAN" else 'kmeans_cluster'
        
        fig7 = px.scatter(
            scatter_df,
            x='x', y='y',
            color=color_col,
            hover_data={'x': False, 'y': False, 'date': True, 'sentiment': ':.2f', 'word_count': True, 'preview': True},
            title=f"Diary Entry Clusters ({cluster_view})",
            color_discrete_sequence=CLUSTER_COLORS,
            size_max=12,
        )
        fig7.update_traces(marker=dict(size=9, opacity=0.8, line=dict(width=0.5, color='rgba(255,255,255,0.3)')))
        fig7.update_layout(**PLOTLY_THEME)
        apply_theme(fig7)
        st.plotly_chart(fig7, use_container_width=True)

        # Cluster timeline
        cluster_col_db = 'hdbscan_cluster_id' if cluster_view == "HDBSCAN" else 'kmeans_cluster_id'
        if cluster_col_db in df.columns and df[cluster_col_db].notna().any():
            df_sorted = df.sort_values('date').copy()
            df_sorted['cluster_label'] = df_sorted[cluster_col_db].apply(
                lambda x: f"Cluster {int(x)}" if x is not None and x != -1 else "Noise/Unclustered"
            )
            
            fig8 = px.scatter(
                df_sorted,
                x='date', y=cluster_col_db,
                color='cluster_label',
                size='word_count', 
                hover_data=['date', 'word_count', 'sentiment_polarity'],
                title=f"Cluster Assignment Over Time ({cluster_view})",
                color_discrete_sequence=CLUSTER_COLORS,
                labels={cluster_col_db: 'Cluster ID', 'cluster_label': 'Cluster Name'}
            )
            fig8.update_layout(**PLOTLY_THEME)
            apply_theme(fig8)
            st.plotly_chart(fig8, use_container_width=True)
    else:
        st.info("No cluster visualization available yet. Run clustering first.")

    # SECTION 6: CORRELATIONS (Static)
    st.markdown('<div class="section-header">📈 Metric–Cluster Correlations</div>', unsafe_allow_html=True)
    st.markdown("Identifies the statistical features that characterize and separate each cluster.", help="Pearson correlation coefficients show which metrics are associated with cluster membership. Positive r values indicate entries in the cluster score higher on that metric; negative r values mean they score lower.")

    with st.expander("ℹ️ How to interpret these correlations (What do they mean?)"):
        st.markdown("""
        ### Identifying Cluster Features
        A **cluster correlation** shows which metrics (like sentiment, subjectivity, or word count) are statistically associated with a note being in that cluster. This answers the question: *what makes a cluster unique?*
        
        * **Positive Correlation ($r > 0$)**: Notes in this cluster tend to have **significantly higher** values for this metric compared to notes in other clusters. 
        * **Negative Correlation ($r < 0$)**: Notes in this cluster tend to have **significantly lower** values for this metric compared to notes in other clusters.
        * **p-value ($p$)**: Measures statistical significance. A value below **$0.05$** means the relationship is statistically valid and highly unlikely to be a random fluke.
        """)

    if not corr_df.empty:
        col1, col2 = st.columns([2, 1])
        with col1:
            try:
                pivot = corr_df.pivot_table(
                    index='metric_name', 
                    columns='cluster_id', 
                    values='correlation_coefficient', 
                    aggfunc='mean'
                ).fillna(0)
                
                fig9 = px.imshow(
                    pivot,
                    color_continuous_scale='RdBu_r',
                    color_continuous_midpoint=0,
                    title="Correlation Heatmap: Metrics × Clusters",
                    aspect='auto',
                    text_auto='.2f'
                )
                fig9.update_layout(**PLOTLY_THEME)
                apply_theme(fig9)
                st.plotly_chart(fig9, use_container_width=True)
            except Exception:
                st.dataframe(corr_df[['metric_name', 'cluster_id', 'correlation_coefficient', 'p_value']].head(20))

        with col2:
            st.markdown("**Top Correlations (|r| > 0.3)**")
            strong = corr_df[abs(corr_df['correlation_coefficient']) > 0.3].head(15)
            if not strong.empty:
                for _, row in strong.iterrows():
                    r = row['correlation_coefficient']
                    color = "#34d399" if r > 0 else "#f87171"
                    arrow = "↑" if r > 0 else "↓"
                    st.markdown(f"""
                    <div class="info-box" style="border-left-color:{color}">
                        {arrow} <b>{row['metric_name']}</b><br>
                        Cluster {row['cluster_id']} · r={r:.2f} · p={row['p_value']:.3f}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No strong correlations found yet.")
    else:
        st.info("Run clustering to see metric-cluster correlations.")
        
    # Daily Explorer (Static)
    render_two_way_cluster_explorer(df, cluster_col_db)

else:
    # 🎮 Interactive Clustering Playground 🎮
    st.markdown('<div class="info-box"><strong>Interactive Clustering Playground</strong>: Adjust dimension reduction and clustering settings to see results dynamically. Learn how changing hyperparameters affects cluster shapes, sizes, and metric correlations. Click the <strong>Save to DB</strong> button to persist your configuration.</div>', unsafe_allow_html=True)
    
    # Control Panel Layout
    st.markdown("### ⚙️ Playground Hyperparameters")
    p_col1, p_col2, p_col3 = st.columns(3)
    
    with p_col1:
        st.markdown("##### 📐 Dimensionality Reduction")
        dr_method = st.selectbox(
            "Reduction Method", ["UMAP", "PCA"], index=0,
            help="UMAP preserves non-linear shapes well. PCA is a linear projection. Highly recommended to use UMAP for embeddings."
        )
        if dr_method == "UMAP":
            umap_neighbors = st.slider(
                "UMAP Neighbors", 2, 40, 15,
                help="Controls local vs global structure. Lower values focus on local neighbors; higher values map the overall global distribution."
            )
            umap_metric = st.selectbox(
                "UMAP Metric", ["cosine", "euclidean", "correlation"], index=0,
                help="The distance metric used to calculate similarity. 'cosine' is best for sentence embeddings."
            )
        else:
            umap_neighbors = 15
            umap_metric = "cosine"

    with p_col2:
        st.markdown("##### 🔮 Clustering Algorithm")
        algo_choice = st.selectbox("Algorithm", ["K-Means", "HDBSCAN"], index=0)
        space_choice = st.selectbox(
            "Clustering Space", ["2D Visual Space", "Raw Embedding Space"], index=0,
            help="Determine whether to cluster points based on their 2D coordinates on the plot, or directly in the original high-dimensional embedding space."
        )

    with p_col3:
        st.markdown("##### 🎛️ Algorithm Parameters")
        if algo_choice == "K-Means":
            auto_k = st.checkbox("Auto-detect optimal K", value=False, help="Uses the Silhouette Score to pick the best number of clusters automatically.")
            if auto_k:
                kmeans_k = 4
            else:
                kmeans_k = st.slider("Number of Clusters (K)", 2, 10, 4)
        else:
            auto_k = False
            kmeans_k = 4
            hdbscan_min_size = st.slider(
                "Min Cluster Size", 2, 20, 5,
                help="The minimum number of points required to form an organic cluster."
            )
            hdbscan_min_samples = st.slider(
                "Min Samples (Conservative)", 1, 10, 1,
                help="Higher values make clustering more conservative, resulting in more points classified as noise/outliers."
            )

    # 1. Run Dimension Reduction
    dr_res = get_reduced_coordinates(dr_method, umap_neighbors, umap_metric)
    if dr_res[0] is not None:
        reduced_2d, note_ids, metrics_df = dr_res
        
        # Get raw embedding matrix
        _, matrix, _ = load_raw_embeddings_and_metrics()
        
        # 2. Run Clustering
        with st.spinner("Clustering..."):
            if algo_choice == "K-Means":
                labels, n_clusters, score = run_in_memory_clustering(
                    matrix, reduced_2d, algo_choice, space_choice, kmeans_k, auto_k, 5, 1
                )
            else:
                labels, n_clusters, score = run_in_memory_clustering(
                    matrix, reduced_2d, algo_choice, space_choice, 4, False, hdbscan_min_size, hdbscan_min_samples
                )
        
        # KPI Card for Playground Results
        res_col1, res_col2, res_col3 = st.columns(3)
        with res_col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div style="font-size:1.1rem;color:rgba(255,255,255,0.6)">CLUSTERS FOUND</div>
                <div class="kpi-value">{n_clusters}</div>
                <div style="font-size:0.85rem;color:rgba(255,255,255,0.5);margin-top:6px">
                    Algorithm: {algo_choice}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with res_col2:
            sil_color = "#34d399" if score > 0.5 else ("#fbbf24" if score > 0.25 else "#f87171")
            st.markdown(f"""
            <div class="kpi-card">
                <div style="font-size:1.1rem;color:rgba(255,255,255,0.6)">SILHOUETTE SCORE</div>
                <div class="kpi-value" style="color:{sil_color};background:none;-webkit-text-fill-color:{sil_color}">{score:.3f}</div>
                <div style="font-size:0.85rem;color:rgba(255,255,255,0.5);margin-top:6px">
                    Higher = Better defined clusters
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with res_col3:
            st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
            save_clicked = st.button("💾 Persist/Save Clusters to DB", help="Overwrite saved cluster labels in your database with these custom playground parameters.")
            
        # 3. Save to database if clicked
        metrics_records = metrics_df.to_dict('records')
        correlations = dynamic_clustering.compute_cluster_correlations(labels, metrics_records, 'interactive')
        summary = dynamic_clustering.summarize_clusters(labels, metrics_records)

        if save_clicked:
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                run_id = f"interactive_{ts}"
                algo_name = f"kmeans_interactive_k{n_clusters}" if algo_choice == "K-Means" else f"hdbscan_interactive_size{hdbscan_min_size}"
                
                # Save run metadata
                cursor.execute("""
                    INSERT OR REPLACE INTO clustering_runs 
                    (run_id, algorithm, n_clusters, silhouette_score, notes_analyzed, cluster_summary)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (run_id, algo_name, int(n_clusters), float(score), len(note_ids), json.dumps(summary)))
                
                # Update note_analysis
                col_name = 'kmeans_cluster_id' if algo_choice == "K-Means" else 'hdbscan_cluster_id'
                for note_id, label in zip(note_ids, labels):
                    cursor.execute(
                        f"UPDATE note_analysis SET {col_name} = ? WHERE note_id = ?",
                        (int(label), note_id)
                    )
                
                # Save correlations
                for corr in correlations:
                    cursor.execute("""
                        INSERT INTO cluster_correlations 
                        (run_id, cluster_id, metric_name, correlation_coefficient, p_value)
                        VALUES (?, ?, ?, ?, ?)
                    """, (run_id, corr['cluster_id'], corr['metric_name'],
                          corr['correlation_coefficient'], corr['p_value']))
                
                conn.commit()
                conn.close()
                st.success("✅ Saved interactive clusters to database successfully! Redrawing...")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save clusters: {e}")

        # 4. Prepare Playground Scatter DataFrame
        str_labels = [f"Cluster {int(l)}" if l != -1 else "Noise/Outliers" for l in labels]
        
        playground_df = pd.DataFrame({
            'note_id': note_ids,
            'date': metrics_df['date'],
            'x': reduced_2d[:, 0],
            'y': reduced_2d[:, 1],
            'cluster': str_labels,
            'sentiment': metrics_df['sentiment_polarity'],
            'word_count': metrics_df['word_count'],
            'preview': metrics_df['preview'],
            'content': metrics_df['content']
        })
        
        # Plot Scatter
        fig_play = px.scatter(
            playground_df,
            x='x', y='y',
            color='cluster',
            hover_data={'x': False, 'y': False, 'date': True, 'sentiment': ':.2f', 'word_count': True, 'preview': True},
            title=f"Interactive Cluster Plot ({algo_choice} on {space_choice})",
            color_discrete_sequence=CLUSTER_COLORS,
            size_max=12,
        )
        fig_play.update_traces(marker=dict(size=9, opacity=0.8, line=dict(width=0.5, color='rgba(255,255,255,0.3)')))
        fig_play.update_layout(**PLOTLY_THEME)
        apply_theme(fig_play)
        st.plotly_chart(fig_play, use_container_width=True)

        # Plot Timeline
        playground_df_sorted = playground_df.sort_values('date').copy()
        
        fig_time = px.scatter(
            playground_df_sorted,
            x='date', y='cluster',
            color='cluster',
            size='word_count', 
            hover_data=['date', 'word_count', 'sentiment'],
            title="Interactive Cluster Assignment Over Time",
            color_discrete_sequence=CLUSTER_COLORS,
            labels={'cluster': 'Cluster Label'}
        )
        fig_time.update_layout(**PLOTLY_THEME)
        apply_theme(fig_time)
        st.plotly_chart(fig_time, use_container_width=True)

        # 5. Interactive Metric-Cluster Correlations
        st.markdown('<div class="section-header">📈 Interactive Metric–Cluster Correlations</div>', unsafe_allow_html=True)
        st.markdown("Identifies the statistical features that characterize and separate each interactive cluster.", help="Calculated dynamically using Pearson correlation coefficients on the active playground clusters.")

        if correlations:
            interactive_corr_df = pd.DataFrame(correlations)
            col1, col2 = st.columns([2, 1])
            with col1:
                try:
                    pivot = interactive_corr_df.pivot_table(
                        index='metric_name', 
                        columns='cluster_id', 
                        values='correlation_coefficient', 
                        aggfunc='mean'
                    ).fillna(0)
                    
                    fig_heat = px.imshow(
                        pivot,
                        color_continuous_scale='RdBu_r',
                        color_continuous_midpoint=0,
                        title="Interactive Heatmap: Metrics × Clusters",
                        aspect='auto',
                        text_auto='.2f'
                    )
                    fig_heat.update_layout(**PLOTLY_THEME)
                    apply_theme(fig_heat)
                    st.plotly_chart(fig_heat, use_container_width=True)
                except Exception as e:
                    st.write("Could not pivot heatmap, showing raw table.", e)
                    st.dataframe(interactive_corr_df)
                    
            with col2:
                st.markdown("**Top Correlations (|r| > 0.3)**")
                strong = interactive_corr_df[abs(interactive_corr_df['correlation_coefficient']) > 0.3].head(15)
                if not strong.empty:
                    for _, row in strong.iterrows():
                        r = row['correlation_coefficient']
                        color = "#34d399" if r > 0 else "#f87171"
                        arrow = "↑" if r > 0 else "↓"
                        st.markdown(f"""
                        <div class="info-box" style="border-left-color:{color}">
                            {arrow} <b>{row['metric_name']}</b><br>
                            Cluster {row['cluster_id']} · r={r:.2f} · p={row['p_value']:.3f}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No strong correlations found yet.")
        else:
            st.info("Not enough data to calculate interactive correlations.")
            
        # 6. Interactive Cluster Summaries
        with st.expander("📋 Interactive Cluster Metric Averages"):
            st.markdown("Average NLP and logged metrics for each interactive cluster:")
            summary_records = []
            for c_id, c_data in summary.items():
                row_data = {'Cluster ID': f"Cluster {c_id}" if c_id != 'noise' else "Noise"}
                for k, v in c_data.items():
                    if k not in ['date_range']:
                        row_data[k] = v
                summary_records.append(row_data)
            if summary_records:
                st.dataframe(pd.DataFrame(summary_records).set_index('Cluster ID'))
            else:
                st.info("No summaries available.")
                
        # 7. Daily Explorer (Interactive)
        render_two_way_cluster_explorer(playground_df, 'cluster')
                
    else:
        st.error("Could not run dimension reduction. Ensure notes have embeddings.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: AI EVALUATION PANEL
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">🤖 AI Evaluation Panel</div>', unsafe_allow_html=True)

st.markdown("""
<div class="ai-panel">
<p style="color:rgba(255,255,255,0.7);margin:0 0 12px 0">
The AI Evaluation Panel uses <strong>Antigravity Agent</strong> to review the mathematical correctness 
of the analysis outputs and identify psychological patterns. It falls back to a rule-based evaluation 
if the SDK is not installed.
</p>
</div>
""", unsafe_allow_html=True)

st.markdown("")

eval_col1, eval_col2 = st.columns([1, 3])

with eval_col1:
    run_eval = st.button("🚀 Run AI Evaluation")

with eval_col2:
    st.markdown('<div class="info-box">This will spawn an AI agent to review your analysis. Results appear below.</div>', 
                unsafe_allow_html=True)

if run_eval:
    with st.spinner("Running AI evaluation... (this may take 30–60 seconds)"):
        try:
            import ai_evaluator
            report = ai_evaluator.run_ai_evaluation(DB_PATH)
            st.session_state['ai_report'] = report
            st.session_state['ai_report_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            st.error(f"Evaluation failed: {e}")

if 'ai_report' in st.session_state:
    st.markdown(f"*Last evaluated: {st.session_state.get('ai_report_time', '')}*")
    with st.container():
        st.markdown(st.session_state['ai_report'])


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "*Personal Diary Analytics · Data stays local · Built with Streamlit & Plotly*",
    help="All your data is processed locally. Nothing is sent to the cloud except when the AI evaluation calls an external API."
)
