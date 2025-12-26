from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

# असली ब्राउज़र जैसा दिखने के लिए Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

def get_challan_count(session, rc_number):
    """
    यह फंक्शन बैकग्राउंड में challan-search पेज पर जाकर 
    'eChallan (X)' में से नंबर निकालकर लाएगा।
    """
    url = f"https://vahanx.in/challan-search/{rc_number}"
    try:
        response = session.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return "Error"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text()

        # Regex से ढूँढो जहाँ "eChallan (3)" जैसा लिखा हो
        match = re.search(r"eChallan\s*\((\d+)\)", text_content)
        if match:
            return match.group(1) # जैसे कि "3" या "1"
        
        # अगर "No Challan Found" लिखा हो
        if "No Challan Found" in text_content or "No Record" in text_content:
            return "0"
            
        return "0" # कुछ न मिले तो 0 मान लो
    except Exception as e:
        print(f"Challan Error: {e}")
        return "Error"

@app.route('/vehicle-info', methods=['GET'])
def vehicle_info():
    rc = request.args.get('rc')
    if not rc:
        return jsonify({"error": "RC Number Required"}), 400

    # Session का यूज़ करेंगे ताकि कनेक्शन तेज़ हो
    session = requests.Session()
    
    # --- STEP 1: RC Details लाओ ---
    rc_url = f"https://vahanx.in/rc-search/{rc}"
    data = {"rc": rc, "status": "Success", "details": {}, "challan_count": "Checking..."}

    try:
        # RC Page Request
        response = session.get(rc_url, headers=HEADERS, timeout=15)
        
        if "No Record Found" in response.text:
            return jsonify({"error": "No Record Found"}), 404
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Parsing Logic (Cards से डेटा निकालना)
        cards = soup.find_all(class_='hrcd-cardbody')
        for card in cards:
            try:
                label_tag = card.find('span')
                value_tag = card.find('p')
                if label_tag and value_tag:
                    label = label_tag.text.strip()
                    val = value_tag.text.strip()
                    data["details"][label] = val
            except:
                continue

        # --- STEP 2: Challan Count लाओ ---
        # उसी session का इस्तेमाल करके चालान चेक करो
        challan_status = get_challan_count(session, rc)
        data["challan_count"] = challan_status
        
        # details object में भी add कर देते हैं ताकि आपके पुराने JS कोड में आसानी हो
        data["details"]["Challan"] = challan_status 

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
