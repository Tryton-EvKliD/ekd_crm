# -*- coding: utf-8 -*-
##############################################################################
#
##############################################################################
#----------------------------------------------------------
# Emails
#----------------------------------------------------------
def email_send(email_from, email_to, subject, body, email_cc=None, email_bcc=None, reply_to=False,
               attach=None, debug=False, subtype='plain', x_headers=None):

    """Send an email."""
    import smtplib
    from email.MIMEText import MIMEText
    from email.MIMEBase import MIMEBase
    from email.MIMEMultipart import MIMEMultipart
    from email.Header import Header
    from email.Utils import formatdate, COMMASPACE
    from email.Utils import formatdate, COMMASPACE
    from email import Encoders

    if x_headers is None:
        x_headers = {}

    if not ssl:
        ssl = config.get('smtp_ssl', False)

    if not email_from and not config['email_from']:
        raise Exception("No Email sender by default, see config file")

    if not email_cc:
        email_cc = []
    if not email_bcc:
        email_bcc = []

    if not attach:
        try:
            msg = MIMEText(body.encode('utf8') or '',_subtype=subtype,_charset='utf-8')
        except:
            msg = MIMEText(body or '',_subtype=subtype,_charset='utf-8')
    else:
        msg = MIMEMultipart()

    msg['Subject'] = Header(ustr(subject), 'utf-8')
    msg['From'] = email_from
    del msg['Reply-To']
    if reply_to:
        msg['Reply-To'] = reply_to
    else:
        msg['Reply-To'] = msg['From']
    msg['To'] = COMMASPACE.join(email_to)
    if email_cc:
        msg['Cc'] = COMMASPACE.join(email_cc)
    if email_bcc:
        msg['Bcc'] = COMMASPACE.join(email_bcc)
    msg['Date'] = formatdate(localtime=True)

    # Add EKD Tryton Server information
    msg['X-Generated-By'] = 'EKD-Tryton (http://www.tryton.org)'
    msg['X-EKD-Tryton-Server-Host'] = socket.gethostname()
    msg['X-EKD-Tryton-Server-Version'] = release.version

    # Add dynamic X Header
    for key, value in x_headers.items():
        msg['X-EKD-Tryton-%s' % key] = str(value)

    if attach:
        try:
            msg.attach(MIMEText(body.encode('utf8') or '',_subtype=subtype,_charset='utf-8'))
        except:
            msg.attach(MIMEText(body or '', _charset='utf-8', _subtype=subtype) )
        for (fname,fcontent) in attach:
            part = MIMEBase('application', "octet-stream")
            part.set_payload( fcontent )
            Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % (fname,))
            msg.attach(part)

    class WriteToLogger(object):
        def __init__(self):
            self.logger = netsvc.Logger()

        def write(self, s):
            self.logger.notifyChannel('email_send', netsvc.LOG_DEBUG, s)

    try:
        oldstderr = smtplib.stderr
        s = smtplib.SMTP()

        try:
            # in case of debug, the messages are printed to stderr.
            if debug:
                smtplib.stderr = WriteToLogger()

            s.set_debuglevel(int(bool(debug)))  # 0 or 1

            s.connect(config['smtp_server'], config['smtp_port'])
            if ssl:
                s.ehlo()
                s.starttls()
                s.ehlo()

            if config['smtp_user'] or config['smtp_password']:
                s.login(config['smtp_user'], config['smtp_password'])

            s.sendmail(email_from, 
                       flatten([email_to, email_cc, email_bcc]), 
                       msg.as_string()
                      )

        finally:
            s.quit()
            if debug:
                smtplib.stderr = oldstderr

    except Exception, e:
        netsvc.Logger().notifyChannel('email_send', netsvc.LOG_ERROR, e)
        return False
    
    return True

#----------------------------------------------------------
# SMS
#----------------------------------------------------------
# text must be latin-1 encoded
def sms_send(user, password, api_id, text, to):
    import urllib
    url = "http://api.urlsms.com/SendSMS.aspx"
    #url = "http://196.7.150.220/http/sendmsg"
    params = urllib.urlencode({'UserID': user, 'Password': password, 'SenderID': api_id, 'MsgText': text, 'RecipientMobileNo':to})
    f = urllib.urlopen(url+"?"+params)
    # FIXME: Use the logger if there is an error
    return True

