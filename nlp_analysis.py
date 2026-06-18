"""
nlp_analysis.py
===============
Computes per-entry NLP metrics on clean diary narratives:

  Lexical:
    - word_count
    - unique_word_count
    - word_diversity (Type-Token Ratio)
    - avg_sentence_length

  Grammatical Structure (via spaCy POS tagging):
    - verb_ratio
    - noun_ratio
    - adjective_ratio
    - adverb_ratio
    - first_person_pronoun_ratio
    - grammatical_error_count
    - grammatical_correctness_score

  Creativity / Style:
    - hapax_legomena_ratio  (words that appear only once)
    - sentence_length_variance
    - creativity_score       (composite of hapax + vocab richness + struct variance)

  Emotion (via pre-trained NLP models):
    - sentiment_polarity    (-1 to +1)
    - sentiment_subjectivity (0 to 1)
    - emotion_joy, emotion_sadness, emotion_anger, emotion_fear, emotion_surprise
    - emotion_diversity     (variance of word embeddings in emotional-word set)
"""

import re
import math
import statistics
import sqlite3
import datetime
import logging

import numpy as np

# Lazy imports — loaded once on first call
_nlp = None
_sia = None
_emotion_pipeline = None
_embedding_model = None

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LAZY MODEL LOADING
# ─────────────────────────────────────────────────────────────────────────────

def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm")
            _nlp = None
    return _nlp


def _get_sia():
    """VADER Sentiment Analyzer for fast sentiment."""
    global _sia
    if _sia is None:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        import nltk
        try:
            _sia = SentimentIntensityAnalyzer()
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
            _sia = SentimentIntensityAnalyzer()
    return _sia


def _get_emotion_pipeline():
    """HuggingFace pipeline for multi-label emotion detection."""
    global _emotion_pipeline
    if _emotion_pipeline is None:
        try:
            from transformers import pipeline
            _emotion_pipeline = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                top_k=None,
                truncation=True,
                max_length=512
            )
        except Exception as e:
            logger.warning(f"Emotion pipeline failed to load: {e}")
            _emotion_pipeline = None
    return _emotion_pipeline


def _get_embedding_model():
    """Sentence-transformer for emotion diversity calculation."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.warning(f"Embedding model failed to load: {e}")
            _embedding_model = None
    return _embedding_model


# ─────────────────────────────────────────────────────────────────────────────
# LEXICAL METRICS
# ─────────────────────────────────────────────────────────────────────────────

def calculate_mtld(tokens: list[str], threshold: float = 0.72) -> float:
    """
    Calculates the Measure of Textual Lexical Diversity (MTLD) in pure Python.
    References: McCarthy & Jarvis (2010).
    """
    if len(tokens) == 0:
        return 0.0

    def get_mtld_factor(word_list, forward=True):
        if not forward:
            word_list = list(reversed(word_list))
        
        factor_count = 0.0
        total_tokens = len(word_list)
        
        i = 0
        while i < total_tokens:
            types = set()
            tokens_in_segment = 0
            ttr = 1.0
            
            while i < total_tokens and ttr >= threshold:
                token = word_list[i]
                types.add(token)
                tokens_in_segment += 1
                ttr = len(types) / tokens_in_segment
                i += 1
            
            if ttr >= threshold:
                fraction = (1.0 - ttr) / (1.0 - threshold) if ttr < 1.0 else 0.0
                factor_count += fraction
            else:
                factor_count += 1.0
                
        return total_tokens / factor_count if factor_count > 0 else float(total_tokens)

    forward_mtld = get_mtld_factor(tokens, forward=True)
    backward_mtld = get_mtld_factor(tokens, forward=False)
    
    if forward_mtld == 0.0 or backward_mtld == 0.0:
        return 0.0
        
    return (forward_mtld + backward_mtld) / 2.0


def compute_lexical_metrics(text: str) -> dict:
    """Compute basic word and sentence-level statistics."""
    if not text or not text.strip():
        return {
            'word_count': 0, 'unique_word_count': 0,
            'word_diversity': 0.0, 'avg_sentence_length': 0.0
        }

    # Tokenize words (alphanumeric only, lowercased)
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

    word_count = len(words)
    unique_count = len(set(words))
    word_diversity = calculate_mtld(words)

    sent_lengths = [len(re.findall(r'\b[a-zA-Z]+\b', s)) for s in sentences]
    avg_sent_len = statistics.mean(sent_lengths) if sent_lengths else 0.0

    return {
        'word_count': word_count,
        'unique_word_count': unique_count,
        'word_diversity': round(word_diversity, 4),
        'avg_sentence_length': round(avg_sent_len, 2)
    }


# ─────────────────────────────────────────────────────────────────────────────
# GRAMMATICAL STRUCTURE (spaCy POS)
# ─────────────────────────────────────────────────────────────────────────────

# First-person pronouns
_FIRST_PERSON = {'i', 'me', 'my', 'mine', 'myself'}

def compute_grammar_structure(text: str) -> dict:
    """
    Uses spaCy POS tagging to analyse the grammatical structure of the text.
    Returns ratios of verbs, nouns, adjectives, adverbs, and first-person pronouns,
    as well as a simple grammatical correctness score.
    """
    nlp = _get_nlp()
    if nlp is None or not text or not text.strip():
        return {
            'verb_ratio': 0.0, 'noun_ratio': 0.0, 'adjective_ratio': 0.0,
            'adverb_ratio': 0.0, 'first_person_pronoun_ratio': 0.0,
            'grammatical_error_count': 0, 'grammatical_correctness_score': 1.0
        }

    # Truncate to avoid spaCy max_length issues
    doc = nlp(text[:100000])
    tokens = [t for t in doc if not t.is_space]
    total = len(tokens)

    if total == 0:
        return {
            'verb_ratio': 0.0, 'noun_ratio': 0.0, 'adjective_ratio': 0.0,
            'adverb_ratio': 0.0, 'first_person_pronoun_ratio': 0.0,
            'grammatical_error_count': 0, 'grammatical_correctness_score': 1.0
        }

    verbs      = sum(1 for t in tokens if t.pos_ == 'VERB')
    nouns      = sum(1 for t in tokens if t.pos_ == 'NOUN')
    adjectives = sum(1 for t in tokens if t.pos_ == 'ADJ')
    adverbs    = sum(1 for t in tokens if t.pos_ == 'ADV')
    first_pron = sum(1 for t in tokens if t.text.lower() in _FIRST_PERSON)

    # Grammatical error detection: use spaCy's sentence parser
    # Heuristic: sentences without a root verb are likely incomplete/malformed
    error_count = 0
    for sent in doc.sents:
        has_root_verb = any(
            t.dep_ == 'ROOT' and t.pos_ in ('VERB', 'AUX')
            for t in sent
        )
        if not has_root_verb and len(list(sent)) > 2:
            error_count += 1

    # Score: 1.0 = no errors, approaches 0 with more errors
    num_sentences = max(len(list(doc.sents)), 1)
    correctness_score = max(0.0, 1.0 - (error_count / num_sentences))

    return {
        'verb_ratio':                  round(verbs / total, 4),
        'noun_ratio':                  round(nouns / total, 4),
        'adjective_ratio':             round(adjectives / total, 4),
        'adverb_ratio':                round(adverbs / total, 4),
        'first_person_pronoun_ratio':  round(first_pron / total, 4),
        'grammatical_error_count':     error_count,
        'grammatical_correctness_score': round(correctness_score, 4)
    }


# ─────────────────────────────────────────────────────────────────────────────
# CREATIVITY / STYLE
# ─────────────────────────────────────────────────────────────────────────────

def compute_creativity_metrics(text: str) -> dict:
    """
    Hapax Legomena: words that appear exactly once (rare words = richer vocab).
    Sentence Length Variance: how varied the sentence structure is.
    Creativity Score: composite metric combining both.
    """
    if not text or not text.strip():
        return {
            'hapax_legomena_ratio': 0.0,
            'sentence_length_variance': 0.0,
            'creativity_score': 0.0
        }

    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    if not words:
        return {
            'hapax_legomena_ratio': 0.0,
            'sentence_length_variance': 0.0,
            'creativity_score': 0.0
        }

    from collections import Counter
    freq = Counter(words)
    hapax = sum(1 for w, c in freq.items() if c == 1)
    hapax_ratio = hapax / len(freq) if freq else 0.0

    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    sent_lengths = [len(re.findall(r'\b[a-zA-Z]+\b', s)) for s in sentences]
    sent_var = statistics.variance(sent_lengths) if len(sent_lengths) > 1 else 0.0

    # Normalize sentence variance (cap at 100 for scoring)
    sent_var_norm = min(sent_var / 100.0, 1.0)

    # Type-Token Ratio contribution
    ttr = len(set(words)) / len(words) if words else 0.0

    # Composite creativity score (equal weights)
    creativity_score = (hapax_ratio + ttr + sent_var_norm) / 3.0

    return {
        'hapax_legomena_ratio':     round(hapax_ratio, 4),
        'sentence_length_variance': round(sent_var, 4),
        'creativity_score':         round(creativity_score, 4)
    }


# ─────────────────────────────────────────────────────────────────────────────
# EMOTION ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

_EMOTION_LABELS = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'neutral']
_EMOTION_ADJECTIVES = {
    'joy':      ['happy', 'joyful', 'excited', 'great', 'amazing', 'wonderful', 'hype', 'love'],
    'sadness':  ['sad', 'depressed', 'unhappy', 'miserable', 'lonely', 'hurt', 'miss'],
    'anger':    ['angry', 'frustrated', 'annoyed', 'furious', 'aggressive', 'mad'],
    'fear':     ['scared', 'anxious', 'worried', 'nervous', 'afraid', 'fearful', 'anxios'],
    'surprise': ['surprised', 'shocked', 'astonished', 'amazed', 'unexpected'],
}

def compute_emotion_metrics(text: str) -> dict:
    """
    1. Uses HuggingFace emotion model for discrete emotion scores.
    2. Computes emotion diversity as the average pairwise cosine distance
       between embeddings of emotion-laden words found in the text.
    """
    # --- Sentiment (VADER — fast, no model download needed) ---
    sia = _get_sia()
    if sia and text.strip():
        scores = sia.polarity_scores(text)
        polarity = scores['compound']
        # Estimate subjectivity from ratio of positive + negative to total
        subjectivity = min(1.0, (scores['pos'] + scores['neg']) / max(scores['neu'], 0.01))
    else:
        polarity, subjectivity = 0.0, 0.0

    # --- Discrete emotions (HuggingFace) ---
    emotions = {'joy': 0.0, 'sadness': 0.0, 'anger': 0.0, 'fear': 0.0, 'surprise': 0.0}
    pipeline = _get_emotion_pipeline()
    if pipeline and text.strip():
        try:
            # Truncate to avoid issues
            result = pipeline(text[:512])
            for item in result[0]:
                label = item['label'].lower()
                score = item['score']
                if label in emotions:
                    emotions[label] = round(score, 4)
        except Exception as e:
            logger.warning(f"Emotion pipeline inference failed: {e}")

    # --- Emotion Diversity via embedding distance ---
    emotion_diversity = 0.0
    model = _get_embedding_model()
    if model and text.strip():
        try:
            words_lower = set(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
            emotion_words = []
            for word_list in _EMOTION_ADJECTIVES.values():
                emotion_words.extend([w for w in word_list if w in words_lower])
            
            if len(emotion_words) >= 2:
                embeddings = model.encode(emotion_words, show_progress_bar=False)
                # Pairwise cosine similarity
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                normalized = embeddings / (norms + 1e-8)
                sim_matrix = normalized @ normalized.T
                # Diversity = 1 - mean similarity (off-diagonal)
                n = len(emotion_words)
                mask = ~np.eye(n, dtype=bool)
                mean_sim = sim_matrix[mask].mean()
                emotion_diversity = round(float(1.0 - mean_sim), 4)
        except Exception as e:
            logger.warning(f"Emotion diversity calculation failed: {e}")

    return {
        'sentiment_polarity':    round(polarity, 4),
        'sentiment_subjectivity': round(subjectivity, 4),
        'emotion_joy':      emotions['joy'],
        'emotion_sadness':  emotions['sadness'],
        'emotion_anger':    emotions['anger'],
        'emotion_fear':     emotions['fear'],
        'emotion_surprise': emotions['surprise'],
        'emotion_diversity': emotion_diversity,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FULL ANALYSIS PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_entry(note_id: str, date: str, text: str) -> dict:
    """
    Runs all NLP metrics on a single diary entry.
    Returns a flat dict matching the note_analysis table schema.
    """
    result = {'note_id': note_id, 'date': date}
    result.update(compute_lexical_metrics(text))
    result.update(compute_grammar_structure(text))
    result.update(compute_creativity_metrics(text))
    result.update(compute_emotion_metrics(text))
    # Cluster IDs are assigned later by dynamic_clustering.py
    result['hdbscan_cluster_id'] = None
    result['kmeans_cluster_id'] = None
    return result


def run_analysis_pipeline(db_path: str, force_rerun: bool = False):
    """
    Reads all notes from the database that haven't been analyzed yet
    (or all of them if force_rerun=True), runs NLP analysis, and saves results.
    Returns number of notes analyzed.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if force_rerun:
        cursor.execute("SELECT id, date, content FROM notes WHERE content != ''")
    else:
        cursor.execute("""
            SELECT n.id, n.date, n.content 
            FROM notes n
            LEFT JOIN note_analysis na ON n.id = na.note_id
            WHERE na.note_id IS NULL AND n.content != ''
        """)
    
    rows = cursor.fetchall()
    
    if not rows:
        logger.info("No new notes to analyze.")
        conn.close()
        return 0

    logger.info(f"Analyzing {len(rows)} notes...")
    analyzed = 0

    for row in rows:
        try:
            metrics = analyze_entry(row['id'], row['date'], row['content'])
            
            cursor.execute("""
                INSERT OR REPLACE INTO note_analysis (
                    note_id, date, word_count, unique_word_count, word_diversity,
                    avg_sentence_length, verb_ratio, noun_ratio, adjective_ratio,
                    adverb_ratio, first_person_pronoun_ratio, grammatical_error_count,
                    grammatical_correctness_score, hapax_legomena_ratio,
                    sentence_length_variance, creativity_score, sentiment_polarity,
                    sentiment_subjectivity, emotion_joy, emotion_sadness, emotion_anger,
                    emotion_fear, emotion_surprise, emotion_diversity,
                    hdbscan_cluster_id, kmeans_cluster_id
                ) VALUES (
                    :note_id, :date, :word_count, :unique_word_count, :word_diversity,
                    :avg_sentence_length, :verb_ratio, :noun_ratio, :adjective_ratio,
                    :adverb_ratio, :first_person_pronoun_ratio, :grammatical_error_count,
                    :grammatical_correctness_score, :hapax_legomena_ratio,
                    :sentence_length_variance, :creativity_score, :sentiment_polarity,
                    :sentiment_subjectivity, :emotion_joy, :emotion_sadness, :emotion_anger,
                    :emotion_fear, :emotion_surprise, :emotion_diversity,
                    :hdbscan_cluster_id, :kmeans_cluster_id
                )
            """, metrics)

            analyzed += 1
            if analyzed % 10 == 0:
                conn.commit()
                logger.info(f"  ...{analyzed}/{len(rows)} done")

        except Exception as e:
            logger.error(f"Failed to analyze note {row['id']}: {e}")
            continue

    conn.commit()
    conn.close()
    logger.info(f"Analysis complete: {analyzed} notes processed.")
    return analyzed


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    force = '--force' in sys.argv
    count = run_analysis_pipeline('personal_metric.db', force_rerun=force)
    print(f"Analyzed {count} entries.")
