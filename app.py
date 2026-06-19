import os
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

BASE_DIR = Path(__file__).parent
IMG_DIR = BASE_DIR / "data" / "images"
KEY_PATH = BASE_DIR / "data" / "answer_key.csv"
RESULT_PATH = BASE_DIR / "data" / "results.csv"

st.set_page_config(page_title="Chạy trạm Giải phẫu", layout="wide")


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def list_images():
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted([p.name for p in IMG_DIR.iterdir() if p.suffix.lower() in exts], key=natural_key)


def strip_accents(text: str) -> str:
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_correct(user_answer: str, correct_answer: str, synonyms: str = "") -> bool:
    ua = strip_accents(user_answer)
    accepted = [correct_answer]
    if pd.notna(synonyms) and str(synonyms).strip():
        accepted += [x.strip() for x in str(synonyms).split(";") if x.strip()]
    return ua in [strip_accents(x) for x in accepted if str(x).strip()]


def make_template(max_numbers=20):
    rows = []
    for img in list_images():
        for n in range(1, max_numbers + 1):
            rows.append({"station": img, "number": n, "answer": "", "synonyms": ""})
    return pd.DataFrame(rows)


def load_key():
    if KEY_PATH.exists():
        df = pd.read_csv(KEY_PATH)
    else:
        df = make_template(20)
        df.to_csv(KEY_PATH, index=False)
    for col in ["station", "number", "answer", "synonyms"]:
        if col not in df.columns:
            df[col] = ""
    df["number"] = pd.to_numeric(df["number"], errors="coerce").fillna(0).astype(int)
    return df


def save_result(row):
    df = pd.DataFrame([row])
    if RESULT_PATH.exists():
        old = pd.read_csv(RESULT_PATH)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(RESULT_PATH, index=False)


st.sidebar.title("⚙️ Chế độ")
mode = st.sidebar.radio("Chọn chế độ", ["Sinh viên", "Giáo viên"], index=0)

st.title("🏥 Web Chạy trạm Giải phẫu")
st.caption("Dành cho ảnh đã được đánh số. Sinh viên điền tên chi tiết tương ứng với từng số.")

images = list_images()
if not images:
    st.error("Chưa có ảnh trong thư mục data/images.")
    st.stop()

key_df = load_key()

if mode == "Giáo viên":
    st.subheader("👩‍🏫 Quản lý đáp án")
    st.info("Điền đáp án vào cột answer. Nếu có nhiều cách viết đúng, nhập vào cột synonyms và ngăn cách bằng dấu chấm phẩy ;")

    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_key = st.file_uploader("Tải lên file answer_key.csv", type=["csv"])
        if uploaded_key is not None:
            new_key = pd.read_csv(uploaded_key)
            new_key.to_csv(KEY_PATH, index=False)
            st.success("Đã cập nhật đáp án. Hãy tải lại trang nếu cần.")
    with col2:
        template = make_template(20).to_csv(index=False).encode("utf-8-sig")
        st.download_button("Tải file mẫu answer_key.csv", template, "answer_key.csv", "text/csv")

    station = st.selectbox("Chọn ảnh để xem", images)
    st.image(str(IMG_DIR / station), use_container_width=True)

    station_key = key_df[key_df["station"] == station].copy()
    edited = st.data_editor(station_key, num_rows="dynamic", use_container_width=True)
    if st.button("Lưu đáp án ảnh này"):
        others = key_df[key_df["station"] != station]
        pd.concat([others, edited], ignore_index=True).to_csv(KEY_PATH, index=False)
        st.success("Đã lưu đáp án.")

    st.subheader("📊 Kết quả đã nộp")
    if RESULT_PATH.exists():
        results = pd.read_csv(RESULT_PATH)
        st.dataframe(results, use_container_width=True)
        st.download_button("Tải kết quả CSV", results.to_csv(index=False).encode("utf-8-sig"), "ket_qua_chay_tram.csv", "text/csv")
    else:
        st.write("Chưa có bài nộp.")

else:
    st.subheader("🧑‍🎓 Làm bài")
    student_name = st.text_input("Họ tên sinh viên")
    station = st.selectbox("Chọn trạm", images)

    station_key = key_df[(key_df["station"] == station) & (key_df["answer"].astype(str).str.strip() != "")].copy()
    if station_key.empty:
        st.warning("Trạm này chưa có đáp án. Giáo viên cần nhập answer_key trước.")
        st.image(str(IMG_DIR / station), use_container_width=True)
        st.stop()

    station_key = station_key.sort_values("number")

    left, right = st.columns([1.35, 1])
    with left:
        st.image(str(IMG_DIR / station), use_container_width=True)
    with right:
        st.write(f"**Trạm:** {station}")
        with st.form("answer_form"):
            user_answers = {}
            for _, row in station_key.iterrows():
                n = int(row["number"])
                user_answers[n] = st.text_input(f"Số {n}", key=f"ans_{station}_{n}")
            submitted = st.form_submit_button("Nộp bài")

    if submitted:
        correct = 0
        detail_rows = []
        for _, row in station_key.iterrows():
            n = int(row["number"])
            ua = user_answers.get(n, "")
            ca = row["answer"]
            ok = is_correct(ua, ca, row.get("synonyms", ""))
            correct += int(ok)
            detail_rows.append({
                "Số": n,
                "Bạn trả lời": ua,
                "Đáp án đúng": ca,
                "Kết quả": "Đúng" if ok else "Sai"
            })

        total = len(station_key)
        st.success(f"Điểm: {correct}/{total}")
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True)
        save_result({
            "student_name": student_name,
            "station": station,
            "score": correct,
            "total": total,
            "percent": round(correct / total * 100, 2)
        })
