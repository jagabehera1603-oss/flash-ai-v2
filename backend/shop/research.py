import os, re, requests


def _money(text):
    vals = re.findall(r'(?:₹|Rs\.?|INR\s*)\s?([0-9][0-9,]{2,})', text, re.I)
    return min((float(v.replace(',', '')) for v in vals), default=None)


def search_web(query):
    key = os.getenv('TAVILY_API_KEY')
    if not key:
        return []
    r = requests.post('https://api.tavily.com/search', json={
        'api_key': key, 'query': query, 'search_depth': 'advanced',
        'max_results': 10, 'include_answer': True
    }, timeout=35)
    r.raise_for_status()
    return r.json().get('results', [])


def summarize(query, evidence):
    key = os.getenv('OPENAI_API_KEY')
    if not key or not evidence:
        return 'Add an OpenAI API key to generate an AI synthesis from the web evidence.'
    model = os.getenv('OPENAI_MODEL', 'gpt-5-mini')
    text = '\n\n'.join(f"SOURCE: {x.get('title')}\n{x.get('content','')[:1800]}\nURL: {x.get('url')}" for x in evidence[:8])
    payload = {'model': model, 'messages': [
        {'role': 'system', 'content': 'You are a careful shopping research analyst. Use only the supplied evidence. Do not invent specs, prices, ratings, or claims.'},
        {'role': 'user', 'content': f"Research request: {query}\n\nEvidence:\n{text}\n\nGive a concise buyer summary, 3 pros, 3 cons, and who should buy it."}
    ], 'temperature': 0.2}
    r = requests.post('https://api.openai.com/v1/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def run(query):
    results = search_web(query + ' India price reviews Amazon Flipkart')
    products = []
    for x in results:
        title = x.get('title', '')
        content = x.get('content', '')
        blob = title + ' ' + content
        price = _money(blob)
        rating_match = re.search(r'([0-5](?:\.[0-9])?)\s*(?:/\s*5|stars?|out of 5)', blob, re.I)
        rating = float(rating_match.group(1)) if rating_match else None
        score = round((rating / 5 * 70 if rating else 35) + min(len(content) / 100, 20), 1)
        products.append({'name': title, 'price': price, 'rating': rating, 'score': min(score, 100), 'url': x.get('url',''), 'source': x.get('url','').split('/')[2] if x.get('url') else '', 'summary': content[:500]})
    return products, results
