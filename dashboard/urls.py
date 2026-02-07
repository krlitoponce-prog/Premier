from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_dashboard, name='home'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('lesionados/', views.lesionados, name='lesionados'),
    path('sancionados/', views.sancionados, name='sancionados'),
]