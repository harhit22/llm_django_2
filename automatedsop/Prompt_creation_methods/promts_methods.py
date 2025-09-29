import json
from ..services.gemini_service import GeminiService
def load_sop_rules(sop_file):
    try:
        with open(sop_file, "r", encoding="utf-8") as file:
            sop_rules = json.load(file)
        return sop_rules
    except Exception as e:
        print(f"Error loading SOP rules: {e}")
        return []

def ask_question_fe(filtered_data, sop_detail, sop_file="sops/translated_output04.json"):
    """
    Constructs a prompt using filtered data, SOP rules, and the user question,
    then sends it to Gemini.
    """
    # Convert filtered data to a JSON string
    data_str = json.dumps(filtered_data, indent=4)

    # Load SOP rules
    sop_rules = load_sop_rules(sop_file)
    sop_str = json.dumps(sop_rules, indent=4) if sop_rules else "No SOP rules available."
    # print(sop_str, "eee")
    # print(data_str)
    print(sop_detail)

    # Construct the prompt
    prompt = f"""
    You are an expert in Operations and SOP (Standard Operating Procedure) Compliance Analysis.

    Your task is to:
    1. Analyze the attendance data *line by line*.
    2. Apply *each SOP rule strictly*.
    3. Return only the entries that are *non-compliant, clearly stating **which SOP rule(s)* were violated.
    4. winter september to april are winter month 

    ---

    ### SOP Rules:
    {str(sop_detail)}

    ### Filtered Attendance Data:
    {str(data_str)}

    ---

    ### Output Format:
    Answer in json format.
    [
      {{
        "Employee ID": "...",
        "Employee Name": "...",
        "Date": "...",
        "In-Time": "...",
        "Out-Time": "...",
        "Total working hours": "" # calculate based on in and out time
        "Violation": ".." which sops is violated give all 
      }},
      ...
    ]

    Only return entries that have any kind of SOP violation.
    Be precise, do not skip any rule, and avoid unnecessary explanation.
    """
    return GeminiService.call_api(prompt)


def ask_question(filtered_data, sop_detail, sop_file="sops/translated_output04.json"):
    print('i am called')
    """
    Constructs a prompt using filtered data, SOP rules, and the user question,
    then sends it to Gemini.
    """
    # Convert filtered data to a JSON string
    data_str = json.dumps(filtered_data, indent=4)

    # Load SOP rules
    sop_rules = load_sop_rules(sop_file)
    sop_str = json.dumps(sop_rules, indent=4) if sop_rules else "No SOP rules available."
    # print(sop_str, "eee")
    # print(data_str)

    # Construct the prompt
    prompt = f"""
        You are an expert in Operations and SOP (Standard Operating Procedure) Compliance Analysis.

        Your task is to:
        1. Analyze the attendance and work details data line by line.
        2. Apply each SOP rule strictly.
        3. Return only the entries that are non-compliant, clearly stating **which SOP rule(s) were violated.
        4. Winter months are from September to April.

        ---

        ### SOP Rules:
        {str(sop_detail)}

        ### Filtered Attendance Data:
        {str(data_str)}

        ### Work Details Data (Extracted from Firebase):
        {{
            "Date": "YYYY-MM-DD",  # Work date in YYYY-MM-DD format
            "Employee ID": "...",  # Employee ID
            "Employee Name": "...",  # Employee Name
            "Arrival Time": "HH:MM:SS",  # Time when the employee arrived
            "Departure Time": "HH:MM:SS",  # Time when the employee left
            "employee mobile number":"..."

            # Add any other relevant fields as per the structure you expect from Firebase
        }}

        ---
        do not add ```json in the start
        ### Output Format:
        [
          {{
            "Employee ID": "...",
            "Employee Name": "...",
            "Date": "...",
            "Arrival Time": "HH:MM:SS",
            "Departure Time": "HH:MM:SS",
            "employee mobile number":"..."

            "Violation": "...",  # Full explanation of all SOP rules that were broken, with timestamps if necessary
          }},
          ...
        ]

        Only return entries that have any kind of SOP violation.
        Be precise, avoid unnecessary explanation.
    """
    return GeminiService.call_api(prompt)