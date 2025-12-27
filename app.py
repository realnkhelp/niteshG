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

def clean(text):
    if not text: return "NA"
    # Remove colons, dashes and extra spaces from start/end
    cleaned = re.sub(r'[:\-\t]', '', text).strip()
    return cleaned

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

# Root Route (For Cron Job / Ping)
@app.route('/')
def home():
    return "Server is Running! (Ping Successful)"

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

        # Convert HTML to text with explicit newlines
        # separator="\n" bahut zaroori hai taki lines alag rahein
        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(separator="\n")
        
        # === NEW STRICT PATTERNS (Stops at newline) ===
        # [^\n]+ ka matlab hai: New line aane tak sab kuch copy karo
        # Isse "Owner Serial No" Father Name me mix nahi hoga
        patterns = {
            "Owner Name": r"(?:Owner Name|Owner's Name)[\s:]+([^\n]+)",
            "Father Name": r"(?:Father Name|Father's Name|S/O|W/O|D/O)[\s:]+([^\n]+)",
            "Registration Date": r"(?:Registration Date|Reg Date)[\s:]+([^\n]+)",
            "Model Name": r"(?:Model Name|Maker Model|Model)[\s:]+([^\n]+)",
            "Vehicle Class": r"(?:Vehicle Class|Class)[\s:]+([^\n]+)",
            "Fuel Type": r"(?:Fuel Type|Fuel)[\s:]+([^\n]+)",
            "Chassis No": r"(?:Chassis No|Chassis)[\s:]+([^\n]+)",
            "Engine No": r"(?:Engine No|Engine)[\s:]+([^\n]+)",
            "Fitness Upto": r"(?:Fitness Upto|Fit up to)[\s:]+([^\n]+)",
            "Insurance Upto": r"(?:Insurance Upto|Insurance Expiry)[\s:]+([^\n]+)",
            "Tax Upto": r"(?:Tax Upto|MV Tax)[\s:]+([^\n]+)",
            "PUC Upto": r"(?:PUC Upto|Pollution Upto|PUC Valid)[\s:]+([^\n]+)",
            "Emission Norms": r"(?:Emission Norms|Fuel Norms)[\s:]+([^\n]+)",
            "RTO": r"(?:Registering Authority|RTO)[\s:]+([^\n]+)",
            "Financier": r"(?:Financier|Hypothecation)[\s:]+([^\n]+)",
            "Status": r"(?:Status|Rc Status)[\s:]+([^\n]+)",
            # Phone ke liye thoda loose pattern taki bina +91 wala bhi pakad le
            "Phone": r"(?:Phone|Mobile|Mobile No)[\s:]+([0-9\+\-\s\*X]+)", 
            "Address": r"(?:Address|Permanent Address)[\s:]+([^\n]+)"
        }

        for key, pattern in patterns.items():
            # Use strict matching line by line
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                value = clean(match.group(1))
                # Extra check: Agar value me abhi bhi garbage hai (bahut lamba text), to reject karo
                if len(value) < 60 and "Serial" not in value and "Registration" not in value:
                    final_data["details"][key] = value

        final_data["details"]["Challan"] = get_challan_count(session, rc)
        return jsonify(final_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
