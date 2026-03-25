"""Advanced text analysis tools."""
from typing import List, Dict, Optional
import re
from collections import Counter

from src.utils.logger import logger


async def detect_language(text: str) -> str:
    """DEPRECATED: Language detection removed.
    
    LLM naturally handles all languages.
    Returns 'en' by default for backward compatibility.
    
    Args:
        text: Text to analyze (ignored)
        
    Returns:
        Always 'en' (LLM handles language naturally)
    """
    logger.debug("Language detection bypassed - LLM handles language")
    return "en"


async def analyze_sentiment(text: str) -> Dict:
    """Analyze sentiment of text (simple rule-based).
    
    Args:
        text: Text to analyze
        
    Returns:
        Sentiment analysis result
    """
    try:
        text_lower = text.lower()
        
        # Positive words
        positive_words = {
            "good", "great", "excellent", "amazing", "wonderful", "fantastic",
            "love", "like", "happy", "joy", "pleased", "satisfied", "best",
            "perfect", "awesome", "brilliant", "outstanding", "superb"
        }
        
        # Negative words
        negative_words = {
            "bad", "terrible", "awful", "horrible", "worst", "hate", "dislike",
            "sad", "angry", "frustrated", "disappointed", "poor", "fail",
            "failure", "wrong", "error", "problem", "issue", "difficult"
        }
        
        # Count occurrences
        words = re.findall(r'\b\w+\b', text_lower)
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # Determine sentiment
        if positive_count > negative_count:
            sentiment = "positive"
            score = min(1.0, 0.5 + (positive_count - negative_count) * 0.1)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = max(0.0, 0.5 - (negative_count - positive_count) * 0.1)
        else:
            sentiment = "neutral"
            score = 0.5
        
        return {
            "sentiment": sentiment,
            "score": round(score, 2),
            "positive_words": positive_count,
            "negative_words": negative_count,
        }
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        return {
            "sentiment": "neutral",
            "score": 0.5,
            "error": str(e)
        }


async def extract_keywords_advanced(text: str, num_keywords: int = 10) -> List[Dict]:
    """Extract keywords using TF-IDF-like approach.
    
    Args:
        text: Text to analyze
        num_keywords: Number of keywords to extract
        
    Returns:
        List of keywords with scores
    """
    try:
        # Stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "can", "this",
            "that", "these", "those", "i", "you", "he", "she", "it", "we", "they"
        }
        
        # Extract words
        words = re.findall(r'\b[a-z]+\b', text.lower())
        
        # Filter stop words and short words
        filtered_words = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Count frequencies
        word_freq = Counter(filtered_words)
        
        # Calculate simple TF score (term frequency)
        total_words = len(filtered_words)
        keywords = []
        
        for word, count in word_freq.most_common(num_keywords * 2):
            if total_words > 0:
                tf_score = count / total_words
                keywords.append({
                    "word": word,
                    "frequency": count,
                    "score": round(tf_score, 4)
                })
        
        # Return top keywords
        return keywords[:num_keywords]
    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")
        return []


async def count_words(text: str) -> Dict:
    """Count words, characters, sentences in text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Text statistics
    """
    try:
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return {
            "characters": len(text),
            "characters_no_spaces": len(text.replace(" ", "")),
            "words": len(words),
            "sentences": len(sentences),
            "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
            "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
            "avg_sentence_length": len(words) / len(sentences) if sentences else 0,
        }
    except Exception as e:
        logger.error(f"Error counting text: {e}")
        return {
            "characters": 0,
            "words": 0,
            "sentences": 0,
            "error": str(e)
        }


async def extract_entities(text: str) -> Dict:
    """Extract basic entities from text (simple pattern matching).
    
    Args:
        text: Text to analyze
        
    Returns:
        Extracted entities
    """
    try:
        entities = {
            "emails": [],
            "urls": [],
            "phone_numbers": [],
            "dates": [],
        }
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = re.findall(email_pattern, text)
        
        # Extract URLs
        url_pattern = r'https?://[^\s]+'
        entities["urls"] = re.findall(url_pattern, text)
        
        # Extract phone numbers (simple pattern)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        entities["phone_numbers"] = re.findall(phone_pattern, text)
        
        # Extract dates (simple pattern)
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        entities["dates"] = re.findall(date_pattern, text)
        
        return entities
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        return {
            "emails": [],
            "urls": [],
            "phone_numbers": [],
            "dates": [],
            "error": str(e)
        }

