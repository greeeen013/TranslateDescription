import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from database import get_suppliers, get_products, update_product_note
from webScrapeDescriptions import get_kosatec_product_data, api_scrape_product_details
from LLMTranslate import get_ai_response, gemini_ai_response
import threading
import queue
import time

DODAVATELE = {
    "api": {"kod": "161784", "funkce": api_scrape_product_details},
    "Kosatec (selenium)": {"kod": "165463", "funkce": get_kosatec_product_data},
}

class TranslationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Překlad produktových popisků")
        self.root.geometry("1200x800")

        self.current_products = []
        self.current_index = 0
        self.supplier_code = None
        self.scrape_function = None
        self.loading = False
        self.translation_in_progress = False
        self.auto_confirm = False

        self.result_queue = queue.Queue()

        self.scrape_in_progress = False
        self.current_siv_code = None

        self.style = ttk.Style()
        try:
            self.style.configure("Big.TButton", font=("Arial", 14), padding=(20, 12))
        except Exception:
            self.style.configure("Big.TButton", padding=(20, 12))

        # Zvýraznění a zvětšení status baru
        self.style.configure("BigStatus.TLabel", font=("Arial", 12), padding=(5, 8))

        self.create_widgets()
        self.check_queue()

    def create_widgets(self):
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=(10, 5))

        supplier_frame = ttk.LabelFrame(control_frame, text="Dodavatel")
        supplier_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        ttk.Label(supplier_frame, text="Vyberte dodavatele:").pack(side="left", padx=5, pady=5)

        self.supplier_var = tk.StringVar()
        self.supplier_cb = ttk.Combobox(
            supplier_frame,
            textvariable=self.supplier_var,
            state="readonly"
        )
        self.supplier_cb.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        self.supplier_cb.bind("<<ComboboxSelected>>", self.supplier_selected)

        self.auto_confirm_var = tk.BooleanVar(value=self.auto_confirm)
        auto_confirm_check = ttk.Checkbutton(
            control_frame,
            text="Automatické potvrzování",
            variable=self.auto_confirm_var,
            command=self.toggle_auto_confirm
        )
        auto_confirm_check.pack(side="right", padx=10, pady=5)

        self.supplier_cb["values"] = list(DODAVATELE.keys())
        self.supplier_cb.set('')

        # Status bar – zvětšený (2,5×)
        self.status_var = tk.StringVar(value="Připraveno")
        status_top = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            style="BigStatus.TLabel"
        )
        status_top.pack(fill="x", padx=10, pady=(0, 8))

        content_frame = ttk.Frame(self.root)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        left_frame = ttk.LabelFrame(content_frame, text="Originální popis")
        left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.original_text = scrolledtext.ScrolledText(
            left_frame,
            wrap=tk.WORD,
            state="disabled",
            width=60
        )
        self.original_text.pack(fill="both", expand=True, padx=5, pady=5)

        right_frame = ttk.LabelFrame(content_frame, text="Překlad")
        right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self.translated_text = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            width=60
        )
        self.translated_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.loading_frame = ttk.Frame(self.root, height=56)
        self.loading_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.loading_frame.pack_propagate(False)

        self.loading_label = ttk.Label(self.loading_frame, text="", font=('Arial', 12))
        self.loading_label.pack(fill="x", pady=(6, 2))

        self.translation_progress = ttk.Progressbar(
            self.loading_frame,
            orient='horizontal',
            mode='indeterminate',
            length=280
        )
        self.translation_progress.pack(fill="x")

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=10, pady=5)

        self.skip_btn = ttk.Button(
            button_frame,
            text="Přeskočit",
            command=self.skip_product,
            state="disabled",
            style="Big.TButton"
        )
        self.skip_btn.pack(side="left", padx=5)

        self.confirm_btn = ttk.Button(
            button_frame,
            text="Potvrdit",
            command=self.confirm_translation,
            state="disabled",
            style="Big.TButton"
        )
        self.confirm_btn.pack(side="right", padx=5)

    def toggle_auto_confirm(self):
        """Přepíná stav automatického potvrzování"""
        self.auto_confirm = self.auto_confirm_var.get()
        print(f"[DEBUG] Automatické potvrzování: {'ZAPNUTO' if self.auto_confirm else 'VYPNUTO'}")

        # Pokud je automatické potvrzování zapnuto a máme aktuální překlad, potvrdíme ho
        if self.auto_confirm and self.translated_text.get("1.0", tk.END).strip():
            self.confirm_translation()

    def supplier_selected(self, event):
        """Zpracování výběru dodavatele"""
        supplier_name = self.supplier_var.get()
        if not supplier_name:
            return

        # Získání kódu a funkce ze slovníku DODAVATELE
        if supplier_name in DODAVATELE:
            dodavatel = DODAVATELE[supplier_name]
            self.supplier_code = dodavatel["kod"]
            self.scrape_function = dodavatel["funkce"]
            print(f"[DEBUG] Vybrán dodavatel: {supplier_name}, kód: {self.supplier_code}")
        else:
            messagebox.showerror("Chyba", f"Neznámý dodavatel: {supplier_name}")
            return

        self.set_loading(True, f"Načítám produkty pro dodavatele: {supplier_name}...")

        threading.Thread(
            target=self.load_products_thread,
            daemon=True
        ).start()

    def load_products_thread(self):
        """Vlákno pro načítání produktů z DB"""
        try:
            print(f"[DEBUG] Začínám načítat produkty pro dodavatele {self.supplier_code}")
            start_time = time.time()

            products = get_products(self.supplier_code)

            print(f"[DEBUG] Načteno {len(products)} produktů za {time.time() - start_time:.2f}s")

            if not products:
                self.result_queue.put(("error", "Žádné produkty k překladu"))
                return

            self.current_products = products
            self.current_index = 0
            self.result_queue.put(("products_loaded", products))
        except Exception as e:
            print(f"[ERROR] Chyba při načítání produktů: {str(e)}")
            self.result_queue.put(("error", str(e)))
        finally:
            self.set_loading(False)

    def load_product_details(self):
        """Načte detaily produktu a připraví překlad"""
        if self.current_index >= len(self.current_products):
            print("[DEBUG] Načítám další produkty...")
            self.set_loading(True, "Načítám další produkty...")
            if self.scrape_in_progress:
                return
            self.scrape_in_progress = True
            threading.Thread(
                target=self.load_products_thread,
                daemon=True
            ).start()
            return

        # Získání aktuálního produktu
        siv_code, siv_name = self.current_products[self.current_index]
        self.current_siv_code = siv_code
        print(f"[DEBUG] Načítám produkt {self.current_index + 1}/{len(self.current_products)}: {siv_code} - {siv_name}")
        self.status_var.set(f"Produkt {self.current_index + 1}/{len(self.current_products)}: {siv_code} - {siv_name}")

        # Vymazání textových polí
        self.clear_texts()

        self.set_loading(True, f"Načítám originál pro {siv_code}…")
        self.translation_progress.start()

        # Spustíme nejprve načtení originálu
        threading.Thread(
            target=self.scrape_original_thread,
            args=(siv_code, siv_name),
            daemon=True
        ).start()

    def scrape_original_thread(self, siv_code, siv_name):
        try:
            print(f"[DEBUG] Začínám scrapovat originál produktu {siv_code}")
            original_html = self.scrape_function(siv_code)
            full_html = f"{original_html}"
            self.result_queue.put(("original_loaded", full_html, siv_code))
            self.start_translation(full_html, siv_code)
        except Exception as e:
            # (viz část B) – neprintovat tady, jen poslat do fronty
            self.result_queue.put(("error", f"Chyba u produktu {siv_code}: {e}"))
        finally:
            self.scrape_in_progress = False

    def start_translation(self, original_html, siv_code):
        """Spustí proces překladu"""
        if self.translation_in_progress:
            return

        self.translation_in_progress = True
        self.translation_progress.start()

        threading.Thread(
            target=self.translate_thread,
            args=(original_html, siv_code),
            daemon=True
        ).start()

    def translate_thread(self, original_html, siv_code):
        """Vlákno pro překlad"""
        try:
            print(f"[DEBUG] Začínám překlad produktu {siv_code}")
            start_time = time.time()

            # Příprava promptu pro překlad
            prompt = (
                    "Přelož následující text z **němčiny** do češtiny. Zachovej přesnou strukturu HTML:"\
                    "\n1. VŠECHNY HTML tagy, atributy a entity (jako `&nbsp;`) ponech beze změny"\
                    "\n2. Překládej POUZE textový obsah mezi tagy"\
                    "\n3. Zachovej číselné hodnoty, kódy (IP42, USB), technické parametry (3.5 mil, 100 řádků/s) a firemní názvy (Honeywell) beze změny"\
                    "\n4. Nikdy nepřidávej cizojazyčné znaky (jako 几乎) ani znaky mimo českou znakovou sadu, drž se českého jazyka"\
                    "\n5. V technických termínech použij standardní českou terminologii (např. 'lineární imager', 'IP42')"\
                    "\n6. Pokud v textu je 3.5 cm, přelož to jako 3,5 cm (s čárkou), pokud je 3.5 mil, přelož to jako 3,5 mil (s čárkou)"\
                    "\n\nText k překladu:\n\n" + original_html
            )

            # Překlad pomocí AI
            if prompt :
                # translated = get_ai_response(prompt)
                translated = gemini_ai_response(prompt)

            print(f"[DEBUG] Překlad dokončen za {time.time() - start_time:.2f}s")

            self.result_queue.put(("translation_loaded", translated, siv_code))

        except Exception as e:
            print(f"[ERROR] Chyba při překladu produktu {siv_code}: {str(e)}")
            self.result_queue.put(("error", f"Chyba při překladu produktu {siv_code}: {str(e)}"))
        finally:
            self.translation_in_progress = False
            self.result_queue.put(("translation_finished",))

    def check_queue(self):
        """Kontrola fronty pro aktualizaci GUI"""
        try:
            while True:
                result = self.result_queue.get_nowait()

                if result[0] == "products_loaded":
                    products = result[1]
                    if not products:
                        messagebox.showinfo("Info", "Žádné další produkty k překladu")
                        self.reset_ui()
                    else:
                        print(f"[DEBUG] Zobrazuji načtené produkty")
                        self.skip_btn["state"] = "normal"
                        self.confirm_btn["state"] = "normal"
                        self.load_product_details()

                elif result[0] == "original_loaded":
                    original, siv_code = result[1], result[2]

                    print(f"[DEBUG] Zobrazuji originál produktu {siv_code}")

                    # Zobrazení původního textu
                    self.original_text.config(state="normal")
                    self.original_text.delete(1.0, tk.END)
                    self.original_text.insert(tk.END, original)
                    self.original_text.config(state="disabled")

                    # Uložení aktuálního kódu produktu
                    self.current_siv_code = siv_code
                    self.set_loading(True, "Překládám…")

                elif result[0] == "translation_loaded":
                    translated, siv_code = result[1], result[2]

                    print(f"[DEBUG] Zobrazuji překlad produktu {siv_code}")

                    # Zobrazení překladu
                    self.translated_text.delete(1.0, tk.END)
                    self.translated_text.insert(tk.END, translated)

                    # Automatické potvrzení pokud je aktivní
                    if self.auto_confirm:
                        print("[DEBUG] Automaticky potvrzuji překlad")
                        self.confirm_translation()

                elif result[0] == "translation_finished":
                    self.translation_progress.stop()
                    self.set_loading(False)

                elif result[0] == "error":
                    err_msg = result[1]
                    print(f"[ERROR] {err_msg}")
                    self.status_var.set("Chyba")
                    self.set_loading(False)
                    self.translation_progress.stop()
                    if self.auto_confirm:
                        # Tiché přeskočení problémového produktu a pokračování
                        self.current_index += 1
                        self.load_product_details()
                    else:
                        # V manuálním režimu ukaž dialog
                        messagebox.showerror("Chyba", err_msg)

                elif result[0] == "info":
                    print(f"[INFO] {result[1]}")
                    self.status_var.set(result[1])

        except queue.Empty:
            pass

        self.root.after(100, self.check_queue)

    def skip_product(self):
        """Přeskočí aktuální produkt"""
        code = getattr(self, "current_siv_code", None)
        print(f"[DEBUG] Přeskakuji produkt {code if code else '<neznámý>'}")
        self.clear_texts()
        self.translation_progress.stop()
        self.translation_in_progress = False
        self.current_index += 1
        self.load_product_details()

    def confirm_translation(self):
        """Potvrdí překlad a uloží do DB"""
        translated = self.translated_text.get(1.0, tk.END).strip()
        print(f"[DEBUG] Potvrzuji překlad pro produkt {self.current_siv_code}")

        if not translated:
            if self.auto_confirm:
                print("[DEBUG] Prázdný překlad – automaticky přeskočeno")
                self.clear_texts()
                self.translation_progress.stop()
                self.translation_in_progress = False
                self.current_index += 1
                self.load_product_details()
            else:
                messagebox.showwarning("Varování", "Překlad je prázdný")
            return

        # Uložení v novém vlákně
        threading.Thread(
            target=self.save_translation_thread,
            args=(self.current_siv_code, translated),
            daemon=True
        ).start()

        # Přesun na další produkt
        self.clear_texts()
        self.translation_progress.stop()
        self.translation_in_progress = False
        self.current_index += 1
        self.load_product_details()

    def save_translation_thread(self, siv_code, translation):
        """Uložení překladu do DB"""
        try:
            print(f"[DEBUG] Ukládám překlad pro produkt {siv_code}")
            update_product_note(siv_code, translation)
            self.result_queue.put(("info", f"Překlad pro produkt {siv_code} uložen"))
        except Exception as e:
            print(f"[ERROR] Chyba při ukládání: {str(e)}")
            self.result_queue.put(("error", str(e)))

    def clear_texts(self):
        """Vymaže obě textová pole"""
        self.original_text.config(state="normal")
        self.original_text.delete(1.0, tk.END)
        self.original_text.config(state="disabled")
        self.translated_text.delete(1.0, tk.END)

    def reset_ui(self):
        """Resetuje UI do výchozího stavu"""
        print("[DEBUG] Resetuji UI")
        self.clear_texts()
        self.skip_btn["state"] = "disabled"
        self.confirm_btn["state"] = "disabled"
        self.status_var.set("Připraveno")
        self.set_loading(False)
        self.translation_progress.stop()
        self.translation_in_progress = False

    def set_loading(self, loading, message=None):
        """Nastaví stav načítání (bez změny layoutu)"""
        self.loading = loading
        if loading:
            self.loading_label.config(text=message or "Načítám…")
            # Progressbar už je v layoutu, stačí ho rozjet
            try:
                self.translation_progress.start()
            except Exception:
                pass
        else:
            self.loading_label.config(text="")
            try:
                self.translation_progress.stop()
            except Exception:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    app = TranslationApp(root)
    root.mainloop()
