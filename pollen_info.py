import requests
import pandas as pd
from bs4 import BeautifulSoup


def get_pollen_forecast():
    url = 'https://www.avogel.co.uk/health/hayfever/pollen-forecast/london/north-london'
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
            print(f"Row of length {len(row)} found, but lengths 1, 5 or 6 expected.")
            print(row)
    return pollen_info


if __name__ == "__main__":
    print(pd.DataFrame(get_pollen_forecast()))
