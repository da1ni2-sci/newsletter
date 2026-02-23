import os
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

class EmailDeliveryTool:
    def __init__(self):
        self.smtp_host = "smtp-relay.brevo.com"
        self.smtp_port = 587
        self.user = os.getenv("BREVO_USER")
        self.password = os.getenv("BREVO_PASS")
        self.sender_email = "service@fordige.com"
        self.sender_name = "鍛碼匠 Fordige"

    async def send_newsletter(
        self, 
        recipient_emails: List[str], 
        subject: str, 
        html_content: str
    ) -> dict:
        """
        Sends the newsletter to a list of recipients via Brevo SMTP.
        Uses a more robust connection method to avoid TLS errors.
        """
        if not self.user or not self.password:
            return {"success": False, "error": "SMTP credentials missing in .env"}

        results = {"success_count": 0, "failed_emails": []}

        try:
            # 使用 context manager 並讓 aiosmtplib 處理 STARTTLS
            # 某些環境下手動呼叫 starttls() 會與自動協商衝突
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=False # 587 端口不直接使用 TLS，而是透過 STARTTLS 升級
            ) as smtp:
                await smtp.login(self.user, self.password)

                for email in recipient_emails:
                    try:
                        message = MIMEMultipart("alternative")
                        message["Subject"] = subject
                        message["From"] = f"{self.sender_name} <{self.sender_email}>"
                        message["To"] = email

                        part = MIMEText(html_content, "html")
                        message.attach(part)

                        await smtp.send_message(message)
                        results["success_count"] += 1
                    except Exception as e:
                        results["failed_emails"].append({"email": email, "error": str(e)})

            return {"success": True, "data": results}

        except Exception as e:
            return {"success": False, "error": f"SMTP connection error: {str(e)}"}
