import os
import bs4
import json
import smtplib
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


def get_pollen_and_pollution():
    "From BBC Weather, for Hendon."
    r = requests.get("https://www.bbc.co.uk/weather/2647116")
    html = r.content.decode()
    soup = BeautifulSoup(html, 'html.parser')
    try:
        pollen_info = soup.find("span", {"class": "wr-c-environmental-data__item--pollen"})
        pollen_info = [i.contents[0] for i in pollen_info]
        pollen_info = [str(i) for i in pollen_info if isinstance(i, bs4.element.NavigableString)]
    except TypeError:
        pollen_info = ["Pollen", "No info found"]
    try:
        pollution_info = soup.find("span", {"class": "wr-c-environmental-data__item--pollution"})
        pollution_info = [i.contents[0] for i in pollution_info]
        pollution_info = [str(i) for i in pollution_info if isinstance(i, bs4.element.NavigableString)]
    except TypeError:
        pollution_info = ["Pollution", "No info found"]
    return dict([pollen_info, pollution_info])


def bbc_info_to_html(info):
    colour_map = {'Low': '#2dc937',
                  'Moderate': '#e7b416',
                  'High': '#cc3232',
                  'Very High': '#ff0000'}
    return f"""
            <b> Pollen: </b><span style="color:{colour_map.get(info['Pollen'], '#000000')}">{info['Pollen']}</span><br>
            <b> Pollution: </b><span style="color:{colour_map.get(info['Pollution'], '#000000')}">{info['Pollution']}</span>
            """


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


def main(filter=True):
    pollen_forecast = get_pollen_forecast()

    if len(pollen_forecast) == 0:
        lgg.info("No pollen forecasts found")
        return

    if filter:
        data = pollen_data(pollen_forecast)
    else:
        data = pollen_forecast

    if len(data) == 1:
        lgg.info("No significant info")
        return

    else:
        lgg.info("Forecast of significance found")
        df = pd.DataFrame(data).to_html()
        bbc_info = get_pollen_and_pollution()
        bbc_info_html = bbc_info_to_html(bbc_info)
        html = f"""
        <b>Avogel Information</b><br>
        {df}<br>
        <b>BBC Information</b><br>
        {bbc_info_html}
        """
        # create and send email
        email_credentials = get_email_credentials()
        receiver_email = email_credentials["receiver_email"]
        sender_email = email_credentials["sender_email"]
        message = MIMEMultipart("alternative")
        message["Subject"] = f"Pollen update - {datetime.now().strftime('%a %d %b %y')}"
        html_main = MIMEText(html, "html")
        message["From"] = sender_email
        message["To"] = receiver_email
        message.attach(html_main)
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
    main(filter=False)
