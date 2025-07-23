import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from database import get_suppliers, get_products, update_product_note
from apiScrapeDescriptions import scrape_description, scrape_specifications
from LLMTranslate import get_ai_response
import threading
import queue
import time


class TranslationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Překlad produktových popisků")
        self.root.geometry("1200x800")

        self.current_products = []
        self.current_index = 0
        self.supplier_code = None
        self.loading = False
        self.translation_in_progress = False
        self.auto_confirm = False  # Inicializace proměnné pro automatické potvrzování

        # Fronta pro komunikaci mezi vlákny
        self.result_queue = queue.Queue()

        self.create_widgets()
        self.check_queue()

    def create_widgets(self):
        # Frame pro dodavatele a automatické potvrzení
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=5)

        # Frame pro dodavatele
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

        # Checkbox pro automatické potvrzení
        self.auto_confirm_var = tk.BooleanVar(value=self.auto_confirm)
        auto_confirm_check = ttk.Checkbutton(
            control_frame,
            text="Automatické potvrzování",
            variable=self.auto_confirm_var,
            command=self.toggle_auto_confirm
        )
        auto_confirm_check.pack(side="right", padx=10, pady=5)

        # Naplnění dodavateli
        suppliers = get_suppliers()
        self.supplier_cb["values"] = [f"{name} ({code})" for code, name in suppliers]
        self.supplier_cb.set('')

        # Frame pro obsah
        content_frame = ttk.Frame(self.root)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Původní popis (vlevo)
        left_frame = ttk.LabelFrame(content_frame, text="Originální popis")
        left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.original_text = scrolledtext.ScrolledText(
            left_frame,
            wrap=tk.WORD,
            state="disabled",
            width=60
        )
        self.original_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Překlad (vpravo)
        right_frame = ttk.LabelFrame(content_frame, text="Překlad")
        right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self.translated_text = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            width=60
        )
        self.translated_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Loading indicator
        self.loading_label = ttk.Label(self.root, text="", font=('Arial', 12))
        self.loading_label.pack(fill="x", padx=10, pady=5)

        # Progress bar pro překlad
        self.translation_progress = ttk.Progressbar(
            self.root,
            orient='horizontal',
            mode='indeterminate',
            length=280
        )
        self.translation_progress.pack(fill="x", padx=10, pady=5)
        self.translation_progress.pack_forget()

        # Status bar
        self.status_var = tk.StringVar(value="Připraveno")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom", padx=10, pady=5)

        # Tlačítka
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=10, pady=5)

        self.skip_btn = ttk.Button(
            button_frame,
            text="Přeskočit",
            command=self.skip_product,
            state="disabled"
        )
        self.skip_btn.pack(side="left", padx=5)

        self.confirm_btn = ttk.Button(
            button_frame,
            text="Potvrdit",
            command=self.confirm_translation,
            state="disabled"
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
        selection = self.supplier_var.get()
        if not selection:
            return

        self.supplier_code = selection.split("(")[-1].rstrip(")")
        print(f"[DEBUG] Vybrán dodavatel: {selection}, kód: {self.supplier_code}")

        self.set_loading(True, f"Načítám produkty pro dodavatele: {selection}...")

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
            threading.Thread(
                target=self.load_products_thread,
                daemon=True
            ).start()
            return

        # Získání aktuálního produktu
        siv_code, siv_name = self.current_products[self.current_index]
        print(f"[DEBUG] Načítám produkt {self.current_index + 1}/{len(self.current_products)}: {siv_code} - {siv_name}")
        self.status_var.set(f"Produkt {self.current_index + 1}/{len(self.current_products)}: {siv_name}")

        # Vymazání textových polí
        self.clear_texts()

        # Spustíme nejprve načtení originálu
        threading.Thread(
            target=self.scrape_original_thread,
            args=(siv_code, siv_name),
            daemon=True
        ).start()

    def scrape_original_thread(self, siv_code, siv_name):
        """Vlákno pro scrapování originálního popisu"""
        try:
            print(f"[DEBUG] Začínám scrapovat originál produktu {siv_code}")
            start_time = time.time()

            # Scrapování popisu a specifikací
            description = scrape_description(siv_code)
            specifications = scrape_specifications(siv_code)
            original_html = f"<h3>{siv_name}</h3>{description}{specifications}"

            print(f"[DEBUG] Scrapování originálu dokončeno za {time.time() - start_time:.2f}s")

            # Okamžitě zobrazíme originál
            self.result_queue.put(("original_loaded", original_html, siv_code))

            # Pak spustíme překlad
            self.start_translation(original_html, siv_code)

        except Exception as e:
            print(f"[ERROR] Chyba u produktu {siv_code}: {str(e)}")
            self.result_queue.put(("error", f"Chyba u produktu {siv_code}: {str(e)}"))

    def start_translation(self, original_html, siv_code):
        """Spustí proces překladu"""
        if self.translation_in_progress:
            return

        self.translation_in_progress = True
        self.translation_progress.pack()
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
                    "Převeď následující text z polštiny do češtiny. Text obsahuje HTML tagy ty ponech beze změny. "
                    "Překládej pouze textový obsah, HTML tagy a atributy zachovej beze změny. Nic do textu nepřidávej ani neodebírej pouze překládej."
                    "Zde je text:\n\n" + original_html
            )

            # Překlad pomocí AI
            translated = get_ai_response(prompt)

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
                    self.translation_progress.pack_forget()

                elif result[0] == "error":
                    print(f"[ERROR] {result[1]}")
                    messagebox.showerror("Chyba", result[1])
                    self.status_var.set("Chyba")
                    self.set_loading(False)
                    self.translation_progress.stop()
                    self.translation_progress.pack_forget()

                    # Pokud je chyba, vypneme auto potvrzení
                    if self.auto_confirm:
                        self.auto_confirm_var.set(False)
                        self.toggle_auto_confirm()

                elif result[0] == "info":
                    print(f"[INFO] {result[1]}")
                    self.status_var.set(result[1])

        except queue.Empty:
            pass

        self.root.after(100, self.check_queue)

    def skip_product(self):
        """Přeskočí aktuální produkt"""
        print(f"[DEBUG] Přeskakuji produkt {self.current_siv_code}")
        self.clear_texts()
        self.translation_progress.stop()
        self.translation_progress.pack_forget()
        self.translation_in_progress = False
        self.current_index += 1
        self.load_product_details()

    def confirm_translation(self):
        """Potvrdí překlad a uloží do DB"""
        translated = self.translated_text.get(1.0, tk.END).strip()
        print(f"[DEBUG] Potvrzuji překlad pro produkt {self.current_siv_code}")

        if not translated:
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
        self.translation_progress.pack_forget()
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
        self.translation_progress.pack_forget()
        self.translation_in_progress = False

    def set_loading(self, loading, message=None):
        """Nastaví stav načítání"""
        self.loading = loading
        if loading:
            self.loading_label.config(text=message)
        else:
            self.loading_label.config(text="")


if __name__ == "__main__":
    root = tk.Tk()
    app = TranslationApp(root)
    root.mainloop()