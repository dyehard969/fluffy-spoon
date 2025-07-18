import logging

logging.info("FircoPage module loaded from %s", __file__)
import time
from enum import Enum, auto
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from bpm import (
    map_transaction_type_to_option,
    perform_login_and_setup,
    select_options_and_submit,
    handle_dropdown_and_search,
)
from Bpm_Page import BPMPage


class TransactionError(Exception):
    """Custom exception for transaction processing errors with error codes and detailed messages."""

    def __init__(self, message, error_code, screenshot_path=None):
        self.message = message
        self.error_code = error_code
        self.screenshot_path = screenshot_path
        super().__init__(f"Error {error_code}: {message}")


class Selectors:
    """Container for page selectors to reduce attribute count in the main class."""

    def __init__(self, page: Page):
        # Navigation selectors
        self.menu_item = page.locator("li#root-menu-0")
        self.history_item = page.locator("li#root-menu-1")
        self.live_messages = page.locator("div.stick#text-element-8")
        self.live_messages_tab = page.locator("a.tab-center").filter(
            has_text="Live Messages"
        )
        self.sanctions_bypass_view_tab = page.locator("a.tab-center").filter(
            has_text="Sanctions Bypass View"
        )
        # Filtering descending date
        self.filtered_date_menu_opener = page.locator(
            "#fmf-table-column-filtered-date-col-menu-opener"
        )
        # self.ascending_date = page.locator(".sort-desc-menu-item")
        self.ascending_date = page.locator("text=Sort ascending")
        self.reset_filter = page.locator(".remove-sort-menu-item")

        # Table selectors
        self.table = page.locator("table")
        self.filtered_column_icon = page.locator("a.column-filtered-icon")
        self.menu_opener = page.locator("#fmf-table-column-message-id-col-menu-opener")
        self.input_field = page.locator("input.quick-filter-input")
        self.search_btn = page.locator("div.quick-filter-icon")
        self.no_data_notice = page.locator(
            "div.no-data-notice-wrapper div.no-data-notice"
        )
        self.first_odd_row_td_text = (
            page.locator("tr.odd-row").first.locator("td").first
        )
        self.first_row = page.locator("tr.even-row.clickable-row")
        self.comment_field = page.locator(
            "textarea.stick.ui-autocomplete-input[name='COMMENT']"
        )
        self.transaction_rows = page.locator(
            "table.hit-table.live tbody tr"
        )  # was self.table / duplicated

        self.table = page.locator("table#table-element-1")
        self.table_rows = self.table.locator("tbody tr")
        # Avoid evaluating locators during initialization; evaluate lazily later
        self.table_rows_first = self.table_rows.first
        self.table_rows_first_message_id_cell = self.table_rows_first.locator("td").nth(
            1
        )

        self.data_filters = page.locator("text=Data filters...")
        self.data_filters_input = page.locator("id=text-input-element-44")
        self.data_filters_add_button = page.locator("id=Add Filter Button")
        self.data_filters_ok_button = page.locator("id=Confirm Button")

        # Navigation link to open Live Messages view (anchor has classes 'hide' and 'unload-page')
        self.live_messages_link = page.locator("li#root-menu-0 a.hide.unload-page")

        # Action buttons
        self.stp_release = page.locator("input[value='STP_Release']")
        self.confirm = page.locator("input#Confirm\\ Button")
        self.release = page.locator("input[value='Release']")
        self.reject = page.locator("input[value='Reject']")
        self.block = page.locator("input[value='Block']")
        self.logout = page.locator("#logout-button")
        self.escalate = page.locator("input[value='Esc_Sanctions']")


class SearchStatus(Enum):
    NONE = auto()
    MULTIPLE = auto()
    FOUND = auto()


class FircoPage:
    """
    Wrapper class for Firco application page that handles page interactions and transaction
    processing.

    This class provides methods to interact with the Firco UI elements, search for transactions,
    and perform various actions on them such as release, block, or reject.
    """

    def __init__(self, page: Page):
        """
        Initialize the FircoPage with a Playwright page object.

        Args:
            page: The Playwright Page object to use for interactions
        """
        logging.info("FircoPage.__init__ called")
        self.page = page
        self.selectors = Selectors(page)  # Group all selectors in a separate object

    def clear_filtered_column(self):
        """
        Clear any filters that may be applied to the transaction column.

        Checks if a filter icon is visible and clicks it if present. Verifies the action
        was successful and logs detailed feedback.
        """
        try:
            if self.selectors.filtered_column_icon.is_visible(timeout=5000):
                logging.info("Filter icon detected. Attempting to clear filter.")
                self.selectors.filtered_column_icon.click()
                # Verify if the filter icon is still visible after clicking
                if self.selectors.filtered_column_icon.is_visible(timeout=2000):
                    logging.warning(
                        "Filter icon still visible after click. Filter may not have cleared."
                    )
                else:
                    logging.info("Filter successfully cleared.")
            else:
                logging.info(
                    "No filter icon detected in transaction column. No action needed."
                )
        except PlaywrightTimeoutError:
            logging.error(
                "Timeout while checking for filter icon. Assuming no filter present."
            )

    def search_transaction(self, transaction: str):
        """
        Search for a specific transaction by ID.

        Args:
            transaction: The transaction ID to search for
        """
        self.selectors.menu_opener.click()
        self.selectors.input_field.fill(transaction)
        self.selectors.search_btn.click()
        try:
            self.page.wait_for_selector(".loading-indicator", state="visible")
            self.page.wait_for_selector(
                ".loading-indicator", state="hidden", timeout=5000
            )
        except PlaywrightTimeoutError as e:
            logging.error("Timeout waiting for loading indicator: %s", e)
        except (ValueError, RuntimeError) as e:
            logging.error("Error while waiting for loading indicator: %s", e)

    def data_filters(self, transaction: str, amount: str = ""):
        self.selectors.menu_opener.click()
        self.selectors.data_filters.click()
        self.page.fill("id=text-input-element-44", transaction)
        self.page.click("id=Add Filter Button")
        self.page.click("id=Confirm Button")

    def check_bpm_page(self, transaction: str, transaction_type: str = ""):
        """
        Perform BPM search for the transaction and return a result dict.
        """
        logging.info(
            f"Transaction {transaction} not uniquely found in Live, History. Checking BPM page."
        )

        # Add retry mechanism for BPM page loading issues
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            try:
                page = self.page
                bpm_page = BPMPage(page)
                options_to_check = map_transaction_type_to_option(transaction_type)
                if not options_to_check:
                    logging.warning(
                        f"Unknown or missing BPM option for transaction type: {transaction_type}"
                    )

                # Attempt to perform BPM operations
                perform_login_and_setup(bpm_page)
                select_options_and_submit(bpm_page, page, options_to_check)

                try:
                    # Perform BPM search and capture results
                    fourth_column_value, last_column_value = handle_dropdown_and_search(
                        bpm_page, page, transaction
                    )
                    logging.info(
                        f"Transaction {transaction} found in BPM: {fourth_column_value}, {last_column_value}"
                    )
                    # If not found in BPM, return not_found status
                    if (
                        fourth_column_value == "NotFound"
                        and last_column_value == "NotFound"
                    ):
                        return {
                            "status": "transaction_not_found",
                            "message": f"Transaction {transaction} not found in BPM.",
                        }
                    # If BPM indicates explicit failure, return failed_in_bpm
                    if (
                        fourth_column_value == "PostedTxtnToFirco"
                        or last_column_value in ("WARNING", "FAILURE")
                    ):
                        return {
                            "status": "failed_in_bpm",
                            "message": f"Transaction {transaction} failed in BPM.",
                            "details": {
                                "fourth_column": fourth_column_value,
                                "last_column": last_column_value,
                            },
                        }
                    # Otherwise, treat as successful find
                    return {
                        "status": "found_in_bpm",
                        "message": f"Transaction {transaction} found in BPM.",
                        "details": {
                            "fourth_column": fourth_column_value,
                            "last_column": last_column_value,
                        },
                    }
                except Exception as search_exc:
                    logging.info(
                        f"Transaction {transaction} not found in BPM: {search_exc}"
                    )
                    # Exit retry loop if this is a normal "not found" scenario
                    if "not visible" in str(search_exc).lower():
                        break
                    raise  # Re-raise to be caught by outer try/except for retry logic

            except Exception as e:
                error_message = str(e).lower()
                logging.error(f"Error during BPM search for {transaction}: {e}")

                # If browser or page closed, treat as BPM failure
                if "target page" in error_message and "closed" in error_message:
                    logging.info(
                        f"Browser closed during BPM search for {transaction}, treating as BPM failure"
                    )
                    return {
                        "status": "failed_in_bpm",
                        "message": f"Transaction {transaction} failed in BPM due to browser closure.",
                        "details": {"error": error_message},
                    }

                # Check if error is related to page reload/timeout issues
                if (
                    "timeout" in error_message
                    or "reload" in error_message
                    or retry_count < max_retries
                ):
                    retry_count += 1
                    logging.warning(
                        f"BPM page appears to be in a reload loop or timed out. Retry attempt {retry_count}/{max_retries}"
                    )

                    # Close and recreate browser context before retrying
                    try:
                        # Close any existing contexts
                        context = page.context
                        browser = context.browser
                        context.close()

                        # Create a new context and page
                        context = browser.new_context()
                        self.page = context.new_page()
                        logging.info("Successfully reset browser context for retry")
                    except Exception as browser_error:
                        logging.error(f"Error resetting browser: {browser_error}")

                    # Wait before retrying
                    time.sleep(3)
                    continue
                else:
                    # Not a timeout/reload issue, break the retry loop
                    break

            # If we got here without errors, break the retry loop
            break

        logging.info(
            f"Transaction {transaction} not found in Live Messages, History, or BPM."
        )
        return {
            "status": "transaction_not_found_in_any_tab",
            "message": f"Transaction {transaction} not found in any relevant tab after checking Live, History, Sanctions Bypass, and BPM.",
        }

    def go_to_transaction_details(
        self,
        transaction: str,
        comment: str,
        transaction_type: str = "",
        perform_on_latest: bool = True,
    ):
        """
        Navigate to a specific transaction's details page and determine its status.
        Prioritizes Live Messages for processing,
        then checks History, then BPM.
        Returns a dictionary indicating the outcome.
        """

        logging.info("Navigating to live messages link!")
        # self.sel.menu_item.click()
        self.selectors.live_messages_link.click()

        expect(self.selectors.live_messages).to_contain_text("Live Messages")

        try:
            expect(self.selectors.live_messages_tab).to_be_visible()
            expect(self.selectors.live_messages_tab).to_have_class(
                r"tab-center tab-center-selected"
            )
        except (AssertionError, PlaywrightTimeoutError) as e:
            logging.info("Live Messages tab not active: %s", e)
            logging.info("Clicking on Live Messages tab.")
            self.selectors.live_messages_tab.click()
            expect(self.selectors.live_messages_tab).to_have_class(
                r"tab-center tab-center-selected"
            )

        # 1. Search in Live Messages tab
        self.clear_filtered_column()  # Assuming this is for Live Messages context
        self.data_filters(transaction)
        live_status = self.verify_search_results(transaction)

        # Return immediately after verify_search_results, regardless of status
        # logging.info(f"Breaking after verify_search_results with status: {live_status}")

        # Handle all possible status values and return immediately
        if live_status == SearchStatus.FOUND:
            logging.info(
                f"Transaction {transaction} found in Live Messages. Preparing for action."
            )
            self.fill_comment_field(comment)
            self.click_all_hits(True)  # Assuming these are preparatory steps
            return {
                "status": "found_in_live",
                "message": f"Transaction {transaction} found in Live Messages and is ready for action.",
            }
        elif live_status == SearchStatus.MULTIPLE:
            if perform_on_latest:
                logging.info(
                    f"Multiple transactions found for ID: {transaction} in Live Messages, but 'perform_on_latest' is set. Selecting the latest transaction."
                )
                # Click filter menu, descending sort, then first row
                self.selectors.filtered_date_menu_opener.click()
                self.selectors.ascending_date.click()
                # Click the first transaction row (assuming self.sel.table is a Playwright locator for rows)
                self.selectors.table_rows_first_message_id_cell.click()
                self.fill_comment_field(comment)
                self.click_all_hits(True)
                return {
                    "status": "found_in_live",
                    "message": f"Latest transaction for ID: {transaction} selected in Live Messages and ready for action.",
                }
            else:
                logging.error(
                    f"Multiple transactions found for ID: {transaction} in Live Messages."
                )
                raise TransactionError(
                    f"Multiple transactions found for ID: {transaction} in Live Messages. Please specify a unique transaction.",
                    409,
                )
        # 3. Search in History tab (if not uniquely found in Live Messages)
        logging.info(
            f"Transaction {transaction} not uniquely found in Live Messages. Checking History tab."
        )
        self.selectors.history_item.click()
        self.page.wait_for_timeout(
            2000
        )  # User-added timeout, consider explicit wait if possible

        # Clear any existing filters and search for the transaction
        self.clear_filtered_column()
        self.data_filters(transaction)
        history_status = self.verify_search_results(transaction)

        if history_status in (SearchStatus.FOUND, SearchStatus.MULTIPLE):
            logging.info(
                f"Transaction {transaction} found in History. Already handled."
            )
            return {
                "status": "already_handled",
                "message": f"Transaction {transaction} found in History. No further action taken by this process.",
            }

        # 4. Search in BPM page (if not uniquely found in Live, History)
        return self.check_bpm_page(transaction, transaction_type)

    def verify_on_bpm(self, transaction: str) -> SearchStatus:
        """
        Placeholder for BPM page search.
        """
        # TODO: implement BPM search logic
        return SearchStatus.NONE

    def click_all_hits(self, screenshots: bool):
        """
        Click on all available transaction hit rows and optionally take screenshots.

        Args:
            screenshots: If True, take screenshots after each click
        """
        if screenshots:
            self.page.screenshot(path="hit_0.png", full_page=True)

        rows = self.selectors.transaction_rows.element_handles()

        for i in range(3, len(rows)):
            row = rows[i]
            try:
                row.click()
                if screenshots:
                    self.page.screenshot(path=f"hit{i-2}.png", full_page=True)
            except PlaywrightTimeoutError as e:
                logging.error("Timeout when clicking row %d: %s", i, e)
            except (ValueError, TypeError) as e:
                logging.error("Invalid parameter when clicking row %d: %s", i, e)
            except RuntimeError as e:
                logging.error("Runtime error when clicking row %d: %s", i, e)

    def verify_search_results(self, transaction: str) -> SearchStatus:
        """
        Verify search results for a transaction and return status.
        """
        logging.info("Verifying search results for transaction %s.", transaction)
        logging.info("Waiting for 2 seconds.")
        time.sleep(2)
        if self.selectors.no_data_notice.is_visible():
            self.page.screenshot(path="no_transactions.png", full_page=True)
            return SearchStatus.NONE

        if (self.selectors.first_odd_row_td_text.text_content() or "").strip():
            self.page.screenshot(path="more_transactions.png", full_page=True)
            return SearchStatus.MULTIPLE

        # one transaction found
        logging.info("One transaction found")
        self.page.screenshot(path="one_transaction.png", full_page=True)
        try:
            self.selectors.first_row.click()
        except Exception as e:
            screenshot_path = "not_active_transaction.png"
            self.page.screenshot(path=screenshot_path, full_page=True)
            raise TransactionError(
                f"Transaction {transaction} found but cannot be selected: {str(e)}",
                error_code=422,
                screenshot_path=screenshot_path,
            ) from e

        return SearchStatus.FOUND

    def fill_comment_field(self, text: str):
        """
        Fill the transaction comment field with the provided text.

        Args:
            text: The comment text to enter
        """
        expect(self.selectors.comment_field).to_be_visible()
        self.selectors.comment_field.fill(text)

    def logout(self):
        """
        Log out from the Firco system.

        Waits for a brief timeout to ensure all actions are complete,
        then clicks the logout button and logs the action.
        """
        self.page.wait_for_timeout(2000)
        self.selectors.logout.click()
        logging.info("logged out!")

    def perform_action(self, action: str):
        logging.info("perform_action called with action '%s'", action)
        """
        Perform a specified action on the current transaction.

        Takes screenshots before and after each step of the action,
        clicks the appropriate button for the action, and confirms it.

        Args:
            action: The action to perform (STP-Release, Release, Block, or Reject)
        """
        action_button_map = {
            "STP-Release": self.selectors.stp_release,
            "Release": self.selectors.release,
            "Block": self.selectors.block,
            "Reject": self.selectors.reject,
        }

        if action in action_button_map:
            # Convert action name to lowercase for screenshot naming
            action_name = action.lower().replace("-", "_")

            # Take screenshot before action
            self.page.screenshot(path=f"{action_name}_1.png", full_page=True)
            logging.info("Taking screenshot before %s action", action_name)

            # Click the action button
            logging.info("Clicking %s button", action_name)
            action_button_map[action].click()

            # Take screenshot after action button click
            self.page.screenshot(path=f"{action_name}_2.png", full_page=True)
            logging.info("Taking screenshot after %s button click", action_name)

            # Click confirm button
            logging.info("Clicking Confirm button")
            self.selectors.confirm.click()

            # Take screenshot after confirmation
            self.page.screenshot(path=f"{action_name}_3.png", full_page=True)
            logging.info("%s action confirmed", action_name)
        else:
            logging.warning(
                "Action '%s' not recognized. Available actions: %s",
                action,
                ", ".join(action_button_map.keys()),
            )
