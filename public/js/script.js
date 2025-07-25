/**
 * MURDOCK - Transaction Processing Tool
 * Main JavaScript File
 */

// DOM Elements
const transactionForm = document.getElementById('transaction-form-element');
const transactionsInput = document.getElementById('transactions');
const commentInput = document.getElementById('comment');
const actionSelect = document.getElementById('action');
const transactionTypeSelect = document.getElementById('transaction-type');
const transactionTypeError = document.getElementById('transaction-type-error'); // Add <small id="transaction-type-error"> in HTML if not present
const themeToggleBtn = document.getElementById('theme-toggle-btn');
const commentCharCount = document.getElementById('comment-char-count');
const submissionStatus = document.getElementById('submission-status');
const transactionsTableBody = document.getElementById('transactions-table-body');
const filterAction = document.getElementById('filter-action');
const searchTransactions = document.getElementById('search-transactions');

// Error message elements
const transactionsError = document.getElementById('transactions-error');
const commentError = document.getElementById('comment-error');
const actionError = document.getElementById('action-error');

// Theme toggle functionality
themeToggleBtn.addEventListener('click', () => {
    // Toggle dark mode class and capture result
    const isDarkMode = document.body.classList.toggle('dark-mode');

    // Ensure classes are mutually exclusive
    if (isDarkMode) {
        document.body.classList.remove('light-mode');
        themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i>';
        localStorage.setItem('theme', 'dark');
    } else {
        document.body.classList.add('light-mode');
        themeToggleBtn.innerHTML = '<i class="fas fa-moon"></i>';
        localStorage.setItem('theme', 'light');
    }

    
    // Update icon based on current theme
    if (isDarkMode) {
        themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i>';
        localStorage.setItem('theme', 'dark');
    } else {
        themeToggleBtn.innerHTML = '<i class="fas fa-moon"></i>';
        localStorage.setItem('theme', 'light');
    }
});

// Check for saved theme preference
document.addEventListener('DOMContentLoaded', () => {
    // existing theme & init code ...
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i>';
    }
    
    // Load any existing transactions
    loadTransactions();
    
    // Hide all sections except the first one
    const sections = document.querySelectorAll('.section');
    sections.forEach((section, index) => {
        if (index !== 0) {
            section.style.display = 'none';
        }
    });

    // Initialize clear buttons on all inputs
    setupClearableInputs();
});

// Navigation links
const navLinks = document.querySelectorAll('.nav-link');
navLinks.forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Remove active class from all links
        navLinks.forEach(l => l.classList.remove('active'));
        
        // Add active class to clicked link
        this.classList.add('active');
        
        // Get the target section id from the href
        const targetId = this.getAttribute('href').substring(1);
        
        // Hide all sections
        document.querySelectorAll('.section').forEach(section => {
            section.style.display = 'none';
        });
        
        // Show the target section
        document.getElementById(targetId).style.display = 'block';
    });
});

// Clearable input setup
function setupClearableInputs() {
    const inputs = document.querySelectorAll('input[type="text"], input[type="search"]');
    inputs.forEach(input => {
        // Skip if already wrapped
        if (input.parentElement && input.parentElement.classList.contains('input-wrapper')) {
            return;
        }

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'input-wrapper';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        // Create clear button
        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'clear-btn';
        clearBtn.innerHTML = '&times;';
        wrapper.appendChild(clearBtn);

        // Show/hide button based on value
        const toggleBtn = () => {
            if (input.value) {
                clearBtn.style.display = 'block';
            } else {
                clearBtn.style.display = 'none';
            }
        };
        input.addEventListener('input', toggleBtn);
        // Initial state
        toggleBtn();

        // Clear logic
        clearBtn.addEventListener('click', () => {
            input.value = '';
            input.dispatchEvent(new Event('input')); // trigger other listeners
            toggleBtn();

            // Special handling for comment input to reset char count
            if (input.id === 'comment' && typeof commentCharCount !== 'undefined') {
                commentCharCount.textContent = '0';
                commentCharCount.style.color = 'var(--text-secondary)';
            }
        });
    });
}

// Utility to hide all clear (x) buttons after inputs are cleared/processed
function hideAllClearButtons() {
    document.querySelectorAll('.clear-btn').forEach(btn => {
        btn.style.display = 'none';
    });
}

// Ensure clear (×) buttons are hidden and comment counter reset when the form is cleared via the
// native “Clear form” button (type="reset").
transactionForm.addEventListener('reset', () => {
    // Hide any visible clear buttons
    hideAllClearButtons();

    // Reset the comment character counter and its color
    if (commentCharCount) {
        commentCharCount.textContent = '0';
        commentCharCount.style.color = 'var(--text-secondary)';
    }


});

// Character count for comment
commentInput.addEventListener('input', () => {
    const currentLength = commentInput.value.length;
    commentCharCount.textContent = currentLength;
    
    // Visual feedback as user approaches limit
    if (currentLength >= 200) {
        commentCharCount.style.color = 'var(--error-color)';
    } else {
        commentCharCount.style.color = 'var(--text-secondary)';
    }
});

// Form validation functions
function validateTransactions(value) {
    // Allow alphanumeric characters, commas, and spaces
    const regex = /^[a-zA-Z0-9, _-]+$/;
    
    if (!value.trim()) {
        showError(transactionsError, 'Transaction details are required');
        return false;
    }
    
    if (!regex.test(value)) {
        // Show the validation error in the submission status area instead of next to the input
        submissionStatus.innerHTML = '<strong>Error:</strong> Only alphanumeric characters, commas, and spaces are allowed';
        submissionStatus.className = 'submission-status error';
        submissionStatus.style.display = 'block';
        // Ensure the inline error is cleared
        hideError(transactionsError);
        return false;
    }

    // Hide any previous status error if validation now passes
    submissionStatus.style.display = 'none';
    hideError(transactionsError);
    return true;
}

function validateComment(value) {
    // Check if comment is empty
    if (!value.trim()) {
        showError(commentError, 'Comment is required');
        return false;
    }
    
    // Check for SQL injection patterns
    const sqlPatterns = /('|\"|;|--|\/\*|\*\/|exec|union|select|insert|update|delete|drop|alter)/i;
    
    if (value.length > 250) {
        showError(commentError, 'Comment must be less than 250 characters');
        return false;
    }
    
    if (sqlPatterns.test(value)) {
        showError(commentError, 'Comment contains invalid characters');
        return false;
    }
    
    hideError(commentError);
    return true;
}

function validateAction(value) {
    const validActions = ['STP-Release', 'Release', 'Block', 'Reject'];
    
    if (!value || !validActions.includes(value)) {
        showError(actionError, 'Please select a valid action');
        return false;
    }
    
    hideError(actionError);
    return true;
}

// Helper functions for error display
function showError(element, message) {
    element.textContent = message;
    element.classList.add('visible');
}

function hideError(element) {
    element.textContent = '';
    element.classList.remove('visible');
}

function validateTransactionType(value) {
    if (!value) {
        showError(transactionTypeError, 'Please select a transaction type');
        return false;
    }
    if (value === '' || value === 'Not defined') {
        showError(transactionTypeError, 'Please select a valid transaction type');
        return false;
    }
    hideError(transactionTypeError);
    return true;
}

// Form submission
transactionForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Get form values
    let transactionsValue = transactionsInput.value;
    // Remove tabs and non-visible whitespace except spaces
    transactionsValue = transactionsValue.replace(/[\s\u200B-\u200D\uFEFF\t\n\r\f\v]+/g, ' ');
    transactionsValue = transactionsValue.replace(/ +/g, ' ').trim();
    let commentValue = commentInput.value.trim();
    if (!commentValue) {
        commentValue = 'MURDOCK';
    }
    const rawActionValue = actionSelect.value;
    const transactionTypeValue = transactionTypeSelect.value;

    // Validate all fields
    const isTransactionsValid = validateTransactions(transactionsValue);
    const isCommentValid = validateComment(commentValue);
    const isActionValid = validateAction(rawActionValue);
    const isTransactionTypeValid = validateTransactionType(transactionTypeValue);

    // If all validations pass
    if (isTransactionsValid && isCommentValid && isActionValid && isTransactionTypeValid) {
        // After validation, map Release to STP-Release for processing
        const actionValue = rawActionValue === 'Release' ? 'STP-Release' : rawActionValue;
        try {
            // Disable submit button and show loading state
            const submitButton = transactionForm.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.textContent = 'Processing...';
            
            // Show status message
            submissionStatus.innerHTML = 'Processing transactions...';
            submissionStatus.className = 'submission-status info';
            submissionStatus.style.display = 'block';
            
            // Parse transactions (comma-separated values)
            const transactionsArray = transactionsValue.split(',').map(t => t.trim()).filter(t => t);
            
            // Cache stored transactions for lookup
            const storedTxns = JSON.parse(localStorage.getItem('transactions') || '[]');
            const noActionLocal = [];
            
            let successCount = 0;
            let failCount = 0;
            let failedTransactions = [];
            let succeededTransactions = [];
            
            for (const txn of transactionsArray) {
                // Check if this transaction was previously processed
                // Normalized compare (case-insensitive & trimmed) to detect duplicates reliably
                const normalizedTxn = txn.trim().toLowerCase();
                const saved = storedTxns.find(t => {
                    const tTxn = t.transaction ? t.transaction.trim().toLowerCase() : '';
                    const tid = t.transactionId ? t.transactionId.trim().toLowerCase() : '';
                    return tTxn === normalizedTxn || tid === normalizedTxn;
                });
                
                // Duplicate detected – log attempt but take no action
                if (saved) {
                    saveTransaction({
                        transaction: txn,
                        comment: commentValue,
                        action: actionValue,
                        timestamp: Date.now(),
                        status: 'No action',
                        status_detail: 'already_handled',
                        statusMessage: 'Already handled'
                    });
                    noActionLocal.push(txn);
                    continue;
                }
                
                // Validate each transaction again for safety
                if (!validateTransactions(txn)) {
                    failCount++;
                    failedTransactions.push({txn, error: 'Invalid transaction format'});
                    continue;
                }
                
                const data = {
                    transaction: txn,
                    comment: commentValue,
                    action: actionValue,
                    transaction_type: transactionTypeValue,
                    timestamp: Date.now(),
                    performOnLatest: true
                };
                
                try {
                    const response = await sendTransactionToServer(data);
                    
                    // Handle network errors or server errors
                    if (response.status_detail === 'network_error' || !response.success) {
                        throw new Error(response.message || 'Transaction processing failed');
                    }
                    
                    // Check specifically for not-found status regardless of success flag
                    if (response.status_detail === 'transaction_not_found_in_any_tab') {
                        // Even though backend considers this "successful automation", treat as failure in UI
                        saveTransaction({
                            transaction: txn,
                            comment: commentValue,
                            action: actionValue,
                            timestamp: data.timestamp,
                            status: 'failed',
                            status_detail: response.status_detail,
                            statusMessage: response.message || 'Transaction not found in any tab',
                            errorCode: response.errorCode
                        });
                        failCount++;
                        failedTransactions.push({txn, error: 'Transaction not found in any tab'});
                        continue;
                    }
                    
                    // If we get here, the transaction was successful
                    saveTransaction({
                        transaction: txn,
                        comment: commentValue,
                        action: actionValue,
                        timestamp: data.timestamp,
                        status: response.status_detail || 'success',
                        status_detail: response.status_detail || 'success',
                        statusMessage: response.message,
                        transactionId: response.transactionId
                    });
                    successCount++;
                    succeededTransactions.push(txn);
                    
                } catch (error) {
                    // Handle network errors or other exceptions
                    console.error('Error processing transaction:', txn, error);
                    const errorMessage = error.message || 'Failed to process transaction';
                    saveTransaction({
                        transaction: txn,
                        comment: commentValue,
                        action: actionValue,
                        timestamp: data.timestamp,
                        status: 'failed',
                        status_detail: 'network_error',
                        statusMessage: errorMessage,
                        errorCode: 'NETWORK_ERROR'
                    });
                    failCount++;
                    failedTransactions.push({txn, error: errorMessage});
                }
            }
            // Show summary message
            let summary = `<strong>Processed ${transactionsArray.length} transaction(s):</strong> <br>`;
            summary += `<span class='success'>${successCount} succeeded</span>, <span class='error'>${failCount} failed</span>`;
            if (failCount > 0) {
                summary += '<br>Failed: ' + failedTransactions.map(f => `${escapeHtml(f.txn)} (${escapeHtml(f.error)})`).join(', ');
            }
            // Determine if any 'not found' for styling
            const hasNotFoundTransactions = transactionsArray.some(txn => {
                const normalizedTxn2 = txn.trim().toLowerCase();
                const savedTxn = storedTxns.find(t => {
                    const tTxn2 = t.transaction ? t.transaction.trim().toLowerCase() : '';
                    const tid2 = t.transactionId ? t.transactionId.trim().toLowerCase() : '';
                    return tTxn2 === normalizedTxn2 || tid2 === normalizedTxn2;
                });
                return savedTxn && savedTxn.status_detail === 'transaction_not_found_in_any_tab';
            });
            // If all transactions were skipped (no success/fail), show no-action only
            if (noActionLocal.length === transactionsArray.length && successCount === 0 && failCount === 0) {
                submissionStatus.innerHTML = `No action taken on transaction${noActionLocal.length > 1 ? 's' : ''} ${noActionLocal.join(', ')}. Found in Transactions History tab.`;
                submissionStatus.className = 'submission-status no-action';
                submissionStatus.style.display = 'block';
            } else {
                submissionStatus.innerHTML = summary;
                submissionStatus.className = (failCount === 0 && !hasNotFoundTransactions)
                    ? 'submission-status success'
                    : 'submission-status error';
                submissionStatus.style.display = 'block';
            }
            
            // Reset form
            transactionForm.reset();
            hideAllClearButtons();
            commentCharCount.textContent = '0';
            
            // Update table
            loadTransactions();
            
            // Re-enable submit button
            submitButton.disabled = false;
            submitButton.textContent = 'Process Transaction';
            
            // Clear status message after 7 seconds for success, 10 seconds for errors
            const clearTimeout = failCount === 0 ? 7000 : 10000;
            setTimeout(() => {
                submissionStatus.style.display = 'none';
            }, clearTimeout);
        } catch (error) {
            // Show error message
            submissionStatus.innerHTML = `<strong>System Error:</strong> ${error.message}`;
            submissionStatus.className = 'submission-status error';
            console.error('Submission error:', error);
            
            // Re-enable submit button
            const submitButton = transactionForm.querySelector('button[type="submit"]');
            submitButton.disabled = false;
            submitButton.textContent = 'Process Transaction';
        }
    }
});

// Function to create and download a text file (keeping for reference)
function createAndDownloadFile(filename, content) {
    // Create a blob with the file content
    const blob = new Blob([content], { type: 'text/plain' });
    
    // Create a URL for the blob
    const url = URL.createObjectURL(blob);
    
    // Create a temporary link element
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    
    // Append to the document
    (link);
    
    // Trigger the download
    link.click();
    
    // Clean up
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// Simulate server submission (in a real app, this would be an API call)
async function simulateServerSubmission(data) {
    return new Promise(resolve => {
        // Simulate network delay
        setTimeout(() => {
            resolve({
                success: true,
                message: 'Transaction processed successfully',
                data: data
            });
        }, 1000);
    });
}

// New function to send transaction data to the server
async function sendTransactionToServer(data) {
    try {
        // Use the actual server endpoint
        // Use relative URL to work regardless of host/port
const API_URL = (window.location.origin && window.location.origin !== 'null' && window.location.origin !== '')
  ? window.location.origin + '/api'
  : 'http://localhost:5000/api';
const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        
        const responseData = await response.json();
        return {
            success: responseData.success, // Overall success boolean
            message: responseData.message, // Detailed message for tooltip
            status_detail: responseData.status_detail, // Specific status string from backend
            transactionId: responseData.transactionId,
            errorCode: responseData.errorCode // Ensure errorCode is passed through
        };
        
        // Use mock function for testing if server is unavailable
        // return await mockProcessTransaction(data);
    } catch (error) {
        console.error('Error sending transaction:', error);
        return {
            success: false,
            message: `Failed to process transaction: ${error.message}`,
            status_detail: 'network_error' // Or some other indicator for client-side failure
        };
    }
}

// Mock function that sometimes succeeds and sometimes fails (for testing)
async function mockProcessTransaction(data) {
    return new Promise(resolve => {
        // Simulate network delay (between 500ms and 1500ms)
        const delay = Math.floor(Math.random() * 1000) + 500;
        
        setTimeout(() => {
            // Randomly succeed or fail (70% success rate)
            const isSuccess = Math.random() < 0.7;
            
            if (isSuccess) {
                resolve({
                    success: true,
                    message: 'Transaction processed successfully',
                    data: data,
                    transactionId: `TXN-${Math.floor(Math.random() * 10000)}`
                });
            } else {
                // Generate different types of errors
                const errorTypes = [
                    'Transaction validation failed',
                    'Server processing error',
                    'Database connection timeout',
                    'Invalid transaction format'
                ];
                const errorMessage = errorTypes[Math.floor(Math.random() * errorTypes.length)];
                
                resolve({
                    success: false,
                    message: errorMessage,
                    errorCode: Math.floor(Math.random() * 100) + 400
                });
            }
        }, delay);
    });
}

// Local storage functions for transactions
function saveTransaction(transaction) {
    let transactions = JSON.parse(localStorage.getItem('transactions') || '[]');
    transactions.push(transaction);
    localStorage.setItem('transactions', JSON.stringify(transactions));
}

function loadTransactions() {
    let transactions = JSON.parse(localStorage.getItem('transactions') || '[]');
    // Sanitize stored data: remove any non-object or undefined entries
    transactions = transactions.filter(t => t && typeof t === 'object');
    
    // Apply filters if any
    const actionFilter = filterAction.value;
    const actionFilterLower = actionFilter.toLowerCase();
    const searchFilter = searchTransactions.value.toLowerCase();
    
    if (actionFilterLower) {
        // Case-insensitive substring match on action
        transactions = transactions.filter(
            t => t && typeof t.action === 'string' && t.action.toLowerCase().includes(actionFilterLower)
        );
    }
    
    if (searchFilter) {
        transactions = transactions.filter(t => 
            t.transaction.toLowerCase().includes(searchFilter) || 
            (t.comment && t.comment.toLowerCase().includes(searchFilter))
        );
    }
    
    // Sort by timestamp (newest first)
    transactions.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    // Clear table
    transactionsTableBody.innerHTML = '';
    
    // If no transactions, show message
    if (transactions.length === 0) {
        const noDataRow = document.createElement('tr');
        noDataRow.className = 'no-data';
        noDataRow.innerHTML = '<td colspan="5">No transaction data available</td>';
        transactionsTableBody.appendChild(noDataRow);
        return;
    }
    
    // Populate table
    transactions.forEach(transaction => {
        const row = document.createElement('tr');
        
        const date = new Date(transaction.timestamp);
        const formattedDate = date.toLocaleString();
        
        let statusHtml = '';
        let statusText = 'Unknown'; // Default text
        let statusClass = 'status-badge'; // Base class

        // Determine status display based on detailed status
        switch (transaction.status) {
            case 'No action':
                statusText = 'No action';
                statusClass += ' no-action'; // Light blue for no action
                break;
            case 'action_performed_on_live':
                statusText = 'Success';
                statusClass += ' success-live'; // Happy path green
                break;
            case 'escalated':
                statusText = 'Escalated';
                statusClass += ' success-escalated'; // Distinct success color for escalated
                break;
            case 'already_handled': // History
                statusText = 'No action';
                statusClass += ' no-action'; // Light blue for no action
                break;
            case 'found_in_bpm':
                statusText = 'No action';
                statusClass += ' no-action'; // Light blue for no action
                break;
            case 'found_in_sanctions_bypass':
                statusText = 'Success';
                statusClass += ' success-sanctions'; // Gradient green + color for sanctions bypass
                break;
            case 'transaction_not_found_in_any_tab':
                statusText = 'Failed';
                statusClass += ' error';
                break;
            case 'failed':
                statusText = 'Failed';
                statusClass += ' error'; // Existing error class
                break;
            default: // Fallback for older data or unexpected statuses
                statusText = 'Success'; // Or 'Info'
                statusClass += ' success'; // Default success color
                break;
        }

        let tooltip = '';
        if (transaction.statusMessage) {
            tooltip = escapeHtml(transaction.statusMessage);
        } else if (transaction.status === 'No action' || 
                  transaction.status === 'already_handled' || 
                  transaction.status === 'found_in_bpm') {
            tooltip = 'Transaction was found in history or BPM';
        }
        if (transaction.status === 'failed' && transaction.errorCode) {
            tooltip += (tooltip ? ' | ' : '') + `Error code: ${escapeHtml(transaction.errorCode)}`;
        }
        
        statusHtml = `<span class='${statusClass}'${tooltip ? ` data-tooltip='${tooltip}'` : ''}>${escapeHtml(statusText)}</span>`;
        
        row.innerHTML = `
            <td>${formattedDate}</td>
            <td>${escapeHtml(transaction.transaction)}</td>
            <td>${escapeHtml(transaction.comment || '')}</td>
            <td>${escapeHtml(transaction.action)}</td>
            <td>${statusHtml}</td>
        `;
        
        transactionsTableBody.appendChild(row);
    });
}

// Security: Escape HTML to prevent XSS
function escapeHtml(unsafe) {
    if (unsafe === undefined || unsafe === null) {
        return '';
    }
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Filter and search functionality
filterAction.addEventListener('change', loadTransactions);
searchTransactions.addEventListener('input', loadTransactions);



    
    