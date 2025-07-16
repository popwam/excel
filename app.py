from flask import Flask, request, render_template_string, send_file
import pandas as pd
import numpy as np
import os
import zipfile
from werkzeug.utils import secure_filename
import threading
import time

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

valid_lengths = {
    "20": 12, "966": 12, "971": 12, "962": 12,
    "965": 11, "212": 12, "213": 12, "216": 12, "1": 11
}

def format_number(num):
    if pd.isna(num) or str(num).strip().lower() in ["n/a", "needed", ""]:
        return None
    num = str(num).strip()
    if num.startswith(("010", "011", "012", "015")):
        num = "20" + num
    elif num.startswith("00"):
        num = num[2:]
    if not num.isdigit():
        return None
    for code, length in valid_lengths.items():
        if num.startswith(code) and len(num) == length:
            return num
    return None

def delete_files_later(file_paths, delay=10):
    def delete():
        time.sleep(delay)
        for f in file_paths:
            try:
                os.remove(f)
            except:
                pass
    threading.Thread(target=delete).start()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return "❌ من فضلك ارفع ملف Excel"

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        try:
            df = pd.read_excel(filepath)
            df.columns = df.columns.astype(str)
            cols = list(df.columns)

            name_col = request.form.get("name_col")
            number_col = request.form.get("number_col")

            if name_col not in df.columns or number_col not in df.columns:
                return "❌ الأعمدة غير صحيحة"

            df['name'] = df[name_col].astype(str).str.strip()
            df['number'] = df[number_col].apply(format_number)

            df = df.dropna(subset=['name', 'number'])
            df = df[(df['name'] != "") & (df['number'] != "")]
            df = df.drop_duplicates(subset=['name', 'number'])
            df = df[['name', 'number']]

            max_rows = 240
            chunks = np.array_split(df, int(len(df) / max_rows) + 1)

            output_files = []
            for i, chunk in enumerate(chunks, start=1):
                out_path = os.path.join(RESULT_FOLDER, f"clients_{i}.xlsx")
                chunk.to_excel(out_path, index=False)
                output_files.append(out_path)

            zip_path = os.path.join(RESULT_FOLDER, "clients_cleaned.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for f in output_files:
                    zipf.write(f, os.path.basename(f))

            delete_files_later(output_files + [zip_path])
            return send_file(zip_path, as_attachment=True)

        except Exception as e:
            return f"❌ حصل خطأ: {str(e)}"

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>تنظيف الأرقام</title></head>
    <body style="font-family:Tahoma;direction:rtl;text-align:right;">
        <h2>📄 رفع ملف Excel لتنظيف الأرقام</h2>
        <form method="POST" enctype="multipart/form-data">
            <label>اختار ملف Excel:</label><br>
            <input type="file" name="file" required><br><br>

            <label>اسم عمود الاسم (زي name):</label><br>
            <input type="text" name="name_col" required><br><br>

            <label>اسم عمود الرقم (زي number):</label><br>
            <input type="text" name="number_col" required><br><br>

            <button type="submit">🚀 ابدأ التنظيف</button>
        </form>
    </body>
    </html>
    """)

if __name__ == "__main__":
    app.run()