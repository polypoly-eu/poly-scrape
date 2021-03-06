import requests
from bs4 import BeautifulSoup
from readability import Document
import sys
import re
import json
import in_place
import numpy as np
import csv

COUNTRIES_PATH = './Countries.csv'

def get_text(html_text):
    doc = Document(html_text)
    return doc.summary()

def is_company_type(text, company_type):
    return min(p for p in [text.find(f" {company_type} "), text.find(f" {company_type}."), text.find(f" {company_type},"), sys.maxsize ] if p > 0)

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

def get_footer_copyright(soup,url):
    company_alias =  re.findall('https://www.([\w\-]+).(\w+).(\w+)',url)
    if company_alias:
        company_alias = company_alias[0][0]
        print('comp alias:',company_alias)
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
                    print('Context of copyright symbol: ', text)
    return copyright_text

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

def get_countries(countries_path):
    countries_list =[]
    with open(countries_path) as c_file:  # pylint: disable=unspecified-encoding
        reader = list(csv.DictReader(c_file, delimiter=','))

        for row in reader:
            countries_list.append(row['Name_EN'])
    return countries_list    

def scrape_country(text_content):
    countries = get_countries(COUNTRIES_PATH)
    occurrences = []
    for idx, country in enumerate(countries):
        count = sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(country),text_content))
        occurrences.append(count)
    sorted_indexes = np.argsort(np.array(occurrences))
    if occurrences[sorted_indexes[-1]] > occurrences[sorted_indexes[-2]] and occurrences[sorted_indexes[-1]] > 0:
        print('Country of jurisdiction: ',countries[sorted_indexes[-1]])

def scrape_content(URLs):
    for url in URLs:
        try:
            page = requests.get(url)
            soup = BeautifulSoup(page.content, "html.parser")
        except Exception as error:
            print('Skipping: ', url, ' ERROR: ', str(error))

        text_content = get_text(soup.text)
        print('Scraping: ', url)
        scrape_country(text_content)
        copyright_text = get_footer_copyright(soup,url)
        if len(copyright_text) > 0:
            print('Copyright text: ',copyright_text)
        else:
            print('Copyright not found')
        
        legal_forms = get_legal_forms('es_legal_forms.json')    
        found_legal_forms, min_position = scrape_legal_forms(text_content, legal_forms)

        if min_position < sys.maxsize:
            print('Company type: ', found_legal_forms, url)                        
        else:
            print('Legal form not found')
        print('==================================================================================')


def get_urls(file_name):
    urls = []
    with in_place.InPlace(file_name) as file:
        for line in file:
            if line.strip().startswith('http'):
                urls.append(line.strip())
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
            # print(f"Processed {line}")
    return urls

def main():
    urls = get_urls('sites.in')
    scrape_content(urls)

if __name__ == '__main__':
    main()