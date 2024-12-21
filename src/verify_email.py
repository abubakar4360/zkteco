import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(subject: str, recipient: str, body: str):
    email = "abubakarabbasi1000@gmail.com"
    password = "tmvl mgad mmpy mllu"
    smtp_server = "smtp.gmail.com"
    port = 465

    msg = MIMEMultipart()
    msg['From'] = email
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL(smtp_server, port) if port == 465 else smtplib.SMTP(smtp_server, port) as server:
            if port != 465:
                server.starttls()
            server.login(email, password)
            server.send_message(msg)
            print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")
