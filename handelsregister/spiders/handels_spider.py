import os
import json
import os
import re
import xmltodict
from scrapy import Spider

from handelsregister.utils import run_etap1_scrape

class HandelsSpider(Spider):
    name = "handels_spider"

    def __init__(self, target_url=None, download_dir=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = target_url or os.environ.get(
            "TARGET_URL", "https://www.handelsregister.de/"
        )
        self.download_dir = (
            download_dir
            or os.environ.get("XML_DIR")
            or os.path.join(os.getcwd(), "plikiXMLbyScrapy")
        )

    def start_requests(self):
        # Uruchamiamy selenium ETAP1 i pobieramy pliki XML
        download_dir = run_etap1_scrape(self.target_url, self.download_dir)
        yield from self._load_items(download_dir)

    def _load_items(self, folder_z_plikami):
        if not os.path.exists(folder_z_plikami):
            self.logger.warning("Brak folderu z XML: %s", folder_z_plikami)
            return

        items = []
        for plik in sorted(os.listdir(folder_z_plikami)):
            if not plik.endswith(".xml"):
                continue
            sciezka_pelna = os.path.join(folder_z_plikami, plik)
            try:
                with open(sciezka_pelna, "r", encoding="utf-8") as f:
                    tresc_xml = f.read()
                tresc_xml_clean = re.sub(r"tns:", "", tresc_xml)
                dane_dict = xmltodict.parse(tresc_xml_clean, force_list={"beteiligung"})
                items.append({"zrodlo_plik": plik, "dane": dane_dict})
            except Exception as e:
                self.logger.error("Błąd przy pliku %s: %s", plik, e)

        # zapis jak w SeleniumScraper: jeden obiekt JSON z count i items
        wynik = {"count": len(items), "items": items}
        os.makedirs("results", exist_ok=True)
        out_path = os.path.join("results", "items.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(wynik, f, indent=4, ensure_ascii=False)
        self.logger.info(
            "SUKCES! Przetworzono %d plików. Wynik zapisano w %s",
            len(items),
            out_path,
        )

        # opcjonalnie zwróć jeden item (nie będzie listy [] w pliku, bo zapis robimy ręcznie)
        yield wynik

