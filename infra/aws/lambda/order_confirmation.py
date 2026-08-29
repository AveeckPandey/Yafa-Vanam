"""SQS consumer for paid YAFA VANAM order receipts.

The API publishes only after a verified Razorpay payment. SQS can retry this
function safely; the order number is the idempotency key recorded by the API.
"""
import html
import json
import os
import boto3

ses = boto3.client("sesv2")

def money(value, currency="INR"):
    return f"{currency} {float(value):,.2f}"

SITE = "https://yafavanam.buildwithaveeck.com"

def trusted_product_image(value):
    """Allow only YAFA-hosted HTTPS images; never render a buyer-supplied URL."""
    image = str(value or "").strip()
    if image.startswith("/"):
        return SITE + image
    if image.startswith(SITE + "/"):
        return image
    return ""

def handler(event, _context):
    for record in event["Records"]:
        order = json.loads(record["body"])
        recipient = order["customer_email"]
        lines = "".join(
            f"<tr><td style='padding:8px 10px 8px 0;width:72px'>{('<img src=\"' + trusted_product_image(item.get('image')) + '\" width=\"64\" height=\"64\" style=\"display:block;object-fit:cover\" alt=\"' + html.escape(item['name'], quote=True) + '\">') if trusted_product_image(item.get('image')) else ''}</td><td style='padding:8px 0'>{html.escape(item['name'])}"
            f"<br><small>{item.get('shade') or item.get('size') or ''}</small>"
            f"</td><td align='center'>{int(item['quantity'])}</td>"
            f"<td align='right'>{money(item['unit_price'] * item['quantity'], order['currency'])}</td></tr>"
            for item in order["items"]
        )
        address = order["shipping_address"]
        address_html = "<br>".join(html.escape(str(part)) for part in [address["recipient_name"], address["line1"], address.get("line2"), f"{address['city']}, {address['state_region']} {address['postal_code']}", address.get("country_code", "IN")] if part)
        site = SITE
        html_body = f"""<html><body style='margin:0;background:#f8f4ef;font-family:Arial,sans-serif;color:#171313'><table role='presentation' width='100%'><tr><td align='center'><table role='presentation' width='600' style='max-width:600px;background:#fff'><tr><td><img src='{site}/email/welcome-hero.png' width='600' style='display:block;width:100%' alt='YAFA VANAM'></td></tr><tr><td style='padding:32px'><img src='{site}/email/yafa-logo.png' width='64' alt='YAFA VANAM'><h1>Thank you for your order</h1><p>We have received your payment and are preparing your ritual.</p><p><strong>Order {html.escape(order['order_number'])}</strong></p><table width='100%' style='border-collapse:collapse'>{lines}<tr><td colspan='2' style='border-top:1px solid #ddd;padding-top:14px'><strong>Total</strong></td><td align='right' style='border-top:1px solid #ddd;padding-top:14px'><strong>{money(order['total_amount'], order['currency'])}</strong></td></tr></table><h2>Delivering to</h2><p>{address_html}</p><p>We will email you again when your order is on its way.</p><p>With care,<br>YAFA VANAM</p></td></tr></table></td></tr></table></body></html>"""
        text_body = f"Thank you for your order {order['order_number']}. Total: {money(order['total_amount'], order['currency'])}. We will email you again when it ships."
        # SQS supplies authenticated internal events only. Do not log customer
        # addresses, order contents, or payment references in this function.
        ses.send_email(FromEmailAddress=os.environ["SENDER"], Destination={"ToAddresses": [recipient]}, Content={"Simple": {"Subject": {"Data": f"Order confirmed: {order['order_number']}"}, "Body": {"Html": {"Data": html_body}, "Text": {"Data": text_body}}}})
