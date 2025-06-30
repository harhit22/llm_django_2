import gspread
from google.oauth2.service_account import Credentials

def upload_to_google_sheet(results, sheet_name="Dustbin Report"):
    # Define the scope
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # Load credentials
    creds = Credentials.from_service_account_file(
        "path/to/your/credentials.json", scopes=scope
    )
    client = gspread.authorize(creds)

    # Create or open spreadsheet
    spreadsheet = client.create(sheet_name)

    # Share sheet publicly or with a specific user
    spreadsheet.share('target-email@gmail.com', perm_type='user', role='writer')  # or role='reader'

    # Select the first worksheet
    sheet = spreadsheet.sheet1

    # Prepare headers
    headers = list(results[0].keys())
    sheet.append_row(headers)

    # Fill rows
    for item in results:
        row = [item.get(h, "") for h in headers]
        sheet.append_row(row)

    return spreadsheet.url
