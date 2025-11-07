# Django Service Booking System - IIS Deployment Guide

## 📋 Complete Step-by-Step Guide for Deploying on Windows Server with IIS

---

## 🎯 Prerequisites

### Server Requirements
- **Operating System**: Windows Server 2016/2019/2022 or Windows 10/11 Pro
- **RAM**: Minimum 4GB (8GB recommended)
- **Storage**: Minimum 10GB free space
- **Python**: Python 3.13 (or 3.10+)
- **Database**: MySQL 8.0+ or MariaDB 10.5+
- **IIS**: Internet Information Services 10.0+

### Software to Install
1. Python 3.13 (with pip)
2. MySQL Server 8.0
3. IIS with CGI support
4. Visual C++ Redistributable (for mysqlclient)

---

## 📦 Part 1: Server Software Installation

### Step 1.1: Install Python

1. Download Python 3.13 from https://www.python.org/downloads/
2. Run the installer
3. ✅ **IMPORTANT**: Check "Add Python to PATH"
4. Choose "Customize installation"
5. ✅ Check all optional features
6. ✅ Check "Install for all users"
7. Set installation path: `C:\Python313`
8. Click Install

**Verify Installation**:
```cmd
python --version
pip --version
```

---

### Step 1.2: Install MySQL Server

1. Download MySQL 8.0 from https://dev.mysql.com/downloads/installer/
2. Run MySQL Installer
3. Choose "Server only" or "Developer Default"
4. Follow installation wizard
5. Set root password (save this securely!)
6. Configure MySQL as Windows Service (auto-start)
7. Complete installation

**Verify Installation**:
```cmd
mysql --version
```

**Create Database**:
```cmd
mysql -u root -p
```

```sql
CREATE DATABASE ybs_service_book_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'django_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON ybs_service_book_db.* TO 'django_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

### Step 1.3: Install IIS and CGI

1. Open **Server Manager** (or Control Panel → Programs)
2. Click "Add Roles and Features"
3. Select **Web Server (IIS)**
4. Under Application Development, check:
   - ✅ **CGI**
   - ✅ ISAPI Extensions
   - ✅ ISAPI Filters
5. Complete installation
6. Restart if prompted

**Verify IIS**:
- Open browser and navigate to `http://localhost`
- You should see the IIS default page

---

## 📁 Part 2: Project Deployment

### Step 2.1: Copy Project Files

1. Create deployment directory:
```cmd
mkdir C:\inetpub\wwwroot\service_booking
```

2. Copy entire project to this directory:
```cmd
xcopy /E /I "C:\Users\User\VScodeProjects\service_booking" "C:\inetpub\wwwroot\service_booking"
```

3. Set proper permissions:
   - Right-click on `C:\inetpub\wwwroot\service_booking`
   - Properties → Security → Edit
   - Add `IIS_IUSRS` with Read & Execute, List folder contents, Read permissions
   - Add `IUSR` with same permissions

---

### Step 2.2: Create Virtual Environment

```cmd
cd C:\inetpub\wwwroot\service_booking
C:\Python313\python.exe -m venv venv
```

**Activate virtual environment**:
```cmd
venv\Scripts\activate
```

---

### Step 2.3: Install Python Dependencies

```cmd
cd C:\inetpub\wwwroot\service_booking
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Install wfastcgi (crucial for IIS)**:
```cmd
venv\Scripts\python.exe -m pip install wfastcgi
venv\Scripts\python.exe -m wfastcgi-enable
```

**Note the output** - it will show the FastCGI path like:
```
Applied configuration changes to section "system.webServer/fastCgi" for "MACHINE/WEBROOT/APPHOST" at configuration commit path "MACHINE/WEBROOT/APPHOST"
"C:\inetpub\wwwroot\service_booking\venv\scripts\python.exe|C:\inetpub\wwwroot\service_booking\venv\lib\site-packages\wfastcgi.py" can now be used as a FastCGI script processor
```

---

### Step 2.4: Configure Environment Variables

1. Copy the example environment file:
```cmd
copy .env.example .env
```

2. Edit `.env` with your production values:
```env
DJANGO_SECRET_KEY=generate-a-new-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-server-ip,your-domain.com,localhost

DB_NAME=ybs_service_book_db
DB_USER=django_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=3306
```

**Generate a new SECRET_KEY**:
```cmd
venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

### Step 2.5: Update web.config

Edit `C:\inetpub\wwwroot\service_booking\web.config`:

1. Update Python path to virtual environment:
```xml
scriptProcessor="C:\inetpub\wwwroot\service_booking\venv\Scripts\python.exe|C:\inetpub\wwwroot\service_booking\venv\Lib\site-packages\wfastcgi.py"
```

2. Update PYTHONPATH:
```xml
<add key="PYTHONPATH" value="C:\inetpub\wwwroot\service_booking" />
```

3. Update WSGI_LOG path (create logs folder first):
```cmd
mkdir C:\inetpub\logs
```

---

### Step 2.6: Run Database Migrations

```cmd
cd C:\inetpub\wwwroot\service_booking
venv\Scripts\python.exe manage.py migrate --settings=service_booking.settings_production
```

Or use the batch script:
```cmd
deploy_scripts\migrate_db.bat
```

---

### Step 2.7: Create Superuser

```cmd
venv\Scripts\python.exe manage.py createsuperuser --settings=service_booking.settings_production
```

Enter:
- Name: Admin User
- Phone: 1234567890
- Email: admin@example.com
- Password: (your secure password)

---

### Step 2.8: Collect Static Files

```cmd
venv\Scripts\python.exe manage.py collectstatic --noinput --settings=service_booking.settings_production
```

Or use the batch script:
```cmd
deploy_scripts\collect_static.bat
```

This creates the `staticfiles` folder with all CSS, JS, and images.

---

## 🌐 Part 3: Configure IIS

### Step 3.1: Create IIS Application Pool

1. Open **IIS Manager** (Start → Internet Information Services)
2. Right-click **Application Pools** → **Add Application Pool**
   - Name: `ServiceBookingAppPool`
   - .NET CLR version: **No Managed Code**
   - Managed pipeline mode: Integrated
   - Click OK

3. Right-click `ServiceBookingAppPool` → **Advanced Settings**
   - Enable 32-Bit Applications: **False**
   - Identity: **ApplicationPoolIdentity** (default)
   - Start Mode: **AlwaysRunning** (optional, for better performance)

---

### Step 3.2: Create IIS Website

1. In IIS Manager, right-click **Sites** → **Add Website**
   - Site name: `ServiceBooking`
   - Application pool: `ServiceBookingAppPool`
   - Physical path: `C:\inetpub\wwwroot\service_booking`
   - Binding:
     - Type: http
     - IP address: All Unassigned (or specific IP)
     - Port: 80 (or custom port like 8080)
     - Host name: (leave empty or enter domain)
   - Click OK

2. **Important**: If using port 80 and there's a default site, either:
   - Stop the default site, OR
   - Use a different port (e.g., 8080)

---

### Step 3.3: Configure FastCGI Settings

1. In IIS Manager, select your server (top level)
2. Double-click **FastCGI Settings**
3. Click **Add Application**
   - Full Path: `C:\inetpub\wwwroot\service_booking\venv\Scripts\python.exe`
   - Arguments: `C:\inetpub\wwwroot\service_booking\venv\Lib\site-packages\wfastcgi.py`
   - Environment Variables → Add:
     - `DJANGO_SETTINGS_MODULE` = `service_booking.settings_production`
     - `PYTHONPATH` = `C:\inetpub\wwwroot\service_booking`
     - `WSGI_HANDLER` = `service_booking.wsgi.application`
   - Activity Timeout: 600
   - Idle Timeout: 600
   - Request Timeout: 600
   - Click OK

---

### Step 3.4: Configure Static Files

1. In IIS Manager, select `ServiceBooking` site
2. Click **Handler Mappings**
3. **Add Script Map**:
   - Request path: `*`
   - Executable: `C:\inetpub\wwwroot\service_booking\venv\Scripts\python.exe|C:\inetpub\wwwroot\service_booking\venv\Lib\site-packages\wfastcgi.py`
   - Name: `Django FastCGI`
   - Request Restrictions:
     - Uncheck "Invoke handler only if request is mapped to"
     - File: All files
   - Click OK

4. Move the `StaticFile` handler to the **TOP** of the list:
   - Right-click `StaticFile` → **Move Up** (repeatedly until at top)

---

### Step 3.5: Set Directory Permissions

```cmd
icacls "C:\inetpub\wwwroot\service_booking" /grant "IIS_IUSRS:(OI)(CI)RX" /T
icacls "C:\inetpub\wwwroot\service_booking" /grant "IUSR:(OI)(CI)RX" /T
icacls "C:\inetpub\wwwroot\service_booking\logs" /grant "IIS_IUSRS:(OI)(CI)F" /T
icacls "C:\inetpub\wwwroot\service_booking\staticfiles" /grant "IIS_IUSRS:(OI)(CI)RX" /T
```

---

## 🧪 Part 4: Testing and Verification

### Step 4.1: Test Django Setup

```cmd
cd C:\inetpub\wwwroot\service_booking
venv\Scripts\python.exe manage.py check --settings=service_booking.settings_production
```

Should show: **System check identified no issues**

---

### Step 4.2: Test IIS Site

1. Open browser
2. Navigate to: `http://localhost` (or your configured port)
3. You should see the login page

**If you see an error**:
- Check `C:\inetpub\logs\django.log` for Python errors
- Check IIS logs in `C:\inetpub\logs\LogFiles\W3SVC1\`

---

### Step 4.3: Test Static Files

Navigate to: `http://localhost/static/...`

Static files should load (CSS, JS, images).

---

### Step 4.4: Test Admin Login

1. Navigate to: `http://localhost/login/`
2. Login with superuser credentials
3. Navigate dashboard

---

## 🔧 Part 5: Troubleshooting

### Issue 1: 500 Internal Server Error

**Check**:
1. `C:\inetpub\logs\django.log` for Python errors
2. IIS logs: `C:\inetpub\logs\LogFiles\`
3. Enable detailed errors in `web.config`:
```xml
<httpErrors errorMode="Detailed" />
```

**Common causes**:
- Database connection failed (check DB credentials in `.env`)
- Missing Python dependencies (`pip install -r requirements.txt`)
- Wrong WSGI path in web.config

---

### Issue 2: Static Files Not Loading (404)

**Fix**:
1. Run collectstatic again:
```cmd
venv\Scripts\python.exe manage.py collectstatic --noinput --settings=service_booking.settings_production
```

2. Check StaticFile handler is at the TOP in IIS Handler Mappings

3. Verify permissions on staticfiles folder

---

### Issue 3: Database Connection Error

**Check**:
1. MySQL service is running:
```cmd
net start MySQL80
```

2. Database exists:
```cmd
mysql -u django_user -p
USE ybs_service_book_db;
SHOW TABLES;
```

3. Credentials in `.env` are correct

---

### Issue 4: FastCGI Timeout

**Fix**: Increase timeouts in FastCGI settings (IIS Manager):
- Activity Timeout: 600
- Request Timeout: 600
- Idle Timeout: 600

---

## 🔒 Part 6: Security Hardening

### Step 6.1: Change Debug Mode

In production, ensure:
```env
DJANGO_DEBUG=False
```

### Step 6.2: Generate New Secret Key

Never use the default secret key in production:
```cmd
venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy output to `.env`:
```env
DJANGO_SECRET_KEY=your-new-generated-key
```

### Step 6.3: Configure HTTPS (Recommended)

1. Obtain SSL certificate (Let's Encrypt, purchased, or self-signed for testing)
2. In IIS Manager, select site → **Bindings** → **Add**:
   - Type: https
   - Port: 443
   - SSL certificate: (select your certificate)

3. Update `.env`:
```env
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Step 6.4: Configure Firewall

Open Windows Firewall and allow:
- Port 80 (HTTP)
- Port 443 (HTTPS)
- Port 3306 (MySQL - only if accessing from other machines)

### Step 6.5: Restrict Database Access

In MySQL, ensure Django user only has necessary permissions:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ybs_service_book_db.* TO 'django_user'@'localhost';
FLUSH PRIVILEGES;
```

---

## 🔄 Part 7: Maintenance & Updates

### Deploying Code Updates

1. **Backup database first**:
```cmd
mysqldump -u django_user -p ybs_service_book_db > backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%.sql
```

2. **Copy new code files**:
```cmd
xcopy /E /I /Y "C:\path\to\updated\code" "C:\inetpub\wwwroot\service_booking"
```

3. **Update dependencies**:
```cmd
cd C:\inetpub\wwwroot\service_booking
venv\Scripts\python.exe -m pip install -r requirements.txt --upgrade
```

4. **Run migrations**:
```cmd
deploy_scripts\migrate_db.bat
```

5. **Collect static files**:
```cmd
deploy_scripts\collect_static.bat
```

6. **Restart IIS**:
```cmd
iisreset
```

---

### Regular Backups

**Automate daily backups** using Windows Task Scheduler:

Create `backup_db.bat`:
```batch
@echo off
set BACKUP_DIR=C:\Backups\service_booking
set DATE=%date:~-4,4%%date:~-10,2%%date:~-7,2%
mkdir %BACKUP_DIR% 2>nul
mysqldump -u django_user -p"your_password" ybs_service_book_db > %BACKUP_DIR%\backup_%DATE%.sql
```

Schedule to run daily at 2 AM.

---

## 📊 Part 8: Monitoring

### Enable Logging

Logs are configured in `settings_production.py`:
- Django logs: `C:\inetpub\wwwroot\service_booking\logs\django.log`
- IIS logs: `C:\inetpub\logs\LogFiles\W3SVC1\`

### Monitor Performance

1. **IIS Performance Counters** (Performance Monitor):
   - Web Service → Current Connections
   - Process → % Processor Time (python.exe)

2. **Database Performance**:
   - Monitor slow queries in MySQL
   - Enable MySQL slow query log

---

## ✅ Deployment Checklist

### Pre-Deployment
- [ ] Python 3.13 installed
- [ ] MySQL Server installed and configured
- [ ] IIS with CGI installed
- [ ] Database created with proper user
- [ ] Project files copied to C:\inetpub\wwwroot\service_booking

### Configuration
- [ ] Virtual environment created
- [ ] Dependencies installed (requirements.txt)
- [ ] wfastcgi enabled
- [ ] .env file configured with production values
- [ ] New SECRET_KEY generated
- [ ] web.config paths updated
- [ ] Database migrations run
- [ ] Superuser created
- [ ] Static files collected

### IIS Setup
- [ ] Application Pool created (No Managed Code)
- [ ] Website created and bound to port
- [ ] FastCGI settings configured
- [ ] Handler mappings configured
- [ ] StaticFile handler at top
- [ ] Directory permissions set

### Testing
- [ ] Django check passes
- [ ] Website loads in browser
- [ ] Static files load correctly
- [ ] Admin login works
- [ ] Database queries work

### Security
- [ ] DEBUG=False in production
- [ ] New SECRET_KEY set
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS configured (if applicable)
- [ ] Firewall rules set

### Maintenance
- [ ] Backup script created
- [ ] Update procedure documented
- [ ] Monitoring enabled
- [ ] Logs location documented

---

## 🆘 Support and Resources

### Official Documentation
- Django Deployment: https://docs.djangoproject.com/en/5.2/howto/deployment/
- IIS Configuration: https://docs.microsoft.com/en-us/iis/

### Common Commands

**Check Django Version**:
```cmd
venv\Scripts\python.exe -m django --version
```

**Django Shell**:
```cmd
venv\Scripts\python.exe manage.py shell --settings=service_booking.settings_production
```

**Restart IIS**:
```cmd
iisreset
```

**View Logs**:
```cmd
type C:\inetpub\wwwroot\service_booking\logs\django.log
```

---

## 🎉 Success!

If you've followed all steps, your Django Service Booking System should now be running on IIS!

Access your application at:
- **Local**: http://localhost
- **Network**: http://your-server-ip
- **Domain**: http://your-domain.com (if configured)

**Default Admin Credentials**:
- Use the superuser you created in Step 2.7

---

**Document Version**: 1.0
**Last Updated**: November 2025
**Django Version**: 5.2.4
**Python Version**: 3.13
