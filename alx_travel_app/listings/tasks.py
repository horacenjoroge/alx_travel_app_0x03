"""
Celery tasks for the listings app.
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_booking_confirmation_email(booking_id, user_email, listing_name, check_in_date, check_out_date):
    """
    Send a booking confirmation email to the user.
    
    Args:
        booking_id: The ID of the booking
        user_email: The email address of the user
        listing_name: The name of the listing/property
        check_in_date: Check-in date
        check_out_date: Check-out date
    
    Returns:
        str: Success or failure message
    """
    try:
        subject = f'Booking Confirmation - {listing_name}'
        
        message = f"""
        Dear Customer,
        
        Thank you for your booking!
        
        Booking Details:
        ----------------
        Booking ID: {booking_id}
        Property: {listing_name}
        Check-in Date: {check_in_date}
        Check-out Date: {check_out_date}
        
        Your booking has been confirmed. We look forward to hosting you!
        
        If you have any questions, please don't hesitate to contact us.
        
        Best regards,
        ALX Travel App Team
        """
        
        # Send the email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        
        logger.info(f"Booking confirmation email sent successfully for booking {booking_id}")
        return f"Email sent successfully to {user_email}"
        
    except Exception as e:
        logger.error(f"Failed to send booking confirmation email for booking {booking_id}: {str(e)}")
        raise