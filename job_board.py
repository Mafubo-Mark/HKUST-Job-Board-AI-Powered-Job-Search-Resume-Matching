"""HKUST browser login, filters, and job export in one module.

Use with main.py for the complete resume-matching workflow. All original
function names, filter limits, timeouts, retries, and export fields are retained.
Importing this module does not launch Chrome or perform network requests.
OUTPUT_FILE retains the original default; main.py sets it beside the project.
"""

from datetime import date, datetime
from pathlib import Path
import json
import re
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


TARGET_URL = 'https://career.hkust.edu.hk/web/job.php?keywords='
MAX_BUSINESS_NATURES = 10
MAX_JOB_NATURES = 10
MAX_EMPLOYMENT_TYPES = 5
MAX_WORKING_LOCATIONS = 5
MAX_QUALIFICATION_LEVELS = 3
MAX_EMPLOYMENT_MODES = 2
MAX_LANGUAGES = 6
OUTPUT_FILE = Path('/Users/mafubo/Desktop/All Files/其他/hkust_job_project/hkust_jobs.json')
PAGE_WAIT_TIMEOUT = 30
SCRIPT_TIMEOUT = 300
MAX_FETCH_RETRIES = 3


def create_driver():
    """Open a maximized Chrome browser and return its Selenium driver."""
    options = Options()
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(options=options)
    return driver


def final_job_board_loaded(driver):
    """Return whether the real job list is visible after login and declarations."""
    try:
        job_lists = driver.find_elements(By.CSS_SELECTOR, '#job-list')
        return len(job_lists) > 0 and job_lists[0].is_displayed()
    except Exception:
        return False


def login_to_hkust(driver):
    """Open HKUST and wait up to 300 seconds for manual login and both agreements."""
    print('Opening the HKUST Career website...')
    driver.get(TARGET_URL)
    print()
    print('Please complete the following steps in the browser:')
    print()
    print('1. Log in to HKUST')
    print('2. Tick the checkbox')
    print('3. Click the first Agree button')
    print('4. Enter the Job Board Declaration page')
    print('5. Click the second Agree button')
    print()
    print('The program is waiting for the actual Job Board to load...')
    WebDriverWait(driver, 300, poll_frequency=1).until(final_job_board_loaded)
    print()
    print('=' * 70)
    print('Successfully entered the actual Job Board')
    print('=' * 70)
    print()
    print('Current URL:')
    print(driver.current_url)
    time.sleep(1)
    return True


def get_select_options(driver, select_name):
    """Read selectable values and labels, excluding empty values and Clear All."""
    select_element = driver.find_element(By.NAME, select_name)
    option_elements = select_element.find_elements(By.TAG_NAME, 'option')
    result = []
    for option in option_elements:
        value = option.get_attribute('value')
        text = option.text.strip()
        if not value:
            continue
        if 'Clear All' in text:
            continue
        result.append({'value': value, 'name': text})
    return result


def choose_multiple_options(options, title, max_choices):
    """Prompt, validate, deduplicate, and confirm choices; Enter skips the filter."""
    print()
    print('=' * 70)
    print(title)
    print('=' * 70)
    print()
    print(f'Please select up to {max_choices} options:')
    print()
    for index, item in enumerate(options, start=1):
        print(f"{index}. {item['name']}")
    print()
    print('-' * 70)
    while True:
        user_input = input('\nEnter the option numbers separated by commas; press Enter to skip: ').strip()
        if user_input == '':
            print()
            print(f'Skipped {title}')
            return []
        try:
            numbers = [int(x.strip()) for x in user_input.split(',') if x.strip()]
        except ValueError:
            print()
            print('Invalid input format.')
            print('Example: 1,3,5')
            continue
        numbers = list(dict.fromkeys(numbers))
        if len(numbers) > max_choices:
            print()
            print(f'You can select at most {max_choices} options.')
            continue
        invalid_numbers = [number for number in numbers if number < 1 or number > len(options)]
        if invalid_numbers:
            print()
            print('The following option numbers do not exist:', invalid_numbers)
            continue
        selected = [options[number - 1] for number in numbers]
        print()
        print('You selected:')
        print()
        for item in selected:
            print(f"✓ {item['name']}")
        confirm = input('\nConfirm these selections? (y/n): ').strip().lower()
        if confirm == 'y':
            return selected
        print()
        print('Please select again.')


def choose_business_natures(driver):
    """Ask the user to choose business natures within the configured selection limit."""
    options = get_select_options(driver, 'BN[]')
    return choose_multiple_options(options, 'Business Nature Filter', MAX_BUSINESS_NATURES)


def choose_job_natures(driver):
    """Ask the user to choose job natures within the configured selection limit."""
    options = get_select_options(driver, 'JN[]')
    return choose_multiple_options(options, 'Job Nature Filter', MAX_JOB_NATURES)


def choose_employment_types(driver):
    """Ask the user to choose employment types within the configured selection limit."""
    options = get_select_options(driver, 'EMT[]')
    return choose_multiple_options(options, 'Employment Type Filter', MAX_EMPLOYMENT_TYPES)


def choose_working_locations(driver):
    """Ask the user to choose working locations within the configured selection limit."""
    options = get_select_options(driver, 'WL[]')
    return choose_multiple_options(options, 'Working Location Filter', MAX_WORKING_LOCATIONS)


def choose_qualification_levels(driver):
    """Ask the user to choose qualification levels within the configured selection limit."""
    options = get_select_options(driver, 'awards[]')
    return choose_multiple_options(options, 'Levels of Qualification Filter', MAX_QUALIFICATION_LEVELS)


def choose_employment_modes(driver):
    """Ask the user to choose employment modes within the configured selection limit."""
    options = get_select_options(driver, 'EM[]')
    return choose_multiple_options(options, 'Employment Mode Filter', MAX_EMPLOYMENT_MODES)


def choose_languages(driver):
    """Ask the user to choose languages within the configured selection limit."""
    options = get_select_options(driver, 'L[]')
    return choose_multiple_options(options, 'Language Filter', MAX_LANGUAGES)


def apply_select_values(driver, select_name, selected):
    """Set a hidden Select2 field and trigger change; skipped filters stay unchanged."""
    if not selected:
        return
    values = [item['value'] for item in selected]
    select_element = driver.find_element(By.NAME, select_name)
    driver.execute_script(r"""
        const select = arguments[0];
        const selectedValues = arguments[1];
        for (const option of select.options) {
            option.selected = selectedValues.includes(option.value);
        }
        if (window.jQuery) {
            $(select).trigger('change');
        } else {
            select.dispatchEvent(new Event('change', {bubbles: true}));
        }
        """, select_element, values)


def apply_business_natures(driver, selected):
    """Apply the selected business natures to the matching webpage filter."""
    apply_select_values(driver, 'BN[]', selected)


def apply_job_natures(driver, selected):
    """Apply the selected job natures to the matching webpage filter."""
    apply_select_values(driver, 'JN[]', selected)


def apply_employment_types(driver, selected):
    """Apply the selected employment types to the matching webpage filter."""
    apply_select_values(driver, 'EMT[]', selected)


def apply_working_locations(driver, selected):
    """Apply the selected working locations to the matching webpage filter."""
    apply_select_values(driver, 'WL[]', selected)


def apply_qualification_levels(driver, selected):
    """Apply the selected qualification levels to the matching webpage filter."""
    apply_select_values(driver, 'awards[]', selected)


def apply_employment_modes(driver, selected):
    """Apply the selected employment modes to the matching webpage filter."""
    apply_select_values(driver, 'EM[]', selected)


def apply_languages(driver, selected):
    """Apply the selected languages to the matching webpage filter."""
    apply_select_values(driver, 'L[]', selected)


def submit_filter(driver):
    """Submit the search and allow the job list to refresh, tolerating wait timeouts."""
    print()
    print('=' * 70)
    print('Searching according to all selected filters...')
    print('=' * 70)
    try:
        old_table = driver.find_element(By.ID, 'job-list')
    except Exception:
        old_table = None
    search_button = driver.find_element(By.CSS_SELECTOR, "#job_search_form button[type='submit']")
    search_button.click()
    if old_table:
        try:
            WebDriverWait(driver, 15).until(EC.staleness_of(old_table))
        except TimeoutException:
            pass
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, 'job-list')))
    except TimeoutException:
        pass
    time.sleep(2)


def get_jobs(driver):
    """Return the job rows currently displayed on the result page."""
    return driver.find_elements(By.CSS_SELECTOR, '#job-list tbody tr.job-item')


def print_jobs(job_rows):
    """Print readable job summaries, skipping short rows and reporting unreadable rows."""
    print()
    print('=' * 70)
    print(f'Found {len(job_rows)} matching jobs on the current page')
    print('=' * 70)
    if not job_rows:
        print()
        print('No matching jobs were found.')
        return
    for index, row in enumerate(job_rows, start=1):
        try:
            columns = row.find_elements(By.CSS_SELECTOR, 'td.detail-text.large-view')
            if len(columns) < 2:
                continue
            company = columns[0].text.strip()
            title_lines = columns[1].text.strip().splitlines()
            if len(title_lines) >= 1:
                title = title_lines[0]
            else:
                title = 'Unknown'
            if len(title_lines) >= 2:
                job_nature = title_lines[1]
            else:
                job_nature = ''
            if len(columns) >= 3:
                posting_date = columns[2].text.strip()
            else:
                posting_date = ''
            if len(columns) >= 4:
                deadline = columns[3].text.strip()
            else:
                deadline = ''
            try:
                detail_link = row.find_element(By.CSS_SELECTOR, 'td.detail-text.large-view a.job-post')
                job_url = detail_link.get_attribute('href')
            except Exception:
                job_url = ''
            print()
            print(f'{index}. {title}')
            print(f'   Company: {company}')
            if job_nature:
                print(f'   Job Nature: {job_nature}')
            if posting_date:
                print(f'   Posting Date: {posting_date}')
            if deadline:
                print(f'   Deadline: {deadline}')
            if job_url:
                print(f'   URL: {job_url}')
        except Exception as e:
            print()
            print(f'{index}. Unable to read job: {e}')


def clean_one_line(text):
    """Collapse whitespace into single spaces and remove leading/trailing whitespace."""
    return ' '.join((text or '').split())


def clean_lines(text):
    """Normalize each text line and discard blank lines."""
    result = []
    for raw_line in (text or '').splitlines():
        line = clean_one_line(raw_line)
        if line:
            result.append(line)
    return result


def parse_deadline(text):
    """Find a date in six supported formats; return a date object or None."""
    text = clean_one_line(text)
    if not text:
        return None
    formats = [
        ('\\b\\d{4}-\\d{1,2}-\\d{1,2}\\b', '%Y-%m-%d'),
        ('\\b\\d{4}/\\d{1,2}/\\d{1,2}\\b', '%Y/%m/%d'),
        ('\\b\\d{1,2}/\\d{1,2}/\\d{4}\\b', '%d/%m/%Y'),
        ('\\b\\d{1,2}-\\d{1,2}-\\d{4}\\b', '%d-%m-%Y'),
        ('\\b\\d{1,2}\\s+[A-Za-z]{3}\\s+\\d{4}\\b', '%d %b %Y'),
        ('\\b\\d{1,2}\\s+[A-Za-z]+\\s+\\d{4}\\b', '%d %B %Y'),
    ]
    for pattern, fmt in formats:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(0), fmt).date()
        except ValueError:
            continue
    return None


def get_deadline_status(text):
    """Classify deadlines as valid, expired, or unknown; today is still valid."""
    text = clean_one_line(text)
    lower = text.lower()
    if 'expired' in lower or 'closed' in lower:
        return 'expired'
    if 'until filled' in lower or 'open until filled' in lower:
        return 'valid'
    deadline = parse_deadline(text)
    if deadline is None:
        return 'unknown'
    if deadline < date.today():
        return 'expired'
    return 'valid'


def extract_current_page_jobs(driver):
    """Read company, title, posting date, deadline, and URL from visible job rows."""
    return driver.execute_script(r"""
        const rows = Array.from(document.querySelectorAll("#job-list tbody tr.job-item"));
        
        // Normalize whitespace in one cell or title line.
        function clean(value) {
            return (value || "").replace(/\s+/g, " ").trim();
        }
        const jobs = [];
        for (const row of rows) {
            const columns = Array.from(row.querySelectorAll("td.detail-text.large-view"));
            const link = row.querySelector("td.detail-text.large-view a.job-post");
            if (columns.length < 4 || !link) {
                continue;
            }
            const titleLines = (columns[1].innerText || "")
                .split(/\r?\n/).map(clean).filter(Boolean);
            jobs.push({
                company: clean(columns[0].innerText),
                job_title_nature: titleLines.join(" / "),
                posting_date: clean(columns[2].innerText),
                application_deadline: clean(columns[3].innerText),
                url: link.href
            });
        }
        return jobs;
        """) or []


def get_first_job_url(driver):
    """Read the first job URL to detect page changes; return an empty string on failure."""
    try:
        return driver.execute_script(r"""
        const link = document.querySelector("#job-list tbody " + "tr.job-item a.job-post");
        return link ? link.href : "";
        """) or ''
    except Exception:
        return ''


def browser_fetch_details(driver, jobs):
    """Fetch one page of job details concurrently using the logged-in browser session."""
    if not jobs:
        return []
    urls = [job['url'] for job in jobs]
    driver.set_script_timeout(SCRIPT_TIMEOUT)
    return driver.execute_async_script(r"""
        const urls = arguments[0];
        const done = arguments[arguments.length - 1];
        
        // Fetch one authenticated detail page and return plain text or an error.
        async function readOne(url) {
            try {
                const response = await fetch(url, {
                    method: "GET", credentials: "include", cache: "no-store", redirect: "follow"
                });
                const html = await response.text();
                if (!response.ok) {
                    return {ok: false, url: url, error: "HTTP " + response.status};
                }
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, "text/html");
                doc.querySelectorAll("script,style,noscript,svg").forEach(element => element.remove());
                const text = doc.body ? doc.body.textContent || "" : "";
                return {ok: true, url: url, text: text};
            } catch (error) {
                return {ok: false, url: url, error: String(error)};
            }
        }
        Promise.all(urls.map(readOne)).then(done).catch(error => {
            done(urls.map(url => ({ok: false, url: url, error: String(error)})));
        });
        """, urls) or []


def fetch_details_with_retries(driver, jobs):
    """Retry missing, empty, or failed details; return success and error maps by URL."""
    pending = {job['url']: job for job in jobs}
    successful = {}
    errors = {}
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        if not pending:
            break
        batch = list(pending.values())
        response_items = browser_fetch_details(driver, batch)
        next_pending = {}
        returned_urls = set()
        for item in response_items:
            url = item.get('url', '')
            if not url:
                continue
            returned_urls.add(url)
            if item.get('ok'):
                text = item.get('text', '') or ''
                if clean_one_line(text):
                    successful[url] = text
                    errors.pop(url, None)
                else:
                    next_pending[url] = pending[url]
                    errors[url] = 'Empty detail page.'
            else:
                if url in pending:
                    next_pending[url] = pending[url]
                errors[url] = item.get('error', 'Unknown fetch error')
        for url, job in pending.items():
            if url not in returned_urls and url not in successful:
                next_pending[url] = job
                errors[url] = 'No response returned.'
        pending = next_pending
        if pending and attempt < MAX_FETCH_RETRIES:
            time.sleep(0.5)
    return (successful, errors)


def extract_deadline_from_detail(text):
    """Find the deadline beside its label or within the following four lines."""
    lines = clean_lines(text)
    for index, line in enumerate(lines):
        lower = line.lower()
        if lower.rstrip(':') == 'application deadline':
            if index + 1 < len(lines):
                return lines[index + 1]
        if lower.startswith('application deadline:'):
            return clean_one_line(line.split(':', 1)[1])
    for index, line in enumerate(lines):
        if 'application deadline' in line.lower():
            nearby = lines[index:min(index + 5, len(lines))]
            for candidate in nearby:
                if parse_deadline(candidate):
                    return candidate
    return ''


def build_job_json(job, detail_text):
    """Build the four export fields, trimming headers and retaining the posting date."""
    lines = clean_lines(detail_text)
    deadline = clean_one_line(job.get('application_deadline', ''))
    deadline_index = -1
    if deadline:
        for index, line in enumerate(lines):
            if clean_one_line(line) == deadline:
                deadline_index = index
                break
    if deadline_index >= 0:
        remaining_lines = lines[deadline_index + 1:]
    else:
        remaining_lines = lines
    other_parts = []
    posting_date = clean_one_line(job.get('posting_date', ''))
    if posting_date:
        other_parts.append(f'Posting Date: {posting_date}')
    other_parts.extend(remaining_lines)
    return {
        'Company/Organization': job.get('company', ''),
        'Job Title/Job Nature': job.get('job_title_nature', ''),
        'Application Deadline': job.get('application_deadline', ''),
        'Other information': ' | '.join(other_parts),
    }


def save_json(results):
    """Create the output directory and overwrite OUTPUT_FILE with readable UTF-8 JSON."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open('w', encoding='utf-8') as file:
        json.dump(results, file, ensure_ascii=False, indent=2)


def process_current_page(driver, page_number, seen_urls):
    """Deduplicate URLs, skip expired jobs, verify unknown deadlines, and fetch details."""
    jobs = extract_current_page_jobs(driver)
    unique_jobs = []
    for job in jobs:
        url = job.get('url', '')
        if not url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        unique_jobs.append(job)
    print(f'Page {page_number}: {len(unique_jobs)} jobs found')
    valid_jobs = []
    unknown_jobs = []
    expired_count = 0
    for job in unique_jobs:
        deadline = job.get('application_deadline', '')
        status = get_deadline_status(deadline)
        if status == 'expired':
            expired_count += 1
            continue
        if status == 'valid':
            valid_jobs.append(job)
        else:
            unknown_jobs.append(job)
    print(f'  Deadline OK: {len(valid_jobs)}')
    print(f'  Expired skipped: {expired_count}')
    if unknown_jobs:
        print(f'  Deadline needs verification: {len(unknown_jobs)}')
    candidates = valid_jobs + unknown_jobs
    if not candidates:
        print('  Nothing to write.')
        return []
    successful, errors = fetch_details_with_retries(driver, candidates)
    page_results = []
    for job in valid_jobs:
        url = job['url']
        if url in successful:
            result = build_job_json(job, successful[url])
        else:
            result = {
                'Company/Organization': job.get('company', ''),
                'Job Title/Job Nature': job.get('job_title_nature', ''),
                'Application Deadline': job.get('application_deadline', ''),
                'Other information': 'ERROR while reading job details: ' + errors.get(url, 'Unknown error'),
            }
        page_results.append(result)
    for job in unknown_jobs:
        url = job['url']
        if url not in successful:
            continue
        detail_text = successful[url]
        detail_deadline = extract_deadline_from_detail(detail_text)
        if detail_deadline:
            job['application_deadline'] = detail_deadline
        status = get_deadline_status(job.get('application_deadline', ''))
        if status != 'valid':
            continue
        page_results.append(build_job_json(job, detail_text))
    print(f'  Written from this page: {len(page_results)}')
    return page_results


def click_next_page(driver, current_page_number):
    """Try next controls, numeric links, and nearby buttons; wait for the page to change."""
    old_first_url = get_first_job_url(driver)
    old_browser_url = driver.current_url
    expected_next_number = current_page_number + 1
    result = driver.execute_script(r"""
        const expectedPage = String(arguments[0]);
        const table = document.querySelector("#job-list");
        
        // Check that a control is displayed and has a nonzero size.
        function visible(element) {
            if (!element) {
                return false;
            }
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return (style.display !== "none" && style.visibility !== "hidden"
                && rect.width > 0 && rect.height > 0);
        }
        
        // Check the control and its two nearest ancestors for disabled markers.
        function disabled(element) {
            if (!element) {
                return true;
            }
            let node = element;
            for (let i = 0; i < 3 && node; i++) {
                const classes = (node.className || "").toString().toLowerCase();
                const aria = (node.getAttribute ? node.getAttribute("aria-disabled") : "") || "";
                if (classes.includes("disabled") || aria.toLowerCase() === "true") {
                    return true;
                }
                node = node.parentElement;
            }
            return false;
        }
        
        // Resolve a wrapper element to an actual link or button.
        function actualClickable(element) {
            if (!element) {
                return null;
            }
            if (element.matches("a, button")) {
                return element;
            }
            return element.querySelector("a, button");
        }
        
        // Click only a visible, enabled link or button and report success.
        function tryClick(element) {
            if (!element) {
                return false;
            }
            let target = actualClickable(element);
            if (!target) {
                return false;
            }
            if (!visible(target) || disabled(target)) {
                return false;
            }
            target.click();
            return true;
        }
        
        // Prefer explicit next-page controls.
        const directSelectors = [
            "#job-list_next", "#job-list_next a",
            "#job-list_paginate .next", "#job-list_paginate .next a",
            ".dataTables_paginate .next", ".dataTables_paginate .next a",
            "ul.pagination li.next", "ul.pagination li.next a",
            ".pagination .next", ".pagination .next a", "a[rel='next']",
            "button[aria-label*='next' i]", "a[aria-label*='next' i]"
        ];
        for (const selector of directSelectors) {
            for (const element of document.querySelectorAll(selector)) {
                if (tryClick(element)) {
                    return {
                        clicked: true, method: "next-selector",
                        text: (element.innerText || "").trim()
                    };
                }
            }
        }
        
        // Gather visible pagination containers once, preserving their order.
        const containers = [];
        const containerSelectors = [
            "#job-list_paginate", ".dataTables_paginate", "ul.pagination",
            ".pagination", "nav[aria-label*='pagination' i]"
        ];
        for (const selector of containerSelectors) {
            for (const container of document.querySelectorAll(selector)) {
                if (visible(container) && !containers.includes(container)) {
                    containers.push(container);
                }
            }
        }
        
        // Try Next labels and arrow symbols inside those containers.
        for (const container of containers) {
            const elements = container.querySelectorAll("a,button");
            for (const element of elements) {
                const text = (element.innerText || "").trim().toLowerCase();
                const aria = (element.getAttribute("aria-label") || "").trim().toLowerCase();
                const title = (element.getAttribute("title") || "").trim().toLowerCase();
                const isNext = (text === "next" || text === "›" || text === "»"
                    || text === ">" || text === ">>" || aria.includes("next") || title.includes("next"));
                if (isNext && tryClick(element)) {
                    return {clicked: true, method: "pagination-next", text: text};
                }
            }
        }
        
        // Fall back to the expected next page number.
        for (const container of containers) {
            const elements = container.querySelectorAll("a,button");
            for (const element of elements) {
                const text = (element.innerText || "").trim();
                if (text === expectedPage && tryClick(element)) {
                    return {clicked: true, method: "numeric-pagination", text: text};
                }
            }
        }
        
        // Last fallback: inspect visible controls immediately below the job table.
        if (table) {
            const tableRect = table.getBoundingClientRect();
            const elements = Array.from(document.querySelectorAll("a,button"));
            for (const element of elements) {
                if (!visible(element)) {
                    continue;
                }
                const rect = element.getBoundingClientRect();
                const belowTable = (rect.top >= tableRect.bottom - 50 && rect.top <= tableRect.bottom + 500);
                if (!belowTable) {
                    continue;
                }
                const text = (element.innerText || "").trim();
                const lower = text.toLowerCase();
                const aria = (element.getAttribute("aria-label") || "").toLowerCase();
                const nextLike = (lower === "next" || text === "›" || text === "»"
                    || text === ">" || text === ">>" || text === expectedPage || aria.includes("next"));
                if (nextLike && tryClick(element)) {
                    return {clicked: true, method: "below-table", text: text};
                }
            }
        }
        return {clicked: false, method: "none", text: ""};
        """, expected_next_number)
    if not result:
        return False
    if not result.get('clicked'):
        return False
    try:
        WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
            lambda d: (get_first_job_url(d) and get_first_job_url(d) != old_first_url)
            or d.current_url != old_browser_url
        )
    except TimeoutException:
        time.sleep(0.5)
        new_first_url = get_first_job_url(driver)
        if not new_first_url or new_first_url == old_first_url:
            return False
    time.sleep(0.2)
    return True


def get_visible_pagination_text(driver):
    """Collect unique pagination labels for diagnostics; return [] on failure."""
    try:
        return driver.execute_script(r"""
        const selectors = [
            "#job-list_paginate", ".dataTables_paginate", "ul.pagination",
            ".pagination", "nav[aria-label*='pagination' i]"
        ];
        const result = [];
        for (const selector of selectors) {
            for (const element of document.querySelectorAll(selector)) {
                const text = (element.innerText || "").replace(/\s+/g, " ").trim();
                if (text && !result.includes(text)) {
                    result.push(text);
                }
            }
        }
        return result;
        """) or []
    except Exception:
        return []


def export_jobs_to_json(driver):
    """Export all reachable pages, saving each page immediately, and return the records."""
    start_time = time.perf_counter()
    WebDriverWait(driver, 60).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, '#job-list tbody tr.job-item')) > 0
    )
    print()
    print('=' * 70)
    print('Processing ALL filtered Job Board pages')
    print('=' * 70)
    print()
    print(f"Today's date: {date.today().isoformat()}")
    print()
    all_results = []
    seen_urls = set()
    page_number = 1
    save_json(all_results)
    while True:
        print('=' * 70)
        print(f'Processing page {page_number}')
        print('=' * 70)
        page_results = process_current_page(driver, page_number, seen_urls)
        all_results.extend(page_results)
        save_json(all_results)
        print(f'  JSON total so far: {len(all_results)}')
        print()
        moved = click_next_page(driver, page_number)
        if not moved:
            print('No further Job Board page found.')
            pagination_text = get_visible_pagination_text(driver)
            if pagination_text:
                print('Visible pagination controls:')
                for text in pagination_text:
                    print(f'  {text}')
            break
        page_number += 1
    elapsed = time.perf_counter() - start_time
    print()
    print('=' * 70)
    print('Export completed')
    print('=' * 70)
    print()
    print(f'Pages processed: {page_number}')
    print(f'Unique jobs checked: {len(seen_urls)}')
    print(f'Jobs written to JSON: {len(all_results)}')
    print()
    print('JSON file location:')
    print(OUTPUT_FILE)
    print()
    print(f'Total processing time: {elapsed:.2f} seconds')
    print()
    return all_results


def print_first_two_pages_job_details(driver):
    """Keep the legacy entry point; export every reachable page, not just two."""
    return export_jobs_to_json(driver)
