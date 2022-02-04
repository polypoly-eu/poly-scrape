#!/usr/bin/python3
from bs4 import BeautifulSoup
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

def is_company_type(text, company_type):
    return min(p for p in [text.find(f" {company_type} "), text.find(f" {company_type}."), text.find(f" {company_type},"), sys.maxsize ] if p > 0)


def get_countries(countries_path):
    countries_list =[]
    with open(countries_path) as c_file:  # pylint: disable=unspecified-encoding
        reader = list(csv.DictReader(c_file, delimiter=','))

        for row in reader:
            countries_list.append(row['Name_EN'])
    return countries_list 

def get_footer_copyright(soup,url):
    company_alias =  re.findall('https://www.([\w\-]+).(\w+).(\w+)',url)
    if company_alias:
        company_alias = company_alias[0][0]
    copyright_text = []
    for item in soup.findAll('div', {"id": re.compile('footer')}):
        if 'copyright' in item.text.lower():            
            # print('id',item.text)
            pattern = "(?:[a-zA-Z'-]+[^a-zA-Z'-]+){0,4}" + 'copyright' +"(?:[^a-zA-Z'-]+[a-zA-Z'-]+){0,5}"               
            context = re.search(pattern, item.text.lower())
            copyright_text.append(context.group())
    
    for item in soup.findAll('div', {"class": re.compile('footer')}):
        if 'copyright' in item.text.lower():
            # print('cls', item.text) #.partition(first_legal_form))
            pattern = "(?:[a-zA-Z'-]+[^a-zA-Z'-]+){0,4}" + 'copyright' +"(?:[^a-zA-Z'-]+[a-zA-Z'-]+){0,5}"               
            context = re.search(pattern, item.text.lower())
            copyright_text.append(context.group())
    if not copyright_text:
        unicode_sym = b'\xc2\xa9'
        unicode_sym = unicode_sym.decode('utf-8')
        copyright_context = re.findall("(?:[a-zA-Z'-]+[^a-zA-Z'-]+){0,4}"+ unicode_sym + "(?:[^a-zA-Z'-]+[a-zA-Z'-]+){0,5}", soup.text)
        for text in copyright_context:
            if company_alias:
                if company_alias in text.lower():
                    copyright_text.append(text)
    return copyright_text 

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


def get_suffixes(file_name):
    suffixes =[]
    with in_place.InPlace(file_name) as file:
        for line in file:
            suffixes.append(line.strip())
            file.write(line)
    return suffixes

def scrape_legal_forms(text_content,legal_forms):
    first_legal_form = None
    min_position = sys.maxsize
    found_legal_forms = []
    suffixes = get_suffixes('SuffixesList.txt')
    for legal_form in legal_forms:
        position_found = is_company_type(text_content, legal_form)
        if position_found > 0:
            if position_found < min_position:
                found_legal_forms.append(legal_form)
                first_legal_form = legal_form
                min_position = position_found
                
                pattern = "(?:[a-zA-Z'-]+[^a-zA-Z'-]+){0,4}" + first_legal_form# +"(?:[^a-zA-Z'-]+[a-zA-Z'-]+){0,5}"               
                context = re.search(pattern, text_content)
                print(f"Legal form found: '{legal_form}'")
                print(f"Context of above legal form: '{context.group()}'")
                found_suffixes = []
                for suff in suffixes:
                    if suff in context.group():
                        print(f"Suffix: '{suff}' found in legal form: '{legal_form}'")
                        suffix_pattern = "(?:[a-zA-Z'-]+[^a-zA-Z'-]+){0,1}" + suff# +"(?:[^a-zA-Z'-]+[a-zA-Z'-]+){0,5}"               
                        suffix_context = re.search(suffix_pattern, context.group())
                        print(f"Context of above suffix: '{suffix_context.group()}'")
                        found_suffixes.append(suffix_context.group())
                print('----------')
                # print(found_suffixes)
    return found_legal_forms, min_position

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

            page = requests.get(response.url)
            soup = BeautifulSoup(page.content, "html.parser")
            copyright_text = get_footer_copyright(soup,response.url)
            with open('log.txt', 'a') as f:
                if len(copyright_text) > 0:
                    f.write(f'Copyright text: {copyright_text}\n\n')
                else:
                    f.write(f'Copyright not found \n\n')
            legal_forms = get_legal_forms('es_legal_forms.json')    
            found_legal_forms, min_position = scrape_legal_forms(tc_content, legal_forms)

            if min_position < sys.maxsize:
                print('Company type: ', found_legal_forms, response.url)
            else:
                print('Legal form not found')
            print('==================================================================================')
        else:
            self.failed_urls.append(response.url)
            with open('log.txt', 'a') as f:
                f.write(f"No T&C page for {response.url}\n\n")
        
    def get_text_content(self, text):
        doc = Document(text)
        return doc.summary()
