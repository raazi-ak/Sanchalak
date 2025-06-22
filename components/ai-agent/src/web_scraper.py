"""
Web Scraper Agent for Farmer AI Pipeline

Handles web scraping of government schemes and agricultural information
"""

import asyncio
import aiohttp
import time
import os
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

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
        
    async def initialize(self):
        """Initialize the web scraper"""
        try:
            logger.info("Initializing Web Scraper Agent...")
            
            # Initialize aiohttp session
            await self._initialize_session()
            
            # Load scraping patterns
            await self._load_scraping_patterns()
            
            self.is_initialized = True
            logger.info("Web Scraper Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Web Scraper Agent: {str(e)}")
            raise
    
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
        
        # Patterns for extracting specific information
        self.extraction_patterns = {
            'amount': [
                r'₹\s*(\d+(?:,\d+)*(?:\.\d+)?)',
                r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d+)?)',
                r'(\d+(?:,\d+)*)\s*(?:rupees|lakh|crore)',
                r'(\d+(?:,\d+)*)\s*(?:रुपये|लाख|करोड़)'
            ],
            'acres': [
                r'(\d+(?:\.\d+)?)\s*(?:acres?|एकड़)',
                r'(\d+(?:\.\d+)?)\s*(?:hectares?|हेक्टेयर)'
            ],
            'age': [
                r'(?:age|आयु|उम्र)\s*(?:between|from)?\s*(\d+)\s*(?:to|-)\s*(\d+)',
                r'(\d+)\s*(?:years|साल|वर्ष)'
            ],
            'income': [
                r'(?:income|आय)\s*(?:below|up to|upto)\s*₹?\s*(\d+(?:,\d+)*)',
                r'₹?\s*(\d+(?:,\d+)*)\s*(?:per annum|annually|सालाना)'
            ]
        }
        
        logger.info("Scraping patterns loaded")
    
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
            
            # Extract structured data
            benefit_amount = self._extract_amount(benefits or description)
            eligibility_rules = self._extract_eligibility_rules(eligibility or description)
            
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
            logger.info(f"Extracted scheme: {scheme.name}")
            
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
        """Extract eligibility rules from text"""
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
            "user_agent": self.user_agent
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Get health status of the web scraper"""
        try:
            return {
                "status": "healthy" if self.is_initialized else "not_ready",
                "session_active": self.session is not None,
                "scraping_stats": await self.get_scraping_stats()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }