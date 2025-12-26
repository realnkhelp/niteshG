from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

# Browser Headers (To avoid blocking)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def clean_text(text):
    if not text: return None
    return text.strip().replace(":", "").strip()

def get_challan_count(session, rc_number):
    url = f"https://vahanx.in/challan-search/{rc_number}"
    try:
        response = session.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text()
        match = re.search(r"eChallan\s*\((\d+)\)", text_content)
        if match: return match.group(1)
        if "No Challan Found" in text_content: return "0"
        return "0"
    except:
        return "Error"

@app.route('/vehicle-info', methods=['GET'])
def vehicle_info():
    rc = request.args.get('rc')
    if not rc:
        return jsonify({"error": "RC Number Required"}), 400

    session = requests.Session()
    data = {"rc": rc, "status": "Success", "details": {}}

    try:
        # 1. Fetch RC Page
        rc_url = f"https://vahanx.in/rc-search/{rc}"
        response = session.get(rc_url, headers=HEADERS, timeout=15)
        
        if "No Record Found" in response.text:
            return jsonify({"error": "No Record Found"}), 404
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ======================================================
        # NEW SMART SCRAPING LOGIC (To find ALL details)
        # ======================================================
        
        # 1. Try finding data in standard Cards (Old Method - Keeps working for basics)
        cards = soup.find_all(class_='hrcd-cardbody')
        for card in cards:
            try:
                label = card.find('span').text.strip()
                val = card.find('p').text.strip()
                data["details"][label] = val
            except:
                continue

        # 2. BRUTE FORCE SEARCH (Ye bache hue data ko dhundega)
        # Ye list mein wo sab naam hain jo aapko chahiye
        keywords = [
            "Father's Name", "Father Name", "Chassis No", "Engine No", 
            "Vehicle Class", "Fuel Type", "Maker Model", "Manufacturing Date",
            "Fitness Upto", "Insurance Upto", "Pollution Upto", "MV Tax",
            "Owner Serial No", "Financier", "PUC No", "Seat Capacity", "Cubic Capacity",
            "Vehicle Color", "Unladen Weight", "Gross Weight", "Sleeper Capacity"
        ]

        # Pure HTML text mein keywords dhundo
        all_text_elements = soup.find_all(text=True)
        
        for keyword in keywords:
            # Agar purane tarike se ye data nahi mila, tabhi dhundo
            if keyword not in data["details"]:
                for element in all_text_elements:
                    if keyword.lower() in element.lower():
                        # Keyword mil gaya, ab uske aas-paas ka value dhundo
                        try:
                            # Case A: Value agle element mein hai
                            parent = element.parent
                            
                            # Koshish 1: Sibling (Baju wala element)
                            value_candidate = parent.find_next_sibling()
                            if value_candidate and value_candidate.name in ['p', 'span', 'div', 'strong']:
                                text_val = clean_text(value_candidate.text)
                                if text_val and len(text_val) > 1:
                                    data["details"][keyword] = text_val
                                    break
                            
                            # Koshish 2: Parent ke text mein hi value chupa ho
                            # Example: <td>Father: RAM LAL</td>
                            full_text = parent.text
                            if ":" in full_text:
                                parts = full_text.split(":")
                                if len(parts) > 1:
                                    text_val = clean_text(parts[1])
                                    data["details"][keyword] = text_val
                                    break

                        except:
                            continue

        # 3. Phone Number Fix (Special handling)
        if "Phone" not in data["details"]:
             # Try finding masked phone pattern
             phone_match = re.search(r"\+91[0-9X*]+", soup.get_text())
             if phone_match:
                 data["details"]["Phone"] = phone_match.group(0)

        # 4. Challan Count Add karo
        challan_count = get_challan_count(session, rc)
        data["details"]["Challan"] = challan_count

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
