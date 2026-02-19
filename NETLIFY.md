# Projeyi Netlify'a Ekleme

Bu projeyi [Netlify](https://app.netlify.com/teams/cahitarfa52/projects) hesabına eklemek için aşağıdaki adımları uygulayın. Netlify’a giriş ve proje ekleme işlemini tarayıcıda sizin yapmanız gerekir.

## 1. Projeyi Git’e (GitHub / GitLab / Bitbucket) yükleyin

Netlify “Import from Git” ile çalışır. Proje henüz bir Git deposunda değilse:

1. [GitHub](https://github.com) (veya GitLab / Bitbucket) hesabınızda yeni bir repository oluşturun.
2. Bilgisayarınızda proje klasöründe terminal açın ve:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADINIZ/REPO_ADI.git
git push -u origin main
```

(KULLANICI_ADINIZ ve REPO_ADI yerine kendi kullanıcı adınızı ve repo adınızı yazın.)

## 2. Netlify’da yeni site ekleyin

1. Tarayıcıda şu adrese gidin: **https://app.netlify.com/teams/cahitarfa52/projects**
2. **“Add new site”** veya **“Import an existing project”** butonuna tıklayın.
3. **“Import from Git”** ile devam edin.
4. GitHub (veya kullandığınız platform) ile giriş / yetki verin.
5. Az önce push ettiğiniz **repository’yi listeden seçin**.
6. **Build settings** genelde otomatik dolar (`netlify.toml` projede olduğu için):
   - **Publish directory:** `.` (proje kökü)
   - Build command boş bırakılabilir.
7. **“Deploy site”** ile deploy’u başlatın.

Birkaç dakika sonra siteniz `https://rastgele-isim.netlify.app` gibi bir adreste yayında olur.

## Önemli not: Flask backend

Bu proje **Flask** ile çalışan bir backend kullanıyor (optimizasyon, PDF rapor vb. istekler sunucuda işleniyor). Netlify **statik site** ve **serverless function** destekler; sürekli çalışan bir Flask sunucusu çalıştırmaz.

- **Şu anki Netlify deploy’u:** Sadece `index.html` ve statik dosyalar yayınlanır. Sayfa açılır ama **optimizasyon çalıştırma, PDF indirme** gibi API istekleri çalışmaz.
- **Tam çalışan uygulama için seçenekler:**
  1. **Backend’i ayrı host etmek:** Flask uygulamasını [Render](https://render.com), [Railway](https://railway.app) veya [PythonAnywhere](https://www.pythonanywhere.com) gibi bir yerde çalıştırıp, frontend’te API adresini bu backend’e yönlendirmek.
  2. **Netlify Functions:** API’yi Netlify Functions (serverless) olarak yazıp, mevcut Flask rotalarını buna taşımak (ek geliştirme gerekir).

Özet: Projeyi Netlify’a “proje olarak ekleme” ve ilk deploy’u yukarıdaki adımlarla yapabilirsiniz; tam backend özellikleri için ek bir host veya Functions’a taşıma gerekir.
