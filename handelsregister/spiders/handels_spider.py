import os
import json
from scrapy import Spider

from handelsregister.utils import run_etap1_scrape

class HandelsSpider(Spider):
    name = "handels_spider"

    def __init__(self, target_url=None, download_dir=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = target_url or os.environ.get(
            "TARGET_URL", "https://www.handelsregister.de/"
        )
        self.download_dir = download_dir or ""

    def start_requests(self):
        # Uruchamiamy selenium ETAP1 i zbieramy linki z wyników wyszukiwania
        collected_links = run_etap1_scrape(self.target_url, self.download_dir)
        
        # Zapisujemy wyniki do JSON (z count i items)
        wynik = {"count": len(collected_links), "items": collected_links}
        os.makedirs("results", exist_ok=True)
        out_path = os.path.join("results", "items.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(wynik, f, indent=4, ensure_ascii=False)
        
        self.logger.info(
            "SUKCES! Zebrano %d wierszy z linkami. Wynik zapisano w %s",
            len(collected_links),
            out_path,
        )

        # Zwracamy jeden item
        yield wynik

