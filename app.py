from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

# --- Blocklist (ये शब्द कभी भी Value नहीं हो सकते) ---
BAD_WORDS = ["Car Insurance", "Bike Insurance", "VahanX", "Policy", "Quote", "Search", "Menu", "Home", "Download", "Verified", "Pending", "Paid", "Online", "Status"]

def clean(text):
    if not text: return None
    # Remove colons, dashes, extra spaces
    cleaned = re.sub(r'[:\-\t]', '', text).strip()
    # Remove extra internal spaces (e.g. "Name   Surname" -> "Name Surname")
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned

def is_valid(value, key_type="text"):
    if not value or len(value) < 2: return False
    
    # Check against Bad Words
    for word in BAD_WORDS:
        if word.lower() in value.lower():
            return False

    # Special Validation for Owner Name (Should not contain digits like PB10)
    if key_type == "name":
        if re.search(r'\d', value): # Agar number hai to reject karo
            return False
            
    # Special Validation for Phone
    if key_type == "phone":
        if "+91" not in value and len(value) < 10:
            return False

    return True

def get_challan_count(session, rc_number):
    url = f"https://vahanx.in/challan-search/{rc_number}"
    try:
        response = session.get(url, headers=HEADERS, timeout=10)
        text = BeautifulSoup(response.text, 'html.parser').get_text()
        match = re.search(r"eChallan\s*\((\d+)\)", text)
        if match: return match.group(1)
        if "No Challan Found" in text: return "0"
        return "0"
    except:
        return "Error"

@app.route('/')
def home():
    return "Server is Running! (Fixed Version)"

@app.route('/vehicle-info', methods=['GET'])
def vehicle_info():
    rc = request.args.get('rc')
    if not rc: return jsonify({"error": "RC Required"}), 400

    session = requests.Session()
    final_data = {"rc": rc, "details": {}}

    try:
        url = f"https://vahanx.in/rc-search/{rc}"
        response = session.get(url, headers=HEADERS, timeout=15)
        
        if "No Record Found" in response.text:
            return jsonify({"error": "No Record Found"}), 404

        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(separator="\n")

        # === 1. DOM SEARCH (High Priority) ===
        # Pehle HTML tags (cards/tables) me dhundo, ye sabse accurate hota hai
        cards = soup.find_all(class_=['hrcd-cardbody', 'row', 'detail-row'])
        for card in cards:
            text = card.get_text(separator="|")
            if ":" in text or "|" in text:
                parts = re.split(r'[:|]', text)
                if len(parts) >= 2:
                    k = clean(parts[0])
                    v = clean(parts[1])
                    if is_valid(v):
                        # Standardize Keys
                        if "Owner" in k and "Name" in k: final_data["details"]["Owner Name"] = v
                        elif "Father" in k: final_data["details"]["Father Name"] = v
                        elif "Mobile" in k or "Phone" in k: final_data["details"]["Phone"] = v
                        elif "Model" in k: final_data["details"]["Model Name"] = v

        # === 2. REGEX SEARCH (Backup with Validation) ===
        # Agar DOM se nahi mila, to Text Regex use karo par Strict Validation ke sath
        patterns = {
            # Name me numbers allowed nahi hain (To avoid PB10 match)
            "Owner Name": (r"(?:Owner Name|Owner's Name)[\s:]+([a-zA-Z\s\.]+)", "name"),
            "Father Name": (r"(?:Father Name|Father's Name|S/O|W/O)[\s:]+([a-zA-Z\s\.]+)", "name"),
            "Phone": (r"(?:Phone|Mobile)[\s:]+(\+91[\d\-\s]+)", "phone"),
            "Address": (r"(?:Address|Permanent Address)[\s:]+([^\n]+)", "text"),
            "Model Name": (r"(?:Model Name|Maker Model)[\s:]+([^\n]+)", "text"),
            "Registration Date": (r"(?:Registration Date)[\s:]+([\d\-\w]+)", "text"),
            "Chassis No": (r"(?:Chassis No)[\s:]+([A-Za-z0-9]+)", "text"),
            "Engine No": (r"(?:Engine No)[\s:]+([A-Za-z0-9]+)", "text"),
            "Fuel Type": (r"(?:Fuel Type)[\s:]+([A-Za-z]+)", "text"),
            "Status": (r"(?:Status|Rc Status)[\s:]+([A-Za-z]+)", "text"),
            "RTO": (r"(?:Registering Authority|RTO)[\s:]+([^\n]+)", "text"),
            "Financier": (r"(?:Financier)[\s:]+([^\n]+)", "text"),
            "Insurance Upto": (r"(?:Insurance Upto|Expiry)[\s:]+([\d\-\w]+)", "text"),
            "Fitness Upto": (r"(?:Fitness Upto)[\s:]+([\d\-\w]+)", "text"),
            "PUC Upto": (r"(?:PUC Upto)[\s:]+([\d\-\w]+)", "text"),
        }

        for key, (pattern, vtype) in patterns.items():
            # Agar DOM se pehle hi mil gaya hai to skip karo (Address/Phone ko override karne do)
            if key in final_data["details"] and key not in ["Address", "Phone"]: 
                continue

            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                val = clean(match.group(1))
                if is_valid(val, vtype):
                    final_data["details"][key] = val

        final_data["details"]["Challan"] = get_challan_count(session, rc)
        return jsonify(final_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
