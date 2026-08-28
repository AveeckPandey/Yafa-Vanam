import json, os, urllib.request
import boto3

ses = boto3.client('sesv2')
secrets = boto3.client('secretsmanager')

def handler(event, context):
    # Post Confirmation is part of Cognito's synchronous confirmation request.
    # Coupon or SES failures must never turn a successfully confirmed account
    # into a misleading verification error for the customer.
    try:
        attrs = event['request']['userAttributes']
        email, subject = attrs['email'], attrs['sub']
        given_name = attrs.get('given_name', '').strip() or 'there'
        token = secrets.get_secret_value(SecretId=os.environ['RUNTIME_SECRET_ARN'])['SecretString']
        request = urllib.request.Request(
            os.environ['COUPON_API_URL'],
            data=json.dumps({'email': email, 'cognito_sub': subject}).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+token}, method='POST')
        with urllib.request.urlopen(request, timeout=8) as response:
            coupon = json.loads(response.read())
        code = coupon['code']
        site = 'https://yafavanam.buildwithaveeck.com'
        html = f'''<html><body style="margin:0;background:#f8f4ef;font-family:Arial,sans-serif;color:#171313"><table role="presentation" width="100%"><tr><td align="center"><table role="presentation" width="600" style="max-width:600px;background:#fff"><tr><td><img src="{site}/email/welcome-hero.png" width="600" style="display:block;width:100%" alt="YAFA VANAM beauty ritual"></td></tr><tr><td align="center" style="padding:32px"><img src="{site}/email/yafa-logo.png" width="70" alt="YAFA VANAM"><h1>Welcome, {given_name}!</h1><p>Beauty is personal. Consider this your invitation to explore colour, care and ritual made for you.</p><h2>Your welcome gift is 10% off</h2><p>Your personal code</p><p style="font-size:22px;font-weight:bold">{code}</p><p><a href="{site}" style="background:#111;color:#fff;padding:14px 26px;text-decoration:none">Find your ritual</a></p><p>With care,<br>YAFA VANAM</p></td></tr></table></td></tr></table></body></html>'''
        ses.send_email(FromEmailAddress=os.environ['SENDER'], Destination={'ToAddresses':[email]},
          Content={'Simple':{'Subject':{'Data':'Welcome to YAFA VANAM'}, 'Body':{'Html':{'Data':html}, 'Text':{'Data':f'Welcome, {given_name}! Your 10% code is {code}. Find your ritual: {site}'}}}})
    except Exception as reason:
        print(json.dumps({
            'level': 'warning',
            'event': 'welcome_coupon_delivery_deferred',
            'error_type': type(reason).__name__,
        }))
    return event
