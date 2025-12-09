BOT_NAME = "handelsregister"

SPIDER_MODULES = ["handelsregister.spiders"]
NEWSPIDER_MODULE = "handelsregister.spiders"

ROBOTSTXT_OBEY = False

ITEM_PIPELINES = {
    "handelsregister.pipelines.HandelsregisterPipeline": 300,
}

# Plik wynikowy zapisujemy ręcznie w spiderze; tutaj wyłączamy FEEDS
FEEDS = {}

LOG_LEVEL = "INFO"

