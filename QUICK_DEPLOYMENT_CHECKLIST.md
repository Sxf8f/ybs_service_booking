# Quick Deployment Checklist for IIS

## 📋 Pre-Deployment (Before Going to Server)

### On Development Machine
- [ ] Test the application locally one final time
- [ ] Run `python manage.py check` - ensure no issues
- [ ] Export project to clean folder (exclude venv, __pycache__, .git)
- [ ] Prepare `.env` file with production values (keep SECRET_KEY secure)
- [ ] Backup current database if migrating data

---

## 🖥️ Server Preparation (30-60 minutes)

### Install Software
- [ ] **Python 3.13**: Download from python.org, install to `C:\Python313`
  - ✅ Check "Add Python to PATH"
  - ✅ Install for all users

- [ ] **MySQL 8.0**: Download from mysql.com
  - Set root password
  - Create database: `ybs_service_book_db`
  - Create user: `django_user`

- [ ] **IIS with CGI**:
  - Server Manager → Add Roles → Web Server (IIS)
  - ✅ CGI
  - ✅ ISAPI Extensions
  - ✅ ISAPI Filters

---

## 📁 Project Deployment (20-30 minutes)

### Copy Files
```cmd
mkdir C:\inetpub\wwwroot\service_booking
```
- [ ] Copy project files to above location
- [ ] Set permissions: IIS_IUSRS and IUSR (Read & Execute)

### Setup Virtual Environment
```cmd
cd C:\inetpub\wwwroot\service_booking
C:\Python313\python.exe -m venv venv
venv\Scripts\activate
```

### Install Dependencies
```cmd
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install wfastcgi
venv\Scripts\python.exe -m wfastcgi-enable
```
**NOTE THE OUTPUT** - you'll need the FastCGI path!

---

## ⚙️ Configuration (15-20 minutes)

### Database
```cmd
mysql -u root -p
```
```sql
CREATE DATABASE ybs_service_book_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'django_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON ybs_service_book_db.* TO 'django_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Environment Variables
- [ ] Copy `.env.example` to `.env`
- [ ] Generate new SECRET_KEY:
```cmd
venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
- [ ] Edit `.env`:
  - DJANGO_SECRET_KEY=<generated-key>
  - DJANGO_DEBUG=False
  - DJANGO_ALLOWED_HOSTS=<server-ip>,<domain>
  - DB credentials

### Update web.config
- [ ] Update Python path (line 8):
```xml
scriptProcessor="C:\inetpub\wwwroot\service_booking\venv\Scripts\python.exe|C:\inetpub\wwwroot\service_booking\venv\Lib\site-packages\wfastcgi.py"
```
- [ ] Update PYTHONPATH (line 37):
```xml
<add key="PYTHONPATH" value="C:\inetpub\wwwroot\service_booking" />
```

### Django Setup
```cmd
mkdir C:\inetpub\logs
cd C:\inetpub\wwwroot\service_booking
venv\Scripts\python.exe manage.py migrate --settings=service_booking.settings_production
venv\Scripts\python.exe manage.py createsuperuser --settings=service_booking.settings_production
venv\Scripts\python.exe manage.py collectstatic --noinput --settings=service_booking.settings_production
```

---

## 🌐 IIS Configuration (15-20 minutes)

### 1. Create Application Pool
IIS Manager → Application Pools → Add
- Name: `ServiceBookingAppPool`
- .NET CLR: **No Managed Code**
- Pipeline: Integrated

### 2. Create Website
IIS Manager → Sites → Add Website
- Name: `ServiceBooking`
- App Pool: `ServiceBookingAppPool`
- Path: `C:\inetpub\wwwroot\service_booking`
- Port: 80 (or custom)

### 3. Configure FastCGI
IIS Manager (server level) → FastCGI Settings → Add Application
- Full Path: `C:\inetpub\wwwroot\service_booking\venv\Scripts\python.exe`
- Arguments: `C:\inetpub\wwwroot\service_booking\venv\Lib\site-packages\wfastcgi.py`
- Environment Variables (add these):
  - `DJANGO_SETTINGS_MODULE` = `service_booking.settings_production`
  - `PYTHONPATH` = `C:\inetpub\wwwroot\service_booking`
  - `WSGI_HANDLER` = `service_booking.wsgi.application`
- Timeouts: 600 seconds each

### 4. Configure Handler Mappings
ServiceBooking site → Handler Mappings → Add Script Map
- Request path: `*`
- Executable: `C:\inetpub\wwwroot\service_booking\venv\Scripts\python.exe|C:\inetpub\wwwroot\service_booking\venv\Lib\site-packages\wfastcgi.py`
- Name: `Django FastCGI`

**IMPORTANT**: Move `StaticFile` handler to TOP!

### 5. Set Permissions
```cmd
icacls "C:\inetpub\wwwroot\service_booking" /grant "IIS_IUSRS:(OI)(CI)RX" /T
icacls "C:\inetpub\wwwroot\service_booking" /grant "IUSR:(OI)(CI)RX" /T
icacls "C:\inetpub\wwwroot\service_booking\logs" /grant "IIS_IUSRS:(OI)(CI)F" /T
```

---

## ✅ Testing (5-10 minutes)

### Django Check
```cmd
venv\Scripts\python.exe manage.py check --settings=service_booking.settings_production
```
Expected: **System check identified no issues (0 silenced).**

### Browser Test
- [ ] Open: `http://localhost`
- [ ] Should see login page
- [ ] Login with superuser
- [ ] Check dashboard loads
- [ ] Verify static files (CSS, images) load
- [ ] Test creating a work order
- [ ] Test navigation menus

### If Errors
Check logs:
```cmd
type C:\inetpub\wwwroot\service_booking\logs\django.log
type C:\inetpub\logs\LogFiles\W3SVC1\u_ex<date>.log
```

---

## 🔒 Security (5 minutes)

- [ ] Verify `DEBUG=False` in `.env`
- [ ] New SECRET_KEY set (not default)
- [ ] ALLOWED_HOSTS configured
- [ ] Database user has minimal permissions
- [ ] Windows Firewall: Allow ports 80, 443

---

## 🔄 Post-Deployment

### Restart Everything
```cmd
iisreset
net stop MySQL80
net start MySQL80
```

### Create Backup
```cmd
mysqldump -u django_user -p ybs_service_book_db > C:\Backups\initial_backup.sql
```

### Document
- [ ] Server IP address: _______________
- [ ] Database password: _______________ (keep secure!)
- [ ] Superuser credentials: _______________
- [ ] Access URL: _______________

---

## 📞 Quick Reference

### Restart IIS
```cmd
iisreset
```

### View Django Logs
```cmd
notepad C:\inetpub\wwwroot\service_booking\logs\django.log
```

### Run Migrations (after updates)
```cmd
cd C:\inetpub\wwwroot\service_booking
deploy_scripts\migrate_db.bat
```

### Collect Static Files (after CSS/JS changes)
```cmd
cd C:\inetpub\wwwroot\service_booking
deploy_scripts\collect_static.bat
```

### Backup Database
```cmd
mysqldump -u django_user -p ybs_service_book_db > backup.sql
```

---

## 🆘 Common Issues

### 500 Error
- Check `logs\django.log` for Python errors
- Verify database connection in `.env`
- Ensure all dependencies installed

### Static Files Not Loading
- Run collectstatic again
- Check StaticFile handler is at TOP
- Verify staticfiles folder permissions

### Can't Access from Network
- Check Windows Firewall
- Verify ALLOWED_HOSTS in `.env`
- Check IIS binding (0.0.0.0 for all IPs)

---

## ⏱️ Total Time Estimate

- **Fresh server setup**: 2-3 hours
- **Pre-configured server**: 1-1.5 hours
- **Code updates only**: 15-30 minutes

---

## ✨ Success Criteria

Your deployment is successful when:
- ✅ Website loads at http://server-ip
- ✅ Login page displays with correct styling
- ✅ Admin can login
- ✅ Dashboard shows real data
- ✅ All navigation menus work
- ✅ Static files (CSS/images) load
- ✅ Database operations work
- ✅ No errors in logs

---

**Need Help?** Check the full deployment guide: `DEPLOYMENT_GUIDE_IIS.md`
