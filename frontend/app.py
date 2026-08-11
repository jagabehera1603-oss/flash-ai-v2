import os, re, html
import requests
from urllib.parse import urlparse, quote_plus
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


def clean_text(text):
    text = html.unescape(text or '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def tavily_headers():
    return {'Authorization': f'Bearer {tavily_key}', 'Content-Type': 'application/json'}


def tavily_search(query, max_results=8):
    if not tavily_key:
        return []
    r = requests.post('https://api.tavily.com/search', headers=tavily_headers(), json={
        'query': query, 'search_depth': 'advanced', 'max_results': max_results, 'include_answer': True
    }, timeout=45)
    r.raise_for_status()
    return r.json().get('results', [])


def tavily_extract(url):
    if not tavily_key:
        return None
    r = requests.post('https://api.tavily.com/extract', headers=tavily_headers(), json={
        'urls': [url], 'extract_depth': 'basic', 'format': 'markdown'
    }, timeout=60)
    r.raise_for_status()
    results = r.json().get('results', [])
    return results[0] if results else None


def jina_extract(url):
    """Key-free page extraction fallback. Useful when retailer extraction is blocked."""
    r = requests.get('https://r.jina.ai/' + url, headers={'User-Agent': 'Jagadish_webscraping/1.0'}, timeout=60)
    r.raise_for_status()
    text = clean_text(r.text)
    return {'title': urlparse(url).netloc, 'url': url, 'content': text[:12000]}


def ddg_search(query, max_results=8):
    """Key-free search fallback using DuckDuckGo's HTML results page."""
    url = 'https://html.duckduckgo.com/html/?q=' + quote_plus(query)
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
    r.raise_for_status()
    page = r.text
    results = []
    # DDG's HTML result blocks are deliberately parsed without extra packages.
    blocks = re.findall(r'<div[^>]+class="result results_links results_links_deep web-result".*?</div>\s*</div>', page, re.I | re.S)
    if not blocks:
        blocks = re.findall(r'<div[^>]+class="result[^>]*".*?</div>\s*</div>', page, re.I | re.S)
    for block in blocks[:max_results]:
        link = re.search(r'class="result__a"[^>]*href="([^"]+)"', block, re.I | re.S)
        title = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, re.I | re.S)
        snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</a?>', block, re.I | re.S)
        if not link:
            continue
        results.append({
            'title': clean_text(re.sub('<[^>]+>', ' ', title.group(1))) if title else link.group(1),
            'url': html.unescape(link.group(1)),
            'content': clean_text(re.sub('<[^>]+>', ' ', snippet.group(1))) if snippet else ''
        })
    return results


def web_search(query, max_results=8):
    """Use Tavily when configured, otherwise a key-free search fallback."""
    if tavily_key:
        return tavily_search(query, max_results)
    try:
        return ddg_search(query, max_results)
    except Exception:
        return []


def make_products(sources):
    products, seen = [], set()
    for x in sources:
        title = clean_text(x.get('title', ''))
        content = clean_text(x.get('content', '') or x.get('raw_content', ''))
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


def simple_summary(query, evidence):
    if not evidence:
        return 'No readable web evidence was found.'
    snippets = [clean_text(x.get('content', x.get('raw_content', ''))) for x in evidence]
    snippets = [x for x in snippets if x]
    price = next((money(x) for x in snippets if money(x) is not None), None)
    lines = [f'Research completed for: {query}.', f'Collected {len(evidence)} web source(s).']
    if price:
        lines.append(f'Lowest price-like value found in the evidence: ₹{price:,.0f}. Verify the retailer page before purchase.')
    if snippets:
        lines.append('Key evidence: ' + snippets[0][:500])
    lines.append('For deeper AI synthesis, configure OPENAI_API_KEY in Streamlit secrets.')
    return '\n\n'.join(lines)


def ai_summary(query, evidence):
    if not openai_key or not evidence:
        return simple_summary(query, evidence)
    text = '\n\n'.join(f"SOURCE: {x.get('title')}\n{x.get('content', x.get('raw_content',''))[:2200]}\nURL: {x.get('url')}" for x in evidence[:10])
    payload = {'model': openai_model, 'messages': [
        {'role': 'system', 'content': 'You are a careful shopping research analyst. Use only supplied evidence. Do not invent specs, prices, ratings, or claims. Distinguish retailer facts from review opinions.'},
        {'role': 'user', 'content': f'Research request: {query}\n\nEvidence:\n{text}\n\nGive a concise verdict, key facts/specifications found, 3 pros, 3 cons, who should buy it, and important caveats.'}
    ], 'temperature': 0.2}
    r = requests.post('https://api.openai.com/v1/chat/completions', headers={'Authorization': f'Bearer {openai_key}', 'Content-Type': 'application/json'}, json=payload, timeout=75)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def research_product_url(url):
    host = urlparse(url).netloc.lower()
    asin = amazon_asin(url)
    evidence = []

    # First try the configured extractor. Then use Jina Reader, which needs no API key.
    try:
        extracted = tavily_extract(url) if tavily_key else None
        if extracted:
            evidence.append({'title': extracted.get('url', 'Product page'), 'url': extracted.get('url', url),
                             'content': extracted.get('raw_content', '')})
    except Exception:
        pass
    if not evidence:
        try:
            evidence.append(jina_extract(url))
        except Exception:
            pass

    if asin:
        queries = [
            f'"{asin}" Amazon India product specifications price',
            f'"{asin}" reviews complaints problems',
            f'"{asin}" review laptop',
        ]
    else:
        queries = [f'"{url}" product reviews price specifications', f'{host} product reviews complaints']

    for query in queries:
        try:
            evidence.extend(web_search(query, max_results=6))
        except Exception:
            pass

    if not evidence:
        raise RuntimeError('Could not read or find this product. Try the clean product URL (without tracking parameters) or paste the product name.')

    # Deduplicate URLs while preserving evidence order.
    unique, seen_urls = [], set()
    for x in evidence:
        u = x.get('url', '')
        if u and u not in seen_urls:
            seen_urls.add(u)
            unique.append(x)

    return {'query': url, 'asin': asin, 'summary': ai_summary(url, unique),
            'products': make_products(unique),
            'sources': [{'title': x.get('title'), 'url': x.get('url'), 'snippet': clean_text(x.get('content', x.get('raw_content','')))[:350]}
                        for x in unique[:20] if x.get('url')]}


def direct_research(query):
    sources = web_search(query + ' India price reviews Amazon Flipkart', max_results=10)
    if not sources:
        raise RuntimeError('No web results were returned. Please try again.')
    return {'query': query, 'summary': ai_summary(query, sources), 'products': make_products(sources),
            'sources': [{'title': x.get('title'), 'url': x.get('url'), 'snippet': clean_text(x.get('content',''))[:350]} for x in sources if x.get('url')]}


if go and q:
    q = q.strip()
    with st.spinner('Researching the product and gathering independent evidence...'):
        try:
            # URL inputs never call localhost. This is the production-safe path.
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
