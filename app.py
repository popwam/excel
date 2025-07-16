import os
import pandas as pd
import numpy as np
import zipfile
from flask import Flask, request, render_template_string, send_file
from werkzeug.utils import secure_filename
from threading import Timer

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# أكواد الدول المسموح بها وطول الرقم
valid_lengths = {
    "20": 12,  # مصر
    "1": 11,   # أمريكا
    "971": 12, # الإمارات
    "966": 12, # السعودية
    "962": 12, # الأردن
    # زود دول تانية لو حبيت
}

def format_number(num):
    if pd.isna(num) or str(num).strip().lower() in ["n/a", "needed", ""]:
        return None

    num = str(num).strip()
    num = ''.join(filter(str.isdigit, num))  # يشيل المسافات والرموز

    if num.startswith("01") and len(num) == 11:
        num = "20" + num[1:]
    elif num.startswith("00"):
        num = num[2:]

    if not num.isdigit():
        return None

    for code, length in valid_lengths.items():
        if num.startswith(code) and len(num) == length:
            return num

    return None

def delete_files_later(files, delay=60):
    def delete():
        for f in files:
            if os.path.exists(f):
                os.remove(f)
    Timer(delay, delete).start()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return "❌ لم يتم اختيار الملف"

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        try:
            df = pd.read_excel(filepath)
            df.columns = df.columns.astype(str)

            name_col = request.form.get("name_col")
            number_col = request.form.get("number_col")

            if name_col not in df.columns or number_col not in df.columns:
                return "❌ الأعمدة غير صحيحة"

            df[number_col] = df[number_col].astype(str)
            df['name'] = df[name_col].astype(str).str.strip()
            df['number'] = df[number_col].apply(format_number)

            total_rows = len(df)

            # استخراج المرفوضين
            rejected_df = df[df['name'].isna() | (df['name'] == "") | df['number'].isna() | (df['number'] == "")]
            valid_df = df.drop(rejected_df.index)
            valid_df = valid_df.drop_duplicates(subset=['name', 'number'])
            valid_df = valid_df[['name', 'number']]

            # تقسيم الصالحين إلى ملفات كل 240 صف
            max_rows = 240
            chunks = [valid_df[i:i+max_rows] for i in range(0, len(valid_df), max_rows)]

            output_files = []
            for i, chunk in enumerate(chunks, start=1):
                out_path = os.path.join(RESULT_FOLDER, f"clients_{i}.xlsx")
                chunk.to_excel(out_path, index=False)
                output_files.append(out_path)

            zip_path = os.path.join(RESULT_FOLDER, "clients_cleaned.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for f in output_files:
                    zipf.write(f, os.path.basename(f))

            delete_files_later(output_files + [zip_path, filepath])

            return render_template_string("""
                <!DOCTYPE html>
                <html lang="ar" dir="rtl">
                <head>
                    <meta charset="UTF-8">
                    <title>نتائج التنظيف</title>
                    <style>
                        body { font-family: Tahoma; max-width: 900px; margin: auto; background: #f9f9f9; padding: 20px; }
                        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                        th, td { border: 1px solid #ccc; padding: 8px; text-align: right; }
                        th { background-color: #eee; }
                        .count { margin: 10px 0; font-weight: bold; }
                        .button { background: #28a745; color: white; padding: 10px 15px; border: none; border-radius: 5px; text-decoration: none; }
                    </style>
                </head>
                <body>
                    <h2>✅ نتائج التنظيف</h2>
                    <p class="count">📊 الصفوف الكلية: {{total}}</p>
                    <p class="count">✅ الصالحة: {{valid}}</p>
                    <p class="count">❌ المرفوضة: {{rejected}}</p>

                    <a class="button" href="/download" download>⬇️ تحميل النتائج الصالحة</a>

                    {% if not rejected_table.empty %}
                        <h3>❌ الصفوف المرفوضة:</h3>
                        {{ rejected_table.to_html(classes="table", index=False) }}
                    {% endif %}
                </body>
                </html>
            """, total=total_rows, valid=len(valid_df), rejected=len(rejected_df), rejected_table=rejected_df[['name', 'number']])
        except Exception as e:
            return f"❌ حصل خطأ: {str(e)}"

    # واجهة الرفع
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تنظيف الأرقام من ملف Excel</title>
        <style>
            body { background: #f9f9f9; font-family: Tahoma; max-width: 600px; margin: auto; padding: 30px; }
            input, button { width: 100%; padding: 10px; margin: 10px 0; border-radius: 6px; border: 1px solid #ccc; }
            button { background: #28a745; color: white; border: none; font-weight: bold; }
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

@app.route("/download")
def download_cleaned():
    zip_path = os.path.join(RESULT_FOLDER, "clients_cleaned.zip")
    return send_file(zip_path, as_attachment=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
