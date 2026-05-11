from datetime import timedelta
import random
from django.utils import timezone 
from .models import EmailVerificationOTP
from django.core.mail import EmailMessage
import threading

#Generate a random 6-digit OTP
def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


#Create an OTP record for email verification
def create_otp_for_user(user, otp_expiry_minutes=10):
    otp = generate_otp()
    expires_at = timezone.now() + timedelta(minutes=otp_expiry_minutes)

    email_otp = EmailVerificationOTP.objects.create(
        user=user,
        otp=otp,
        expires_at=expires_at
    )

    return email_otp

class EmailThread(threading.Thread):
    def __init__(self,email):
        self.email = email
        threading.Thread.__init__(self)

    def run(self):
        self.email.send()


class Util:
    @staticmethod
    def send_email(data):
        email = EmailMessage(
            subject=data['email_subject'], body=data['email_body'], to=[data['to_email']])
        EmailThread(email).start()