import re
from collections import Counter

STOPWORDS = {
    'a','an','the','and','or','but','in','on','at','to','for',
    'of','with','is','are','was','were','be','been','have','has',
    'will','can','we','you','our','your','this','that','they'
}

def score_resume(job_text: str, resume_content: str) -> int:
    def tokenize(text):
        words = re.findall(r'[a-z0-9#+.]+', text.lower())
        return set(w for w in words if w not in STOPWORDS and len(w) > 2)

    job_words = tokenize(job_text)
    resume_words = tokenize(resume_content)
    return len(job_words & resume_words)

def select_best_resume(job_description: str, resumes: list[dict]) -> dict:
    """
    resumes = [{"id": 1, "name": "Frontend", "content": "..."}, ...]
    Returns the resume dict with the highest keyword overlap score.
    """
    if not resumes:
        return None
    scored = [(score_resume(job_description, r["content"]), r) for r in resumes]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]