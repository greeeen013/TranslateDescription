import requests
from bs4 import BeautifulSoup

def scrape_specifications(pnumber):
    url = f"https://shop.api.de/product/details/{pnumber}?seek=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Chyba stahování stránky: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    sections = soup.find_all("span", class_="displayTabOnPrint")

    if not sections:
        raise Exception("Nebyla nalezena žádná sekce s hlavními specifikacemi.")

    result_html = ""

    for section in sections:
        # Najdi všechny specifikační bloky v pořadí, jak se vyskytují na stránce
        spec_divs = section.find_all(
            lambda tag: tag.name == "div" and tag.get("class") in [["mb-5", "px-2", "pb-5"], ["mb-4", "px-2"]]
        )

        for div in spec_divs:
            title_tag = div.find("h6", class_="fw-bold")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            items_html = ""

            for row in div.find_all("div", class_="row mb-1 ms-3 align-items-end"):
                cols = row.find_all("div", class_="col")
                if len(cols) < 2:
                    continue
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                items_html += f"<li>{key}: {value}</li>\n"

            if items_html:
                result_html += f"<b>{title}</b>\n<ul>\n{items_html}</ul>\n"

    return result_html

def scrape_description(pnumber):
    url = f"https://shop.api.de/product/details/{pnumber}?seek=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Chyba stahování stránky: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    span_section = soup.find("span", class_="displayTabOnPrint")

    if not span_section:
        raise Exception("Popis produktu nebyl nalezen.")

    # Najdi hlavní odstavec
    description_paragraph = span_section.find("p", class_="mb-4 mt-3")
    description_text = description_paragraph.get_text(strip=True) if description_paragraph else ""

    # Najdi všechny doplňkové body
    bullet_spans = span_section.find_all("span", class_="mb-3 ms-2")
    bullets = [f"<br>{span.get_text(strip=True)}" for span in bullet_spans]

    # Poskládej finální HTML
    full_html = f"<span>{description_text}\n\n{''.join(bullets)}</span><br>"
    return full_html


if __name__ == "__main__":
    pnumber = "171914"
    try:
        description_html = scrape_description(pnumber)
        #print("Popis produktu:")
        print(description_html)
        #print("Specifikace produktu:")
        specifications_html = scrape_specifications(pnumber)
        print(specifications_html)

    except Exception as e:
        print(f"Chyba při získávání specifikací: {e}")