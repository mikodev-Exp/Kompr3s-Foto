import streamlit as st
from PIL import Image
import io
import zipfile
import hashlib
import pandas as pd

# Konfigurasi Halaman
st.set_page_config(page_title="Image Compressor Pro", page_icon="🖼️", layout="wide")

# --- 1. FUNGSI HELPER KEAMANAN & DATABASE SEMENTARA ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Catatan: Untuk produksi di .streamlit.app, hubungkan dictionary ini ke Supabase / Google Sheets / MongoDB
if "users_db" not in st.session_state:
    st.session_state.users_db = {
        "admin": hash_password("admin123")  # Akun default untuk testing
    }

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# --- 2. FUNGSI INTI KOMPRESI (ADAPTASI DARI compressor.py) ---
def compress_image(uploaded_file, quality: int = 75):
    """
    Ganti atau sesuaikan isi fungsi ini dengan logika kompresi spesifik
    yang ada di dalam script compressor.py milikmu.
    """
    original_bytes = uploaded_file.getvalue()
    original_size = len(original_bytes)
    
    img = Image.open(io.BytesIO(original_bytes))
    output_buffer = io.BytesIO()
    
    # Pertahankan format asli atau konversi ke JPEG/WEBP sesuai kebutuhan scriptmu
    img_format = img.format if img.format in ["JPEG", "PNG", "WEBP"] else "JPEG"
    
    if img_format == "PNG":
        # Optimasi PNG
        img.save(output_buffer, format="PNG", optimize=True)
    else:
        # Konversi RGBA ke RGB jika ingin disimpan sebagai JPEG
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output_buffer, format=img_format, quality=quality, optimize=True)
        
    compressed_bytes = output_buffer.getvalue()
    compressed_size = len(compressed_bytes)
    
    return {
        "name": uploaded_file.name,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "data": compressed_bytes,
        "mime": uploaded_file.type
    }

def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

# --- 3. HALAMAN LOGIN & REGISTER ---
def auth_page():
    st.title("🔐 Selamat Datang di Image Compressor")
    st.write("Silakan masuk atau daftar akun terlebih dahulu untuk mengakses dashboard kompresi.")
    
    tab_login, tab_register = st.tabs(["Login", "Daftar Akun"])
    
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Masuk", use_container_width=True)
            
            if submit_login:
                if username in st.session_state.users_db and st.session_state.users_db[username] == hash_password(password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Username atau password salah!")

    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("Buat Username")
            new_pass = st.text_input("Buat Password", type="password")
            confirm_pass = st.text_input("Konfirmasi Password", type="password")
            submit_reg = st.form_submit_button("Daftar Sekarang", use_container_width=True)
            
            if submit_reg:
                if not new_user or not new_pass:
                    st.warning("Username dan password tidak boleh kosong.")
                elif new_user in st.session_state.users_db:
                    st.error("Username sudah terdaftar, silakan pilih yang lain.")
                elif new_pass != confirm_pass:
                    st.error("Konfirmasi password tidak cocok.")
                else:
                    st.session_state.users_db[new_user] = hash_password(new_pass)
                    st.success("Akun berhasil dibuat! Silakan pindah ke tab Login.")

# --- 4. HALAMAN DASHBOARD UTAMA ---
def dashboard_page():
    # Header & Tombol Logout
    col_title, col_logout = st.columns([8, 1])
    with col_title:
        st.title(f"🖼️ Dashboard Kompresor Foto")
        st.caption(f"Halo, **{st.session_state.username}**! Unggah satu atau banyak foto sekaligus untuk dikompres.")
    with col_logout:
        st.write("")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    st.divider()

    # Pengaturan & Input File
    quality = st.slider("Tingkat Kualitas Kompresi (Semakin kecil = ukuran makin hemat)", min_value=10, max_value=95, value=75)
    
    uploaded_files = st.file_uploader(
        "Pilih foto (bisa pilih 1 foto atau blok banyak foto sekaligus)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("🚀 Mulai Kompres Foto", type="primary"):
            results = []
            
            # Indikator Loading
            progress_bar = st.progress(0, text="Mempersiapkan proses kompresi...")
            total_files = len(uploaded_files)
            
            for idx, file in enumerate(uploaded_files):
                progress_bar.progress(
                    (idx + 1) / total_files,
                    text=f"Sedang mengompres ({idx + 1}/{total_files}): {file.name}..."
                )
                res = compress_image(file, quality=quality)
                results.append(res)
                
            progress_bar.empty()
            st.success(f"Selesai! {total_files} foto berhasil dikompres.")

            # --- RINCIAN DETAIL UKURAN ---
            st.subheader("📊 Rincian Hasil Kompresi")
            
            table_data = []
            total_awal = 0
            total_akhir = 0
            
            for item in results:
                awal = item["original_size"]
                akhir = item["compressed_size"]
                total_awal += awal
                total_akhir += akhir
                hemat_persen = ((awal - akhir) / awal) * 100 if awal > 0 else 0
                
                table_data.append({
                    "Nama File": item["name"],
                    "Ukuran Awal": format_size(awal),
                    "Ukuran Akhir": format_size(akhir),
                    "Penghematan": f"{hemat_persen:.1f}%"
                })

            # Ringkasan Metrik Total
            total_hemat = ((total_awal - total_akhir) / total_awal) * 100 if total_awal > 0 else 0
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Ukuran Awal", format_size(total_awal))
            m2.metric("Total Ukuran Akhir", format_size(total_akhir))
            m3.metric("Total Ruang Dihemat", f"{total_hemat:.1f}%", delta=f"-{format_size(total_awal - total_akhir)}")

            # Tabel Detail per File
            df_report = pd.DataFrame(table_data)
            st.dataframe(df_report, use_container_width=True, hide_index=True)

            # --- AREA UNDUH HASIL ---
            st.subheader("📥 Unduh Hasil Kompresi")
            
            # Jika lebih dari 1 file, sediakan tombol Download All (.ZIP)
            if len(results) > 1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for item in results:
                        zf.writestr(f"compressed_{item['name']}", item["data"])
                
                st.download_button(
                    label="📦 Unduh Semua Foto (.ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="hasil_kompres_foto.zip",
                    mime="application/zip",
                    type="primary"
                )
                st.write("Atau unduh satuan:")

            # Tombol download per file
            for idx, item in enumerate(results):
                col_name, col_btn = st.columns([4, 1])
                with col_name:
                    st.write(f"📄 **{item['name']}** ({format_size(item['original_size'])} ➔ {format_size(item['compressed_size'])})")
                with col_btn:
                    st.download_button(
                        label="Unduh",
                        data=item["data"],
                        file_name=f"compressed_{item['name']}",
                        mime=item["mime"],
                        key=f"dl_{idx}"
                    )

# --- 5. ROUTING APLIKASI ---
if st.session_state.logged_in:
    dashboard_page()
else:
    auth_page()