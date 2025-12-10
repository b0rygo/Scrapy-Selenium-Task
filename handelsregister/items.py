import scrapy


class HandelsItem(scrapy.Item):
    row_number = scrapy.Field()
    links = scrapy.Field()  # Lista słowników z href, text, title

