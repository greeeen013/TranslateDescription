import requests, html
from bs4 import BeautifulSoup

def get_product_details_html(PNumber: str) -> str:
    url = f"https://shop.api.de/product/details/{PNumber}"
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    product_section = soup.find(id="product_details")
    if not product_section:
        return ""

    # 1. Popis
    description_text = ""
    desc_tab = product_section.find('div', id=lambda s: s and s.endswith('_0'))
    if desc_tab:
        p = desc_tab.find('p')
        if p:
            description_text = html.escape(p.get_text(separator="\n").strip())

    # 2. Technická data
    specs_output = ""
    tech_tab = product_section.find('div', id=lambda s: s and s.endswith('_1'))
    if tech_tab:
        rows = tech_tab.find_all('div', class_=lambda c: c and 'ms-3' in c and 'align-items-end' in c)
        for row in rows:
            key_div = row.find('div', class_=lambda c: c and 'col-lg-2' in c)
            val_div = row.find('div', class_=lambda c: c and 'col-lg-10' in c)
            if not key_div or not val_div:
                continue

            label = html.escape(key_div.get_text(strip=True))

            # Získání jednotlivých řádků nebo li
            list_items = []
            li_tags = val_div.find_all("li")
            if li_tags:
                # Pokud jsou <li>, použij je přímo
                for li in li_tags:
                    text = li.get_text(strip=True)
                    if text:
                        list_items.append(html.escape(text))
            else:
                # Pokud ne, rozděl <br> nebo text podle řádků
                text = val_div.get_text(separator="\n").strip()
                for line in text.splitlines():
                    line = line.strip()
                    if line:
                        list_items.append(html.escape(line))

            # Vygeneruj HTML
            if list_items:
                specs_output += f"<b>{label}</b>\n<ul>\n"
                for item in list_items:
                    specs_output += f"  <li>{item}</li>\n"
                specs_output += "</ul>\n"

    # Výsledný HTML výstup
    result = ""
    if description_text:
        result += f"<span>{description_text}</span>\n"
    if specs_output:
        result += "<h6>Technické podrobnosti</h6>\n" + specs_output

    return result



if __name__ == "__main__":
    # Example usage
    product_number = "462846"  # Replace with a valid product number
    html_content = get_product_details_html(product_number)
    print(html_content)  # Output the HTML content