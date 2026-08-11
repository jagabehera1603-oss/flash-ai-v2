import os, requests, streamlit as st

st.set_page_config(page_title='Jagadish_webscraping', page_icon='🔎', layout='wide')

st.markdown('''<style>
.main {max-width: 1180px; margin:auto}
.hero {padding: 48px 0 28px; text-align:center}
.hero h1 {font-size:58px; margin-bottom:8px}
.hero p {font-size:20px; opacity:.7}
.card {padding:18px; border:1px solid rgba(128,128,128,.25); border-radius:16px; margin:10px 0}
.score {font-size:30px; font-weight:800}
</style>''', unsafe_allow_html=True)

api = st.secrets.get('DJANGO_API_URL', os.getenv('DJANGO_API_URL','http://localhost:8000/api')).rstrip('/')

st.markdown('<div class="hero"><h1>🔎 Jagadish_webscraping</h1><p>AI-powered product research, review aggregation and comparisons.</p></div>', unsafe_allow_html=True)

q = st.text_input('What are you looking for?', placeholder='Best phone under ₹30,000 for camera and battery')
col1, col2 = st.columns([1,5])
with col1:
    go = st.button('🔎 Research', use_container_width=True, type='primary')

if go and q:
    with st.spinner('Searching the web, analyzing evidence and scoring products...'):
        try:
            r = requests.get(f'{api}/research/', params={'q':q}, timeout=90)
            r.raise_for_status()
            data = r.json()
            st.session_state['result'] = data
        except Exception as e:
            st.error(f'Backend unavailable: {e}')

if 'result' in st.session_state:
    data = st.session_state['result']
    st.subheader('🧠 AI Research Summary')
    st.write(data.get('summary',''))
    products = data.get('products', [])
    st.subheader(f'🏆 Products found ({len(products)})')
    for i,p in enumerate(products):
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
        st.markdown(f"- [{s.get('title','Source')}]({s.get('url','')}) — {s.get('snippet','')}")
else:
    st.info('Try a request such as: “Best laptop under ₹70,000 for coding” or “Compare iPhone 17 vs Galaxy S26”.')
