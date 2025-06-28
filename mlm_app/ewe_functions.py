import random
import requests
import string
import smtplib
from email.message import EmailMessage
from django.contrib.auth.models import User
import os


def generate_random_password(length: int):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

def send_gmail(receiver_gmail: str, subject: str, message: str):
    try:
        # Get email credentials from environment variables
        email_user = os.getenv("EMAIL_HOST_USER", "mskearning@gmail.com")
        email_password = os.getenv("EMAIL_HOST_PASSWORD", "default_password")
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_user, email_password)
        email = EmailMessage()
        email['From'] = "MSK Earning"
        email['To'] = receiver_gmail
        email['Subject'] = subject
        email.set_content(message)
        server.send_message(email)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            server.quit()
        except:
            pass

def generate_username():
    """Generates a unique username starting with 'MSK' followed by random digits."""
    while True:
        username = f"MSK{''.join(random.choices(string.digits, k=6))}"
        if not User.objects.filter(username=username).exists():
            return username

def create_otp(digits: int):
    return random.randint(10**(digits - 1), 10**digits - 1)


# API Configuration for mobile recharge service
API_URL = "https://mrobotics.in/api/recharge"
API_TOKEN = os.getenv("RECHARGE_API_TOKEN", "0c5b76e1-c06b-4a8f-a5cb-c7102d9ca11b")


def create_order_id(digits: int):
    return random.randint(10**(digits - 1), 10**digits - 1)

def recharge_mobile(mobile_no, amount, company_name, order_id, is_stv=False):
    company_ids = {
        "vi": 1,
        "airtel": 2,
        "bsnl": 4,
        "jio": 5
    }
    company_id = company_ids.get(company_name.lower(), None)
    
    if company_id is None:
        return {"error": "Invalid company name", "status": "failed"}
    
    data = {
        "api_token": API_TOKEN,
        "mobile_no": mobile_no,
        "amount": amount,
        "company_id": company_id,
        "order_id": order_id,
        "is_stv": str(is_stv).lower()
    }
    
    try:
        response = requests.post(API_URL, data=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": "API request failed", "details": str(e), "status": "failed"}

def check_recharge_status(mobile_no, amount, company_name, order_id, is_stv=False):
    company_ids = {
        "vodafone": 1,
        "airtel": 2,
        "idea": 3,
        "bsnl": 4,
        "jio": 5
    }
    
    company_id = company_ids.get(company_name.lower())
    if company_id is None:
        return {"error": "Invalid company name"}
    
    url = (f"https://mrobotics.in/api/recharge_get?api_token={API_TOKEN}"
           f"&mobile_no={mobile_no}&amount={amount}&company_id={company_id}"
           f"&order_id={order_id}&is_stv={str(bool(is_stv)).lower()}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raises an error for HTTP failure codes (4xx, 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": "API request failed", "details": str(e)}

def send_registration_email(email, username, password, referrer_username):
    """Send registration confirmation email with login credentials and referral links."""
    try:
        subject = "Welcome to MSK Earning - Registration Successful"
        message = f"""
Dear Member,

Welcome to MSK Earning! Your registration has been completed successfully.

Login Credentials:
Username: {username}
Password: {password}

Your Referral Links:
Right Position: http://127.0.0.1:5000/referral/{username}/Right/
Left Position: http://127.0.0.1:5000/referral/{username}/Left/

Please keep these credentials safe and change your password after first login.

Thank you for joining MSK Earning!

Best Regards,
MSK Earning Team
        """
        send_gmail(email, subject, message)
        return True
    except Exception as e:
        print(f"Error sending registration email: {e}")
        return False

def calculate_level_income(member, new_member_plan):
    """Calculate and distribute level income to upline members."""
    from .models import Level, IncomeHistory, CompanyWallet
    from decimal import Decimal
    
    try:
        plan = new_member_plan.plan
        levels = Level.objects.filter(plan=plan).order_by('level')
        
        current_member = member
        for level_obj in levels:
            # Find the sponsor at this level
            for _ in range(level_obj.level):
                if current_member and current_member.sponsor:
                    current_member = current_member.sponsor.mlm_profile
                else:
                    return  # No more sponsors up the line
            
            if current_member and current_member.status == 'Active':
                level_income = Decimal(level_obj.distributed_amount)
                
                # Add income to the member
                current_member.level_income += level_income
                current_member.total_income += level_income
                current_member.today_income += level_income
                current_member.account_balance += level_income
                current_member.save(update_fields=['level_income', 'total_income', 'today_income', 'account_balance'])
                
                # Create income history record
                IncomeHistory.objects.create(
                    member=current_member,
                    income_type='level_income',
                    amount=level_income,
                    description=f"Level {level_obj.level} income from {member.user.username}"
                )
                
                # Deduct from company wallet
                try:
                    company_wallet, _ = CompanyWallet.objects.get_or_create(id=1)
                    company_wallet.deduct_from_wallet(level_income)
                except Exception as e:
                    print(f"Error deducting level income from company wallet: {e}")
    
    except Exception as e:
        print(f"Error calculating level income: {e}")
