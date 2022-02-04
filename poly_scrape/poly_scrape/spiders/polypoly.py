#!/usr/bin/python3
import csv
import numpy as np
import in_place
import json
import logging
import re
from readability import Document
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from scrapy.spiders import Spider, Rule
from scrapy.linkextractors import LinkExtractor
import sys

logger = logging.getLogger(__name__)
logging.getLogger("readability").setLevel(logging.WARNING)

COUNTRIES_PATH = './Countries.csv'
LEGAL_FORMS_FILE = './es_legal_forms.json'
URLS_FILE = 'sites.in'

def get_urls(file_name):
    urls = []
    with in_place.InPlace(file_name) as file:
        for line in file:
            if line.strip().startswith('http'):
                urls.append(line)
            else:
                try:
                    r = requests.get(f"https://{line.strip()}")
                    if r.url is not None:
                        if r.url.startswith('https://'):
                            line = "https://" + line.strip()
                        else:
                            line = "http://" + line.strip()
                    else:
                        line = "https://" + line.strip()
                    urls.append(line)
                    line = line+'\n'
                except:
                    pass
            file.write(line)
    return urls

def get_countries(countries_path):
    countries_list =[]
    with open(countries_path) as c_file:  # pylint: disable=unspecified-encoding
        reader = list(csv.DictReader(c_file, delimiter=','))

        for row in reader:
            countries_list.append(row['Name_EN'])
    return countries_list 

def get_legal_forms(file_name):
    legal_forms = []
    with open(file_name) as json_file:
        data = json.load(json_file)
        for legal_form in data['data']:
            acronym = legal_form['acronym']
            if acronym :
                acronyms = [l.strip() for l in acronym.split(';') if (len(l.strip()) > 2 and l.strip()[0].isupper())]
                legal_forms.extend(acronyms)
    return legal_forms 


def scrape_country(text_content):

    countries = get_countries(COUNTRIES_PATH)
    occurrences = []
    for country in countries:
        count = sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(country),text_content))
        occurrences.append(count)
    sorted_indexes = np.argsort(np.array(occurrences))
    if occurrences[sorted_indexes[-1]] > occurrences[sorted_indexes[-2]] and occurrences[sorted_indexes[-1]] > 0:
        print('Country of jurisdiction: ',countries[sorted_indexes[-1]])
   
        return countries[sorted_indexes[-1]]
    else:
        return None


class PolypolySpider(Spider):
    name = 'polypoly'
    count = 0
    failed_urls = []
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.max_redirects = 5
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    legal_forms = get_legal_forms(LEGAL_FORMS_FILE)
    open('log.txt', 'w')

    start_urls = get_urls(URLS_FILE)

    # rules = (
    #     Rule(LinkExtractor(restrict_xpaths="//a[contains(., 'Terms') or contains(., 'Conditions of Use') or contains(., 'Legal') or contains(., 'Privacy Policy')]"), callback='parse_toc'),
    # )
    
    def parse(self, response):
        print(response.status, response.url)
        if response.status == 200:
            self.count += 1
            self.logger.info(f"Discovered T&C page for {response.url}")


            tc_content = self.get_text_content(response.body)
            country = scrape_country(tc_content)
            with open('log.txt', 'a') as f:
                f.write(f"Discovered T&C page for {response.url}\n")
                if country:
                    f.write(f'Country of jurisdiction: {country}\n\n')
                else:
                    f.write('No result found for country jurisdiction\n\n')
        else:
            self.failed_urls.append(response.url)
            with open('log.txt', 'a') as f:
                f.write(f"No T&C page for {response.url}\n\n")
        
    def get_text_content(self, text):
        doc = Document(text)
        return doc.summary()
