import os
import logging
import time
import json
import sys

# Add current directory to path to find local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Third-party imports
from playwright.sync_api import Page, expect, sync_playwright

# Local application imports
from FircoPage import FircoPage, TransactionError
from utils import (
    parse_txt_file,
    create_output_structure,
    move_screenshots_to_folder,
    get_txt_files,
)

# --- Config ---
INCOMING_DIR = "input"
OUTPUT_DIR = "output"
LOG_FILE = "transactions.log"
TEST_URL = "https://example.com"
USERNAME = "user"
PASSWORD = "pass"
MANAGER_USERNAME = "manager"
MANAGER_PASSWORD = "pass"

# Define module-level constants for status strings
TRANSACTION_NOT_FOUND_STATUS = "transaction_not_found_in_any_tab"


# --- Logging Setup ---
def setup_logging() -> None:
    """Set up logging configuration with file and console handlers."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(msecs)03d] :: %(levelname)s :: %(name)s :: %(funcName)s :: %(message)s",
        datefmt="%X",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


# --- Firco Login ---
def login_to_firco(
    page: Page, url: str = TEST_URL, username: str = USERNAME, password: str = PASSWORD
) -> None:
    """
    Login to the Firco system.

    Args:
        page: The Playwright page object
        url: The URL of the Firco system
        username: Login username
        password: Login password
    """
    logging.info("Logging to Firco as %s.", username)
    page.goto(url)
    expect(page).to_have_title("State Street Login")
    page.fill("input[name='username']", username)
    page.fill("input[name='PASSWORD']", password)
    page.click("input[type='submit'][value='Submit']")
    page.wait_for_load_state("networkidle")
    logging.info("We are in Firco as %s.", username)


# --- Firco Transaction Processing ---
def process_firco_transaction(
    page: Page,
    transaction: str,
    action: str,
    user_comment: str,
    transaction_type: str = "",
    needs_escalation: bool = False,
    perform_on_latest: bool = False,
) -> dict:
    """
    Process a Firco transaction with the specified action.
    Returns a dictionary with processing status.
    """
    logging.info("Processing transaction %s with action %s.", transaction, action)
    firco_page = FircoPage(page)

    details_result = firco_page.go_to_transaction_details(
        transaction, user_comment, transaction_type, perform_on_latest
    )
    logging.info(
        f"Transaction details result from go_to_transaction_details: {details_result}"
    )

    current_status = details_result.get("status")

    # Define statuses where no further action (escalate/perform_action) is needed from this function
    TERMINAL_READ_ONLY_STATUSES = [
        "already_handled",  # Found in History
        "found_in_sanctions_bypass",  # Found in Sanctions Bypass View
        "found_in_bpm",  # Found in BPM
        "failed_in_bpm",  # BPM search failed
        TRANSACTION_NOT_FOUND_STATUS,  # Not found in any tab
    ]

    if current_status in TERMINAL_READ_ONLY_STATUSES:
        logging.info(
            f"Transaction {transaction} status '{current_status}' requires no further action here. Logging out."
        )
        # Safely logout without raising if page already closed
        try:
            firco_page.logout()
        except Exception as e:
            logging.warning(f"Logout failed for status '{current_status}': {e}")
        return details_result

    elif current_status == "found_in_live":
        if needs_escalation:
            logging.info(
                f"Transaction {transaction} found in Live Messages. Escalating for action '{action}'."
            )
            firco_page.selectors.escalate.click()
            time.sleep(2)  # Consider replacing with an explicit wait
            firco_page.logout()
            return {
                "status": "escalated",
                "message": f"Transaction {transaction} found in Live Messages and escalated for action '{action}'.",
            }
        else:  # Not needs_escalation, perform direct action
            logging.info(
                f"Transaction {transaction} found in Live Messages. Performing action '{action}'."
            )
            firco_page.perform_action(action)
            firco_page.logout()
            return {
                "status": "action_performed_on_live",
                "message": f"Action '{action}' performed on transaction {transaction} found in Live Messages.",
            }
    else:
        logging.warning(
            f"Transaction {transaction} not found in Live or History. Attempting BPM search."
        )
        bpm_result = firco_page.check_bpm_page(transaction, transaction_type)
        return bpm_result


# --- Error Handling Functions ---
def cleanup_browser_resources(page: Page = None, browser: object = None) -> None:
    """
    Safely close browser resources even if there are exceptions.

    Args:
        page: The Playwright page object
        browser: The Playwright browser object
    """
    # Close page if it exists
    if page:
        try:
            page.close()
        except (OSError, ConnectionError, RuntimeError) as e:
            logging.warning("Failed to close page: %s", e)

    # Close browser if it exists
    if browser:
        try:
            browser.close()
        except (OSError, ConnectionError, RuntimeError) as e:
            logging.warning("Failed to close browser: %s", e)


def handle_generic_error(transaction: str, error: Exception, result: dict) -> None:
    """
    Handle generic errors during transaction processing.

    Args:
        transaction: The transaction ID
        error: The caught exception
        result: Result dictionary to update
    """
    # Log the error
    logging.error("Failed processing %s: %s", transaction, error)

    # Update result dictionary
    result["success"] = False
    result["message"] = str(error)
    result["error_code"] = 500


def handle_transaction_error(
    transaction: str, action: str, te: TransactionError, result: dict
) -> None:
    """
    Handle specific transaction errors with detailed information.

    Args:
        transaction: The transaction ID
        action: The action being performed
        te: TransactionError exception object
        result: Result dictionary to update
    """
    # Log the error
    logging.error("Transaction error processing %s: %s", transaction, te)

    # Update result dictionary
    result["success"] = False
    result["message"] = te.message
    result["error_code"] = te.error_code
    result["screenshot_path"] = te.screenshot_path

    # Log the error to the transaction history file
    error_msg = (
        f"ERROR {te.error_code}: {transaction}, action: {action}, error: {te.message}"
    )
    with open(os.path.join(OUTPUT_DIR, "error_log.txt"), "a", encoding="utf-8") as log:
        log.write(error_msg + "\n")


# --- Transaction Processor ---
def process_transaction(
    playwright: object,
    txt_path: str,
    transaction_type: str = "",
    perform_on_latest: bool = False,
) -> str:
    """
    Process a transaction from a text file and return the result as JSON.

    Args:
        playwright: The Playwright instance
        txt_path: Path to the transaction text file

    Returns:
        JSON string with the processing result
    """
    transaction, action, user_comment = parse_txt_file(txt_path)
    # transaction_type is now received from server.py and passed in
    transaction_folder, date_folder = create_output_structure(transaction, OUTPUT_DIR)

    # Check if folder creation was successful
    if transaction_folder is None or date_folder is None:
        logging.error(
            "Failed to create output folders for transaction: %s", transaction
        )
        return json.dumps(
            {
                "success": False,
                "message": "Failed to create output folders",
                "error_code": 500,
                "screenshot_path": None,
                "status_detail": "unknown",
            }
        )

    browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
    page = browser.new_page()

    result = {
        "success": False,
        "message": "",
        "error_code": None,
        "screenshot_path": None,
        "status_detail": "unknown",  # Initialize with a default
    }

    try:
        # I would like to log all the transaction info
        logging.info(f"Processing transaction: {transaction}")
        logging.info(f"Transaction type: {transaction_type}")
        logging.info(f"Action: {action}")
        logging.info(f"User comment: {user_comment}")

        # First user login and process
        login_to_firco(page, url=TEST_URL, username=USERNAME, password=PASSWORD)

        firco_result_user1 = None

        if action != "STP-Release":
            # For non-STP actions, we expect escalation
            logging.info("Processing non-STP action with escalation.")
            firco_result_user1 = process_firco_transaction(
                page,
                transaction,
                action,
                user_comment,
                transaction_type=transaction_type,
                needs_escalation=True,
                perform_on_latest=perform_on_latest,
            )
        else:
            # For STP-Release, process directly without escalation flag initially
            logging.info("Processing STP-Release transaction directly.")
            firco_result_user1 = process_firco_transaction(
                page,
                transaction,
                action,
                user_comment,
                transaction_type=transaction_type,
                perform_on_latest=perform_on_latest,
            )

        # Determine if manager processing is needed based on the result from the first user's session
        needs_manager = firco_result_user1.get("status") == "escalated"

        # If escalation was performed (or if status indicates manager is needed), do manager processing
        if needs_manager:
            logging.info(
                f"Manager processing required for transaction {transaction} due to status: {firco_result_user1.get('status')}"
            )
            login_to_firco(
                page, url=TEST_URL, username=MANAGER_USERNAME, password=MANAGER_PASSWORD
            )
            # The action for the manager might be different or implicit post-escalation
            # Assuming the 'action' here is what the manager should perform
            firco_result_manager = process_firco_transaction(
                page,
                transaction,
                action,
                user_comment,
                transaction_type=transaction_type,
            )
            # The final result for the API will be based on the manager's action outcome
            final_firco_result = firco_result_manager
        else:
            # If no manager action was needed, the result from the first user is the final one
            final_firco_result = firco_result_user1

        # Populate the main result dictionary based on the final_firco_result
        # Define statuses that indicate the automation step completed successfully,
        # even if no direct action was taken on the transaction (e.g., already handled or not found).
        SUCCESSFUL_AUTOMATION_STEP_STATUSES = [
            "action_performed_on_live",  # Action taken on a live item
            "escalated",  # User1 successfully escalated
            "already_handled",  # Found in History, no action needed
            "found_in_bpm",  # Found in BPM, no action needed
            "found_in_sanctions_bypass",  # Found in Sanctions Bypass, no action needed
            TRANSACTION_NOT_FOUND_STATUS,  # Successfully determined not found in any relevant tab
        ]

        if final_firco_result.get("status") in SUCCESSFUL_AUTOMATION_STEP_STATUSES:
            result["success"] = True
            result["message"] = final_firco_result.get(
                "message",
                f"Transaction {transaction} status: {final_firco_result.get('status')}",
            )
            result["status_detail"] = final_firco_result.get(
                "status"
            )  # Pass the detailed status
        else:
            # Handle cases where final_firco_result indicates a processing failure or an unexpected status
            result["success"] = False
            result["message"] = final_firco_result.get(
                "message",
                f"Transaction {transaction} failed or has an unknown status: {final_firco_result.get('status')}",
            )
            result["error_code"] = final_firco_result.get(
                "error_code", 500
            )  # Default error code
            result["screenshot_path"] = final_firco_result.get("screenshot_path")
            result["status_detail"] = final_firco_result.get(
                "status", "processing_error"
            )  # Pass detailed error status

        # File operations and logging remain largely the same, assuming success means the workflow step completed
        if result["success"]:
            try:
                # Move screenshots into the per-transaction folder
                move_screenshots_to_folder(transaction_folder)
            except FileNotFoundError:
                logging.error("Screenshot folder not found: %s", transaction_folder)
            except PermissionError:
                logging.error(
                    "Permission denied when moving screenshots to %s",
                    transaction_folder,
                )
            except OSError as e:
                logging.error("OS error when moving screenshots: %s", e)

            try:
                os.rename(
                    txt_path,
                    os.path.join(transaction_folder, os.path.basename(txt_path)),
                )
            except FileNotFoundError:
                logging.error("Transaction file not found: %s", txt_path)
            except PermissionError:
                logging.error(
                    "Permission denied when moving transaction file to %s",
                    transaction_folder,
                )
            except FileExistsError:
                logging.error(
                    "A file with the same name already exists in %s", transaction_folder
                )
            except OSError as e:
                logging.error("OS error when moving transaction file: %s", e)

            log_msg = f"Transaction {transaction} processing attempt. Final status: {final_firco_result.get('status')}, Action: {action}, User: {user_comment}"
            with open(
                os.path.join(OUTPUT_DIR, "daily_log.txt"), "a", encoding="utf-8"
            ) as log:
                log.write(log_msg + "\n")
            logging.info("%s", log_msg)

    except TransactionError as te:
        handle_transaction_error(transaction, action, te, result)
    except (OSError, ConnectionError, ValueError, RuntimeError) as e:
        # Using more specific error types instead of general Exception
        handle_generic_error(transaction, e, result)
    finally:
        cleanup_browser_resources(page, browser)

    # Return the result as JSON string for the server to use
    return json.dumps(result)


# --- Main Execution ---
def main() -> None:
    """Main function to set up logging and process all transactions in the input directory."""
    setup_logging()
    logging.info("Script started")

    with sync_playwright() as p:
        for txt_file in get_txt_files(INCOMING_DIR):
            txt_path = os.path.join(INCOMING_DIR, txt_file)
            result = process_transaction(p, txt_path)
            print(result)


if __name__ == "__main__":
    main()
