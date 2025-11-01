"""
Views for the listings app.
Handles booking creation, Chapa payment integration, and confirmation workflows.
"""

import uuid
import logging
import requests

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Booking, Payment, Listing
from .serializers import BookingSerializer
from .tasks import send_booking_confirmation_email, send_payment_confirmation_email

logger = logging.getLogger(__name__)


# =============================================================================
# Booking ViewSet - Clean, DRY, and Scalable
# =============================================================================

class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bookings.
    - Only allows users to access their own bookings.
    - Integrates with Chapa for payment initiation.
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's bookings."""
        return Booking.objects.filter(user=self.request.user).select_related('listing', 'user')

    def perform_create(self, serializer):
        """Create booking and queue confirmation email."""
        booking = serializer.save(user=self.request.user, status='pending')
        logger.info(f"Booking {booking.booking_id} created by user {self.request.user.id}")

        # Queue email confirmation
        try:
            send_booking_confirmation_email.delay(
                booking_id=booking.id,
                user_email=self.request.user.email,
                listing_name=booking.listing.name,
                check_in_date=str(booking.check_in),
                check_out_date=str(booking.check_out),
                guests=booking.guests
            )
            logger.info(f"Booking confirmation email queued for booking {booking.id}")
        except Exception as e:
            logger.error(f"Failed to queue booking email for {booking.id}: {str(e)}")

    def create(self, request, *args, **kwargs):
        """Override create to return user-friendly message."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response({
            'message': 'Booking created successfully. Confirmation email will be sent shortly.',
            'booking': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'], url_path='initiate-payment')
    def initiate_payment(self, request, pk=None):
        """
        Initiate payment for a booking using Chapa.
        POST /api/bookings/{id}/initiate-payment/
        """
        booking = self.get_object()

        # Prevent re-initiating payment if already paid
        if booking.payments.filter(payment_status='completed').exists():
            return Response({
                'error': 'This booking already has a completed payment.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate unique transaction reference
        tx_ref = f"tx-{uuid.uuid4()}"

        # Prepare Chapa payload
        payment_data = {
            "amount": str(booking.total_price),
            "currency": "ETB",
            "email": request.user.email,
            "first_name": request.user.first_name or request.user.username,
            "last_name": request.user.last_name or "",
            "tx_ref": tx_ref,
            "callback_url": request.build_absolute_uri('/api/payments/verify/'),
            "return_url": request.build_absolute_uri('/bookings/'),
            "customization": {
                "title": "Travel Booking Payment",
                "description": f"Payment for booking {booking.booking_id}"
            }
        }

        headers = {
            "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                f"{settings.CHAPA_BASE_URL}/transaction/initialize",
                json=payment_data,
                headers=headers,
                timeout=30
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 'success':
                # Create payment record
                payment = Payment.objects.create(
                    booking=booking,
                    transaction_id=tx_ref,
                    amount=booking.total_price,
                    currency='ETB',
                    payment_status='pending',
                    chapa_reference=tx_ref,
                    checkout_url=response_data['data']['checkout_url']
                )

                logger.info(f"Payment initiated for booking {booking.booking_id}, tx_ref: {tx_ref}")

                return Response({
                    'message': 'Payment initiated successfully',
                    'payment_id': str(payment.payment_id),
                    'checkout_url': response_data['data']['checkout_url'],
                    'transaction_reference': tx_ref
                }, status=status.HTTP_200_OK)

            else:
                logger.error(f"Chapa initialization failed: {response_data}")
                return Response({
                    'error': 'Failed to initiate payment with Chapa',
                    'details': response_data
                }, status=status.HTTP_400_BAD_REQUEST)

        except requests.RequestException as e:
            logger.error(f"Chapa API error: {str(e)}")
            return Response({
                'error': 'Payment service temporarily unavailable'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception(f"Unexpected error in initiate_payment: {str(e)}")
            return Response({
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Payment Verification & Status
# =============================================================================

@api_view(['GET', 'POST'])
def verify_payment(request):
    """
    Verify payment status with Chapa.
    Called by Chapa webhook or frontend polling.
    """
    tx_ref = request.GET.get('tx_ref') or request.data.get('tx_ref')

    if not tx_ref:
        return Response({'error': 'tx_ref is required'}, status=status.HTTP_400_BAD_REQUEST)

    headers = {"Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"}

    try:
        response = requests.get(
            f"{settings.CHAPA_BASE_URL}/transaction/verify/{tx_ref}",
            headers=headers,
            timeout=30
        )
        response_data = response.json()

        if response.status_code != 200 or response_data.get('status') != 'success':
            return Response({
                'error': 'Payment verification failed',
                'details': response_data
            }, status=status.HTTP_400_BAD_REQUEST)

        payment_info = response_data['data']
        payment = Payment.objects.filter(transaction_id=tx_ref).first()

        if not payment:
            return Response({'error': 'Payment record not found'}, status=status.HTTP_404_NOT_FOUND)

        if payment_info['status'] == 'success':
            payment.payment_status = 'completed'
            payment.payment_method = payment_info.get('payment_method', '')
            payment.verified_at = timezone.now()
            payment.save()

            # Update booking
            booking = payment.booking
            booking.status = 'confirmed'
            booking.save()

            # Send confirmation email
            try:
                send_payment_confirmation_email.delay(
                    user_email=booking.user.email,
                    booking_id=str(booking.booking_id),
                    amount=str(payment.amount),
                    check_in=str(booking.check_in),
                    check_out=str(booking.check_out),
                    listing_name=booking.listing.name
                )
                logger.info(f"Payment confirmation email queued for booking {booking.booking_id}")
            except Exception as e:
                logger.error(f"Failed to queue payment email: {str(e)}")

            return Response({
                'message': 'Payment verified and confirmed',
                'booking_id': str(booking.booking_id),
                'payment_status': 'completed'
            }, status=status.HTTP_200_OK)

        else:
            payment.payment_status = 'failed'
            payment.save()
            return Response({
                'message': 'Payment failed',
                'payment_status': 'failed'
            }, status=status.HTTP_400_BAD_REQUEST)

    except requests.RequestException as e:
        logger.error(f"Chapa verification request failed: {str(e)}")
        return Response({'error': 'Verification service unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.exception(f"Unexpected error in verify_payment: {str(e)}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_status(request, payment_id):
    """
    Get payment status for a user.
    GET /api/payments/status/{payment_id}/
    """
    try:
        payment = get_object_or_404(Payment, payment_id=payment_id)

        if payment.booking.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        return Response({
            'payment_id': str(payment.payment_id),
            'booking_id': str(payment.booking.booking_id),
            'amount': str(payment.amount),
            'currency': payment.currency,
            'status': payment.payment_status,
            'transaction_id': payment.transaction_id,
            'checkout_url': payment.checkout_url,
            'created_at': payment.created_at,
            'updated_at': payment.updated_at,
            'verified_at': payment.verified_at
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in payment_status: {str(e)}")
        return Response({'error': 'Failed to retrieve payment status'}, status=status.HTTP_400_BAD_REQUEST)