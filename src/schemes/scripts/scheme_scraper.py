import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pdfplumber
import re
import json
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import argparse
import yaml

section_keywords = [
    ("eligibility", ["eligibility", "who can apply", "criteria", "requirements", "conditions", "eligible", "applicant must", "applicants must"]),
    ("exclusions", ["not eligible", "exclusions", "ineligible", "exceptions", "not covered", "not applicable", "not entitled"]),
    ("documents", ["required documents", "documents needed", "proof", "certificates", "supporting documents", "document required"]),
    ("benefits", ["benefit", "amount", "financial assistance", "support", "grant", "disbursement", "entitlement", "assistance", "aid"]),
    ("application", ["how to apply", "application process", "procedure", "steps", "timeline", "application form", "submission", "apply"]),
    ("monitoring", ["monitoring", "tracking", "claim settlement", "status", "reporting", "follow up", "progress"]),
    ("notes", ["notes", "remarks", "important", "special instructions", "caveats"]),
    ("general", ["about", "summary", "introduction", "scheme details", "overview", "background"]),
]

def is_pdf(url):
    return url.lower().endswith('.pdf')

def is_same_domain(url, base):
    return urlparse(url).netloc == urlparse(base).netloc

def extract_sections(text, section_keywords):
    sections = {k: "" for k, _ in section_keywords}
    lines = text.splitlines()
    current_section = None
    buffer = []
    for line in lines:
        l = line.strip().lower()
        found = False
        for sec, keywords in section_keywords:
            if any(kw in l for kw in keywords):
                if current_section and buffer:
                    sections[current_section] += "\n".join(buffer) + "\n"
                current_section = sec
                buffer = [line]
                found = True
                break
        if not found:
            buffer.append(line)
    if current_section and buffer:
        sections[current_section] += "\n".join(buffer)
    return sections

def crawl(url, base_url, html_dir, pdf_links, visited, depth=0, max_depth=2):
    if url in visited or depth > max_depth:
        return
    visited.add(url)
    print(f"Crawling: {url}")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        if 'text/html' in resp.headers.get('Content-Type', ''):
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Save raw text
            text = soup.get_text(separator='\n', strip=True)
            fname = os.path.join(html_dir, f"page_{len(visited)}.txt")
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\n\n{text}")
            # Find links
            for link in soup.find_all('a', href=True):
                href = urljoin(url, link['href'])
                if is_pdf(href):
                    pdf_links.add(href)
                elif is_same_domain(href, base_url):
                    crawl(href, base_url, html_dir, pdf_links, visited, depth+1, max_depth)
        elif is_pdf(url):
            pdf_links.add(url)
    except Exception as e:
        print(f"Failed to crawl {url}: {e}")

def extract_text_from_pdf(pdf_path):
    # Try text extraction with pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = ""
            for page in pdf.pages:
                all_text += page.extract_text() or ""
        if all_text.strip():
            return all_text
    except Exception as e:
        print(f"pdfplumber failed for {pdf_path}: {e}")
    # Fallback to OCR
    try:
        print(f"Running OCR on {pdf_path}")
        images = convert_from_path(pdf_path)
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img, lang='eng') + "\n"
        return ocr_text
    except Exception as e:
        print(f"OCR failed for {pdf_path}: {e}")
    return ""

def download_and_extract_pdfs(pdf_links, pdf_dir, section_keywords, structured):
    for pdf_url in pdf_links:
        try:
            print(f"Downloading PDF: {pdf_url}")
            pdf_name = os.path.join(pdf_dir, os.path.basename(urlparse(pdf_url).path))
            r = requests.get(pdf_url, timeout=15)
            with open(pdf_name, 'wb') as f:
                f.write(r.content)
            # Extract text (with OCR fallback)
            all_text = extract_text_from_pdf(pdf_name)
            txt_name = pdf_name.replace('.pdf', '.txt')
            with open(txt_name, 'w', encoding='utf-8') as f:
                f.write(f"URL: {pdf_url}\n\n{all_text}")
            # Extract and save structured sections
            sections = extract_sections(all_text, section_keywords)
            structured.append({
                "source_url": pdf_url,
                "type": "pdf",
                "sections": sections,
                "raw_text": all_text
            })
        except Exception as e:
            print(f"Failed to process PDF {pdf_url}: {e}")

def get_outputs_base():
    # Always resolve to schemes/outputs/ (two levels up from this script)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))

def run_scraper(url, scheme, max_depth, section_keywords_override=None):
    section_kw = section_keywords_override if section_keywords_override else section_keywords
    scheme_name = scheme.strip().replace(' ', '_').lower()
    base_outputs = get_outputs_base()
    out_dir = os.path.join(base_outputs, scheme_name)
    html_dir = os.path.join(out_dir, 'html_pages')
    pdf_dir = os.path.join(out_dir, 'pdfs')
    os.makedirs(html_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)

    visited = set()
    pdf_links = set()
    structured = []

    print(f"Starting crawl for {scheme_name} at {url}")
    crawl(url, url, html_dir, pdf_links, visited, depth=0, max_depth=max_depth)
    print(f"Found {len(pdf_links)} PDFs. Downloading and extracting...")
    download_and_extract_pdfs(pdf_links, pdf_dir, section_kw, structured)

    # Extract and save structured sections from HTML pages
    for fname in os.listdir(html_dir):
        if fname.endswith('.txt'):
            with open(os.path.join(html_dir, fname), 'r', encoding='utf-8') as f:
                text = f.read()
            sections = extract_sections(text, section_kw)
            structured.append({
                "source_url": None,
                "type": "html",
                "sections": sections,
                "raw_text": text
            })

    # Save all structured data
    raw_json_path = os.path.join(out_dir, 'raw.json')
    with open(raw_json_path, 'w', encoding='utf-8') as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)
    print(f"Done. All outputs saved in {out_dir}")
    return scheme_name, raw_json_path

def update_index_yaml(scheme_name, scheme_display_name, raw_json_path):
    index_path = os.path.join(get_outputs_base(), 'supported_schemes.yaml')
    entry = {
        'code': scheme_name,
        'name': scheme_display_name,
        'raw': raw_json_path
    }
    # Load or create index
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            index = yaml.safe_load(f) or []
    else:
        index = []
    # Remove any existing entry for this code
    index = [e for e in index if e['code'] != scheme_name]
    index.append(entry)
    with open(index_path, 'w', encoding='utf-8') as f:
        yaml.dump(index, f, allow_unicode=True)
    print(f"Updated index at {index_path}")

def main():
    parser = argparse.ArgumentParser(description="Scheme-Agnostic Web Scraper")
    parser.add_argument('--url', help='Root URL of the scheme website')
    parser.add_argument('--scheme', help='Scheme name (for output folder)')
    parser.add_argument('--max_depth', type=int, default=2, help='Max crawl depth')
    args = parser.parse_args()

    # Interactive mode if no flags
    if not args.url or not args.scheme:
        print("Interactive mode: Please enter scheme details.")
        url = input("Enter scheme root URL: ").strip()
        scheme = input("Enter scheme name (e.g., PM-KISAN): ").strip()
    else:
        url = args.url
        scheme = args.scheme

    scheme_name, raw_json_path = run_scraper(url, scheme, args.max_depth)
    update_index_yaml(scheme_name, scheme, raw_json_path)

if __name__ == "__main__":
    main()