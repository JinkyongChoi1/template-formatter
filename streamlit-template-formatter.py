
import os
import sys
import json
import re
from pathlib import Path

import streamlit as st

# Install required packages before imports
try:
    import google
except ImportError:
    st.error("Installing required packages...")
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2")
    st.rerun()

# Now import Google packages
from google.oauth2 import service_account
from googleapiclient.discovery import build


# Configuration - Change these values to your Google Sheet
SPREADSHEET_ID = "1_DiX8jgahLhkLmIIEXXkOlTMkXMYyf1hj3FRRodS8RQ"  # Extract from your Google Sheets URL
SHEET_NAME = "Templates"  # Name of the sheet tab
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


# Path for credentials (this will be handled differently in Streamlit Cloud)
CREDENTIALS_PATH = Path("service_account.json")

# Set page configuration
st.set_page_config(
    page_title="Template Formatter",
    page_icon="📝",
    layout="wide"
)

# Function to get Google Sheets service
@st.cache_resource
def get_sheets_service():
    """Get Google Sheets API service using service account credentials."""
    try:
        # For local development, use the service account file
        if CREDENTIALS_PATH.exists():
            credentials = service_account.Credentials.from_service_account_file(
                CREDENTIALS_PATH, scopes=SCOPES)
            service = build('sheets', 'v4', credentials=credentials)
            return service
        # For Streamlit Cloud, use secrets
        elif 'google_credentials' in st.secrets:
            credentials_dict = st.secrets["google_credentials"]
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict, scopes=SCOPES)
            service = build('sheets', 'v4', credentials=credentials)
            return service
        else:
            st.error("Google credentials not found. Please check setup instructions.")
            return None
    except Exception as e:
        st.error(f"Error setting up Google Sheets API: {e}")
        return None

# Function to fetch templates from Google Sheet
@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_templates_from_sheet():
    """Fetch templates from Google Sheet."""
    try:
        service = get_sheets_service()
        if not service:
            return {}
            
        sheet = service.spreadsheets()
        
        # Get the range that contains our data
        range_name = f"{SHEET_NAME}!A:B"
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = result.get('values', [])
        
        templates = {}
        if not values:
            st.warning("No data found in sheet.")
            return templates
            
        # Skip the header row if it exists
        start_row = 1 if values[0][0].lower() in ['name', 'template name', 'template'] else 0
        
        # Process each row
        for row in values[start_row:]:
            if len(row) >= 2:  # Make sure we have both name and template
                template_name = row[0].strip()
                template_content = row[1]
                templates[template_name] = template_content
                
        return templates
        
    except Exception as e:
        st.error(f"Error fetching templates: {e}")
        return {}

# Function to save a template to Google Sheet
def save_template_to_sheet(name, content):
    """Save a template to Google Sheet."""
    try:
        if not name or not content:
            return False, "Template name and content are required."
            
        service = get_sheets_service()
        if not service:
            return False, "Google Sheets service not available."
            
        sheet = service.spreadsheets()
        
        # Check if template with this name already exists
        templates = get_templates_from_sheet()
        
        # Get the next available row
        range_name = f"{SHEET_NAME}!A:B"
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = result.get('values', [])
        next_row = len(values) + 1
        
        # If template exists, update it
        if name in templates:
            # Find the row with this template name
            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == name:
                    row_num = i + 1  # Sheets API uses 1-based indexing
                    update_range = f"{SHEET_NAME}!B{row_num}"
                    
                    # Update the template content
                    request = sheet.values().update(
                        spreadsheetId=SPREADSHEET_ID,
                        range=update_range,
                        valueInputOption="RAW",
                        body={"values": [[content]]}
                    )
                    request.execute()
                    st.cache_data.clear()  # Clear cache to refresh templates
                    return True, f"Template '{name}' updated successfully."
        
        # Otherwise, add a new row
        append_range = f"{SHEET_NAME}!A:B"
        request = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=append_range,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [[name, content]]}
        )
        request.execute()
        st.cache_data.clear()  # Clear cache to refresh templates
        return True, f"Template '{name}' saved successfully."
        
    except Exception as e:
        return False, f"Error saving template: {e}"

# Function to extract variables from template
def extract_variables(template):
    """Extract variables from template text using regex."""
    variables = set()
    pattern = r'{{([^}]+)}}'
    matches = re.findall(pattern, template)
    for match in matches:
        variables.add(match.strip())
    return variables

# Function to format template
def format_template(template_text, variables_dict):
    """Replace variables in template with their values."""
    formatted = template_text
    for var_name, var_value in variables_dict.items():
        placeholder = '{{' + var_name + '}}'
        formatted = formatted.replace(placeholder, var_value)
    return formatted

# Main app layout
def main():
    st.title("📝 Template Formatter")
    
    # Connection details
    with st.expander("Google Sheets Connection", expanded=False):
        st.info(f"Connected to spreadsheet: {SPREADSHEET_ID}")
        st.info(f"Sheet tab: {SHEET_NAME}")
        if st.button("Refresh Templates"):
            st.cache_data.clear()
            st.rerun()
    
    # Get templates
    templates = get_templates_from_sheet()
    
    # Split the app into two columns
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("Template Selection & Editing")
        
        # Template selection
        template_names = list(templates.keys())
        if template_names:
            selected_template = st.selectbox(
                "Choose a template:", 
                options=[""] + template_names,
                index=0
            )
        else:
            selected_template = ""
            st.warning("No templates found. Add a new template below.")
        
        # Template editing
        if selected_template:
            template_text = templates.get(selected_template, "")
        else:
            template_text = ""
            
        template_content = st.text_area(
            "Template (use {{variable_name}} for variables):", 
            value=template_text,
            height=200
        )
        
        # Save template section
        st.subheader("Save Template")
        save_col1, save_col2 = st.columns([3, 1])
        
        with save_col1:
            new_template_name = st.text_input("Template name:", 
                                            value=selected_template)
        
        with save_col2:
            if st.button("Save to Sheets", type="primary"):
                if new_template_name and template_content:
                    success, message = save_template_to_sheet(
                        new_template_name, template_content)
                    if success:
                        st.success(message)
                        st.rerun()  # Refresh the page to show updated templates
                    else:
                        st.error(message)
                else:
                    st.error("Please enter both template name and content.")
    
    with col2:
        st.subheader("Format Template")
        
        # Extract variables
        variables = extract_variables(template_content)
        
        if not variables:
            st.info("No variables found in the template. Add variables using {{variable_name}} syntax.")
        
        # Variable inputs
        st.write("Enter values for variables:")
        
        # Create a dictionary to store variable values
        var_values = {}
        
        # Create input fields for each variable
        for var in variables:
            var_values[var] = st.text_input(f"{var}:", key=f"var_{var}")
        
        # Add custom variable
        with st.expander("Add custom variable", expanded=False):
            custom_var_name = st.text_input("Variable name:")
            custom_var_value = st.text_input("Variable value:")
            if st.button("Add Variable"):
                if custom_var_name:
                    var_values[custom_var_name] = custom_var_value
                    st.rerun()
        
        # Format button
        if st.button("Format Template", type="primary"):
            if template_content:
                result = format_template(template_content, var_values)
                st.subheader("Result:")
                st.text_area("Formatted Output:", value=result, height=200)
                
                # Copy button (uses JavaScript)
                st.markdown(
                    """
                    <script>
                    function copyToClipboard(text) {
                        navigator.clipboard.writeText(text).then(function() {
                            alert('Copied to clipboard!');
                        });
                    }
                    </script>
                    """,
                    unsafe_allow_html=True
                )
                
                st.button(
                    "Copy to Clipboard",
                    on_click=lambda: st.markdown(
                        f"""
                        <script>
                        copyToClipboard(`{result}`);
                        </script>
                        """,
                        unsafe_allow_html=True
                    ),
                    help="Copy formatted text to clipboard"
                )
            else:
                st.error("Please select or enter a template.")

if __name__ == "__main__":
    main()