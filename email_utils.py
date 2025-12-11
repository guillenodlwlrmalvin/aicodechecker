"""Email utility functions for CodeCraft application."""
import smtplib
import ssl
from email.mime.text import MIMEText
from flask import url_for, current_app


def send_verification_email(recipient_email: str, code: str, app_instance) -> None:
    """Send a Gmail-based verification email with 6-digit code if SMTP is configured.
    This is for EMAIL/PASSWORD registration - user must verify before login.
    """
    gmail_user = app_instance.config.get('MAIL_GMAIL_USER')
    gmail_pass = app_instance.config.get('MAIL_GMAIL_PASS')
    
    # Remove spaces from password if present (Gmail App Passwords sometimes have spaces)
    if gmail_pass:
        gmail_pass = gmail_pass.replace(' ', '')

    if not gmail_user or not gmail_pass:
        # Dev fallback: no SMTP configured
        app_instance.logger.warning(f"Gmail SMTP credentials not configured; skipping verification email. Verification code: {code}")
        return

    subject = "Verify your CodeCraft account"
    body = f"""Hello,

Thank you for registering for CodeCraft.

Your verification code is: {code}

Enter this code on the verification page to activate your account.

This code will expire in 10 minutes.

If you did not request this, you can ignore this email.

– CodeCraft"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = recipient_email
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [recipient_email], msg.as_string())
        app_instance.logger.info(f"✓ Verification email with code sent to {recipient_email}")
    except smtplib.SMTPAuthenticationError as e:
        app_instance.logger.error(f"✗ Gmail authentication failed for {gmail_user}: {e}")
        app_instance.logger.error("Please check your Gmail App Password is correct and 2-Step Verification is enabled.")
    except Exception as e:
        app_instance.logger.error(f"✗ Failed to send verification email to {recipient_email}: {e}", exc_info=True)


def send_welcome_email(recipient_email: str, name: str, app_instance) -> None:
    """Send a welcome/confirmation email to Google SSO users.
    This is for GOOGLE SSO registration - user is already verified by Google.
    """
    gmail_user = app_instance.config.get('MAIL_GMAIL_USER')
    gmail_pass = app_instance.config.get('MAIL_GMAIL_PASS')
    
    # Remove spaces from password if present (Gmail App Passwords sometimes have spaces)
    if gmail_pass:
        gmail_pass = gmail_pass.replace(' ', '')

    if not gmail_user or not gmail_pass:
        # Dev fallback: no SMTP configured
        app_instance.logger.warning(f"Gmail SMTP credentials not configured; skipping welcome email for {recipient_email}")
        return

    subject = "Welcome to CodeCraft!"
    body = f"""Hello {name},

Welcome to CodeCraft! Your account has been successfully created and verified.

Your account is ready to use. You can start analyzing code, joining groups, and submitting activities right away.

Since you signed up with Google, your account is already verified and approved.

If you have any questions, feel free to reach out.

Happy coding!

– The CodeCraft Team"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = recipient_email
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [recipient_email], msg.as_string())
        app_instance.logger.info(f"✓ Welcome email sent successfully to {recipient_email}")
    except smtplib.SMTPAuthenticationError as e:
        app_instance.logger.error(f"✗ Gmail authentication failed for {gmail_user}: {e}")
        app_instance.logger.error("Please check your Gmail App Password is correct and 2-Step Verification is enabled.")
    except Exception as e:
        app_instance.logger.error(f"✗ Failed to send welcome email to {recipient_email}: {e}", exc_info=True)

