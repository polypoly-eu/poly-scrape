import requests
from bs4 import BeautifulSoup
from readability import Document
import sys
import re
import json
import in_place


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


def scrape_legal_forms(text_content,legal_forms):
    first_legal_form = None
    min_position = sys.maxsize
    found_legal_forms = []
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
                print('----------')
    return found_legal_forms, min_position

def scrape_content(URLs):
    for url in URLs:
        try:
            page = requests.get(url)
            soup = BeautifulSoup(page.content, "html.parser")
            text_content = get_text(soup.text)
            print('Scraping: ', url)
            
            legal_forms = get_legal_forms('es_legal_forms.json')    
            found_legal_forms, min_position = scrape_legal_forms(text_content, legal_forms)

            if min_position < sys.maxsize:
                print('Company type: ', found_legal_forms, url)                        
            else:
                print('Legal form not found')
            print('==================================================================================')
        except Exception as error:
            print('Skipping: ', url, ' ERROR: ', str(error))

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