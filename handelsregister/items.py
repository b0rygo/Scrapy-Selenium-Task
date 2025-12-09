import scrapy


class HandelsItem(scrapy.Item):
    zrodlo_plik = scrapy.Field()
    dane = scrapy.Field()

