from django.db import models

class Research(models.Model):
    query = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

class Product(models.Model):
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=500)
    price = models.FloatField(null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    score = models.FloatField(default=0)
    url = models.URLField(max_length=1000, blank=True)
    source = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)
