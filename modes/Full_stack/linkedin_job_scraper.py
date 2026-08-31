#!/usr/bin/env python3
"""
LinkedIn Job Scraper v2.1 - Robust Edition
==========================================
Fixed with resilient selectors, multiple fallback strategies, and debug mode.

LinkedIn frequently changes class names (e.g., ember123, scaffold-layout__list-item).
This version uses pattern matching and heuristics instead of hardcoded class names.
"""

import os
import sys
import time
import pickle
import logging
import re
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('linkedin_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class JobListing:
    """Represents a scraped job listing."""
    title: str = "N/A"
    company: str = "N/A"
    location: str = "N/A"
    apply_link: str = "N/A"
    job_id: str = "N/A"
    posting_date: str = "N/A"
    applicants_count: str = "N/A"
    employment_type: str = "N/A"
    seniority_level: str = "N/A"
    job_function: str = "N/A"
    industries: str = "N/A"
    description: str = "N/A"
    company_size: str = "N/A"
    company_industry: str = "N/A"
    scraped_at: str = ""
    source: str = "linkedin"


class LinkedInJobScraper:
    """LinkedIn Job Scraper with robust, anti-fragile selectors."""

    BASE_URL = "https://www.linkedin.com"
    LOGIN_URL = "https://www.linkedin.com/login"

    def __init__(self, headless: bool = False, session_file: str = "linkedin_session.pkl"):
        self.headless = headless
        self.session_file = session_file
        self.driver = None
        self.wait = None
        self.is_logged_in = False
        self.email = os.getenv("LINKEDIN_EMAIL", "")
        self.password = os.getenv("LINKEDIN_PASSWORD", "")
        self.scroll_pause = 2
        self.max_jobs = 25

    def setup_driver(self) -> webdriver.Chrome:
        """Configure and initialize Chrome WebDriver."""
        logger.info("Setting up Chrome WebDriver...")
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        })

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            self.driver = driver
            self.wait = WebDriverWait(driver, 20)
            logger.info("WebDriver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def save_session(self) -> bool:
        if not self.driver:
            return False
        try:
            cookies = self.driver.get_cookies()
            session_data = {
                'cookies': cookies,
                'timestamp': datetime.now().isoformat(),
                'user_agent': self.driver.execute_script("return navigator.userAgent;"),
                'url': self.driver.current_url
            }
            with open(self.session_file, 'wb') as f:
                pickle.dump(session_data, f)
            logger.info(f"Session saved to {self.session_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def load_session(self) -> bool:
        if not os.path.exists(self.session_file):
            return False
        try:
            with open(self.session_file, 'rb') as f:
                session_data = pickle.load(f)
            session_time = datetime.fromisoformat(session_data['timestamp'])
            if (datetime.now() - session_time).days > 7:
                logger.warning("Session is older than 7 days, may be expired")
            self.driver.get(self.BASE_URL)
            time.sleep(2)
            for cookie in session_data['cookies']:
                try:
                    if 'expiry' in cookie:
                        del cookie['expiry']
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass
            logger.info("Session cookies loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False

    def detect_login_status(self) -> bool:
        try:
            self.driver.get(self.BASE_URL)
            time.sleep(3)
            indicators = [
                "//div[contains(@class, 'global-nav')]",
                "//img[contains(@class, 'nav__me-photo')]",
                "//a[contains(@href, '/feed/')]",
                "//span[text()='Home']",
                "//span[text()='My Network']"
            ]
            for indicator in indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0:
                        logger.info("Already logged in!")
                        return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"Error detecting login status: {e}")
            return False

    def try_auto_login(self) -> bool:
        if not self.email or not self.password:
            print("\n[!] No credentials found. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD.")
            return False
        logger.info("Attempting automatic login...")
        try:
            self.driver.get(self.LOGIN_URL)
            time.sleep(2)
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.clear()
            email_field.send_keys(self.email)
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            time.sleep(3)
            current_url = self.driver.current_url
            if "checkpoint" in current_url or "challenge" in current_url:
                print("\n[!] CAPTCHA detected. Switching to manual login...")
                return False
            if self.detect_login_status():
                self.is_logged_in = True
                self.save_session()
                return True
            logger.warning("Could not confirm login status after auto-login")
            return False
        except Exception as e:
            logger.error(f"Auto-login failed: {e}")
            return False

    def manual_login(self) -> bool:
        print("\n" + "="*60)
        print("MANUAL LOGIN REQUIRED")
        print("="*60)
        print("A browser window has opened. Please:")
        print("1. Log in to LinkedIn manually")
        print("2. Complete any CAPTCHA/2FA if prompted")
        print("3. Wait until you see your LinkedIn feed/homepage")
        print("4. Press ENTER in this terminal to continue...")
        print("="*60 + "\n")
        try:
            self.driver.get(self.LOGIN_URL)
            input("Press ENTER after you have logged in successfully...")
            time.sleep(2)
            if self.detect_login_status():
                self.is_logged_in = True
                self.save_session()
                print("\n[✓] Login confirmed and session saved!")
                return True
            else:
                print("\n[!] Could not confirm login status.")
                return False
        except Exception as e:
            logger.error(f"Manual login error: {e}")
            return False

    def login(self) -> bool:
        self.setup_driver()
        if self.load_session():
            if self.detect_login_status():
                self.is_logged_in = True
                return True
        if self.try_auto_login():
            return True
        if self.manual_login():
            return True
        logger.error("All login methods failed")
        return False

    def _dismiss_modals(self):
        """Dismiss any popups that block interaction."""
        dismiss_selectors = [
            "//button[contains(@aria-label, 'Dismiss')]",
            "//button[contains(@class, 'modal__dismiss')]",
            "//button[@aria-label='Dismiss']",
            "//icon[@data-test-icon='close-small']",
        ]
        for selector in dismiss_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for elem in elements:
                    if elem.is_displayed():
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(0.5)
            except Exception:
                pass

    def _debug_dump(self, prefix: str):
        """Save page source and screenshot for debugging."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_path = f"debug_{prefix}_{ts}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            screenshot_path = f"debug_{prefix}_{ts}.png"
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Debug dump saved: {html_path}, {screenshot_path}")
        except Exception as e:
            logger.debug(f"Debug dump failed: {e}")

    def scrape_jobs_authenticated(self, keywords: str, location: str = "", max_results: int = 25) -> List[JobListing]:
        """Scrape jobs using authenticated session with robust selectors."""
        logger.info(f"Scraping jobs (authenticated): '{keywords}' in '{location}'")
        jobs = []

        try:
            # Build search URL
            search_params = f"?keywords={keywords.replace(' ', '%20')}"
            if location:
                search_params += f"&location={location.replace(' ', '%20')}"
            url = f"https://www.linkedin.com/jobs/search/{search_params}"

            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            time.sleep(5)

            self._dismiss_modals()

            # Wait for page to have job-related content using multiple strategies
            job_content_found = False
            wait_strategies = [
                ("//ul[contains(@class, 'jobs-search__results-list')]", "results list"),
                ("//div[contains(@class, 'jobs-search-results-list')]", "results container"),
                ("//div[contains(@class, 'scaffold-layout__list')]", "scaffold list"),
                ("//div[contains(@class, 'jobs-search-two-pane__results')]", "two-pane results"),
                ("//a[contains(@href, '/jobs/view/')]", "job links"),
                ("//div[contains(@class, 'jobs-search-results')]", "generic results"),
            ]

            for xpath, desc in wait_strategies:
                try:
                    self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    logger.info(f"Found job content: {desc}")
                    job_content_found = True
                    break
                except TimeoutException:
                    continue

            if not job_content_found:
                logger.warning("Standard selectors failed. Dumping debug info...")
                self._debug_dump("job_page")
                # Try one more time with a generic wait
                time.sleep(5)

            # Scroll to load more jobs
            scroll_attempts = 0
            max_scrolls = min(max_results // 3, 15)

            while scroll_attempts < max_scrolls:
                # Try to scroll the job list container first
                scrolled = False
                scroll_containers = [
                    "//div[contains(@class, 'jobs-search-results-list')]",
                    "//ul[contains(@class, 'jobs-search__results-list')]",
                    "//div[contains(@class, 'scaffold-layout__list')]",
                    "//div[contains(@class, 'jobs-search-two-pane__results')]",
                ]
                for container_xpath in scroll_containers:
                    try:
                        container = self.driver.find_element(By.XPATH, container_xpath)
                        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
                        scrolled = True
                        time.sleep(1)
                        break
                    except Exception:
                        continue

                if not scrolled:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                time.sleep(self.scroll_pause)

                # Check for "Show more" button
                try:
                    show_more = self.driver.find_elements(By.XPATH, 
                        "//button[contains(text(), 'Show more') or contains(@aria-label, 'Show more')]")
                    for btn in show_more:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(2)
                            break
                except Exception:
                    pass

                scroll_attempts += 1

            # Parse the page
            time.sleep(2)
            soup = BeautifulSoup(self.driver.page_source, 'lxml')

            # STRATEGY 1: Find job cards by data attributes
            job_cards = soup.find_all('div', attrs={'data-job-id': True})
            if job_cards:
                logger.info(f"Found {len(job_cards)} job cards by data-job-id")

            # STRATEGY 2: Find by base-card class pattern
            if not job_cards:
                job_cards = soup.find_all('div', class_=re.compile('base-card'))
                if job_cards:
                    logger.info(f"Found {len(job_cards)} job cards by base-card pattern")

            # STRATEGY 3: Find by list item with job link
            if not job_cards:
                job_cards = soup.find_all('li', class_=re.compile('jobs-search-results__list-item|scaffold-layout__list-item'))
                if job_cards:
                    logger.info(f"Found {len(job_cards)} job cards by list-item pattern")

            # STRATEGY 4: Heuristic - find any container that has a /jobs/view/ link
            if not job_cards:
                logger.info("Using heuristic job card detection...")
                all_job_links = soup.find_all('a', href=re.compile(r'/jobs/view/'))
                seen_parents = set()
                for link in all_job_links[:max_results * 2]:
                    parent = link.find_parent(['div', 'li', 'article'])
                    if parent:
                        parent_id = id(parent)
                        if parent_id not in seen_parents:
                            seen_parents.add(parent_id)
                            job_cards.append(parent)
                logger.info(f"Heuristic found {len(job_cards)} job cards")

            # Parse each card
            for card in job_cards[:max_results]:
                try:
                    job = self._parse_job_card(card)
                    if job and job.title != "N/A":
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Error parsing job card: {e}")
                    continue

            logger.info(f"Parsed {len(jobs)} valid jobs from cards")

            # Enrich with detail data
            if jobs:
                logger.info("Enriching job data from detail panels...")
                jobs = self._enrich_jobs_from_details(jobs, min(10, len(jobs)))

        except Exception as e:
            logger.error(f"Error during authenticated scraping: {e}")
            import traceback
            traceback.print_exc()

        return jobs

    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a single job card using multiple strategies."""
        job = JobListing()
        job.scraped_at = datetime.now().isoformat()
        job.source = "authenticated"

        try:
            # Find the job link (contains /jobs/view/)
            job_links = card.find_all('a', href=re.compile(r'/jobs/view/'))
            if job_links:
                link = job_links[0]
                href = link.get('href', '')
                if href.startswith('/'):
                    job.apply_link = f"https://www.linkedin.com{href}"
                else:
                    job.apply_link = href
                # Extract job ID
                match = re.search(r'/jobs/view/(\d+)', job.apply_link)
                if match:
                    job.job_id = match.group(1)
                # Title from link text or aria-label
                job.title = link.get_text(strip=True) or link.get('aria-label', 'N/A')

            # If no link found, try to find title in headings
            if job.title == "N/A":
                for tag in ['h3', 'h2', 'h4', 'strong', 'b']:
                    elem = card.find(tag)
                    if elem:
                        text = elem.get_text(strip=True)
                        if text and len(text) > 2 and len(text) < 100:
                            job.title = text
                            break

            # Find company name
            # Strategy: look for text that isn't the title and isn't location-like
            all_text = card.get_text(separator='\n').split('\n')
            for text in all_text:
                text = text.strip()
                if not text or text == job.title:
                    continue
                # Company often appears as a link or prominent text
                if len(text) > 1 and len(text) < 60 and job.company == "N/A":
                    # Skip if it looks like a location (contains commas, numbers, or "Remote")
                    if not re.match(r'^[\d,\s]+(applicants?|ago)$', text, re.I):
                        if 'remote' not in text.lower() or len(text) < 20:
                            job.company = text
                            break

            # Better company detection: look for links that aren't the job link
            if job.company == "N/A":
                all_links = card.find_all('a')
                for link in all_links:
                    href = link.get('href', '')
                    if '/company/' in href or '/jobs/view/' not in href:
                        text = link.get_text(strip=True)
                        if text and len(text) > 1 and len(text) < 60:
                            job.company = text
                            break

            # Find location
            loc_patterns = [
                (re.compile(r'\b[A-Z][a-z]+,\s*[A-Z]{2}\b'), None),  # City, ST
                (re.compile(r'\b[A-Z][a-z]+,\s*[A-Za-z\s]+\b'), None),  # City, Country
                (re.compile(r'Remote\b', re.I), None),
                (re.compile(r'Hybrid\b', re.I), None),
                (re.compile(r'On-site\b', re.I), None),
            ]
            for pattern, _ in loc_patterns:
                text = card.get_text()
                match = pattern.search(text)
                if match:
                    job.location = match.group(0)
                    break

            # If still no location, look for specific elements
            if job.location == "N/A":
                for elem in card.find_all(['span', 'div']):
                    text = elem.get_text(strip=True)
                    if re.search(r'\b[A-Z][a-z]+,\s*[A-Z]{2}\b|\bRemote\b|\bHybrid\b', text):
                        job.location = text
                        break

            # Date posted
            date_elem = card.find('time')
            if date_elem:
                job.posting_date = date_elem.get('datetime', date_elem.get_text(strip=True))
            else:
                text = card.get_text()
                date_match = re.search(r'(\d+\s+(day|week|month|hour|minute)s?\s+ago)', text, re.I)
                if date_match:
                    job.posting_date = date_match.group(1)

            # Applicants count
            text = card.get_text()
            app_match = re.search(r'(\d+)\s+applicants?', text, re.I)
            if app_match:
                job.applicants_count = app_match.group(0)

            # Clean up title
            if job.title != "N/A" and job.company != "N/A" and job.company in job.title:
                job.title = job.title.replace(job.company, "").strip()

            # Validate: title should be reasonable
            if job.title == "N/A" or len(job.title) < 2 or len(job.title) > 150:
                return None

        except Exception as e:
            logger.debug(f"Error in card parsing: {e}")

        return job if job.title != "N/A" else None

    def _enrich_jobs_from_details(self, jobs: List[JobListing], max_to_enrich: int = 10) -> List[JobListing]:
        """Click on jobs to get detailed info from the right panel."""
        enriched = []

        for i, job in enumerate(jobs[:max_to_enrich]):
            try:
                if job.job_id == "N/A" and job.apply_link == "N/A":
                    enriched.append(job)
                    continue

                # Click on job card
                selectors = [
                    f"//a[contains(@href, '{job.job_id}')]",
                    f"//a[contains(@href, 'jobs/view')]",
                ]
                clicked = False
                for selector in selectors:
                    try:
                        cards = self.driver.find_elements(By.XPATH, selector)
                        for card in cards:
                            text = card.text or ""
                            if job.title[:20] in text or job.company[:15] in text:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                                time.sleep(0.5)
                                self.driver.execute_script("arguments[0].click();", card)
                                time.sleep(2.5)
                                clicked = True
                                break
                        if clicked:
                            break
                    except Exception:
                        continue

                if not clicked:
                    enriched.append(job)
                    continue

                # Parse detail panel
                detail_soup = BeautifulSoup(self.driver.page_source, 'lxml')

                # Description
                desc_patterns = [
                    ('div', re.compile('jobs-description__content')),
                    ('div', re.compile('job-details-jobs-description__content')),
                    ('div', re.compile('show-more-less-html__markup')),
                    ('article', re.compile('jobs-description')),
                ]
                for tag, pattern in desc_patterns:
                    elem = detail_soup.find(tag, pattern)
                    if elem:
                        job.description = elem.get_text(separator='\n', strip=True)
                        break

                # Job insights (employment type, seniority, etc.)
                insight_patterns = [
                    ('li', re.compile('jobs-unified-top-card__job-insight')),
                    ('span', re.compile('jobs-unified-top-card__bullet')),
                    ('div', re.compile('job-details-jobs-unified-top-card__job-insight')),
                ]
                for tag, pattern in insight_patterns:
                    insights = detail_soup.find_all(tag, pattern)
                    for insight in insights:
                        text = insight.get_text(strip=True)
                        if re.search(r'full-time|part-time|contract|temporary|internship|volunteer', text, re.I):
                            job.employment_type = text
                        elif re.search(r'entry|associate|mid-senior|senior|director|executive|internship', text, re.I):
                            job.seniority_level = text
                        elif re.search(r'engineering|sales|marketing|operations|finance|hr|design|product|it', text, re.I):
                            job.job_function = text
                        elif 'industr' in text.lower():
                            job.industries = text

                # Applicants in detail view
                app_text = detail_soup.get_text()
                app_match = re.search(r'(\d+)\s+applicants?', app_text, re.I)
                if app_match:
                    job.applicants_count = app_match.group(0)

                enriched.append(job)

            except Exception as e:
                logger.debug(f"Could not enrich job {i}: {e}")
                enriched.append(job)

        if len(jobs) > max_to_enrich:
            enriched.extend(jobs[max_to_enrich:])
        return enriched

    def scrape_jobs_public(self, keywords: str, location: str = "", max_results: int = 25) -> List[JobListing]:
        """Fallback: Scrape from public pages without login."""
        logger.info(f"Scraping jobs (public): '{keywords}' in '{location}'")
        jobs = []

        try:
            search_params = f"?keywords={keywords.replace(' ', '%20')}"
            if location:
                search_params += f"&location={location.replace(' ', '%20')}"
            url = f"https://www.linkedin.com/jobs/search/{search_params}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            # Try multiple strategies
            job_cards = soup.find_all('div', attrs={'data-job-id': True})
            if not job_cards:
                job_cards = soup.find_all('div', class_=re.compile('base-card'))
            if not job_cards:
                job_cards = soup.find_all('li', class_=re.compile('jobs-search-results__list-item'))
            if not job_cards:
                all_links = soup.find_all('a', href=re.compile(r'/jobs/view/'))
                seen = set()
                for link in all_links[:max_results * 2]:
                    parent = link.find_parent(['div', 'li'])
                    if parent and id(parent) not in seen:
                        seen.add(id(parent))
                        job_cards.append(parent)

            logger.info(f"Found {len(job_cards)} job cards on public page")

            for card in job_cards[:max_results]:
                try:
                    job = self._parse_job_card(card)
                    if job and job.title != "N/A":
                        job.source = "public"
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Error parsing public card: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error during public scraping: {e}")

        return jobs

    def save_to_markdown(self, jobs: List[JobListing], filename: str = "linkedin_jobs.md") -> str:
        """Save scraped jobs to a Markdown file."""
        if not jobs:
            logger.warning("No jobs to save")
            return ""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_label = "Authenticated (Logged In)" if jobs[0].source == "authenticated" else "Public (No Login)"

        md_content = f"""# LinkedIn Job Search Results

**Generated:** {timestamp}  
**Total Jobs:** {len(jobs)}  
**Source:** {source_label}

---

## Summary Table

| # | Company | Role | Location | Type | Posted | Applicants | Link |
|---|---------|------|----------|------|--------|------------|------|
"""

        for i, job in enumerate(jobs, 1):
            company = str(job.company).replace('|', '\\|').replace('\n', ' ')
            title = str(job.title).replace('|', '\\|').replace('\n', ' ')
            location = str(job.location).replace('|', '\\|').replace('\n', ' ')
            emp_type = str(job.employment_type).replace('|', '\\|').replace('\n', ' ')

            md_content += f"| {i} | {company} | {title} | {location} | {emp_type} | {job.posting_date} | {job.applicants_count} | [Apply]({job.apply_link}) |\n"

        md_content += f"""

---

## Detailed Listings

"""

        for i, job in enumerate(jobs, 1):
            desc = job.description[:800] + "..." if len(job.description) > 800 else job.description
            desc = desc.replace('\n', '\n\n')

            md_content += f"""### {i}. {job.title} at {job.company}

- **Company:** {job.company}
- **Role:** {job.title}
- **Location:** {job.location}
- **Job ID:** {job.job_id}
- **Apply Link:** [{job.apply_link}]({job.apply_link})
- **Posted:** {job.posting_date}
- **Applicants:** {job.applicants_count}
- **Employment Type:** {job.employment_type}
- **Seniority Level:** {job.seniority_level}
- **Job Function:** {job.job_function}
- **Industries:** {job.industries}
- **Scraped:** {job.scraped_at}

**Description:**

{desc if desc != "N/A" else "No description available."}

---

"""

        filepath = Path(filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"Saved {len(jobs)} jobs to {filepath.absolute()}")
        return str(filepath.absolute())

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except Exception:
                pass


def create_env_template():
    env_content = """# LinkedIn Credentials
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password

# Search Parameters
DEFAULT_KEYWORDS=Software Engineer
DEFAULT_LOCATION=United States
DEFAULT_MAX_RESULTS=25
"""
    with open('.env.template', 'w') as f:
        f.write(env_content)
    print("Created .env.template")


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║        LinkedIn Job Scraper v2.1 - Robust Edition            ║
    ║                                                              ║
    ║  WARNING: Scraping violates LinkedIn's Terms of Service.    ║
    ║  Use responsibly. Consider the official API for production.  ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    keywords = os.getenv("DEFAULT_KEYWORDS", input("Enter job keywords: ") or "Software Engineer")
    location = os.getenv("DEFAULT_LOCATION", input("Enter location: ") or "")
    max_results = int(os.getenv("DEFAULT_MAX_RESULTS", input("Max jobs (default 25): ") or "25"))

    scraper = LinkedInJobScraper(headless=False)

    try:
        login_success = scraper.login()

        jobs = []

        if login_success:
            print("\n[✓] Logged in! Scraping with full access...")
            jobs = scraper.scrape_jobs_authenticated(keywords, location, max_results)
        else:
            print("\n[!] Login failed. Attempting public page scraping...")
            jobs = scraper.scrape_jobs_public(keywords, location, max_results)

        if jobs:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_jobs_{timestamp}.md"
            filepath = scraper.save_to_markdown(jobs, filename)
            print(f"\n[✓] Successfully scraped {len(jobs)} jobs!")
            print(f"[✓] Results saved to: {filepath}")
        else:
            print("\n[!] No jobs were scraped.")
            print("[!] LinkedIn may have changed their page structure.")
            print("[!] Check debug_*.html files in the directory for troubleshooting.")
            print("[!] Tips:")
            print("    - Try manual login (the browser should stay open)")
            print("    - Use different search terms")
            print("    - Increase scroll_pause in the script")
            print("    - Check linkedin_scraper.log for details")

    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n[!] Error: {e}")
    finally:
        scraper.close()
        print("\nDone.")


if __name__ == "__main__":
    if not os.path.exists('.env.template'):
        create_env_template()
    main()
