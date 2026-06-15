import pandas as pd
from sqlalchemy import create_engine

# 1. Baca data dari file CSV
file_name = 'Electronics_Sales_Data.xlsx - Sales Data.csv'
df = pd.read_csv(file_name)


# 2. Membuat Engine Koneksi
# Contoh di bawah ini untuk PostgreSQL.
# Jika Cloud SQL Anda MySQL, ubah 'postgresql://' menjadi 'mysql+pymysql://'
koneksi_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
engine = create_engine(koneksi_url)

# 3. Buat Tabel dan Import Data Secara Otomatis
try:
    print("Mencoba terhubung ke Cloud SQL dan mengirim data...")
    
    # Fungsi to_sql akan otomatis membuat tabel berdasarkan tipe data di dataframe Pandas
    # if_exists='replace' -> Jika tabel sudah ada, akan dihapus lalu dibuat ulang. (Bisa diganti 'append')
    # index=False -> Kolom index bawaan pandas (0, 1, 2...) tidak akan dimasukkan ke database
    df.to_sql(name='data_penjualan', 
              con=engine, 
              if_exists='replace', 
              index=False)
              
    print("BERHASIL! Tabel 'data_penjualan' telah dibuat dan data telah diimpor.")
except Exception as e:
    print("GAGAL mengimpor data. Detail error:", e)