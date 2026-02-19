# Python + Arayüz Birlikte Çalışsın: Render'da Deploy

Bu proje **Render** üzerinde deploy edildiğinde hem Flask backend (optimizasyon, PDF, Excel) hem de arayüz tek adreste çalışır.

## 1. Projeyi GitHub'a yükleyin

Eğer henüz yapmadıysanız:

```bash
git init
git add .
git commit -m "Render deploy icin hazir"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADINIZ/REPO_ADI.git
git push -u origin main
```

## 2. Render hesabı ve yeni Web Service

1. **https://render.com** adresine gidin ve (ücretsiz) hesap açın veya giriş yapın.
2. **Dashboard** → **"New +"** → **"Web Service"** seçin.
3. GitHub (veya GitLab/Bitbucket) ile **bağlanın** ve bu projenin **repository'sini seçin**.
4. Render ayarları:
   - **Name:** İstediğiniz isim (örn. `tusas-laminate-optimizer`).
   - **Region:** Size yakın bölge (örn. Frankfurt).
   - **Branch:** `main`.
   - **Runtime:** `Python 3`.
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
   - **Instance Type:** **Free** (ücretsiz plan).

   Proje kökünde `render.yaml` olduğu için bu alanlar otomatik dolu gelebilir; kontrol edip **Create Web Service** deyin.

5. İlk deploy birkaç dakika sürer. Bittiğinde size şöyle bir URL verilir:  
   `https://tusas-laminate-optimizer.onrender.com` (isim sizinkiyle değişir).

## 3. Sonuç

- Bu URL'yi tarayıcıda açtığınızda **arayüz** açılır.
- **Optimizasyon**, **PDF rapor**, **Excel export** gibi tüm istekler aynı sunucuda çalışan **Python/Flask** koduna gider; yani backend de çalışır.

## Notlar

- **Ücretsiz plan:** Uygulama bir süre kullanılmazsa uyur; ilk istekte 30–60 saniye uyanma süresi olabilir.
- **Ortam:** Render, `PORT` değişkenini kendisi verir; `gunicorn` bu portu kullanır.
- **Python sürümü:** Projede `runtime.txt` ile Python 3.10 kullanılıyor; Render bunu kullanır.

Projeyi bu adımlarla Render’a eklediğinizde hem arayüz hem Python kodları aynı adreste çalışır.
