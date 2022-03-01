import smtplib
from email.message import EmailMessage

def sendmail(to, subject, body=None, sender=None):
    if body is None:
        body = subject
    if sender is None:
        sender = 'lachouffe'

    msg = EmailMessage()
    msg.set_content(body)

    msg['From'] = sender
    msg['To'] = to
    msg['Subject'] = subject

    # Send the message via our own SMTP server.
    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()

