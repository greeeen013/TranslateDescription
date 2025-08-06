import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

def api_scrape_specifications(pnumber):
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

def api_scrape_description(pnumber):
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
    full_html = f"<span>{description_text}\n\n{''.join(bullets)}</span><br><br>"
    return full_html

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def get_kosatec_product_data(pnumber):
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(options=options)

    try:
        url = f"https://shop.kosatec.de/factfinder/result?query={pnumber}"
        driver.get(url)

        wait = WebDriverWait(driver, 10)
        product_link = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.product-image-link"))
        ).get_attribute("href")

        driver.get(product_link)
        time.sleep(2)

        output = ""

        # --- POPIS PRODUKTU ---
        try:
            bullet_ul = driver.find_element(By.ID, "bullet-points-list")
            bullet_points = bullet_ul.find_elements(By.TAG_NAME, "li")
            output += "<span>\n"
            for li in bullet_points:
                output += f"{li.text.strip()}\n"
            output += "</span>\n<br><br>\n"
        except:
            output += "<span><i>Popis produktu nebyl nalezen</i></span><br><br>\n"

        # --- SPECIFIKACE ---
        try:
            table = driver.find_element(By.CLASS_NAME, "-icecat-table")
            feature_groups = table.find_elements(By.CLASS_NAME, "-icecat-feature-group")

            for group in feature_groups:
                section_title = group.find_element(By.CLASS_NAME, "-icecat-tableRowHead").text.strip()
                output += f"<b>{section_title}</b>\n<ul>\n"

                rows = group.find_elements(By.CLASS_NAME, "-icecat-tableRow")
                for row in rows:
                    try:
                        label_el = row.find_element(By.CLASS_NAME, "-icecat-ds_label")
                        label = label_el.text.strip().replace("\n", " ")
                        value_el = row.find_element(By.CLASS_NAME, "-icecat-ds_data")

                        aria_label = value_el.get_attribute("aria-label")
                        if not value_el.text.strip() and aria_label == "Yes":
                            value = "Hat"
                        elif not value_el.text.strip() and aria_label == "No":
                            value = "Hat nicht"
                        else:
                            value = value_el.text.strip()

                        output += f"<li>{label}: {value}</li>\n"
                    except:
                        continue

                output += "</ul>\n"

        except:
            output += "<i>Specifikace nebyla nalezena</i>\n"

        return output

    finally:
        driver.quit()


# Test
if __name__ == "__main__":
    pnumber = "21230357"
    formatted_html = get_kosatec_product_data(pnumber)
    print(formatted_html)