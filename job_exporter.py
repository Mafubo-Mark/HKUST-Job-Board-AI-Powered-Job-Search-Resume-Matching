import json
import re
import time
from datetime import date, datetime
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException


# ============================================================
# Configuration
# ============================================================

OUTPUT_FILE = Path(
    "/Users/mafubo/Desktop/All Files/其他/hkust_job_project/hkust_jobs.json"
)

PAGE_WAIT_TIMEOUT = 30
SCRIPT_TIMEOUT = 300
MAX_FETCH_RETRIES = 3


# ============================================================
# Basic text helpers
# ============================================================

def clean_one_line(text):
    return " ".join(
        (text or "").split()
    )


def clean_lines(text):
    result = []

    for raw_line in (text or "").splitlines():

        line = clean_one_line(raw_line)

        if line:
            result.append(line)

    return result


# ============================================================
# Deadline parsing
# ============================================================

def parse_deadline(text):
    """
    Parse the application deadline.
    """

    text = clean_one_line(text)

    if not text:
        return None

    formats = [
        (
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",
            "%Y-%m-%d",
        ),
        (
            r"\b\d{4}/\d{1,2}/\d{1,2}\b",
            "%Y/%m/%d",
        ),
        (
            r"\b\d{1,2}/\d{1,2}/\d{4}\b",
            "%d/%m/%Y",
        ),
        (
            r"\b\d{1,2}-\d{1,2}-\d{4}\b",
            "%d-%m-%Y",
        ),
        (
            r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b",
            "%d %b %Y",
        ),
        (
            r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
            "%d %B %Y",
        ),
    ]

    for pattern, fmt in formats:

        match = re.search(
            pattern,
            text
        )

        if not match:
            continue

        try:

            return datetime.strptime(
                match.group(0),
                fmt
            ).date()

        except ValueError:
            continue

    return None


def get_deadline_status(text):
    """
    Returns:

        valid
        expired
        unknown
    """

    text = clean_one_line(text)

    lower = text.lower()

    if (
        "expired" in lower
        or "closed" in lower
    ):
        return "expired"

    if (
        "until filled" in lower
        or "open until filled" in lower
    ):
        return "valid"

    deadline = parse_deadline(text)

    if deadline is None:
        return "unknown"

    if deadline < date.today():
        return "expired"

    return "valid"


# ============================================================
# Read jobs from CURRENT page
# ============================================================

def extract_current_page_jobs(driver):
    """
    Read ONLY the current visible page.

    HKUST structure:

        columns[0] = Company
        columns[1] = Job Title + Job Nature
        columns[2] = Posting Date
        columns[3] = Application Deadline
    """

    return driver.execute_script(
        r"""
        const rows = Array.from(
            document.querySelectorAll(
                "#job-list tbody tr.job-item"
            )
        );

        function clean(value) {
            return (value || "")
                .replace(/\s+/g, " ")
                .trim();
        }

        const jobs = [];

        for (const row of rows) {

            const columns = Array.from(
                row.querySelectorAll(
                    "td.detail-text.large-view"
                )
            );

            const link = row.querySelector(
                "td.detail-text.large-view a.job-post"
            );

            if (
                columns.length < 4
                || !link
            ) {
                continue;
            }

            const titleLines =
                (columns[1].innerText || "")
                    .split(/\r?\n/)
                    .map(clean)
                    .filter(Boolean);

            jobs.push({
                company:
                    clean(
                        columns[0].innerText
                    ),

                job_title_nature:
                    titleLines.join(" / "),

                posting_date:
                    clean(
                        columns[2].innerText
                    ),

                application_deadline:
                    clean(
                        columns[3].innerText
                    ),

                url:
                    link.href
            });
        }

        return jobs;
        """
    ) or []


# ============================================================
# Current first-job URL
# ============================================================

def get_first_job_url(driver):

    try:

        return (
            driver.execute_script(
                """
                const link = document.querySelector(
                    "#job-list tbody "
                    + "tr.job-item a.job-post"
                );

                return link
                    ? link.href
                    : "";
                """
            )
            or ""
        )

    except Exception:
        return ""


# ============================================================
# Browser-side fast concurrent fetching
# ============================================================

def browser_fetch_details(
    driver,
    jobs
):
    """
    Fetch all job detail pages for ONE result page concurrently.

    Selenium stays on the Job Board.
    """

    if not jobs:
        return []

    urls = [
        job["url"]
        for job in jobs
    ]

    driver.set_script_timeout(
        SCRIPT_TIMEOUT
    )

    return (
        driver.execute_async_script(
            r"""
            const urls = arguments[0];

            const done =
                arguments[
                    arguments.length - 1
                ];

            async function readOne(url) {

                try {

                    const response =
                        await fetch(
                            url,
                            {
                                method: "GET",
                                credentials: "include",
                                cache: "no-store",
                                redirect: "follow"
                            }
                        );

                    const html =
                        await response.text();

                    if (!response.ok) {

                        return {
                            ok: false,
                            url: url,
                            error:
                                "HTTP "
                                + response.status
                        };
                    }

                    const parser =
                        new DOMParser();

                    const doc =
                        parser.parseFromString(
                            html,
                            "text/html"
                        );

                    doc.querySelectorAll(
                        "script,style,noscript,svg"
                    ).forEach(
                        element =>
                            element.remove()
                    );

                    const text =
                        doc.body
                        ? doc.body.textContent || ""
                        : "";

                    return {
                        ok: true,
                        url: url,
                        text: text
                    };

                } catch (error) {

                    return {
                        ok: false,
                        url: url,
                        error: String(error)
                    };
                }
            }

            Promise.all(
                urls.map(readOne)
            )
            .then(done)
            .catch(
                error => {

                    done(
                        urls.map(
                            url => ({
                                ok: false,
                                url: url,
                                error:
                                    String(error)
                            })
                        )
                    );
                }
            );
            """,
            urls
        )
        or []
    )


# ============================================================
# Retry fetch failures
# ============================================================

def fetch_details_with_retries(
    driver,
    jobs
):
    """
    Returns:

        successful[url] = detail text
        errors[url] = error message
    """

    pending = {
        job["url"]: job
        for job in jobs
    }

    successful = {}
    errors = {}

    for attempt in range(
        1,
        MAX_FETCH_RETRIES + 1
    ):

        if not pending:
            break

        batch = list(
            pending.values()
        )

        response_items = (
            browser_fetch_details(
                driver,
                batch
            )
        )

        next_pending = {}

        returned_urls = set()

        for item in response_items:

            url = item.get(
                "url",
                ""
            )

            if not url:
                continue

            returned_urls.add(url)

            if item.get("ok"):

                text = (
                    item.get(
                        "text",
                        ""
                    )
                    or ""
                )

                if clean_one_line(text):

                    successful[url] = text

                    errors.pop(
                        url,
                        None
                    )

                else:

                    next_pending[url] = (
                        pending[url]
                    )

                    errors[url] = (
                        "Empty detail page."
                    )

            else:

                if url in pending:

                    next_pending[url] = (
                        pending[url]
                    )

                errors[url] = (
                    item.get(
                        "error",
                        "Unknown fetch error"
                    )
                )

        # A URL not returned by JavaScript should also retry.
        for url, job in pending.items():

            if (
                url not in returned_urls
                and url not in successful
            ):

                next_pending[url] = job

                errors[url] = (
                    "No response returned."
                )

        pending = next_pending

        if (
            pending
            and attempt
            < MAX_FETCH_RETRIES
        ):

            time.sleep(0.5)

    return successful, errors


# ============================================================
# Extract deadline from a detail page
# ============================================================

def extract_deadline_from_detail(text):

    lines = clean_lines(text)

    for index, line in enumerate(lines):

        lower = line.lower()

        if (
            lower.rstrip(":")
            == "application deadline"
        ):

            if index + 1 < len(lines):

                return lines[
                    index + 1
                ]

        if lower.startswith(
            "application deadline:"
        ):

            return clean_one_line(
                line.split(
                    ":",
                    1
                )[1]
            )

    # Search nearby lines.
    for index, line in enumerate(lines):

        if (
            "application deadline"
            in line.lower()
        ):

            nearby = lines[
                index:
                min(
                    index + 5,
                    len(lines)
                )
            ]

            for candidate in nearby:

                if parse_deadline(
                    candidate
                ):

                    return candidate

    return ""


# ============================================================
# Build requested JSON
# ============================================================

def build_job_json(
    job,
    detail_text
):
    """
    JSON format:

    {
        "Company/Organization": ...,
        "Job Title/Job Nature": ...,
        "Application Deadline": ...,
        "Other information": ...
    }
    """

    lines = clean_lines(
        detail_text
    )

    deadline = clean_one_line(
        job.get(
            "application_deadline",
            ""
        )
    )

    # Try to remove duplicated header information
    # before the remaining detail content.

    deadline_index = -1

    if deadline:

        for index, line in enumerate(lines):

            if clean_one_line(line) == deadline:

                deadline_index = index
                break

    if deadline_index >= 0:

        remaining_lines = lines[
            deadline_index + 1:
        ]

    else:

        remaining_lines = lines

    other_parts = []

    posting_date = clean_one_line(
        job.get(
            "posting_date",
            ""
        )
    )

    if posting_date:

        other_parts.append(
            f"Posting Date: "
            f"{posting_date}"
        )

    other_parts.extend(
        remaining_lines
    )

    return {
        "Company/Organization":
            job.get(
                "company",
                ""
            ),

        "Job Title/Job Nature":
            job.get(
                "job_title_nature",
                ""
            ),

        "Application Deadline":
            job.get(
                "application_deadline",
                ""
            ),

        "Other information":
            " | ".join(
                other_parts
            )
    }


# ============================================================
# Save JSON immediately
# ============================================================

def save_json(results):

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# Process ONE PAGE
# ============================================================

def process_current_page(
    driver,
    page_number,
    seen_urls
):
    """
    EXACT workflow:

        current page
            ↓
        read all deadlines
            ↓
        expired -> skip
            ↓
        acceptable -> fetch details concurrently
            ↓
        return JSON records
    """

    jobs = extract_current_page_jobs(
        driver
    )

    unique_jobs = []

    for job in jobs:

        url = job.get(
            "url",
            ""
        )

        if not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        unique_jobs.append(job)

    print(
        f"Page {page_number}: "
        f"{len(unique_jobs)} jobs found"
    )

    valid_jobs = []
    unknown_jobs = []

    expired_count = 0

    # ========================================================
    # CHECK DEADLINES FIRST
    # ========================================================

    for job in unique_jobs:

        deadline = (
            job.get(
                "application_deadline",
                ""
            )
        )

        status = get_deadline_status(
            deadline
        )

        if status == "expired":

            expired_count += 1
            continue

        if status == "valid":

            valid_jobs.append(job)

        else:

            unknown_jobs.append(job)

    print(
        f"  Deadline OK: "
        f"{len(valid_jobs)}"
    )

    print(
        f"  Expired skipped: "
        f"{expired_count}"
    )

    if unknown_jobs:

        print(
            f"  Deadline needs verification: "
            f"{len(unknown_jobs)}"
        )

    candidates = (
        valid_jobs
        + unknown_jobs
    )

    if not candidates:

        print(
            "  Nothing to write."
        )

        return []

    # ========================================================
    # FETCH ALL CANDIDATES ON THIS PAGE AT ONCE
    # ========================================================

    successful, errors = (
        fetch_details_with_retries(
            driver,
            candidates
        )
    )

    page_results = []

    # ========================================================
    # NORMAL VALID JOBS
    # ========================================================

    for job in valid_jobs:

        url = job["url"]

        if url in successful:

            result = build_job_json(
                job,
                successful[url]
            )

        else:

            # Deadline is definitely acceptable,
            # so preserve the job even if detail fetching failed.

            result = {
                "Company/Organization":
                    job.get(
                        "company",
                        ""
                    ),

                "Job Title/Job Nature":
                    job.get(
                        "job_title_nature",
                        ""
                    ),

                "Application Deadline":
                    job.get(
                        "application_deadline",
                        ""
                    ),

                "Other information":
                    (
                        "ERROR while reading job details: "
                        + errors.get(
                            url,
                            "Unknown error"
                        )
                    )
            }

        page_results.append(
            result
        )

    # ========================================================
    # UNKNOWN DEADLINES
    #
    # Verify them from detail page.
    # ========================================================

    for job in unknown_jobs:

        url = job["url"]

        if url not in successful:

            continue

        detail_text = successful[url]

        detail_deadline = (
            extract_deadline_from_detail(
                detail_text
            )
        )

        if detail_deadline:

            job[
                "application_deadline"
            ] = detail_deadline

        status = get_deadline_status(
            job.get(
                "application_deadline",
                ""
            )
        )

        if status != "valid":

            continue

        page_results.append(
            build_job_json(
                job,
                detail_text
            )
        )

    print(
        f"  Written from this page: "
        f"{len(page_results)}"
    )

    return page_results


# ============================================================
# Robust pagination
#
# NO DATATABLES API REQUIRED.
# ============================================================

def click_next_page(
    driver,
    current_page_number
):
    """
    Find and click the real next-page control.

    Supports:

        Next
        >
        >>
        ›
        »
        Bootstrap .pagination
        DataTables HTML pagination
        aria-label="Next"
        numeric page links
    """

    old_first_url = (
        get_first_job_url(
            driver
        )
    )

    old_browser_url = (
        driver.current_url
    )

    expected_next_number = (
        current_page_number + 1
    )

    result = driver.execute_script(
        r"""
        const expectedPage =
            String(arguments[0]);

        const table =
            document.querySelector(
                "#job-list"
            );

        function visible(element) {

            if (!element) {
                return false;
            }

            const style =
                window.getComputedStyle(
                    element
                );

            const rect =
                element.getBoundingClientRect();

            return (
                style.display !== "none"
                && style.visibility !== "hidden"
                && rect.width > 0
                && rect.height > 0
            );
        }

        function disabled(element) {

            if (!element) {
                return true;
            }

            let node = element;

            for (
                let i = 0;
                i < 3 && node;
                i++
            ) {

                const classes =
                    (
                        node.className
                        || ""
                    ).toString().toLowerCase();

                const aria =
                    (
                        node.getAttribute
                            ? node.getAttribute(
                                "aria-disabled"
                            )
                            : ""
                    )
                    || "";

                if (
                    classes.includes(
                        "disabled"
                    )
                    || aria.toLowerCase()
                        === "true"
                ) {
                    return true;
                }

                node =
                    node.parentElement;
            }

            return false;
        }

        function actualClickable(element) {

            if (!element) {
                return null;
            }

            if (
                element.matches(
                    "a, button"
                )
            ) {
                return element;
            }

            return element.querySelector(
                "a, button"
            );
        }

        function tryClick(element) {

            if (!element) {
                return false;
            }

            let target =
                actualClickable(
                    element
                );

            if (!target) {
                return false;
            }

            if (
                !visible(target)
                || disabled(target)
            ) {
                return false;
            }

            target.click();

            return true;
        }

        // ===================================================
        // 1. Strong selectors for NEXT
        // ===================================================

        const directSelectors = [
            "#job-list_next",
            "#job-list_next a",
            "#job-list_paginate .next",
            "#job-list_paginate .next a",
            ".dataTables_paginate .next",
            ".dataTables_paginate .next a",
            "ul.pagination li.next",
            "ul.pagination li.next a",
            ".pagination .next",
            ".pagination .next a",
            "a[rel='next']",
            "button[aria-label*='next' i]",
            "a[aria-label*='next' i]"
        ];

        for (
            const selector
            of directSelectors
        ) {

            for (
                const element
                of document.querySelectorAll(
                    selector
                )
            ) {

                if (
                    tryClick(
                        element
                    )
                ) {

                    return {
                        clicked: true,
                        method:
                            "next-selector",
                        text:
                            (
                                element.innerText
                                || ""
                            ).trim()
                    };
                }
            }
        }

        // ===================================================
        // 2. Known pagination containers
        // ===================================================

        const containers = [];

        const containerSelectors = [
            "#job-list_paginate",
            ".dataTables_paginate",
            "ul.pagination",
            ".pagination",
            "nav[aria-label*='pagination' i]"
        ];

        for (
            const selector
            of containerSelectors
        ) {

            for (
                const container
                of document.querySelectorAll(
                    selector
                )
            ) {

                if (
                    visible(container)
                    && !containers.includes(
                        container
                    )
                ) {

                    containers.push(
                        container
                    );
                }
            }
        }

        // Look for text such as Next / › / »
        for (
            const container
            of containers
        ) {

            const elements =
                container.querySelectorAll(
                    "a,button"
                );

            for (
                const element
                of elements
            ) {

                const text =
                    (
                        element.innerText
                        || ""
                    )
                    .trim()
                    .toLowerCase();

                const aria =
                    (
                        element.getAttribute(
                            "aria-label"
                        )
                        || ""
                    )
                    .trim()
                    .toLowerCase();

                const title =
                    (
                        element.getAttribute(
                            "title"
                        )
                        || ""
                    )
                    .trim()
                    .toLowerCase();

                const isNext =
                    (
                        text === "next"
                        || text === "›"
                        || text === "»"
                        || text === ">"
                        || text === ">>"
                        || aria.includes(
                            "next"
                        )
                        || title.includes(
                            "next"
                        )
                    );

                if (
                    isNext
                    && tryClick(
                        element
                    )
                ) {

                    return {
                        clicked: true,
                        method:
                            "pagination-next",
                        text:
                            text
                    };
                }
            }
        }

        // ===================================================
        // 3. Numeric NEXT page
        //
        // Current page 1 -> find "2"
        // Current page 2 -> find "3"
        // etc.
        // ===================================================

        for (
            const container
            of containers
        ) {

            const elements =
                container.querySelectorAll(
                    "a,button"
                );

            for (
                const element
                of elements
            ) {

                const text =
                    (
                        element.innerText
                        || ""
                    ).trim();

                if (
                    text === expectedPage
                    && tryClick(element)
                ) {

                    return {
                        clicked: true,
                        method:
                            "numeric-pagination",
                        text: text
                    };
                }
            }
        }

        // ===================================================
        // 4. Final fallback:
        //
        // Search visible buttons directly below the job table.
        // This avoids depending on a particular pagination CSS
        // library.
        // ===================================================

        if (table) {

            const tableRect =
                table.getBoundingClientRect();

            const elements =
                Array.from(
                    document.querySelectorAll(
                        "a,button"
                    )
                );

            for (
                const element
                of elements
            ) {

                if (!visible(element)) {
                    continue;
                }

                const rect =
                    element.getBoundingClientRect();

                const belowTable =
                    (
                        rect.top
                        >= tableRect.bottom - 50
                        &&
                        rect.top
                        <= tableRect.bottom + 500
                    );

                if (!belowTable) {
                    continue;
                }

                const text =
                    (
                        element.innerText
                        || ""
                    ).trim();

                const lower =
                    text.toLowerCase();

                const aria =
                    (
                        element.getAttribute(
                            "aria-label"
                        )
                        || ""
                    ).toLowerCase();

                const nextLike =
                    (
                        lower === "next"
                        || text === "›"
                        || text === "»"
                        || text === ">"
                        || text === ">>"
                        || text === expectedPage
                        || aria.includes(
                            "next"
                        )
                    );

                if (
                    nextLike
                    && tryClick(
                        element
                    )
                ) {

                    return {
                        clicked: true,
                        method:
                            "below-table",
                        text: text
                    };
                }
            }
        }

        return {
            clicked: false,
            method: "none",
            text: ""
        };
        """,
        expected_next_number
    )

    if not result:
        return False

    if not result.get(
        "clicked"
    ):
        return False

    # ========================================================
    # Wait until the actual job rows change.
    # ========================================================

    try:

        WebDriverWait(
            driver,
            PAGE_WAIT_TIMEOUT
        ).until(
            lambda d:
            (
                (
                    get_first_job_url(d)
                    and
                    get_first_job_url(d)
                    != old_first_url
                )
                or
                d.current_url
                != old_browser_url
            )
        )

    except TimeoutException:

        # Sometimes page number changes without URL change.
        # Check once more after a very short delay.

        time.sleep(0.5)

        new_first_url = (
            get_first_job_url(
                driver
            )
        )

        if (
            not new_first_url
            or new_first_url
            == old_first_url
        ):
            return False

    time.sleep(0.2)

    return True


# ============================================================
# Pagination diagnostics
# ============================================================

def get_visible_pagination_text(driver):
    """
    Used only if we cannot find another page.
    """

    try:

        return driver.execute_script(
            r"""
            const selectors = [
                "#job-list_paginate",
                ".dataTables_paginate",
                "ul.pagination",
                ".pagination",
                "nav[aria-label*='pagination' i]"
            ];

            const result = [];

            for (
                const selector
                of selectors
            ) {

                for (
                    const element
                    of document.querySelectorAll(
                        selector
                    )
                ) {

                    const text =
                        (
                            element.innerText
                            || ""
                        )
                        .replace(/\s+/g, " ")
                        .trim();

                    if (
                        text
                        && !result.includes(
                            text
                        )
                    ) {

                        result.push(text);
                    }
                }
            }

            return result;
            """
        ) or []

    except Exception:
        return []


# ============================================================
# Main export
# ============================================================

def export_jobs_to_json(driver):
    """
    Required procedure:

        PAGE 1
            check deadlines
            expired -> skip
            valid -> fetch details
            write JSON

        NEXT PAGE

        PAGE 2
            check deadlines
            expired -> skip
            valid -> fetch details
            append JSON

        NEXT PAGE

        ...

        Stop only when no next page exists.
    """

    start_time = (
        time.perf_counter()
    )

    WebDriverWait(
        driver,
        60
    ).until(
        lambda d:
        len(
            d.find_elements(
                By.CSS_SELECTOR,
                "#job-list tbody tr.job-item"
            )
        ) > 0
    )

    print()
    print("=" * 70)
    print("Processing ALL filtered Job Board pages")
    print("=" * 70)
    print()

    print(
        f"Today's date: "
        f"{date.today().isoformat()}"
    )

    print()

    all_results = []

    seen_urls = set()

    page_number = 1

    # Start with clean JSON.
    save_json(
        all_results
    )

    while True:

        print(
            "=" * 70
        )

        print(
            f"Processing page "
            f"{page_number}"
        )

        print(
            "=" * 70
        )

        # ====================================================
        # 1. CHECK THIS PAGE
        # 2. FETCH VALID DETAILS
        # ====================================================

        page_results = (
            process_current_page(
                driver,
                page_number,
                seen_urls
            )
        )

        # ====================================================
        # 3. WRITE THIS PAGE TO JSON IMMEDIATELY
        # ====================================================

        all_results.extend(
            page_results
        )

        save_json(
            all_results
        )

        print(
            f"  JSON total so far: "
            f"{len(all_results)}"
        )

        print()

        # ====================================================
        # 4. CHANGE TO NEXT PAGE
        # ====================================================

        moved = click_next_page(
            driver,
            page_number
        )

        if not moved:

            print(
                "No further Job Board page found."
            )

            pagination_text = (
                get_visible_pagination_text(
                    driver
                )
            )

            if pagination_text:

                print(
                    "Visible pagination controls:"
                )

                for text in pagination_text:

                    print(
                        f"  {text}"
                    )

            break

        page_number += 1

    elapsed = (
        time.perf_counter()
        - start_time
    )

    print()
    print("=" * 70)
    print("Export completed")
    print("=" * 70)
    print()

    print(
        f"Pages processed: "
        f"{page_number}"
    )

    print(
        f"Unique jobs checked: "
        f"{len(seen_urls)}"
    )

    print(
        f"Jobs written to JSON: "
        f"{len(all_results)}"
    )

    print()

    print(
        "JSON file location:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        f"Total processing time: "
        f"{elapsed:.2f} seconds"
    )

    print()

    return all_results


# ============================================================
# Compatibility with your existing main.py
# ============================================================

def print_first_two_pages_job_details(driver):
    """
    Your existing main.py can keep calling this name.

    It now processes ALL pages.
    """

    return export_jobs_to_json(
        driver
    )