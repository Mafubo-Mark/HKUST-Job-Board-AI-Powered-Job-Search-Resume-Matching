import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


# ============================================================
# Maximum number of selections allowed for each filter
# ============================================================

MAX_BUSINESS_NATURES = 10
MAX_JOB_NATURES = 10
MAX_EMPLOYMENT_TYPES = 5
MAX_WORKING_LOCATIONS = 5
MAX_QUALIFICATION_LEVELS = 3
MAX_EMPLOYMENT_MODES = 2
MAX_LANGUAGES = 6


# ============================================================
# General function:
# Read all options from a select element on the webpage
# ============================================================

def get_select_options(driver, select_name):

    select_element = driver.find_element(
        By.NAME,
        select_name
    )

    option_elements = select_element.find_elements(
        By.TAG_NAME,
        "option"
    )

    result = []

    for option in option_elements:

        value = option.get_attribute("value")
        text = option.text.strip()

        # Ignore options with an empty value
        if not value:
            continue

        # Ignore Clear All
        if "Clear All" in text:
            continue

        result.append({
            "value": value,
            "name": text
        })

    return result


# ============================================================
# General function:
# Let the user select multiple options in the Terminal
# ============================================================

def choose_multiple_options(
    options,
    title,
    max_choices
):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    print()
    print(f"Please select up to {max_choices} options:")
    print()

    for index, item in enumerate(
        options,
        start=1
    ):
        print(
            f"{index}. {item['name']}"
        )

    print()
    print("-" * 70)

    while True:

        user_input = input(
            "\nEnter the option numbers separated by commas; "
            "press Enter to skip: "
        ).strip()

        # User does not select anything
        if user_input == "":

            print()
            print(f"Skipped {title}")

            return []

        try:

            numbers = [
                int(x.strip())
                for x in user_input.split(",")
                if x.strip()
            ]

        except ValueError:

            print()
            print("Invalid input format.")
            print("Example: 1,3,5")

            continue

        # Remove duplicates while preserving the user's input order
        numbers = list(
            dict.fromkeys(numbers)
        )

        # Check whether the maximum number of selections is exceeded
        if len(numbers) > max_choices:

            print()
            print(
                f"You can select at most {max_choices} options."
            )

            continue

        # Check whether all option numbers are valid
        invalid_numbers = [
            number
            for number in numbers
            if number < 1
            or number > len(options)
        ]

        if invalid_numbers:

            print()
            print(
                "The following option numbers do not exist:",
                invalid_numbers
            )

            continue

        # Find the actual options based on the user's input
        selected = [
            options[number - 1]
            for number in numbers
        ]

        print()
        print("You selected:")
        print()

        for item in selected:

            print(
                f"✓ {item['name']}"
            )

        confirm = input(
            "\nConfirm these selections? (y/n): "
        ).strip().lower()

        if confirm == "y":

            return selected

        print()
        print("Please select again.")


# ============================================================
# 1. Business Nature
# name = BN[]
# Maximum 10 selections
# ============================================================

def choose_business_natures(driver):

    options = get_select_options(
        driver,
        "BN[]"
    )

    return choose_multiple_options(
        options,
        "Business Nature Filter",
        MAX_BUSINESS_NATURES
    )


# ============================================================
# 2. Job Nature
# name = JN[]
# Maximum 5 selections
# ============================================================

def choose_job_natures(driver):

    options = get_select_options(
        driver,
        "JN[]"
    )

    return choose_multiple_options(
        options,
        "Job Nature Filter",
        MAX_JOB_NATURES
    )


# ============================================================
# 3. Employment Type
# name = EMT[]
# Maximum 5 selections
# ============================================================

def choose_employment_types(driver):

    options = get_select_options(
        driver,
        "EMT[]"
    )

    return choose_multiple_options(
        options,
        "Employment Type Filter",
        MAX_EMPLOYMENT_TYPES
    )


# ============================================================
# 4. Working Location
# name = WL[]
# Maximum 5 selections
# ============================================================

def choose_working_locations(driver):

    options = get_select_options(
        driver,
        "WL[]"
    )

    return choose_multiple_options(
        options,
        "Working Location Filter",
        MAX_WORKING_LOCATIONS
    )


# ============================================================
# 5. Levels of Qualification
# name = awards[]
# Maximum 3 selections
# ============================================================

def choose_qualification_levels(driver):

    options = get_select_options(
        driver,
        "awards[]"
    )

    return choose_multiple_options(
        options,
        "Levels of Qualification Filter",
        MAX_QUALIFICATION_LEVELS
    )


# ============================================================
# 6. Employment Mode
# name = EM[]
# Maximum 2 selections
# ============================================================

def choose_employment_modes(driver):

    options = get_select_options(
        driver,
        "EM[]"
    )

    return choose_multiple_options(
        options,
        "Employment Mode Filter",
        MAX_EMPLOYMENT_MODES
    )


# ============================================================
# 7. Language
# name = L[]
# Maximum 6 selections
# ============================================================

def choose_languages(driver):

    options = get_select_options(
        driver,
        "L[]"
    )

    return choose_multiple_options(
        options,
        "Language Filter",
        MAX_LANGUAGES
    )


# ============================================================
# General function:
# Apply the selections made in the Terminal to the webpage select
#
# HKUST uses Select2,
# so the underlying select element is hidden.
#
# JavaScript is used here to directly modify the options
# and then trigger the change event.
# ============================================================

def apply_select_values(
    driver,
    select_name,
    selected
):

    # If the user skipped this filter, do nothing
    if not selected:
        return

    values = [
        item["value"]
        for item in selected
    ]

    select_element = driver.find_element(
        By.NAME,
        select_name
    )

    driver.execute_script(
        """
        const select = arguments[0];
        const selectedValues = arguments[1];

        for (const option of select.options) {

            option.selected =
                selectedValues.includes(option.value);

        }

        if (window.jQuery) {

            $(select).trigger('change');

        } else {

            select.dispatchEvent(
                new Event(
                    'change',
                    {
                        bubbles: true
                    }
                )
            );

        }
        """,
        select_element,
        values
    )


# ============================================================
# Apply Business Nature
# ============================================================

def apply_business_natures(
    driver,
    selected
):

    apply_select_values(
        driver,
        "BN[]",
        selected
    )


# ============================================================
# Apply Job Nature
# ============================================================

def apply_job_natures(
    driver,
    selected
):

    apply_select_values(
        driver,
        "JN[]",
        selected
    )


# ============================================================
# Apply Employment Type
# ============================================================

def apply_employment_types(
    driver,
    selected
):

    apply_select_values(
        driver,
        "EMT[]",
        selected
    )


# ============================================================
# Apply Working Location
# ============================================================

def apply_working_locations(
    driver,
    selected
):

    apply_select_values(
        driver,
        "WL[]",
        selected
    )


# ============================================================
# Apply Levels of Qualification
# ============================================================

def apply_qualification_levels(
    driver,
    selected
):

    apply_select_values(
        driver,
        "awards[]",
        selected
    )


# ============================================================
# Apply Employment Mode
# ============================================================

def apply_employment_modes(
    driver,
    selected
):

    apply_select_values(
        driver,
        "EM[]",
        selected
    )


# ============================================================
# Apply Language
# ============================================================

def apply_languages(
    driver,
    selected
):

    apply_select_values(
        driver,
        "L[]",
        selected
    )


# ============================================================
# Submit all filter conditions
# ============================================================

def submit_filter(driver):

    print()
    print("=" * 70)
    print("Searching according to all selected filters...")
    print("=" * 70)

    try:

        old_table = driver.find_element(
            By.ID,
            "job-list"
        )

    except Exception:

        old_table = None

    # Find the Search button
    search_button = driver.find_element(
        By.CSS_SELECTOR,
        "#job_search_form button[type='submit']"
    )

    search_button.click()

    # ========================================================
    # Wait for the old job list to disappear
    # ========================================================

    if old_table:

        try:

            WebDriverWait(
                driver,
                15
            ).until(
                EC.staleness_of(old_table)
            )

        except TimeoutException:

            # If the website does not completely refresh the page,
            # do not let the program fail because of this
            pass

    # ========================================================
    # Wait for the new Job Board to appear
    # ========================================================

    try:

        WebDriverWait(
            driver,
            15
        ).until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "job-list"
                )
            )
        )

    except TimeoutException:

        pass

    time.sleep(2)


# ============================================================
# Get all jobs on the current page
# ============================================================

def get_jobs(driver):

    return driver.find_elements(
        By.CSS_SELECTOR,
        "#job-list tbody tr.job-item"
    )


# ============================================================
# Print jobs on the current page
# ============================================================

def print_jobs(job_rows):

    print()
    print("=" * 70)

    print(
        f"Found {len(job_rows)} matching jobs on the current page"
    )

    print("=" * 70)

    if not job_rows:

        print()
        print(
            "No matching jobs were found."
        )

        return

    for index, row in enumerate(
        job_rows,
        start=1
    ):

        try:

            columns = row.find_elements(
                By.CSS_SELECTOR,
                "td.detail-text.large-view"
            )

            # The normal desktop version should have at least 2 columns
            if len(columns) < 2:
                continue

            # =================================================
            # Company
            # =================================================

            company = (
                columns[0]
                .text
                .strip()
            )

            # =================================================
            # Job Title + Job Nature
            # =================================================

            title_lines = (
                columns[1]
                .text
                .strip()
                .splitlines()
            )

            if len(title_lines) >= 1:

                title = title_lines[0]

            else:

                title = "Unknown"

            if len(title_lines) >= 2:

                job_nature = title_lines[1]

            else:

                job_nature = ""

            # =================================================
            # Posting Date
            # =================================================

            if len(columns) >= 3:

                posting_date = (
                    columns[2]
                    .text
                    .strip()
                )

            else:

                posting_date = ""

            # =================================================
            # Application Deadline
            # =================================================

            if len(columns) >= 4:

                deadline = (
                    columns[3]
                    .text
                    .strip()
                )

            else:

                deadline = ""

            # =================================================
            # Job Detail URL
            # =================================================

            try:

                detail_link = row.find_element(
                    By.CSS_SELECTOR,
                    "td.detail-text.large-view a.job-post"
                )

                job_url = (
                    detail_link
                    .get_attribute("href")
                )

            except Exception:

                job_url = ""

            # =================================================
            # Print
            # =================================================

            print()
            print(
                f"{index}. {title}"
            )

            print(
                f"   Company: {company}"
            )

            if job_nature:

                print(
                    f"   Job Nature: {job_nature}"
                )

            if posting_date:

                print(
                    f"   Posting Date: {posting_date}"
                )

            if deadline:

                print(
                    f"   Deadline: {deadline}"
                )

            if job_url:

                print(
                    f"   URL: {job_url}"
                )

        except Exception as e:

            print()
            print(
                f"{index}. Unable to read job: {e}"
            )