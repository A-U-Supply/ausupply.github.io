"""Filter Slack messages to identify song titles using HF Inference API."""
import logging

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = (
    'Is this Slack message a potential song title? Not discussion about titles — the title itself.\n'
    'Reply only YES or NO.\n\n'
    'Message: "{message}"'
)


def classify_messages(
    messages: list[dict],
    client: InferenceClient,
    model: str,
) -> list[dict]:
    """Filter message dicts to only those classified as song titles.

    Each message dict must have a 'title' key with the text to classify.
    Returns the subset of messages that the LLM considers song titles.
    """
    if not messages:
        return []

    results = []
    for msg in messages:
        prompt = CLASSIFICATION_PROMPT.format(message=msg["title"])
        try:
            resp = client.chat_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            answer = resp.choices[0].message.content.strip().upper()
            if answer.startswith("YES"):
                results.append(msg)
                logger.debug(f"YES: {msg['title'][:50]}")
            else:
                logger.debug(f"NO:  {msg['title'][:50]}")
        except Exception as e:
            logger.warning(f"Classification failed for '{msg['title'][:50]}': {e}, keeping message")
            results.append(msg)

    logger.info(f"Classified {len(messages)} messages: {len(results)} are song titles")
    return results
