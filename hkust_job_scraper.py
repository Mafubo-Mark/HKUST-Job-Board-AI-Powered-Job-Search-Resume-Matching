"""Log in manually, filter HKUST jobs, and export all unexpired results.

Install: python3 -m pip install selenium
Run:     python3 hkust_job_scraper.py [--output /path/to/hkust_jobs.json]
Requires Google Chrome. Login and declaration acceptance happen in the browser.

Workflow: main -> login_to_hkust -> filter_jobs -> export_jobs_to_json.
Python manages the workflow and saves data; Selenium controls Chrome;
JavaScript reads the page and downloads job details inside the logged-in browser.
"""

# Standard-library tools: these come with Python and need no separate install.
import argparse  # Read command-line options such as --output.
import json  # Convert Python dictionaries and lists into a JSON file.
import re  # Find date patterns using regular expressions (text-matching rules).
import time  # Pause briefly between requests and measure elapsed time.
from contextlib import closing  # Close a download generator if saving is interrupted.
from datetime import date, datetime  # Parse dates and compare deadlines with today.
from pathlib import Path  # Build file paths and create/read/write files.

# Selenium is the external package that sends browser commands to Chrome.
from selenium import webdriver
from selenium.common.exceptions import TimeoutException  # Handle waits that expire.
from selenium.webdriver.common.by import By  # Locate elements by ID, name, or CSS.
from selenium.webdriver.support import expected_conditions as EC  # Ready-made wait checks.
from selenium.webdriver.support.ui import WebDriverWait  # Poll until a condition is true.

# Configuration: change these values to adjust destinations, waits, or limits.
TARGET_URL = "https://career.hkust.edu.hk/web/job.php?keywords="
# __file__ is this script's path; with_name places the JSON in the same folder.
OUTPUT_FILE = Path(__file__).with_name("hkust_jobs.json")
# Timeouts are in seconds; MAX_FETCH_RETRIES is the total number of attempts.
PAGE_WAIT_TIMEOUT, SCRIPT_TIMEOUT, MAX_FETCH_RETRIES = 30, 10, 3
# Up to eight downloads run together. Each gets 60 seconds per attempt;
# short result polls return completed jobs while slow downloads keep running.
FETCH_WORKERS, REQUEST_TIMEOUT = 8, 60
# Each tuple stores (HTML select name, terminal label, maximum selections).
# One shared loop uses this table instead of seven nearly identical functions.
FILTERS = (
    ("BN[]", "Business Nature", 15),
    ("JN[]", "Job Nature", 10),
    ("EMT[]", "Employment Type", 5),
    ("WL[]", "Working Location", 5),
    ("awards[]", "Levels of Qualification", 3),
    ("EM[]", "Employment Mode", 2),
    ("L[]", "Language", 6),
)
# CSS selectors describe possible page-navigation containers in the HTML.
# '#' means an element ID, '.' a class, and commas separate alternatives.
PAGINATION = (
    "#job-list_paginate, .dataTables_paginate, ul.pagination, "
    ".pagination, nav[aria-label*='pagination' i]"
)


def clean_one_line(text):
    # Collapse spaces, tabs, and newlines using split/join; None becomes empty text.
    return " ".join((text or "").split())


def clean_lines(text):
    # Split into lines, clean each with map(), and remove empty lines with filter().
    return list(filter(None, map(clean_one_line, (text or "").splitlines())))


def create_driver():
    # Start a Selenium-controlled Chrome window; return its control object (driver).
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)


def login_to_hkust(driver):
    # Open the site and let you complete authentication and declarations yourself.
    driver.get(TARGET_URL)
    print("Log in, tick the checkbox, and accept both declarations in Chrome.\n"
          "Waiting up to 5 minutes for the Job Board...")
    # Poll once per second for a visible job table, instead of guessing login time.
    WebDriverWait(driver, 300, poll_frequency=1).until(
        EC.visibility_of_element_located((By.ID, "job-list"))
    )
    print(f"Job Board ready: {driver.current_url}")


def choose_multiple_options(options, title, max_choices):
    # Reusable terminal menu: return selected option dictionaries after confirmation.
    print(f"\n{title} — select up to {max_choices}:")
    # enumerate(..., 1) gives user-friendly numbering starting at 1.
    for index, item in enumerate(options, 1):
        print(f"{index}. {item['name']}")
    while True:
        # Keep asking until the user confirms valid input or skips with Enter.
        answer = input("Numbers separated by commas (Enter to skip): ").strip()
        if not answer:
            return []
        try:
            # Split comma-separated numbers; dict.fromkeys removes duplicates
            # while preserving input order. int() rejects non-numeric entries.
            numbers = list(dict.fromkeys(int(n.strip()) for n in answer.split(",")
                                         if n.strip()))
            # Enforce both the filter limit and the available option-number range.
            if not numbers or len(numbers) > max_choices:
                raise ValueError
            if any(n < 1 or n > len(options) for n in numbers):
                raise ValueError
        except ValueError:
            print(f"Enter 1–{max_choices} valid option numbers, e.g. 1,3,5.")
            continue
        # Python lists start at 0, so menu number 1 maps to options[0].
        selected = [options[n - 1] for n in numbers]
        print("Selected: " + ", ".join(item["name"] for item in selected))
        if input("Confirm? (y/n): ").strip().lower() == "y":
            return selected


def filter_jobs(driver):
    # Read each site's dropdown, ask for choices, then apply all filters and search.
    for name, title, limit in FILTERS:
        # Selenium reads the underlying <select> and its <option> elements.
        # Ignore placeholder and Clear All entries, which are not actual filters.
        select = driver.find_element(By.NAME, name)
        # One browser call reads the whole menu instead of several calls per option.
        options = driver.execute_script("""
            return [...arguments[0].options]
                .filter(o => o.value && !o.text.includes('Clear All'))
                .map(o => ({value: o.value, name: o.text.trim()}));
        """, select)
        selected = choose_multiple_options(options, title, limit)
        if selected:
            # Select2 hides the native dropdown, so update it with JavaScript.
            # execute_script passes Python values through JavaScript's arguments.
            driver.execute_script("""
                const [select, values] = arguments;
                for (const option of select.options)
                    option.selected = values.includes(option.value);
                // Notify the site's Select2/jQuery handlers that choices changed.
                // A native DOM event is the fallback if jQuery is unavailable.
                if (window.jQuery) window.jQuery(select).trigger('change');
                else select.dispatchEvent(new Event('change', {bubbles: true}));
            """, select, [item["value"] for item in selected])
    # Submit the form, keeping the old table reference to detect page replacement.
    old_table = driver.find_element(By.ID, "job-list")
    driver.find_element(By.CSS_SELECTOR, "#job_search_form button[type='submit']").click()
    try:
        # 'Stale' means the old HTML element is no longer attached to the page.
        WebDriverWait(driver, 15).until(EC.staleness_of(old_table))
    except TimeoutException:
        pass  # Some searches update the table without replacing it.
    WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
        EC.visibility_of_element_located((By.ID, "job-list"))
    )
    time.sleep(2)  # Give in-place table updates a short additional settling time.


def parse_deadline(text):
    # Return a Python date, or None if no supported, valid date can be found.
    # Each pair combines a regex to locate text with a strptime format to parse it.
    formats = (
        (r"\b\d{4}-\d{1,2}-\d{1,2}\b", "%Y-%m-%d"),
        (r"\b\d{4}/\d{1,2}/\d{1,2}\b", "%Y/%m/%d"),
        (r"\b\d{1,2}/\d{1,2}/\d{4}\b", "%d/%m/%Y"),
        (r"\b\d{1,2}-\d{1,2}-\d{4}\b", "%d-%m-%Y"),
        (r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b", "%d %b %Y"),
        (r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", "%d %B %Y"),
    )
    for pattern, fmt in formats:
        match = re.search(pattern, clean_one_line(text))
        if match:
            try:
                # strptime also rejects impossible dates, such as 30 February.
                return datetime.strptime(match[0], fmt).date()
            except ValueError:
                pass
    return None


def get_deadline_status(text):
    # Classify by status words first, then by date. Today's deadlines remain valid.
    # date.today() uses the computer's local date; unknown dates need detail lookup.
    lower = clean_one_line(text).lower()
    if "expired" in lower or "closed" in lower:
        return "expired"
    if "until filled" in lower:
        return "valid"
    deadline = parse_deadline(text)
    return "unknown" if deadline is None else "expired" if deadline < date.today() else "valid"


def extract_current_page_jobs(driver):
    # Read this page in one browser call. JavaScript examines the DOM (HTML tree)
    # and Selenium converts the returned objects into Python lists/dictionaries.
    return driver.execute_script(r"""
        const clean = s => (s || '').replace(/\s+/g, ' ').trim();
        // CSS finds job rows; a layout rectangle excludes display:none rows.
        return [...document.querySelectorAll('#job-list tbody tr.job-item')]
            .filter(row => row.getClientRects().length)
            .flatMap(row => {
                // Desktop columns: company, title/nature, posting date, deadline.
                const c = row.querySelectorAll('td.detail-text.large-view');
                const link = row.querySelector('td.detail-text.large-view a.job-post');
                if (c.length < 4 || !link) return []; // Skip incomplete rows.
                // flatMap merges these one-job arrays; empty arrays add nothing.
                return [{company: clean(c[0].innerText),
                    job_title_nature: c[1].innerText.split(/\r?\n/)
                        .map(clean).filter(Boolean).join(' / '),
                    posting_date: clean(c[2].innerText),
                    application_deadline: clean(c[3].innerText), url: link.href}];
            });
    """) or []


def browser_fetch_details(driver, jobs):
    # Yield completed batches while a browser-side worker pool downloads details.
    # Each worker retries its own failures immediately; other workers keep going.
    if not jobs:
        return
    key = f"hkust_export_{time.time_ns()}"
    driver.set_script_timeout(SCRIPT_TIMEOUT)
    driver.execute_script(r"""
        const [key, urls, workers, timeout, attempts] = arguments;
        const state = window[key] = {queue: [], remaining: urls.length,
            next: 0, stopped: false, controllers: new Set()};
        async function readOne(url) {
            // Keep the original retry count and request timeout to preserve slow jobs.
            for (let attempt = 1; attempt <= attempts && !state.stopped; attempt++) {
                const controller = new AbortController();
                state.controllers.add(controller);
                const timer = setTimeout(() => controller.abort(), timeout * 1000);
                let result;
                try {
                    // fetch uses the logged-in browser's cookies; no extra login needed.
                    const response = await fetch(url, {credentials: 'include',
                        cache: 'no-store', redirect: 'follow', signal: controller.signal});
                    if (!response.ok) throw new Error('HTTP ' + response.status);
                    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
                    doc.querySelectorAll('script,style,noscript,svg').forEach(e => e.remove());
                    // Normalize whitespace before sending text across the Selenium connection.
                    const text = (doc.body ? doc.body.textContent : '').split(/\r?\n/)
                        .map(s => s.replace(/\s+/g, ' ').trim()).filter(Boolean).join('\n');
                    if (!text) throw new Error('Empty detail page.');
                    result = {ok: true, url, text};
                } catch (error) {
                    result = {ok: false, url, error: String(error)};
                } finally {
                    clearTimeout(timer);
                    state.controllers.delete(controller);
                }
                if (result.ok || attempt === attempts) return result;
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        async function worker() {
            // JavaScript assigns each URL once; await lets other workers run meanwhile.
            while (!state.stopped && state.next < urls.length) {
                const result = await readOne(urls[state.next++]);
                if (state.stopped) return;
                state.queue.push(result);
                state.remaining--;
            }
        }
        // Start the pool and return immediately so Python can collect completed jobs.
        for (let i = 0; i < Math.min(workers, urls.length); i++) worker();
    """, key, [job["url"] for job in jobs], FETCH_WORKERS, REQUEST_TIMEOUT, MAX_FETCH_RETRIES)
    last_update = time.perf_counter()
    try:
        while True:
            # A short async callback batches completions, avoiding a busy Python loop.
            batch = driver.execute_async_script("""
                const state = window[arguments[0]], done = arguments[arguments.length - 1];
                if (!state) { done(null); return; }
                const send = () => done({items: state.queue.splice(0), remaining: state.remaining});
                if (state.remaining === 0) send();
                else setTimeout(send, 500);
            """, key)
            if batch is None:
                raise RuntimeError("The detail-fetch session was lost; saved results are retained.")
            if batch["items"]:
                last_update = time.perf_counter()
                yield batch["items"]
            elif time.perf_counter() - last_update >= 10:
                # Explain long server waits even when no request has finished yet.
                print(f"  Waiting for {batch['remaining']} detail downloads (including retries)...",
                      flush=True)
                last_update = time.perf_counter()
            if batch["remaining"] == 0:
                break
    finally:
        # Stop outstanding requests on interruption and remove this run's browser state.
        driver.execute_script("""
            const state = window[arguments[0]];
            if (state) {
                state.stopped = true;
                state.controllers.forEach(c => c.abort());
                delete window[arguments[0]];
            }
        """, key)


def extract_deadline_from_detail(text):
    # Recover a missing deadline by inspecting cleaned lines from the detail page.
    lines = clean_lines(text)
    # First support the label on its own line, or 'Application Deadline: value'.
    for index, line in enumerate(lines):
        lower = line.lower()
        if lower.rstrip(":") == "application deadline" and index + 1 < len(lines):
            return lines[index + 1]
        if lower.startswith("application deadline:"):
            return clean_one_line(line.split(":", 1)[1])
    # Fallback: search up to five lines near the label for a recognizable date.
    for index, line in enumerate(lines):
        if "application deadline" in line.lower():
            for candidate in lines[index:index + 5]:
                if parse_deadline(candidate):
                    return candidate
    return ""


def build_job_json(job, detail_text, error=None):
    # Combine listing data and detail text into the four original JSON fields.
    lines = clean_lines(detail_text)
    deadline = clean_one_line(job.get("application_deadline"))
    if deadline and deadline in lines:
        # Heuristic: omit header lines up through an exact match of the deadline.
        lines = lines[lines.index(deadline) + 1:]
    # Put the posting date and remaining detail lines into one readable text field.
    posting = clean_one_line(job.get("posting_date"))
    other = " | ".join(([f"Posting Date: {posting}"] if posting else []) + lines)
    # This is a Python dictionary; json.dumps later serializes it into JSON text.
    return {
        "Company/Organization": job.get("company", ""),
        "Job Title/Job Nature": job.get("job_title_nature", ""),
        "Application Deadline": job.get("application_deadline", ""),
        "Other information": f"ERROR while reading job details: {error}" if error else other,
    }


def process_current_page(driver, page_number, seen_urls, jobs=None, on_records=None):
    # Reuse already-read rows and deliver finished records to the save callback.
    # Output follows download completion order so one slow job cannot delay saving.
    groups = {"valid": [], "unknown": [], "expired": []}
    for job in extract_current_page_jobs(driver) if jobs is None else jobs:
        url = job.get("url")
        if url and url not in seen_urls:
            # A shared set remembers URLs across every page to prevent duplicates.
            seen_urls.add(url)
            groups[get_deadline_status(job.get("application_deadline"))].append(job)
    print(f"Page {page_number}: " + ", ".join(f"{len(v)} {k}" for k, v in groups.items()))
    # Skip expired listings before downloading; unknown deadlines need checking.
    candidates = groups["valid"] + groups["unknown"]
    by_url = {job["url"]: job for job in candidates}
    results, finished, failures = [], 0, 0
    started = time.perf_counter()
    # closing() guarantees cancellation if an exception occurs in the loop body.
    with closing(browser_fetch_details(driver, candidates)) as batches:
        for items in batches:
            records = []
            for item in items:
                job = by_url[item["url"]]
                text = item.get("text", "")
                failures += not item["ok"]
                if get_deadline_status(job.get("application_deadline")) == "unknown":
                    # Unknown deadlines still require successful detail verification.
                    job["application_deadline"] = extract_deadline_from_detail(text)
                    if get_deadline_status(job["application_deadline"]) != "valid":
                        continue
                # Retain valid listings even if fetching fails, with an error message.
                records.append(build_job_json(job, text, item.get("error")))
            if records and on_records:
                on_records(records)
            results.extend(records)
            finished += len(items)
            print(f"  Details {finished}/{len(candidates)}; {len(results)} records; "
                  f"{failures} failed; {time.perf_counter() - started:.1f}s", flush=True)
    return results


def get_page_urls(driver):
    # During pagination, read only links; avoid repeatedly extracting all cell text.
    return driver.execute_script("""
        return [...document.querySelectorAll('#job-list tbody tr.job-item')]
            .filter(row => row.getClientRects().length)
            .map(row => row.querySelector('td.detail-text.large-view a.job-post'))
            .filter(Boolean).map(link => link.href);
    """) or []


def click_next_page(driver, current_page_number, old_urls=None):
    # Find the next control using several HTML layouts, click it, and wait for new rows.
    # Save the current URLs so a URL change alone cannot falsely signal loaded jobs.
    if old_urls is None:
        old_urls = get_page_urls(driver)
    clicked = driver.execute_script("""
        const [expected, containersSelector] = arguments;
        // Use computed CSS and element geometry to exclude hidden controls.
        const visible = e => e && getComputedStyle(e).visibility !== 'hidden'
            && e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0;
        const disabled = e => {
            // Check the control and two ancestors: disabled styles may be on a <li>.
            for (let i = 0; e && i < 3; i++, e = e.parentElement)
                if (e.disabled || String(e.className).toLowerCase().includes('disabled')
                    || e.getAttribute('aria-disabled') === 'true') return true;
            return false;
        };
        const click = e => {
            // A container may wrap the actual link/button; click only usable targets.
            const target = e.matches('a,button') ? e : e.querySelector('a,button');
            if (!visible(target) || disabled(target)) return false;
            target.click();
            return true;
        };
        // Recognize next-page text, symbols, accessibility labels, and tooltips.
        const nextLike = e => ['next', '›', '»', '>', '>>'].includes(e.innerText.trim().toLowerCase())
            || /next/i.test((e.getAttribute('aria-label') || '') + ' ' + (e.title || ''));
        // Strategy 1: common Next selectors, including DataTables-style controls.
        const direct = "#job-list_next, #job-list_paginate .next, .dataTables_paginate .next, "
            + ".pagination .next, a[rel='next'], button[aria-label*='next' i], a[aria-label*='next' i]";
        if ([...document.querySelectorAll(direct)].some(click)) return true;
        // Strategy 2: inspect links/buttons inside known pagination containers.
        const controls = [...document.querySelectorAll(containersSelector)].filter(visible)
            .flatMap(c => [...c.querySelectorAll('a,button')]);
        if (controls.filter(nextLike).some(click)) return true;
        // Strategy 3: look for the next page number, such as '2' after page 1.
        if (controls.filter(e => e.innerText.trim() === String(expected)).some(click)) return true;
        // Strategy 4: use screen geometry to look for controls near the table bottom.
        const table = document.querySelector('#job-list');
        if (!table) return false;
        const bottom = table.getBoundingClientRect().bottom;
        return [...document.querySelectorAll('a,button')].filter(e => {
            const top = e.getBoundingClientRect().top;
            return visible(e) && top >= bottom - 50 && top <= bottom + 500
                && (nextLike(e) || e.innerText.trim() === String(expected));
        }).some(click);
    """, current_page_number + 1, PAGINATION)
    if not clicked:
        return False

    def rows_changed(browser):
        # Selenium repeatedly calls this local helper until a nonempty URL list changes.
        urls = get_page_urls(browser)
        return bool(urls) and urls != old_urls

    # A clicked control that never loads must not silently truncate the export.
    WebDriverWait(driver, PAGE_WAIT_TIMEOUT, poll_frequency=0.2).until(rows_changed)
    return True


def append_json(file, records):
    # Append only new records to a JSON array, replacing its closing bracket.
    # Binary mode makes seek offsets correct for both English and Chinese text.
    if not records:
        return
    data = json.dumps(records, ensure_ascii=False, indent=2)[2:-2].encode("utf-8")
    offset = file.seek(-3, 2)  # Start of the trailing newline + ']' + newline.
    try:
        file.write((b",\n" if offset > 1 else b"\n") + data + b"\n]\n")
        file.truncate()
        file.flush()  # Keep the file readable after every completed batch.
    except BaseException:
        # Roll back this batch on a write error or Ctrl+C, keeping prior JSON valid.
        file.seek(offset)
        file.write(b"\n]\n")
        file.truncate()
        file.flush()
        raise


def export_jobs_to_json(driver, output_file=OUTPUT_FILE):
    # Read each results table once and stream completed detail batches to JSON.
    output_file = Path(output_file)
    # pathlib creates missing destination folders, including any parent folders.
    output_file.parent.mkdir(parents=True, exist_ok=True)
    # Sets track duplicate jobs and repeated pages; the list holds JSON records.
    results, seen_urls, seen_pages = [], set(), set()
    page_number, started = 1, time.perf_counter()

    write_seconds = 0.0
    # Start a fresh JSON array, replacing an existing file at this destination.
    with output_file.open("w+b") as file:
        file.write(b"[\n]\n")
        file.flush()

        def save(records):
            # Serialize only the new batch; previous records are never rewritten.
            nonlocal write_seconds
            started_write = time.perf_counter()
            append_json(file, records)
            write_seconds += time.perf_counter() - started_write
            results.extend(records)

        while True:
            jobs = extract_current_page_jobs(driver)
            # An ordered tuple of URLs detects repeated pages without another browser call.
            signature = tuple(job["url"] for job in jobs)
            if signature in seen_pages:
                raise RuntimeError("Pagination repeated a page; results so far have been saved.")
            seen_pages.add(signature)
            process_current_page(driver, page_number, seen_urls, jobs=jobs, on_records=save)
            print(f"Saved {len(results)} jobs so far; JSON writing: {write_seconds:.3f}s total.")
            # Stop when no usable next control is found; loading timeouts raise an error.
            navigation_started = time.perf_counter()
            if not click_next_page(driver, page_number, list(signature)):
                break
            print(f"  Next page loaded in {time.perf_counter() - navigation_started:.2f}s.")
            page_number += 1
    print(f"Exported {len(results)} jobs from {page_number} pages to {output_file}\n"
          f"Checked {len(seen_urls)} unique jobs in {time.perf_counter() - started:.2f}s.")
    return results


def main():
    # Entry point: argparse handles --help and an optional --output file path.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE, help="JSON destination")
    args = parser.parse_args()
    driver = create_driver()
    try:
        # Run the three main stages in order. expanduser resolves '~' in output paths.
        login_to_hkust(driver)
        filter_jobs(driver)
        export_jobs_to_json(driver, args.output.expanduser())
    finally:
        # finally runs even after an error or interruption, ensuring Chrome is closed.
        driver.quit()


# Run main only when launched as a script; importing it exposes functions without login.
if __name__ == "__main__":
    main()
