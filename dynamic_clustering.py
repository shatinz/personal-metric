"""
dynamic_clustering.py
=====================
Performs dynamic, repeatable clustering on diary note embeddings.

Features:
  - Dual-algorithm: HDBSCAN (density, finds organic shapes) 
                  + K-Means (with silhouette score to pick optimal K)
  - Reduces embeddings to 2D/3D with UMAP for visualization
  - Computes Pearson correlations between cluster membership and NLP metrics
  - Saves all run results and correlations to the DB (idempotent, repeatable)
  - Generates a structured evaluation summary per run
"""

import sqlite3
import json
import uuid
import logging
import datetime
from typing import Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LAZY IMPORTS
# ─────────────────────────────────────────────────────────────────────────────

def _import_clustering_libs():
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.decomposition import PCA
        import hdbscan
        import umap.umap_ as umap
        return KMeans, silhouette_score, PCA, hdbscan, umap
    except ImportError as e:
        raise ImportError(
            f"Missing clustering dependencies: {e}\n"
            "Install with: pip install hdbscan umap-learn scikit-learn"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────

def load_embeddings_and_metrics(db_path: str):
    """
    Loads all notes that have both:
      1. A valid embedding (BLOB) in `notes`
      2. An NLP analysis record in `note_analysis`
    Returns (note_ids, embeddings_matrix, metrics_df)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            n.id, n.date, n.embedding,
            na.word_count, na.word_diversity, na.sentiment_polarity,
            na.sentiment_subjectivity, na.emotion_joy, na.emotion_sadness,
            na.emotion_anger, na.emotion_fear, na.emotion_surprise,
            na.emotion_diversity, na.creativity_score, na.verb_ratio,
            na.noun_ratio, na.adjective_ratio, na.first_person_pronoun_ratio,
            na.grammatical_correctness_score, na.hapax_legomena_ratio,
            n.mood, n.energy, n.focus
        FROM notes n
        INNER JOIN note_analysis na ON n.id = na.note_id
        WHERE n.embedding IS NOT NULL
        ORDER BY n.date
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return [], np.array([]), []

    note_ids = []
    embeddings = []
    metrics_records = []

    for row in rows:
        blob = row['embedding']
        if blob is None:
            continue
        try:
            vec = np.frombuffer(blob, dtype=np.float32)
            if vec.shape[0] == 0:
                continue
        except Exception:
            continue

        note_ids.append(row['id'])
        embeddings.append(vec)

        rec = {k: row[k] for k in row.keys() if k not in ('embedding', 'id')}
        rec['note_id'] = row['id']
        metrics_records.append(rec)

    if not embeddings:
        return [], np.array([]), []

    # Ensure all embeddings have same shape (take first shape as reference)
    ref_shape = embeddings[0].shape[0]
    valid_indices = [i for i, e in enumerate(embeddings) if e.shape[0] == ref_shape]
    
    note_ids     = [note_ids[i] for i in valid_indices]
    embeddings   = [embeddings[i] for i in valid_indices]
    metrics_records = [metrics_records[i] for i in valid_indices]

    matrix = np.array(embeddings, dtype=np.float32)
    return note_ids, matrix, metrics_records


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSIONALITY REDUCTION
# ─────────────────────────────────────────────────────────────────────────────

def reduce_dimensions(matrix: np.ndarray, n_components: int = 2, method: str = 'umap'):
    """
    Reduces high-dim embedding matrix to 2D or 3D for visualization and clustering.
    Falls back to PCA if UMAP is unavailable.
    """
    KMeans, silhouette_score, PCA, hdbscan_lib, umap_lib = _import_clustering_libs()
    
    n_samples = matrix.shape[0]
    
    if method == 'umap' and umap_lib is not None:
        try:
            reducer = umap_lib.UMAP(
                n_components=n_components,
                n_neighbors=min(15, n_samples - 1),
                min_dist=0.1,
                metric='cosine',
                random_state=42
            )
            return reducer.fit_transform(matrix)
        except Exception as e:
            logger.warning(f"UMAP failed ({e}), falling back to PCA.")

    # PCA fallback
    n_comp = min(n_components, n_samples, matrix.shape[1])
    pca = PCA(n_components=n_comp, random_state=42)
    return pca.fit_transform(matrix)


# ─────────────────────────────────────────────────────────────────────────────
# CLUSTERING ALGORITHMS
# ─────────────────────────────────────────────────────────────────────────────

def run_hdbscan(matrix: np.ndarray, min_cluster_size: Optional[int] = None) -> np.ndarray:
    """
    HDBSCAN clustering. min_cluster_size is auto-adjusted to dataset size.
    Returns array of cluster labels (-1 = noise).
    """
    KMeans, silhouette_score, PCA, hdbscan_lib, umap_lib = _import_clustering_libs()
    
    n = matrix.shape[0]
    if min_cluster_size is None:
        min_cluster_size = max(2, int(np.sqrt(n)))
    min_cluster_size = min(min_cluster_size, n // 2)

    clusterer = hdbscan_lib.HDBSCAN(
        min_cluster_size=max(2, min_cluster_size),
        min_samples=1,
        metric='euclidean',
        cluster_selection_method='eom'
    )
    labels = clusterer.fit_predict(matrix)
    return labels


def run_kmeans_optimal(matrix: np.ndarray, k_range: range = None) -> tuple[np.ndarray, int, float]:
    """
    K-Means with silhouette score optimization to pick the best K.
    Returns (labels, best_k, best_silhouette_score).
    """
    KMeans, silhouette_score, PCA, hdbscan_lib, umap_lib = _import_clustering_libs()
    
    n = matrix.shape[0]
    if n < 4:
        labels = np.zeros(n, dtype=int)
        return labels, 1, 0.0

    if k_range is None:
        k_max = min(15, n // 2)
        k_range = range(2, k_max + 1)

    best_k, best_score, best_labels = 2, -1.0, None

    for k in k_range:
        if k >= n:
            continue
        km = KMeans(n_clusters=k, n_init=10, random_state=42, max_iter=300)
        labels = km.fit_predict(matrix)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(matrix, labels, metric='euclidean')
        if score > best_score:
            best_score = score
            best_k = k
            best_labels = labels.copy()

    if best_labels is None:
        best_labels = np.zeros(n, dtype=int)
        best_k, best_score = 1, 0.0

    return best_labels, best_k, round(float(best_score), 4)


# ─────────────────────────────────────────────────────────────────────────────
# CORRELATION ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

_NUMERIC_METRICS = [
    'word_count', 'word_diversity', 'sentiment_polarity', 'sentiment_subjectivity',
    'emotion_joy', 'emotion_sadness', 'emotion_anger', 'emotion_fear', 'emotion_surprise',
    'emotion_diversity', 'creativity_score', 'verb_ratio', 'noun_ratio', 'adjective_ratio',
    'first_person_pronoun_ratio', 'grammatical_correctness_score', 'hapax_legomena_ratio',
    'mood', 'energy', 'focus'
]

def compute_cluster_correlations(labels: np.ndarray, metrics_records: list, algorithm: str) -> list[dict]:
    """
    Computes Pearson correlation between (one-hot) cluster membership
    and each NLP metric. Returns list of correlation dicts.
    """
    unique_clusters = sorted(set(labels))
    correlations = []

    for cluster_id in unique_clusters:
        if cluster_id == -1:  # HDBSCAN noise
            continue
        
        membership = (labels == cluster_id).astype(float)
        
        for metric in _NUMERIC_METRICS:
            values = []
            for rec in metrics_records:
                v = rec.get(metric)
                values.append(float(v) if v is not None else float('nan'))
            
            values = np.array(values, dtype=float)
            
            # Remove NaNs
            valid_mask = ~np.isnan(values) & (membership.shape[0] == values.shape[0])
            if valid_mask.sum() < 3:
                continue

            try:
                r, p = stats.pearsonr(membership[valid_mask], values[valid_mask])
                if not (np.isnan(r) or np.isnan(p)):
                    correlations.append({
                        'cluster_id': int(cluster_id),
                        'metric_name': metric,
                        'correlation_coefficient': round(float(r), 4),
                        'p_value': round(float(p), 4),
                        'algorithm': algorithm
                    })
            except Exception:
                continue

    return correlations


# ─────────────────────────────────────────────────────────────────────────────
# CLUSTER SUMMARIES
# ─────────────────────────────────────────────────────────────────────────────

def summarize_clusters(labels: np.ndarray, metrics_records: list) -> dict:
    """
    For each cluster, compute mean values of key metrics.
    Returns a dict mapping cluster_id -> {metric: mean_value}.
    """
    unique_clusters = sorted(set(labels))
    summary = {}

    for cluster_id in unique_clusters:
        label_str = 'noise' if cluster_id == -1 else str(cluster_id)
        indices = [i for i, l in enumerate(labels) if l == cluster_id]
        
        cluster_metrics = {}
        for metric in _NUMERIC_METRICS:
            values = [metrics_records[i].get(metric) for i in indices]
            values = [float(v) for v in values if v is not None]
            if values:
                cluster_metrics[metric] = round(float(np.mean(values)), 4)
        
        cluster_metrics['size'] = len(indices)
        # Get a representative date range
        dates = [metrics_records[i].get('date', '') for i in indices if metrics_records[i].get('date')]
        if dates:
            cluster_metrics['date_range'] = f"{min(dates)} to {max(dates)}"
        
        summary[label_str] = cluster_metrics

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# SAVE RESULTS
# ─────────────────────────────────────────────────────────────────────────────

def save_clustering_results(
    db_path: str,
    run_id: str,
    algorithm: str,
    n_clusters: int,
    silhouette: float,
    note_ids: list,
    labels: np.ndarray,
    label_column: str,
    correlations: list[dict],
    cluster_summary: dict,
    n_analyzed: int
):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Save run metadata
    cursor.execute("""
        INSERT OR REPLACE INTO clustering_runs 
        (run_id, algorithm, n_clusters, silhouette_score, notes_analyzed, cluster_summary)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (run_id, algorithm, n_clusters, silhouette, n_analyzed, json.dumps(cluster_summary)))

    # Update note_analysis with cluster labels
    for note_id, label in zip(note_ids, labels):
        cursor.execute(
            f"UPDATE note_analysis SET {label_column} = ? WHERE note_id = ?",
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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLUSTERING PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_clustering_pipeline(db_path: str) -> dict:
    """
    Full repeatable clustering pipeline:
      1. Load embeddings + metrics from DB
      2. Reduce dimensions
      3. Run HDBSCAN and K-Means (optimal K)
      4. Compute correlations for both
      5. Save everything to DB
      6. Return evaluation summary dict

    Safe to run multiple times — creates a new run_id each time.
    """
    logger.info("Loading embeddings and metrics...")
    note_ids, matrix, metrics_records = load_embeddings_and_metrics(db_path)

    if len(note_ids) < 4:
        logger.warning(f"Not enough data points ({len(note_ids)}) for clustering. Need at least 4.")
        return {'status': 'skipped', 'reason': f'Only {len(note_ids)} entries with embeddings and analysis.'}

    n = len(note_ids)
    logger.info(f"Loaded {n} entries for clustering.")

    # ── Dimensionality Reduction ──────────────────────────────────────────────
    logger.info("Reducing dimensions with UMAP...")
    reduced = reduce_dimensions(matrix, n_components=min(10, n - 1))

    # ── HDBSCAN ──────────────────────────────────────────────────────────────
    logger.info("Running HDBSCAN...")
    hdbscan_labels = run_hdbscan(reduced)
    n_hdbscan = len(set(hdbscan_labels) - {-1})
    n_noise = int((hdbscan_labels == -1).sum())
    logger.info(f"HDBSCAN: {n_hdbscan} clusters, {n_noise} noise points.")

    hdbscan_sil = 0.0
    if n_hdbscan >= 2:
        try:
            from sklearn.metrics import silhouette_score
            valid_mask = hdbscan_labels != -1
            if valid_mask.sum() >= 2:
                hdbscan_sil = silhouette_score(reduced[valid_mask], hdbscan_labels[valid_mask])
                hdbscan_sil = round(float(hdbscan_sil), 4)
        except Exception:
            pass

    # ── K-Means ───────────────────────────────────────────────────────────────
    logger.info("Running K-Means with optimal K search...")
    kmeans_labels, best_k, kmeans_sil = run_kmeans_optimal(reduced)
    logger.info(f"K-Means: optimal K={best_k}, silhouette={kmeans_sil:.3f}")

    # ── Correlations ──────────────────────────────────────────────────────────
    hdbscan_corrs = compute_cluster_correlations(hdbscan_labels, metrics_records, 'hdbscan')
    kmeans_corrs  = compute_cluster_correlations(kmeans_labels, metrics_records, 'kmeans')

    # ── Summaries ──────────────────────────────────────────────────────────────
    hdbscan_summary = summarize_clusters(hdbscan_labels, metrics_records)
    kmeans_summary  = summarize_clusters(kmeans_labels, metrics_records)

    # ── Save to DB ─────────────────────────────────────────────────────────────
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    hdbscan_run_id = f"hdbscan_{ts}_{uuid.uuid4().hex[:6]}"
    kmeans_run_id  = f"kmeans_{ts}_{uuid.uuid4().hex[:6]}"

    save_clustering_results(
        db_path, hdbscan_run_id, 'hdbscan', n_hdbscan, hdbscan_sil,
        note_ids, hdbscan_labels, 'hdbscan_cluster_id', hdbscan_corrs, hdbscan_summary, n
    )
    save_clustering_results(
        db_path, kmeans_run_id, 'kmeans', best_k, kmeans_sil,
        note_ids, kmeans_labels, 'kmeans_cluster_id', kmeans_corrs, kmeans_summary, n
    )

    # ── Evaluation Summary ─────────────────────────────────────────────────────
    # Find strongest correlations (|r| > 0.3 and p < 0.05)
    strong_corrs = [c for c in (hdbscan_corrs + kmeans_corrs)
                    if abs(c['correlation_coefficient']) > 0.3 and c['p_value'] < 0.05]
    strong_corrs.sort(key=lambda x: abs(x['correlation_coefficient']), reverse=True)

    evaluation = {
        'status': 'success',
        'notes_analyzed': n,
        'hdbscan': {
            'run_id': hdbscan_run_id,
            'n_clusters': n_hdbscan,
            'noise_points': n_noise,
            'silhouette_score': hdbscan_sil,
            'cluster_summary': hdbscan_summary,
        },
        'kmeans': {
            'run_id': kmeans_run_id,
            'optimal_k': best_k,
            'silhouette_score': kmeans_sil,
            'cluster_summary': kmeans_summary,
        },
        'strong_cross_cluster_correlations': strong_corrs[:20],  # top 20
    }

    logger.info(f"Clustering complete. Found {len(strong_corrs)} strong correlations.")
    return evaluation


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    result = run_clustering_pipeline('personal_metric.db')
    print(json.dumps(result, indent=2, default=str))
