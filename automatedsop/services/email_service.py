from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.conf import settings
import os


class EmailService:
    """Centralized email service"""

    @staticmethod
    def send_report_email(site_name, date, report_url, recipients, subject_suffix="Report"):
        """Send standard report email"""
        subject = f"{site_name} - {subject_suffix} - {date}"
        body = f"The report for {site_name} on {date} has been generated.\n\nView it at: {report_url}"

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.send()

    @staticmethod
    def send_file_attachment_email(site_name, date, filepath, recipients, subject_suffix="Report"):
        """Send email with file attachment"""
        subject = f"{site_name} - {subject_suffix} - {date}"
        body = f"Please find attached the {subject_suffix.lower()} for {site_name}."

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email="harshitshrimalee.wevois@gmail.com",
            to=recipients,
        )
        email.attach_file(filepath)
        email.send()