from django.urls import path
from shop.views import health, research, compare

urlpatterns = [
    path('api/health/', health),
    path('api/research/', research),
    path('api/compare/', compare),
]
