"""
Web Scraper Agent for Farmer AI Pipeline

Handles web scraping of government schemes and agricultural information
Enhanced with advanced NLP capabilities for better rule extraction
"""

import asyncio
import aiohttp
import time
import os
from typing import List, Dict, Any, Optional, Set, Union
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# Enhanced NLP imports
import spacy
from textblob import TextBlob

from config import get_settings
from models import GovernmentScheme, DocumentChunk, EligibilityRule
from utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

class WebScraperAgent:
    """Agent for scraping government scheme information from websites"""
    
    def __init__(self):
        self.session = None
        self.scraped_urls = set()
        self.scheme_patterns = {}
        self.is_initialized = False
        self.user_agent = settings.scraper_user_agent
        self.delay = settings.scraper_delay
        self.timeout = settings.scraping_timeout
        self.max_pages = settings.max_pages_per_site
        
        # NLP components
        self.nlp = None
        self.nlp_initialized = False
        
    async def initialize(self):
        """Initialize the web scraper"""
        try:
            logger.info("Initializing Web Scraper Agent...")
            
            # Initialize aiohttp session
            await self._initialize_session()
            
            # Load scraping patterns
            await self._load_scraping_patterns()
            
            # Initialize NLP components
            await self._initialize_nlp()
            
            self.is_initialized = True
            logger.info("Web Scraper Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Web Scraper Agent: {str(e)}")
            raise
    
    async def _initialize_nlp(self):
        """Initialize NLP components for enhanced text processing"""
        try:
            logger.info("Initializing NLP components...")
            
            # Load spaCy model
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy English model not found. Installing...")
                os.system("python -m spacy download en_core_web_sm")
                self.nlp = spacy.load("en_core_web_sm")
            
            self.nlp_initialized = True
            logger.info("NLP components initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to initialize NLP components: {str(e)}")
            logger.warning("Falling back to regex-only extraction")
            self.nlp_initialized = False
    
    async def _initialize_session(self):
        """Initialize aiohttp session with proper headers"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            connector=aiohttp.TCPConnector(limit=10)
        )
        
        logger.info("HTTP session initialized")
    
    async def _load_scraping_patterns(self):
        """Load patterns for extracting scheme information"""
        self.scheme_patterns = {
            'scheme_name_selectors': [
                'h1', 'h2', '.scheme-title', '.title', '.heading',
                '.scheme-name', '[class*="title"]', '[class*="heading"]'
            ],
            'description_selectors': [
                '.description', '.content', '.scheme-desc', '.overview',
                'p', '.text-content', '[class*="desc"]', '.summary'
            ],
            'benefit_selectors': [
                '.benefit', '.benefits', '.amount', '.financial-support',
                '[class*="benefit"]', '[class*="amount"]', '.subsidy'
            ],
            'eligibility_selectors': [
                '.eligibility', '.criteria', '.requirements', '.conditions',
                '[class*="eligib"]', '[class*="criteria"]', '.who-can-apply'
            ],
            'process_selectors': [
                '.process', '.procedure', '.application', '.how-to-apply',
                '[class*="process"]', '[class*="apply"]', '.steps'
            ],
            'documents_selectors': [
                '.documents', '.required-docs', '.paperwork', '.doc-list',
                '[class*="document"]', '[class*="required"]', '.checklist'
            ]
        }
        
        # Enhanced patterns for better extraction
        self.extraction_patterns = {
            'amount': [
                r'₹\s*(\d+(?:,\d+)*(?:\.\d+)?)',
                r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d+)?)',
                r'(\d+(?:,\d+)*)\s*(?:rupees|lakh|crore)',
                r'(\d+(?:,\d+)*)\s*(?:रुपये|लाख|करोड़)',
                r'amount.*?(\d+(?:,\d+)*)',
                r'subsidy.*?(\d+(?:,\d+)*)'
            ],
            'acres': [
                r'(\d+(?:\.\d+)?)\s*(?:acres?|एकड़)',
                r'(\d+(?:\.\d+)?)\s*(?:hectares?|हेक्टेयर)',
                r'land.*?(\d+(?:\.\d+)?)\s*(?:acre|hectare)'
            ],
            'age': [
                r'(?:age|आयु|उम्र)\s*(?:between|from)?\s*(\d+)\s*(?:to|-|और)\s*(\d+)',
                r'(\d+)\s*(?:years|साल|वर्ष)',
                r'minimum.*?age.*?(\d+)',
                r'maximum.*?age.*?(\d+)'
            ],
            'income': [
                r'(?:income|आय)\s*(?:below|up to|upto|maximum|अधिकतम)\s*₹?\s*(\d+(?:,\d+)*)',
                r'₹?\s*(\d+(?:,\d+)*)\s*(?:per annum|annually|सालाना)',
                r'annual.*?income.*?(\d+(?:,\d+)*)',
                r'family.*?income.*?(\d+(?:,\d+)*)'
            ],
            'category': [
                r'(?:SC|ST|OBC|scheduled caste|scheduled tribe|other backward class)',
                r'(?:general|unreserved|UR)',
                r'(?:minority|अल्पसंख्यक)',
                r'(?:BPL|below poverty line|गरीबी रेखा)'
            ]
        }
        
        logger.info("Enhanced scraping patterns loaded")
    
    def _extract_eligibility_rules_enhanced(self, text: str) -> List[EligibilityRule]:
        """Enhanced rule extraction using spaCy + regex"""
        if not text:
            return []
            
        rules = []
        
        try:
            # Use spaCy if available, otherwise fall back to regex
            if self.nlp_initialized and self.nlp:
                doc = self.nlp(text)
                rules.extend(self._extract_rules_with_spacy(doc, text))
            else:
                rules.extend(self._extract_rules_with_regex(text))
            
            # Use TextBlob for sentiment analysis of eligibility text
            blob = TextBlob(text)
            sentiment = blob.sentiment.polarity
            
            # Adjust rule weights based on text clarity/sentiment
            for rule in rules:
                if sentiment > 0.1:  # Positive sentiment suggests clear, well-written criteria
                    rule.weight = min(rule.weight + 0.1, 1.0)
                elif sentiment < -0.1:  # Negative sentiment might indicate complex/confusing criteria
                    rule.weight = max(rule.weight - 0.1, 0.1)
            
        except Exception as e:
            logger.warning(f"Enhanced rule extraction failed, falling back to basic extraction: {str(e)}")
            rules = self._extract_eligibility_rules(text)
        
        return rules
    
    def _extract_rules_with_spacy(self, doc, text: str) -> List[EligibilityRule]:
        """Extract rules using spaCy NLP"""
        rules = []
        
        try:
            # Extract age rules with better context understanding
            age_patterns = [
                r"(?:age|आयु)\s*(?:between|from|range)?\s*(\d+)\s*(?:to|-|और|से)\s*(\d+)",
                r"(?:minimum|न्यूनतम)\s*(?:age|आयु)\s*(?:of|:)?\s*(\d+)",
                r"(?:maximum|अधिकतम)\s*(?:age|आयु)\s*(?:of|:)?\s*(\d+)",
                r"(\d+)\s*(?:years|साल|वर्ष)\s*(?:to|से)\s*(\d+)\s*(?:years|साल|वर्ष)"
            ]
            
            for pattern in age_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    groups = match.groups()
                    if len(groups) == 2 and groups[1]:  # Age range
                        min_age, max_age = int(groups[0]), int(groups[1])
                        rules.append(EligibilityRule(
                            field="age",
                            operator="between",
                            value=[min_age, max_age],
                            weight=0.85
                        ))
                    elif len(groups) == 1:  # Single age limit
                        age_val = int(groups[0])
                        if "minimum" in match.group().lower() or "न्यूनतम" in match.group():
                            rules.append(EligibilityRule(
                                field="age",
                                operator=">=",
                                value=age_val,
                                weight=0.8
                            ))
                        elif "maximum" in match.group().lower() or "अधिकतम" in match.group():
                            rules.append(EligibilityRule(
                                field="age",
                                operator="<=",
                                value=age_val,
                                weight=0.8
                            ))
            
            # Extract income rules with currency handling
            income_patterns = [
                r"(?:income|आय)\s*(?:below|up to|maximum|अधिकतम|से कम)\s*₹?\s*([\d,]+)(?:\s*(?:lakh|लाख|crore|करोड़))?",
                r"annual\s*(?:family\s*)?income.*?₹?\s*([\d,]+)(?:\s*(?:lakh|लाख|crore|करोड़))?",
                r"family\s*income.*?(?:not\s*exceeding|below|अधिकतम)\s*₹?\s*([\d,]+)(?:\s*(?:lakh|लाख|crore|करोड़))?"
            ]
            
            for pattern in income_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    
                    # Handle Indian numbering system
                    match_text = match.group().lower()
                    if 'lakh' in match_text or 'लाख' in match_text:
                        amount *= 100000
                    elif 'crore' in match_text or 'करोड़' in match_text:
                        amount *= 10000000
                    
                    rules.append(EligibilityRule(
                        field="annual_income",
                        operator="<=",
                        value=amount,
                        weight=0.9
                    ))
            
            # Extract land size rules
            land_patterns = [
                r"(?:land|भूमि|farm).*?(?:up to|maximum|अधिकतम|से कम)\s*([\d.]+)\s*(?:hectare|हेक्टेयर|acre|एकड़)",
                r"(?:small|marginal)\s*(?:farmer|किसान).*?([\d.]+)\s*(?:hectare|हेक्टेयर|acre|एकड़)",
                r"landholding.*?(?:below|up to)\s*([\d.]+)\s*(?:hectare|हेक्टेयर|acre|एकड़)"
            ]
            
            for pattern in land_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    size = float(match.group(1))
                    
                    # Convert hectares to acres if needed
                    unit = match.group().lower()
                    if 'hectare' in unit or 'हेक्टेयर' in unit:
                        size *= 2.47  # Convert hectares to acres
                    
                    rules.append(EligibilityRule(
                        field="land_size_acres",
                        operator="<=",
                        value=size,
                        weight=0.9
                    ))
            
            # Extract category-based rules
            category_patterns = [
                r"(?:SC|ST|OBC|scheduled\s*caste|scheduled\s*tribe|other\s*backward\s*class)",
                r"(?:minority|अल्पसंख्यक)",
                r"(?:BPL|below\s*poverty\s*line|गरीबी\s*रेखा)",
                r"(?:women|महिला|female)"
            ]
            
            for pattern in category_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    category = re.search(pattern, text, re.IGNORECASE).group().lower()
                    rules.append(EligibilityRule(
                        field="category",
                        operator="in",
                        value=category.replace(' ', '_'),
                        weight=0.7
                    ))
        
        except Exception as e:
            logger.warning(f"spaCy rule extraction failed: {str(e)}")
        
        return rules
    
    def _extract_rules_with_regex(self, text: str) -> List[EligibilityRule]:
        """Fallback regex-based rule extraction"""
        rules = []
        
        try:
            # Age rules
            age_pattern = r"(?:age|आयु)\s*(?:between|from)?\s*(\d+)\s*(?:to|-|और)\s*(\d+)"
            for match in re.finditer(age_pattern, text, re.IGNORECASE):
                min_age, max_age = match.groups()
                rules.append(EligibilityRule(
                    field="age",
                    operator="between",
                    value=[int(min_age), int(max_age)],
                    weight=0.8
                ))
            
            # Income rules
            income_pattern = r"income.*?(?:below|up to|maximum|अधिकतम)\s*₹?\s*([\d,]+)"
            for match in re.finditer(income_pattern, text, re.IGNORECASE):
                amount = int(match.group(1).replace(',', ''))
                rules.append(EligibilityRule(
                    field="annual_income",
                    operator="<=",
                    value=amount,
                    weight=0.9
                ))
            
            # Land size rules
            land_pattern = r"(?:land|भूमि).*?(?:up to|maximum|अधिकतम)\s*([\d.]+)\s*(?:hectare|हेक्टेयर|acre|एकड़)"
            for match in re.finditer(land_pattern, text, re.IGNORECASE):
                size = float(match.group(1))
                rules.append(EligibilityRule(
                    field="land_size_acres",
                    operator="<=",
                    value=size,
                    weight=0.9
                ))
        
        except Exception as e:
            logger.warning(f"Regex rule extraction failed: {str(e)}")
        
        return rules
    
    async def scrape_government_schemes(self) -> List[GovernmentScheme]:
        """Scrape government schemes from configured URLs"""
        try:
            if not self.is_initialized:
                raise ValueError("Web Scraper Agent not initialized")
            
            schemes = []
            urls_to_scrape = getattr(settings, 'scheme_urls', [
                "https://www.pmkisan.gov.in/",
                "https://pmfby.gov.in/",
                "https://agriwelfare.gov.in/",
            ])
            
            logger.info(f"Starting to scrape {len(urls_to_scrape)} URLs")
            
            for url in urls_to_scrape:
                try:
                    site_schemes = await self._scrape_website(url)
                    schemes.extend(site_schemes)
                    
                    # Add delay between sites
                    await asyncio.sleep(self.delay)
                    
                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {str(e)}")
                    continue
            
            logger.info(f"Scraped {len(schemes)} schemes total")
            return schemes
            
        except Exception as e:
            logger.error(f"Scheme scraping failed: {str(e)}")
            return []
    
    async def _scrape_website(self, base_url: str) -> List[GovernmentScheme]:
        """Scrape schemes from a single website"""
        schemes = []
        pages_scraped = 0
        
        try:
            # Get the main page
            main_content = await self._fetch_page(base_url)
            if not main_content:
                return schemes
            
            # Find scheme-related links
            scheme_links = await self._extract_scheme_links(main_content, base_url)
            
            # Scrape individual scheme pages
            for link in scheme_links[:self.max_pages]:
                try:
                    if pages_scraped >= self.max_pages:
                        break
                    
                    scheme = await self._scrape_scheme_page(link)
                    if scheme:
                        schemes.append(scheme)
                    
                    pages_scraped += 1
                    await asyncio.sleep(self.delay)
                    
                except Exception as e:
                    logger.warning(f"Failed to scrape scheme page {link}: {str(e)}")
                    continue
            
            # Also extract schemes from main page
            main_schemes = await self._extract_schemes_from_page(main_content, base_url)
            schemes.extend(main_schemes)
            
            logger.info(f"Scraped {len(schemes)} schemes from {base_url}")
            
        except Exception as e:
            logger.error(f"Website scraping failed for {base_url}: {str(e)}")
        
        return schemes
    
    async def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page"""
        try:
            if url in self.scraped_urls:
                return None
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    self.scraped_urls.add(url)
                    
                    soup = BeautifulSoup(content, 'html.parser')
                    return soup
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return None
    
    async def _extract_scheme_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract links to individual scheme pages"""
        links = []
        
        try:
            # Look for links that might be scheme pages
            scheme_keywords = [
                'scheme', 'yojana', 'योजना', 'policy', 'program', 'benefit',
                'subsidy', 'support', 'assistance', 'aid', 'welfare'
            ]
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                text = link.get_text().lower()
                
                # Check if link text or href contains scheme-related keywords
                if any(keyword in text or keyword in href.lower() for keyword in scheme_keywords):
                    full_url = urljoin(base_url, href)
                    
                    # Avoid duplicate domains and common exclusions
                    if (full_url not in links and 
                        self._is_valid_scheme_url(full_url) and
                        len(links) < 50):  # Limit to avoid too many links
                        links.append(full_url)
            
            logger.info(f"Found {len(links)} potential scheme links")
            
        except Exception as e:
            logger.error(f"Failed to extract scheme links: {str(e)}")
        
        return links
    
    def _is_valid_scheme_url(self, url: str) -> bool:
        """Check if URL is valid for scheme scraping"""
        try:
            parsed = urlparse(url)
            
            # Exclude certain file types and irrelevant pages
            excluded_extensions = ['.pdf', '.doc', '.xls', '.zip', '.jpg', '.png']
            excluded_paths = ['login', 'register', 'contact', 'about', 'privacy']
            
            if any(url.lower().endswith(ext) for ext in excluded_extensions):
                return False
            
            if any(path in url.lower() for path in excluded_paths):
                return False
            
            # Must be HTTP/HTTPS
            if parsed.scheme not in ['http', 'https']:
                return False
            
            return True
            
        except Exception:
            return False
    
    async def _scrape_scheme_page(self, url: str) -> Optional[GovernmentScheme]:
        """Scrape a single scheme page"""
        try:
            soup = await self._fetch_page(url)
            if not soup:
                return None
            
            # Extract scheme information
            scheme_data = await self._extract_schemes_from_page(soup, url)
            
            return scheme_data[0] if scheme_data else None
            
        except Exception as e:
            logger.error(f"Failed to scrape scheme page {url}: {str(e)}")
            return None
    
    async def _extract_schemes_from_page(self, soup: BeautifulSoup, url: str) -> List[GovernmentScheme]:
        """Extract scheme information from a page"""
        schemes = []
        
        try:
            # Extract basic information
            title = self._extract_text_by_selectors(soup, self.scheme_patterns['scheme_name_selectors'])
            description = self._extract_text_by_selectors(soup, self.scheme_patterns['description_selectors'])
            
            if not title and not description:
                return schemes
            
            # Generate scheme ID
            scheme_id = self._generate_scheme_id(title or url)
            
            # Extract additional information
            benefits = self._extract_text_by_selectors(soup, self.scheme_patterns['benefit_selectors'])
            eligibility = self._extract_text_by_selectors(soup, self.scheme_patterns['eligibility_selectors'])
            process = self._extract_text_by_selectors(soup, self.scheme_patterns['process_selectors'])
            documents = self._extract_text_by_selectors(soup, self.scheme_patterns['documents_selectors'])
            
            # Extract structured data using enhanced methods
            benefit_amount = self._extract_amount(benefits or description)
            eligibility_rules = self._extract_eligibility_rules_enhanced(eligibility or description)
            
            # Create scheme object
            scheme = GovernmentScheme(
                scheme_id=scheme_id,
                name=title or "Unknown Scheme",
                description=description or "No description available",
                benefit_amount=benefit_amount,
                benefit_type="subsidy",  # Default type
                eligibility_rules=eligibility_rules,
                implementing_agency=self._extract_agency(soup),
                application_process=process or "Contact implementing agency",
                required_documents=self._extract_document_list(documents) if documents else [],
                official_website=url,
                last_updated=datetime.utcnow(),
                is_active=True
            )
            
            schemes.append(scheme)
            logger.info(f"Extracted scheme: {scheme.name} with {len(eligibility_rules)} eligibility rules")
            
        except Exception as e:
            logger.error(f"Failed to extract scheme from page: {str(e)}")
        
        return schemes
    
    def _extract_text_by_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        """Extract text using CSS selectors"""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    # Get text from first relevant element
                    for element in elements:
                        text = element.get_text(strip=True)
                        if len(text) > 10:  # Minimum meaningful length
                            return text
            except Exception:
                continue
        return None
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract monetary amount from text"""
        if not text:
            return None
        
        for pattern in self.extraction_patterns['amount']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    
                    # Check for lakh/crore multipliers
                    if 'lakh' in text.lower() or 'लाख' in text:
                        amount *= 100000
                    elif 'crore' in text.lower() or 'करोड़' in text:
                        amount *= 10000000
                    
                    return amount
                except ValueError:
                    continue
        
        return None
    
    def _extract_eligibility_rules(self, text: str) -> List[EligibilityRule]:
        """Extract eligibility rules from text (legacy method for fallback)"""
        rules = []
        
        if not text:
            return rules
        
        try:
            # Look for age requirements
            age_matches = re.findall(r'(?:age|आयु|उम्र).*?(\d+).*?(?:to|-|से).*?(\d+)', text, re.IGNORECASE)
            for match in age_matches:
                min_age, max_age = match
                rules.append(EligibilityRule(
                    field="age",
                    operator=">=",
                    value=int(min_age),
                    weight=0.8
                ))
                rules.append(EligibilityRule(
                    field="age",
                    operator="<=",
                    value=int(max_age),
                    weight=0.8
                ))
            
            # Look for land requirements
            land_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:acre|hectare|एकड़|हेक्टेयर)', text, re.IGNORECASE)
            for match in land_matches:
                rules.append(EligibilityRule(
                    field="land_size_acres",
                    operator="<=",
                    value=float(match),
                    weight=0.9
                ))
            
            # Look for income requirements
            income_matches = re.findall(r'income.*?(?:below|up to|upto).*?(\d+(?:,\d+)*)', text, re.IGNORECASE)
            for match in income_matches:
                income = float(match.replace(',', ''))
                # Check for lakh/crore
                if 'lakh' in text.lower():
                    income *= 100000
                elif 'crore' in text.lower():
                    income *= 10000000
                
                rules.append(EligibilityRule(
                    field="annual_income",
                    operator="<=",
                    value=income,
                    weight=0.8
                ))
        
        except Exception as e:
            logger.warning(f"Failed to extract eligibility rules: {str(e)}")
        
        return rules
    
    def _extract_agency(self, soup: BeautifulSoup) -> str:
        """Extract implementing agency from page"""
        agency_selectors = [
            '.agency', '.department', '.ministry', '.implementing-agency',
            '[class*="agency"]', '[class*="department"]'
        ]
        
        agency = self._extract_text_by_selectors(soup, agency_selectors)
        
        if not agency:
            # Look in page text for common agency names
            page_text = soup.get_text().lower()
            agencies = [
                'ministry of agriculture', 'department of agriculture',
                'krishi vibhag', 'कृषि विभाग', 'government of india'
            ]
            
            for agency_name in agencies:
                if agency_name in page_text:
                    return agency_name.title()
        
        return agency or "Government Agency"
    
    def _extract_document_list(self, text: str) -> List[str]:
        """Extract required documents from text"""
        if not text:
            return []
        
        documents = []
        
        # Common document keywords
        doc_patterns = [
            r'aadhaar|आधार',
            r'pan card|पैन कार्ड',
            r'voter id|मतदाता पहचान',
            r'ration card|राशन कार्ड',
            r'bank passbook|बैंक पासबुक',
            r'land records|भूमि रिकॉर्ड',
            r'income certificate|आय प्रमाण पत्र',
            r'caste certificate|जाति प्रमाण पत्र'
        ]
        
        for pattern in doc_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                documents.append(pattern.split('|')[0].title())
        
        return documents
    
    def _generate_scheme_id(self, title: str) -> str:
        """Generate a unique scheme ID from title"""
        # Clean title and create ID
        clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
        words = clean_title.split()[:3]  # Use first 3 words
        scheme_id = '_'.join(words) + '_' + str(int(time.time()))[-6:]
        
        return scheme_id
    
    async def update_schemes(self) -> List[GovernmentScheme]:
        """Update scheme database by re-scraping"""
        try:
            logger.info("Starting scheme update process")
            
            # Clear scraped URLs to allow re-scraping
            self.scraped_urls.clear()
            
            # Scrape fresh data
            schemes = await self.scrape_government_schemes()
            
            logger.info(f"Scheme update completed. Found {len(schemes)} schemes")
            return schemes
            
        except Exception as e:
            logger.error(f"Scheme update failed: {str(e)}")
            return []
    
    async def scrape_custom_url(self, url: str) -> List[GovernmentScheme]:
        """Scrape schemes from a custom URL"""
        try:
            return await self._scrape_website(url)
        except Exception as e:
            logger.error(f"Custom URL scraping failed: {str(e)}")
            return []
    
    async def is_ready(self) -> bool:
        """Check if the agent is ready"""
        return self.is_initialized and self.session is not None
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.session:
                await self.session.close()
            
            self.session = None
            self.scraped_urls.clear()
            self.is_initialized = False
            self.nlp_initialized = False
            
            logger.info("Web Scraper Agent cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during Web Scraper cleanup: {str(e)}")
    
    async def get_scraping_stats(self) -> Dict[str, Any]:
        """Get scraping statistics"""
        return {
            "urls_scraped": len(self.scraped_urls),
            "max_pages_per_site": self.max_pages,
            "delay_between_requests": self.delay,
            "timeout": self.timeout,
            "user_agent": self.user_agent,
            "nlp_enabled": self.nlp_initialized
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Get health status of the web scraper"""
        try:
            return {
                "status": "healthy" if self.is_initialized else "not_ready",
                "session_active": self.session is not None,
                "nlp_available": self.nlp_initialized,
                "scraping_stats": await self.get_scraping_stats()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def analyze_text_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of extracted text for quality assessment"""
        try:
            blob = TextBlob(text)
            return {
                "polarity": blob.sentiment.polarity,
                "subjectivity": blob.sentiment.subjectivity
            }
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {str(e)}")
            return {"polarity": 0.0, "subjectivity": 0.0}
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities from text using spaCy"""
        entities = []
        
        try:
            if self.nlp_initialized and self.nlp:
                doc = self.nlp(text)
                for ent in doc.ents:
                    entities.append({
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "description": spacy.explain(ent.label_)
                    })
        except Exception as e:
            logger.warning(f"Entity extraction failed: {str(e)}")
        
        return entities
    
    def get_enhanced_extraction_stats(self) -> Dict[str, Any]:
        """Get statistics about enhanced extraction capabilities"""
        return {
            "nlp_model_loaded": self.nlp_initialized,
            "spacy_model": "en_core_web_sm" if self.nlp_initialized else None,
            "textblob_available": True,
            "enhanced_patterns_count": {
                "amount": len(self.extraction_patterns.get('amount', [])),
                "age": len(self.extraction_patterns.get('age', [])),
                "income": len(self.extraction_patterns.get('income', [])),
                "acres": len(self.extraction_patterns.get('acres', [])),
                "category": len(self.extraction_patterns.get('category', []))
            }
        }
    