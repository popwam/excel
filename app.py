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
    num = ''.join(filter(str.isdigit, num))  # شيل أي رموز أو فواصل

    # لو الرقم مصري بيبدأ بـ 01 وطوله 11 → حط 20 وشيل الـ 0
    if num.startswith("01") and len(num) == 11:
        num = "20" + num[1:]

    # لو بيبدأ بـ 00 نشيلهم
    elif num.startswith("00"):
        num = num[2:]

    # لازم كله أرقام
    if not num.isdigit():
        return None

    # تأكد من أنه رقم صحيح حسب الأكواد المسموحة
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

            # تحويل عمود الرقم لنص عشان يحتفظ بالأصفار
            df[number_col] = df[number_col].astype(str)

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
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تنظيف الأرقام من ملف Excel</title>
        <style>
            body {
                background-color: #f9f9f9;
                font-family: 'Tahoma', sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                direction: rtl;
                text-align: right;
                border: 1px solid #ccc;
                border-radius: 12px;
                box-shadow: 0 0 12px rgba(0,0,0,0.05);
            }
            h2 {
                color: #444;
            }
            input[type="text"], input[type="file"] {
                width: 100%;
                padding: 10px;
                margin: 10px 0 20px 0;
                border: 1px solid #ccc;
                border-radius: 8px;
                font-size: 15px;
            }
            button {
                background-color: #28a745;
                color: white;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover {
                background-color: #218838;
            }
            label {
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <h2>📄 تنظيف الأرقام من ملف Excel</h2>
        <form method="POST" enctype="multipart/form-data">
            <label>📂 اختار ملف Excel:</label>
            <input type="file" name="file" required>

            <label>📛 اسم عمود الاسم (مثلاً: name):</label>
            <input type="text" name="name_col" required>

            <label>📞 اسم عمود الرقم (مثلاً: number):</label>
            <input type="text" name="number_col" required>

            <button type="submit">🚀 ابدأ التنظيف</button>
        </form>
    </body>
    </html>
    """)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
