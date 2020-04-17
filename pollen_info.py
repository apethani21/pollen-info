import os
import ssl
import json
import requests
import pandas as pd
import logging as lgg
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


lgg.basicConfig(level=lgg.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s')

base_url = f'https://www.avogel.co.uk/health/hayfever/pollen-forecast/london/'
regions = ['north-london/',
           'west-london/',
           'central-london/',
           'south-london/',
           'east-london/']
urls = [base_url] + [base_url + region for region in regions]


def get_email_credentials():
    home = os.path.expanduser('~')
    with open(f"{home}/keys/gmail/sender_config.json", "r") as f:
        config = json.loads(f.read())
    return config


def get_aws_ses_credentials():
    home = os.path.expanduser('~')
    with open(f"{home}/keys/aws/ses-credentials.json", "r") as f:
        config = json.loads(f.read())
    return config


def get_pollen_info(url):
    r = requests.get(url, timeout=1)
    html = r.content.decode()
    soup = BeautifulSoup(html, 'html.parser')
    pollen_table = soup.find_all("tr")

    parsed_pollen_table = []
    for row in pollen_table:
        tag_contents = row.contents
        tag_contents = [item for item in tag_contents if not isinstance(item, str)]
        tag_contents = [item.contents for item in tag_contents if item.contents]
        parsed_pollen_table.append(tag_contents)

    pollen_info = {}
    for row in parsed_pollen_table:
        if len(row) == 1:
            continue
        elif len(row) == 5:
            dates = [str(day) for item in row for day in item]
        elif len(row) == 6:
            pollen_source = row[0][0]
            pollen_forecast = [i.attrs["title"] for item in row[1:] for i in item]
            pollen_forecast = dict(zip(dates, pollen_forecast))
            pollen_info[pollen_source] = pollen_forecast
        else:
            lgg.warning(f"Row of length {len(row)} found, but lengths 1, 5 or 6 expected.")
            lgg.warning(row)
    return pollen_info


def get_pollen_forecast():
    pollen_forecast = {}
    for url in urls:
        pollen_forecast = get_pollen_info(url)
        if len(pollen_forecast) != 0:
            lgg.info(f"Got forecast for {url.split('/')[-2]}")
            return pollen_forecast
    return pollen_forecast


def pollen_data(pollen_forecast):
    day = datetime.today().day
    data_to_keep = {}
    for pollen_type, value in pollen_forecast.items():
        if pollen_type == "Overall":
            data_to_keep[pollen_type] = value
        else:
            for date, level in value.items():
                if 'high' in level.lower():
                    data_to_keep[pollen_type] = value
                    break
    return data_to_keep
            

def main():
    pollen_forecast = get_pollen_forecast()
    if len(pollen_forecast) == 0:
        lgg.info("No pollen forecasts found")
        return
    data = pollen_data(pollen_forecast)
    if len(data) == 0:
        lgg.info("No significant info")
    else:
        lgg.info("Forecast of significance found")
        df = pd.DataFrame(data).to_html()

        # create and send email
        email_credentials = get_email_credentials()
        receiver_email = email_credentials["receiver_email"]
        sender_email = email_credentials["sender_email"]
        message = MIMEMultipart("alternative")
        message["Subject"] = f"Pollen update - {datetime.now().strftime('%a %d %b %y')}"
        html_main = MIMEText(df, "html")
        message["From"] = sender_email
        message["To"] = receiver_email
        message.attach(html_main)
        password = email_credentials["sender_password"]
        context = ssl.create_default_context()
        aws_ses_credentials = get_aws_ses_credentials()
        smtp_username = aws_ses_credentials["smtp-username"]
        smtp_password = aws_ses_credentials["smtp-password"]
        with smtplib.SMTP("email-smtp.eu-west-2.amazonaws.com",
                          port=587) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message, sender_email, receiver_email)
        lgg.info("pollen update sent")
    return


if __name__ == "__main__":
    main()
