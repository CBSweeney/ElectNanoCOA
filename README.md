# Certificate of Analysis (COA) Generator

**Live App:** [https://electnanocoa.streamlit.app/](https://electnanocoa.streamlit.app/)

This Streamlit-based application lets you quickly generate **professional PDF Certificates of Analysis** (COAs) from either manual form entry or uploaded CSV/Excel data.  
It is designed for **ease of use** in a browser and produces PDFs that match your standardized format with custom header, footer, disclaimer, and page numbering.

---

## ✨ Features

- **Web-based form entry** – Fill out customer info, product info, and tested properties directly in your browser.
- **File upload** – Import all required COA fields from CSV or Excel (`.xlsx`) files.
- **Custom branding** – Uses your own `header.png` and `footer.png`.
- **Auto-formatted output**:
  - All dates → `YYYY-MM-DD`
  - Large numbers → scientific notation (e.g., `1.5E+06`)
  - Fixed margins and column widths
- **Disclaimer text** – Pulled from `disclaimer.txt` with controlled line spacing.
- **Automatic page numbering** – Version and page number placed consistently on each page.
- **One-click PDF download** – Generates and downloads the COA in one step.
- **Responsive layout** – Optimized for fitting all form inputs in a normal browser window.

---

## 📂 File Structure

```
streamlit_COA.py        # Main Streamlit app
requirements.txt        # Python dependencies
runtime.txt             # Python version for hosting
header.png              # COA header image
footer.png              # COA footer image
disclaimer.txt          # COA disclaimer text
version.txt             # Version number printed on PDFs
```

---

## 🖥️ Running Locally

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/coa-generator.git
   cd coa-generator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**:
   ```bash
   streamlit run streamlit_COA.py
   ```

4. Open the provided URL in your browser (default: `http://localhost:8501`).

---

## 🌐 Deploying to Streamlit Cloud

1. Push your repository to GitHub.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Select “New App” → connect your GitHub repo.
4. Choose:
   - **Branch:** `main`
   - **File:** `streamlit_COA.py`
5. Click **Deploy**.  
   Any future `git push` to the branch will redeploy automatically.

---

## 📊 Using the App

1. **Choose data input method**:
   - **Form Entry:** Manually type each COA field.
   - **File Upload:** Upload a `.csv` or `.xlsx` with your COA data.

2. **Generate COA**:
   - Click **Generate & Download PDF** in the left panel.

3. **Output**:
   - A single-page, 8.5” x 11” PDF with header, footer, tables, disclaimer, version info, and page number.

---

## ⚠️ Notes

- **Header/Footer**: Must be PNG format, placed in the same directory as `streamlit_COA.py`.
- **Disclaimer/Version**: Stored in plain text files in the same directory.
- **Data Formatting**: Dates auto-formatted; large values auto-converted to scientific notation.

---

## 🛠 Tech Stack

- [Streamlit](https://streamlit.io/) – Frontend and app hosting
- [ReportLab](https://www.reportlab.com/) – High-quality PDF generation
- [Pandas](https://pandas.pydata.org/) – Data handling
- [OpenPyXL](https://openpyxl.readthedocs.io/) – Excel file support

---

## 📄 License

This project is proprietary to **Elect Nano LLC**.  
All rights reserved.
