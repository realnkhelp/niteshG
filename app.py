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
    # Remove extra spaces and colons
    return re.sub(r'[:\-\n\r\t]', '', text).strip()

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

        # Convert entire HTML to plain text line by line
        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(separator="\n")
        
        # === POWERFUL REGEX SEARCH ===
        # Ye patterns text me se value nikalenge chahe wo kahi bhi chupi ho
        patterns = {
            "Owner Name": r"(?:Owner Name|Owner's Name)[\s:]+([A-Za-z\s\.]+)",
            "Father Name": r"(?:Father Name|Father's Name|S/O|W/O|D/O)[\s:]+([A-Za-z\s\.]+)",
            "Registration Date": r"(?:Registration Date|Reg Date)[\s:]+([\d\-\w]+)",
            "Model Name": r"(?:Model Name|Maker Model|Model)[\s:]+([A-Za-z0-9\s\.\-\(\)]+)",
            "Vehicle Class": r"(?:Vehicle Class|Class)[\s:]+([A-Za-z0-9\s\.\-\(\)]+)",
            "Fuel Type": r"(?:Fuel Type|Fuel)[\s:]+([A-Za-z\s]+)",
            "Chassis No": r"(?:Chassis No|Chassis)[\s:]+([A-Za-z0-9]+)",
            "Engine No": r"(?:Engine No|Engine)[\s:]+([A-Za-z0-9]+)",
            "Fitness Upto": r"(?:Fitness Upto|Fit up to)[\s:]+([\d\-\w]+)",
            "Insurance Upto": r"(?:Insurance Upto|Insurance Expiry)[\s:]+([\d\-\w]+)",
            "Tax Upto": r"(?:Tax Upto|MV Tax)[\s:]+([\d\-\w]+|LTT|One Time)",
            "PUC Upto": r"(?:PUC Upto|Pollution Upto|PUC Valid)[\s:]+([\d\-\w]+)",
            "Emission Norms": r"(?:Emission Norms|Fuel Norms)[\s:]+([A-Za-z0-9\s]+)",
            "RTO": r"(?:Registering Authority|RTO)[\s:]+([A-Za-z0-9\s\,\-]+)",
            "Financier": r"(?:Financier|Hypothecation)[\s:]+([A-Za-z0-9\s\.]+)",
            "Status": r"(?:Status|Rc Status)[\s:]+([A-Za-z]+)",
            "Phone": r"(?:Phone|Mobile)[\s:]+(\+91[0-9X*]+)",
            "Address": r"(?:Address|Permanent Address)[\s:]+([A-Za-z0-9\s\,\-\.]+)"
        }

        for key, pattern in patterns.items():
            # Multiline mode + Case Insensitive
            match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = clean(match.group(1))
                # Validation: Value shouldn't be too long (garbage check)
                if len(value) < 100: 
                    final_data["details"][key] = value

        # Challan Count
        final_data["details"]["Challan"] = get_challan_count(session, rc)

        return jsonify(final_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
