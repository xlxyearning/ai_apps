import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# --- Core Logic (For Scripts) ---

def send_email_core(subject: str, body: str, to_addrs: list = None, is_html: bool = True) -> bool:
    """
    发送邮件的核心逻辑。
    
    Args:
        subject: 邮件标题
        body: 邮件内容
        to_addrs: 收件人列表 (如果不传，则读取环境变量 EMAIL_RECIPIENTS)
        is_html: 是否为 HTML 格式
    """
    # Load config
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    
    # Default recipients
    if to_addrs is None:
        recipients_str = os.getenv("EMAIL_RECIPIENTS", "")
        if recipients_str:
            to_addrs = [r.strip() for r in recipients_str.split(",")]
        else:
            to_addrs = []

    if not sender or not password or not to_addrs:
        print("Error: Email configuration (SENDER, PASSWORD, RECIPIENTS) missing.")
        return False
        
    if sender == "YOUR_EMAIL@gmail.com":
        print("Error: Default email configuration detected. Please configure .env.")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ", ".join(to_addrs)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html' if is_html else 'plain'))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            
        server.login(sender, password)
        server.sendmail(sender, to_addrs, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# --- MCP Interface (For LLM Agent) ---

def send_email_tool(subject: str, content: str, recipient: str = None) -> str:
    """
    发送邮件给指定收件人（或默认列表）。
    
    Args:
        subject: 邮件标题。
        content: 邮件正文内容（支持简单 HTML）。
        recipient: (可选) 单个收件人邮箱地址。如果不填，则发送给系统配置的默认收件人列表。
    """
    to_list = [recipient] if recipient else None
    
    success = send_email_core(subject, content, to_addrs=to_list, is_html=True)
    
    if success:
        target = recipient if recipient else "默认收件人列表"
        return f"邮件 '{subject}' 已成功发送给 {target}。"
    else:
        return "邮件发送失败，请检查服务器日志或配置。"
