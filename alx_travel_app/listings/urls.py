# listings/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('bookings/create/', views.create_booking, name='create-booking'),
    path('payments/initiate/', views.initiate_payment, name='initiate-payment'),
    path('payments/verify/', views.verify_payment, name='verify-payment'),
    path('payments/status/<uuid:payment_id>/', views.payment_status, name='payment-status'),
]