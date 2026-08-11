from rest_framework.decorators import api_view
from rest_framework.response import Response
from .research import run, summarize
from .models import Research, Product

@api_view(['GET'])
def health(request):
    return Response({'status':'ok','service':'flash-ai-v2'})

@api_view(['GET','POST'])
def research(request):
    query = (request.data.get('query') if request.method == 'POST' else request.GET.get('q','')) or ''
    query = query.strip()
    if not query:
        return Response({'error':'Enter a product or shopping request.'}, status=400)
    products, sources = run(query)
    summary = summarize(query, sources)
    session = Research.objects.create(query=query)
    for p in products:
        Product.objects.create(research=session, **p)
    return Response({'query':query,'summary':summary,'products':products,'sources':[{'title':x.get('title'),'url':x.get('url'),'snippet':x.get('content','')[:300]} for x in sources]})

@api_view(['POST'])
def compare(request):
    items = request.data.get('products', [])
    ranked = sorted(items, key=lambda x: float(x.get('score') or 0), reverse=True)
    return Response({'products': ranked})
