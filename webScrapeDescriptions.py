import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


def api_scrape_product_details(PNumber):
    url = f"https://shop.api.de/product/details/{PNumber}"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Chyba při načítání stránky: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')

    # První část: popis produktu
    description_section = soup.find('span', class_='displayTabOnPrint')
    description = ""
    if description_section:
        description_p = description_section.find('p', class_='mb-4 mt-3')
        if description_p:
            description = f"<span>{description_p.get_text(strip=True)}</span>"

    # Druhá část: specifikace (hlavní tabulka)
    specs_html = ""
    specs_section = soup.find('div', class_='mb-5 px-2 pb-5')
    if specs_section:
        section_title = specs_section.find('h6', class_='fw-bold')
        if section_title:
            specs_html += f"<b>{section_title.get_text(strip=True)}</b>\n<ul>\n"

        spec_rows = specs_section.find_all('div', class_='row mb-1 ms-3 align-items-end')
        for row in spec_rows:
            spec_name = row.find('div', class_='col col-lg-2 col-6')
            spec_value = row.find('div', class_='col col-lg-10 col-6')
            if spec_name and spec_value:
                specs_html += f"<li>{spec_name.get_text(strip=True)}: {spec_value.get_text(strip=True)}</li>\n"

        specs_html += "</ul>"

    # Další tabulky s class 'mb-4 px-2'
    more_sections = soup.find_all('div', class_='mb-4 px-2')
    for section in more_sections:
        section_title = section.find('h6', class_='fw-bold')
        if section_title:
            specs_html += f"<b>{section_title.get_text(strip=True)}</b>\n<ul>\n"

        spec_rows = section.find_all('div', class_='row mb-1 ms-3 align-items-end')
        for row in spec_rows:
            spec_name = row.find('div', class_='col col-lg-2 col-6')
            spec_value = row.find('div', class_='col col-lg-10 col-6')
            if spec_name and spec_value:
                specs_html += f"<li>{spec_name.get_text(strip=True)}: {spec_value.get_text(strip=True)}</li>\n"

        specs_html += "</ul>"

    final_output = f"{description}<br><br>\n{specs_html}" if description else specs_html
    return final_output


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def get_kosatec_product_data(pnumber: str) -> str:
    """
    Najde správný produkt na Kosatec podle 'Artikel <pnumber>', otevře detail
    a vrátí HTML výpis s bullet points + Icecat specifikacemi.
    - Na výsledcích klikne jen na kartu, kde <li> obsahuje 'Artikel <pnumber>'.
    - Na detailu si znovu ověří, že 'Artikel' odpovídá pnumber (robustní regex).
    - V tabulce specifikací (Icecat) převádí Yes/No ikony (aria-label) na 'hat' / 'hat nicht'.
    """
    # --- importy uvnitř funkce, aby byla samostatná ---
    import re
    from urllib.parse import urlparse

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    def only_digits(s: str) -> str:
        return re.sub(r"\D+", "", str(s or ""))

    wanted = only_digits(pnumber)

    # --- Selenium driver ---
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)

    try:
        wait = WebDriverWait(driver, 15)

        # =========================================================
        # 1) Vyhledání a klik na správnou kartu dle "Artikel <num>"
        # =========================================================
        search_url = f"https://shop.kosatec.de/factfinder/result?query={pnumber}"
        driver.get(search_url)

        # Počkej, až se objeví aspoň jedna karta
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".product-box")))
        product_cards = driver.find_elements(By.CSS_SELECTOR, ".product-box")

        product_link = None

        for card in product_cards:
            try:
                # V kartě hledej <ul><li> s textem "Artikel <číslo>"
                lis = card.find_elements(By.CSS_SELECTOR, "ul li")
                artikel_num = None
                for li in lis:
                    # Robustní regex: libovolné ne-číslice mezi 'Artikel' a číslem (NBSP/newline apod.)
                    m = re.search(r"(?i)\bArtikel\b\D*([0-9]+)", (li.text or ""))
                    if m:
                        artikel_num = only_digits(m.group(1))
                        break

                if artikel_num and artikel_num == wanted:
                    a = card.find_element(By.CSS_SELECTOR, "a.product-image-link, a.product-name")
                    product_link = a.get_attribute("href")
                    break
            except NoSuchElementException:
                continue

        # Fallback: když nic nenašlo (např. jiný layout výsledků) → vezmi první odkaz,
        # ale na detailu ještě ověříme 'Artikel'
        if not product_link:
            first_a = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.product-image-link, a.product-name"))
            )
            product_link = first_a.get_attribute("href")

        # ========================================
        # 2) Otevři detail + ověř 'Artikel <num>'
        # ========================================
        driver.get(product_link)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))

        # Počkej cíleně na seznam s 'Artikel / EAN / MPN'
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//ul[contains(@class,'fw-light')]/li")))
        except TimeoutException:
            pass  # zkusíme další metody

        artikel_ok = False
        wanted_digits = only_digits(pnumber)

        # Pokus 1: najdi 'Artikel' v <ul class="fw-light ..."><li>…</li>
        try:
            detail_lis = driver.find_elements(By.XPATH, "//ul[contains(@class,'fw-light')]/li")
            for li in detail_lis:
                raw = (li.get_attribute("textContent") or "").strip()
                m = re.search(r"(?i)\bArtikel\b\D*([0-9]+)", raw, flags=re.S)
                if m and only_digits(m.group(1)) == wanted_digits:
                    artikel_ok = True
                    break
        except Exception:
            detail_lis = []

        # Pokus 2: fallback přes celou stránku (kdyby byl jiný wrapper)
        if not artikel_ok:
            page_src = driver.page_source or ""
            m = re.search(r"(?i)Artikel\D*([0-9]{3,})", page_src)
            if m and only_digits(m.group(1)) == wanted_digits:
                artikel_ok = True

        # Pokus 3: fallback přes URL: /.../<Artikel>
        if not artikel_ok:
            try:
                path_last = urlparse(driver.current_url).path.rstrip("/").split("/")[-1]
                if only_digits(path_last) == wanted_digits:
                    artikel_ok = True
            except Exception:
                pass

        if not artikel_ok:
            # Užitečné pro debug: seber kandidáty s textem 'Artikel'
            candidates = []
            try:
                for li in detail_lis:
                    txt = (li.get_attribute("textContent") or "").strip()
                    if "Artikel" in txt:
                        candidates.append(txt)
            except Exception:
                pass
            raise ValueError(f"Produkt s PNumber '{pnumber}' nebyl nalezen na Kosatec.")

        # ========================================
        # 3) Extrakce obsahu (bullet points + Icecat)
        # ========================================
        output_parts = []

        # --- BULLET POINTS ---
        try:
            bullet_ul = driver.find_element(By.ID, "bullet-points-list")
            bullet_points = bullet_ul.find_elements(By.TAG_NAME, "li")
            if bullet_points:
                bp_texts = []
                for li in bullet_points:
                    txt = (li.text or "").strip()
                    if txt:
                        bp_texts.append(txt)
                if bp_texts:
                    output_parts.append("<span>\n" + "\n".join(bp_texts) + "\n</span>\n<br><br>")
        except NoSuchElementException:
            pass  # bullet points nejsou vždy

        # --- ICECAT SPECIFIKACE ---
        # Převede Yes/No (ikony s role="img" aria-label) na 'hat' / 'hat nicht'
        def normalize_yes_no(value_el, text_value: str) -> str:
            text = (text_value or "").strip()
            # Zkus ikonu
            try:
                icon = value_el.find_element(By.CSS_SELECTOR, "[role='img'][aria-label]")
                aria = (icon.get_attribute("aria-label") or "").strip().lower()
                if not text and aria:
                    if aria == "yes":
                        return "hat"
                    if aria == "no":
                        return "hat nicht"
                    return aria
            except NoSuchElementException:
                pass
            # Zkus textová "Ja/Nein/Yes/No"
            lowered = text.lower()
            if lowered in ("ja", "yes"):
                return "hat"
            if lowered in ("nein", "no"):
                return "hat nicht"
            return text

        try:
            table = driver.find_element(By.CLASS_NAME, "-icecat-table")
            feature_groups = table.find_elements(By.CLASS_NAME, "-icecat-feature-group")

            for group in feature_groups:
                # Název sekce (někdy je v .-icecat-tableRowHead)
                section_title = ""
                try:
                    section_title = group.find_element(By.CLASS_NAME, "-icecat-tableRowHead").text.strip()
                except Exception:
                    pass

                if section_title:
                    output_parts.append(f"<b>{section_title}</b>\n<ul>")
                else:
                    output_parts.append("<ul>")

                rows = group.find_elements(By.CLASS_NAME, "-icecat-tableRow")
                for row in rows:
                    try:
                        label_el = row.find_element(By.CLASS_NAME, "-icecat-ds_label")
                        label = (label_el.text or "").strip().replace("\n", " ")

                        value_el = row.find_element(By.CLASS_NAME, "-icecat-ds_data")
                        value_text = (value_el.text or "").strip()

                        value = normalize_yes_no(value_el, value_text)
                        if label:
                            output_parts.append(f"<li>{label}: {value}</li>")
                    except Exception:
                        continue

                output_parts.append("</ul>")
        except NoSuchElementException:
            # Icecat tabulka nemusí být přítomná
            pass

        # ========================================
        # 4) Výstup
        # ========================================
        output = "\n".join(output_parts).strip()
        if not output:
            return None
        return output

    finally:
        driver.quit()



# Test
if __name__ == "__main__":

    #print(api_scrape_product_details("440604"))
    print(get_kosatec_product_data("120437"))