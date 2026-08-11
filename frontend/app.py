import os, re, requests
from urllib.parse import urlparse
import streamlit as st

st.set_page_config(page_title='Jagadish_webscraping', page_icon='🔎', layout='wide')

st.markdown('''<style>
.main {max-width: 1180px; margin:auto}
.hero {padding: 48px 0 28px; text-align:center}
.hero h1 {font-size:58px; margin-bottom:8px}
.hero p {font-size:20px; opacity:.7}
</style>''', unsafe_allow_html=True)

api = st.secrets.get('DJANGO_API_URL', os.getenv('DJANGO_API_URL', '')).rstrip('/')
tavily_key = st.secrets.get('TAVILY_API_KEY', os.getenv('TAVILY_API_KEY', ''))
openai_key = st.secrets.get('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))
openai_model = st.secrets.get('OPENAI_MODEL', os.getenv('OPENAI_MODEL', 'gpt-5-mini'))

st.markdown('<div class="hero"><h1>🔎 Jagadish_webscraping</h1><p>AI-powered product research, review aggregation and comparisons.</p></div>', unsafe_allow_html=True)

q = st.text_input('What are you looking for?', placeholder='Paste an Amazon/Flipkart product link or type: Best laptop under ₹70,000 for coding')
col1, col2 = st.columns([1,5])
with col1:
    go = st.button('🔎 Research', use_container_width=True, type='primary')


def is_url(text):
    try:
        p = urlparse(text.strip())
        return p.scheme in ('http', 'https') and bool(p.netloc)
    except Exception:
        return False


def amazon_asin(url):
    m = re.search(r'/(?:dp|gp/product|product)/([A-Z0-9]{10})(?:[/?]|$)', url, re.I)
    return m.group(1).upper() if m else None


def money(text):
    vals = re.findall(r'(?:₹|Rs\.?|INR\s*)\s?([0-9][0-9,]{2,})', text, re.I)
    return min((float(v.replace(',', '')) for v in vals), default=None)


def tavily_headers():
    return {'Authorization': f'Bearer {tavily_key}', 'Content-Type': 'application/json'}


def tavily_search(query, max_results=8):
    r = requests.post('https://api.tavily.com/search', headers=tavily_headers(), json={
        'query': query, 'search_depth': 'advanced', 'max_results': max_results, 'include_answer': True
    }, timeout=45)
    r.raise_for_status()
    return r.json().get('results', [])


def tavily_extract(url):
    r = requests.post('https://api.tavily.com/extract', headers=tavily_headers(), json={
        'urls': [url], 'extract_depth': 'basic', 'format': 'markdown'
    }, timeout=60)
    r.raise_for_status()
    results = r.json().get('results', [])
    return results[0] if results else None


def make_products(sources):
    products, seen = [], set()
    for x in sources:
        title = x.get('title', '')
        content = x.get('content', '') or x.get('raw_content', '')
        url = x.get('url', '')
        key = (title.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        blob = title + ' ' + content
        price = money(blob)
        rm = re.search(r'([0-5](?:\.[0-9])?)\s*(?:/\s*5|stars?|out of 5)', blob, re.I)
        rating = float(rm.group(1)) if rm else None
        score = round((rating / 5 * 70 if rating else 35) + min(len(content) / 100, 20), 1)
        products.append({'name': title or 'Unnamed result', 'price': price, 'rating': rating,
                         'score': min(score, 100), 'url': url,
                         'source': urlparse(url).netloc if url else '', 'summary': content[:700]})
    return products


def ai_summary(query, evidence):
    if not openai_key or not evidence:
        return 'Web research completed. Add OPENAI_API_KEY to generate the AI synthesis.'
    text = '\n\n'.join(f"SOURCE: {x.get('title')}\n{x.get('content', x.get('raw_content',''))[:2200]}\nURL: {x.get('url')}" for x in evidence[:10])
    payload = {'model': openai_model, 'messages': [
        {'role': 'system', 'content': 'You are a careful shopping research analyst. Use only supplied evidence. Do not invent specs, prices, ratings, or claims. Distinguish retailer facts from review opinions.'},
        {'role': 'user', 'content': f'Research request: {query}\n\nEvidence:\n{text}\n\nGive a concise verdict, key facts/specifications found, 3 pros, 3 cons, who should buy it, and important caveats.'}
    ], 'temperature': 0.2}
    r = requests.post('https://api.openai.com/v1/chat/completions', headers={'Authorization': f'Bearer {openai_key}', 'Content-Type': 'application/json'}, json=payload, timeout=75)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def research_product_url(url):
    if not tavily_key:
        raise RuntimeError('TAVILY_API_KEY is not configured. Add it in Streamlit App Settings → Secrets.')
    host = urlparse(url).netloc.lower()
    asin = amazon_asin(url)
    evidence = []

    # Try the exact product page first. Retailers can block extraction, so failures are non-fatal.
    try:
        extracted = tavily_extract(url)
        if extracted:
            evidence.append({'title': extracted.get('url', 'Product page'), 'url': extracted.get('url', url),
                             'content': extracted.get('raw_content', '')})
    except Exception:
        pass

    if asin:
        queries = [
            f'Amazon India ASIN {asin} product specifications price',
            f'ASIN {asin} reviews complaints problems',
            f'"{asin}" laptop review',
        ]
    else:
        queries = [f'"{url}" product reviews price specifications', f'{host} product reviews complaints']

    for query in queries:
        try:
            evidence.extend(tavily_search(query, max_results=6))
        except Exception:
            pass

    if not evidence:
        raise RuntimeError('No web evidence was found for this product link. The retailer may be blocking access; try a clean product URL without tracking parameters.')

    return {'query': url, 'asin': asin, 'summary': ai_summary(url, evidence),
            'products': make_products(evidence),
            'sources': [{'title': x.get('title'), 'url': x.get('url'), 'snippet': x.get('content', x.get('raw_content',''))[:350]}
                        for x in evidence[:20] if x.get('url')]}


def direct_research(query):
    if not tavily_key:
        raise RuntimeError('TAVILY_API_KEY is not configured. Add it in Streamlit App Settings → Secrets.')
    sources = tavily_search(query + ' India price reviews Amazon Flipkart', max_results=10)
    return {'query': query, 'summary': ai_summary(query, sources), 'products': make_products(sources),
            'sources': [{'title': x.get('title'), 'url': x.get('url'), 'snippet': x.get('content','')[:350]} for x in sources if x.get('url')]}


if go and q:
    q = q.strip()
    with st.spinner('Researching the product and gathering independent evidence...'):
        try:
            # URL inputs are handled here instead of calling localhost:8000.
            if is_url(q):
                data = research_product_url(q)
            elif api:
                r = requests.get(f'{api}/research/', params={'q': q}, timeout=90)
                r.raise_for_status()
                data = r.json()
            else:
                data = direct_research(q)
            st.session_state['result'] = data
        except Exception as e:
            st.error(f'Research failed: {e}')

if 'result' in st.session_state:
    data = st.session_state['result']
    if data.get('asin'):
        st.caption(f"Amazon ASIN detected: {data['asin']}")
    st.subheader('🧠 AI Research Summary')
    st.write(data.get('summary',''))
    products = data.get('products', [])
    st.subheader(f'🏆 Research results ({len(products)})')
    for i, p in enumerate(products):
        with st.container(border=True):
            a,b,c,d = st.columns([4,1,1,1])
            a.markdown(f"### {i+1}. {p.get('name','Unknown product')}")
            a.caption(p.get('source',''))
            b.metric('Price', f"₹{p['price']:,.0f}" if p.get('price') else '—')
            c.metric('Rating', f"{p['rating']}/5" if p.get('rating') else '—')
            d.metric('Score', f"{p.get('score',0):.0f}/100")
            st.write(p.get('summary',''))
            if p.get('url'): st.link_button('View source', p['url'])

    st.subheader('🔎 Research Sources')
    for s in data.get('sources', []):
        if s.get('url'):
            st.markdown(f"- [{s.get('title','Source')}]({s['url']}) — {s.get('snippet','')}")
else:
    st.info('Paste an Amazon/Flipkart product link, or type a shopping request such as “Best laptop under ₹70,000 for coding”.')
