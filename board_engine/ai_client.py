"""
Direct AI generation for the canvas: send a prompt to the configured provider and return its reply text.

Provider from the environment (the key never reaches the browser):
  GEMINI_API_KEY    -> Google Gemini (REST generateContent), model GEMINI_MODEL (default gemini-2.5-pro)
  ANTHROPIC_API_KEY -> Anthropic Claude (official SDK, streaming), model ANTHROPIC_MODEL (default claude-opus-5-5)
  AI_PROVIDER=gemini|claude picks one when both keys are set.
Claude requests opt into server-side refusal fallbacks (`fallbacks: "default"`): a declined request is re-run on the
model Anthropic recommends for that refusal category instead of failing.
"""
import os

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
TIMEOUT_S = 300


class AIError(RuntimeError):
    pass


def provider():
    """('gemini' | 'claude', model) for the configured provider, or (None, None)."""
    want = (os.environ.get('AI_PROVIDER') or '').lower()
    has_g, has_c = bool(os.environ.get('GEMINI_API_KEY')), bool(os.environ.get('ANTHROPIC_API_KEY'))
    if has_g and (want in ('', 'gemini') or not has_c):
        return 'gemini', os.environ.get('GEMINI_MODEL', 'gemini-2.5-pro')
    if has_c:
        return 'claude', os.environ.get('ANTHROPIC_MODEL', 'claude-opus-5-5')
    return None, None


def complete(prompt):
    """The provider's reply text for `prompt`. Raises AIError with a message safe to show the user."""
    name, model = provider()
    if name is None:
        raise AIError('no AI provider is configured on the server (set GEMINI_API_KEY or ANTHROPIC_API_KEY)')
    return _gemini(prompt, model) if name == 'gemini' else _claude(prompt, model)


def _gemini(prompt, model):
    import requests
    try:
        r = requests.post(GEMINI_URL.format(model=model), timeout=TIMEOUT_S,
                          headers={'x-goog-api-key': os.environ['GEMINI_API_KEY'], 'Content-Type': 'application/json'},
                          json={'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
                                'generationConfig': {'responseMimeType': 'application/json', 'maxOutputTokens': 65536}})
    except requests.RequestException as e:
        raise AIError(f'could not reach Gemini: {type(e).__name__}') from None
    if r.status_code != 200:
        msg = ''
        try:
            msg = r.json().get('error', {}).get('message', '')
        except ValueError:
            pass
        raise AIError(f'Gemini answered HTTP {r.status_code}{": " + msg[:300] if msg else ""}')
    data = r.json()
    cand = (data.get('candidates') or [{}])[0]
    text = ''.join(p.get('text', '') for p in (cand.get('content') or {}).get('parts', []))
    if not text.strip():
        raise AIError(f"Gemini returned no design (finish reason: {cand.get('finishReason') or 'unknown'})")
    return text


def _claude(prompt, model):
    try:
        import anthropic
    except ImportError:
        raise AIError('the anthropic package is not installed on the server (pip install anthropic)') from None
    client = anthropic.Anthropic(timeout=TIMEOUT_S)
    try:
        with client.beta.messages.stream(
            model=model,
            max_tokens=64000,
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
            output_config={'effort': 'xhigh'},      # complex structures: deeper thinking
            messages=[{'role': 'user', 'content': prompt}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.RateLimitError:
        raise AIError('Claude is rate-limiting requests; try again in a minute') from None
    except anthropic.APIStatusError as e:
        raise AIError(f'Claude answered HTTP {e.status_code}: {e.message[:300]}') from None
    except anthropic.APIConnectionError:
        raise AIError('could not reach Claude') from None
    if message.stop_reason == 'refusal':
        raise AIError('Claude declined this request; rephrase the product description and try again')
    text = ''.join(b.text for b in message.content if b.type == 'text')
    if not text.strip():
        raise AIError(f'Claude returned no design (stop reason: {message.stop_reason})')
    return text
