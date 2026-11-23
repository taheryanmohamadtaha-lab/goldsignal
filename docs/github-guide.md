# راهنمای گام‌به‌گام GitHub (برای مبتدی)

من به GitHub شما دسترسی ندارم، پس مخزن را **نساخته‌ام و چیزی منتشر نکرده‌ام**. همهٔ فایل‌ها آماده‌اند؛ این مراحل را بروید:

1. در github.com وارد شوید ← **New repository** ← نام `goldsignal` ← Create (بدون README).
2. پوشهٔ پروژه را از zip باز کنید. در صفحهٔ مخزن: **uploading an existing file** ← همهٔ فایل‌ها و پوشه‌ها (از جمله پوشهٔ مخفی `.github`) را بکشید و **Commit changes** بزنید.
   - اگر آپلود وب پوشهٔ `.github` را نگرفت، Git نصب کنید و در پوشهٔ پروژه بزنید:
     ```
     git init
     git add .
     git commit -m "first commit"
     git branch -M main
     git remote add origin https://github.com/USERNAME/goldsignal.git
     git push -u origin main
     ```
3. تب **Actions** ← workflow به نام `build` خودکار اجرا می‌شود (تست ← EXE ← نصب‌کننده ← Artifact).
4. برای انتشار: تب **Releases** ← Draft a new release ← Tag جدید مثل `v1.0.0` ← Publish. بعد از چند دقیقه `GoldSignal-Setup-1.0.0.exe` و zip قابل‌حمل خودکار در همان Release اضافه می‌شود.
5. اگر Workflow قرمز شد، متن خطا را همین‌جا برایم بفرستید تا درستش کنم.

نکته: مخزن را Private بسازید اگر نمی‌خواهید عمومی باشد. هیچ توکن یا کلیدی در پروژه نیست.
