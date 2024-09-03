import imaplib
import email
from email.header import decode_header
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import re
import psycopg2  # PostgreSQL adapter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HtmlContentException(Exception):
    pass

class TransactionDetail:
    def __init__(self, amount, card, location, date, hour, bank_id=None):
        self.amount = amount
        self.card = card
        self.location = location
        self.date = date
        self.hour = hour
        self.bank_id = bank_id

    def set_bank_id(self, bank_id):
        self.bank_id = bank_id

    def __str__(self):
        return (f"Amount: {self.amount}, Card: {self.card}, Location: {self.location}, "
                f"Date: {self.date}, Hour: {self.hour}, Bank ID: {self.bank_id}")

class TransactionParser:
    BANCO_DE_CHILE_BANK_ID = "1"

    def retrieve_transaction(self, html):
        content = self.extract_content(html)
        transaction_detail = self.extract_transaction(content)
        transaction_detail.set_bank_id(self.BANCO_DE_CHILE_BANK_ID)
        return transaction_detail

    def extract_content(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        transaction_details = soup.find_all(string=re.compile(r"Te informamos que se ha realizado una compra"))

        if not transaction_details:
            raise HtmlContentException("Transaction details not found in the HTML content.")

        return transaction_details[0].parent.get_text(strip=True)

    def extract_transaction(self, content):
        regex = r"(?<=por )\$(\d+\.\d+).*?(\*{4}\d{4}) en (.*?)(?= el) el (\d{2}/\d{2}/\d{4}) (\d{2}:\d{2})"
        pattern = re.compile(regex)
        matcher = pattern.search(content)
        if matcher:
            amount = int(matcher.group(1).replace(".", ""))
            card = matcher.group(2)
            location = matcher.group(3)
            date = matcher.group(4)
            hour = matcher.group(5)

            # Clean up the location by replacing multiple spaces with a single space
            location = re.sub(r'\s+', ' ', location.strip())

            return TransactionDetail(amount, card, location, date, hour)
        else:
            return TransactionDetail(0, "", "", "", "")


def insert_transaction_to_db(transaction, conn):
    """Insert a transaction into the PostgreSQL database."""
    with conn.cursor() as cur:
        insert_query = """
            INSERT INTO credit_transactions (amount, card_last_digits, location, date, hour, bank_id)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        # Convert empty strings to None for nullable fields
        amount = transaction.amount if transaction.amount != 0 else None
        card_last_digits = transaction.card if transaction.card else None
        location = transaction.location if transaction.location else None
        date = transaction.date if transaction.date else None
        hour = transaction.hour if transaction.hour else None
        bank_id = transaction.bank_id if transaction.bank_id else None
        
        # Debugging output
        logging.info(f"Extracted data - Amount: {amount}, Card: {card_last_digits}, Location: {location}, Date: {date}, Hour: {hour}, Bank ID: {bank_id}")

        # Only insert if mandatory fields (e.g., amount, date, and card_last_digits) are not None
        if amount and date and card_last_digits:
            cur.execute(insert_query, (
                amount, 
                card_last_digits, 
                location, 
                date, 
                hour, 
                bank_id
            ))
            conn.commit()
        else:
            logging.warning("Skipping insertion due to missing mandatory fields.")


# Load credentials
logging.info("Loading credentials from the YAML file.")

user, password = "sergio.lagos@mail.udp.cl", "dqlw uwjq phry rbzr"

# URL for IMAP connection
imap_url = 'imap.gmail.com'

# Connection with GMAIL using SSL
logging.info("Connecting to Gmail IMAP server.")
my_mail = imaplib.IMAP4_SSL(imap_url)

# Log in using your credentials
logging.info("Logging into Gmail account.")
my_mail.login(user, password)

# Select the Inbox to fetch messages
logging.info("Selecting 'Inbox'.")
my_mail.select('Inbox')

# Define the date since August 1, 2024, in the format DD-Mon-YYYY
since_date = '30-Aug-2024'
logging.info(f"Fetching emails since {since_date} from the specified sender.")

# Define Key and Value for email search
key = 'FROM'
value = 'enviodigital@bancochile.cl'
# Perform a basic search by sender and date, ignoring the subject for now
_, data = my_mail.search(None, f'({key} "{value}")', f'SINCE {since_date}')

mail_id_list = data[0].split()  # IDs of all emails that match the criteria

logging.info(f"Found {len(mail_id_list)} emails matching the criteria.")

msgs = []  # Empty list to capture all messages

parser = TransactionParser()

# PostgreSQL connection details
db_host = "aws-0-us-west-1.pooler.supabase.com"
db_port = 6543
db_name = "postgres"
db_user = "postgres.wecshjdatgvaquwvcmjk"
db_password = "Sergioelias123#"

# Connect to the PostgreSQL database
logging.info("Connecting to PostgreSQL database.")
conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password
)

# Iterate through messages and fetch them
logging.info("Fetching email headers and bodies.")
for num in mail_id_list[:50]:  # Limiting to the first 50 emails for performance
    typ, data = my_mail.fetch(num, '(RFC822)')
    msg = email.message_from_bytes(data[0][1])

    # Decode the subject
    subject, encoding = decode_header(msg['subject'])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or 'utf-8')

    # Manually filter the emails by subject in Python
    if 'Compra con Tarjeta de Crédito' in subject:
        msgs.append((msg, subject))

logging.info(f"Filtered to {len(msgs)} emails with the correct subject.")

# Process and print the subject, sender, and body of the filtered emails
logging.info("Processing and inserting email transactions into the database.")
for msg, subject in msgs[::-1]:
    logging.info(f"Processing email from {msg['from']} with subject: {subject}")
    print("_________________________________________")
    print("subj:", subject)
    print("from:", msg['from'])
    print("body:")
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            html_content = part.get_payload(decode=True).decode('utf-8')
            try:
                transaction_detail = parser.retrieve_transaction(html_content)

                # Insert transaction into the database
                insert_transaction_to_db(transaction_detail, conn)
            except HtmlContentException as e:
                logging.error(f"Error processing HTML content: {e}")
        elif part.get_content_type() == 'text/plain':
            print(part.get_payload(decode=True).decode('utf-8'))

logging.info("Email fetching and processing completed.")

# Close the database connection
conn.close()
logging.info("Database connection closed.")
