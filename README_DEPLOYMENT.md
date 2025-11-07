# Service Booking System - Deployment Package

## 📦 What's Included

This Django-based Service Booking System is ready for deployment on Windows Server with IIS.

### Project Files
```
service_booking/
├── core/                          # Main application
├── service_booking/               # Project settings
│   ├── settings.py               # Development settings
│   ├── settings_production.py   # Production settings
│   └── wsgi.py                   # WSGI configuration
├── deploy_scripts/               # Deployment helper scripts
│   ├── collect_static.bat       # Collect static files
│   └── migrate_db.bat            # Run database migrations
├── web.config                     # IIS configuration
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── DEPLOYMENT_GUIDE_IIS.md       # Complete deployment guide
├── QUICK_DEPLOYMENT_CHECKLIST.md # Quick reference checklist
└── README_DEPLOYMENT.md          # This file
```

---

## 🎯 Quick Start

### For System Administrators

**If this is your first time deploying a Django application on IIS:**
1. Read **DEPLOYMENT_GUIDE_IIS.md** (complete step-by-step guide)
2. Expected time: 2-3 hours for first deployment

**If you're familiar with IIS and Django:**
1. Use **QUICK_DEPLOYMENT_CHECKLIST.md** (condensed checklist)
2. Expected time: 1-1.5 hours

---

## 📋 System Requirements

### Minimum Requirements
- **OS**: Windows Server 2016+ or Windows 10/11 Pro
- **RAM**: 4GB (8GB recommended)
- **Storage**: 10GB free space
- **Python**: 3.10+ (3.13 recommended)
- **Database**: MySQL 8.0+ or MariaDB 10.5+
- **IIS**: Version 10.0+

### Required Software
1. **Python 3.13**: https://www.python.org/downloads/
2. **MySQL Server 8.0**: https://dev.mysql.com/downloads/
3. **IIS with CGI**: Enable via Server Manager

---

## 🚀 Deployment Overview

### Phase 1: Server Preparation
1. Install Python 3.13
2. Install MySQL Server
3. Enable IIS with CGI support

### Phase 2: Application Setup
1. Copy project files to `C:\inetpub\wwwroot\service_booking`
2. Create virtual environment
3. Install Python dependencies
4. Configure database
5. Run migrations
6. Collect static files

### Phase 3: IIS Configuration
1. Create Application Pool
2. Create Website
3. Configure FastCGI
4. Set up handler mappings
5. Configure permissions

### Phase 4: Testing & Security
1. Test website access
2. Verify static files
3. Test login and features
4. Configure security settings
5. Set up backups

---

## 🔧 Key Configuration Files

### 1. `web.config`
IIS configuration for FastCGI and URL rewriting.

**What to update:**
- Python executable path (line 8)
- PYTHONPATH (line 37)

### 2. `.env` (create from `.env.example`)
Environment variables for production.

**Required values:**
```env
DJANGO_SECRET_KEY=<generate-new-key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<server-ip>,<domain>
DB_NAME=ybs_service_book_db
DB_USER=django_user
DB_PASSWORD=<secure-password>
```

### 3. `settings_production.py`
Django production settings.

**Key features:**
- Uses environment variables
- Security settings enabled
- Logging configured
- Static files optimization

---

## 🔐 Security Checklist

Before going live:

- [ ] Generate new `SECRET_KEY` (don't use default!)
- [ ] Set `DEBUG=False` in production
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Use strong database password
- [ ] Set proper file permissions
- [ ] Enable HTTPS (recommended)
- [ ] Configure firewall rules
- [ ] Set up regular backups

---

## 📊 Application Features

### User Roles
1. **Admin**: Full system access
2. **Supervisor**: Manage team (Sales or Service or Both)
3. **FOS**: Field operations
4. **Retailer**: Create work orders, manage SIM/EC
5. **Technician**: Complete assigned work

### Main Features
- **Work Management**: STB installations, repairs, service requests
- **User Management**: Role-based access control
- **SIM Stock**: Track SIM cards with serial numbers
- **EC Stock**: Electronic coupon management
- **Product Stock**: Inventory management
- **Collection Management**: Payment tracking
- **Reports & Analytics**: Various operational reports

### Supervisor Categories
- **Sales Supervisor**: Manages FOS, Retailers, SIM/EC stock
- **Service Supervisor**: Manages Technicians, work orders
- **Both**: Full access to sales and service operations

---

## 🛠️ Maintenance Commands

### After Code Updates
```cmd
cd C:\inetpub\wwwroot\service_booking
deploy_scripts\migrate_db.bat
deploy_scripts\collect_static.bat
iisreset
```

### Backup Database
```cmd
mysqldump -u django_user -p ybs_service_book_db > backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%.sql
```

### View Logs
```cmd
type C:\inetpub\wwwroot\service_booking\logs\django.log
```

### Django Admin Commands
```cmd
cd C:\inetpub\wwwroot\service_booking
venv\Scripts\python.exe manage.py <command> --settings=service_booking.settings_production
```

Common commands:
- `migrate` - Run database migrations
- `createsuperuser` - Create admin user
- `collectstatic` - Collect static files
- `check` - Verify Django configuration
- `shell` - Open Django shell

---

## 📁 Directory Structure After Deployment

```
C:\inetpub\wwwroot\service_booking\
├── venv\                         # Virtual environment
├── core\                         # Application code
├── service_booking\              # Project settings
├── staticfiles\                  # Collected static files (created by collectstatic)
├── logs\                         # Application logs (create manually)
├── media\                        # User uploads (create if needed)
├── deploy_scripts\               # Deployment scripts
├── web.config                    # IIS configuration
├── manage.py                     # Django management script
└── requirements.txt              # Python dependencies
```

---

## 🧪 Testing the Deployment

### 1. Basic Connectivity Test
```
http://localhost
```
Expected: Login page with styling

### 2. Admin Login Test
1. Navigate to login page
2. Enter superuser credentials
3. Verify dashboard loads

### 3. Static Files Test
- Check if CSS styles load
- Check if images display
- Check if JavaScript works

### 4. Database Test
- Create a new work order
- Assign to technician
- Complete work order
- Verify OTP system

### 5. API Test (if using API)
```
http://localhost/api/login/
```
Should return JSON response

---

## 🔄 Update Procedure

### Minor Updates (Bug fixes, small changes)
1. Backup database
2. Copy new files
3. Run migrations (if any)
4. Collect static files
5. Restart IIS

### Major Updates (New features, schema changes)
1. Backup database AND files
2. Test in staging environment first
3. Schedule maintenance window
4. Follow minor update steps
5. Run full regression testing

---

## 🆘 Troubleshooting

### Website Shows 500 Error
**Check:**
1. `logs\django.log` for Python errors
2. Database connection in `.env`
3. All dependencies installed
4. IIS logs in `C:\inetpub\logs\LogFiles\`

### Static Files Not Loading
**Fix:**
1. Run `collect_static.bat`
2. Check StaticFile handler in IIS (must be at top)
3. Verify staticfiles folder permissions

### Database Connection Failed
**Check:**
1. MySQL service running: `net start MySQL80`
2. Database exists and user has permissions
3. Credentials in `.env` correct
4. MySQL port (3306) not blocked

### FastCGI Timeout
**Fix:**
Increase timeouts in IIS FastCGI Settings to 600 seconds

---

## 📞 Support Information

### Documentation Files
- `DEPLOYMENT_GUIDE_IIS.md` - Complete deployment guide
- `QUICK_DEPLOYMENT_CHECKLIST.md` - Quick reference
- `SERVICE_SUPERVISOR_FIX.md` - Supervisor category fix
- `PRODUCT_ADMIN_ONLY_RESTRICTION.md` - Product access control
- `SUPERVISOR_RESTRICTIONS_FIXED.md` - Template fixes

### Log Locations
- Django logs: `C:\inetpub\wwwroot\service_booking\logs\django.log`
- IIS logs: `C:\inetpub\logs\LogFiles\W3SVC1\`
- MySQL logs: `C:\ProgramData\MySQL\MySQL Server 8.0\Data\`

### Useful Commands
```cmd
# Restart IIS
iisreset

# Check Django configuration
venv\Scripts\python.exe manage.py check --settings=service_booking.settings_production

# Django shell
venv\Scripts\python.exe manage.py shell --settings=service_booking.settings_production

# View running processes
tasklist | findstr python
```

---

## 🎓 Training Resources

### For System Administrators
- IIS Configuration: https://docs.microsoft.com/en-us/iis/
- Django Deployment: https://docs.djangoproject.com/en/5.2/howto/deployment/
- MySQL Administration: https://dev.mysql.com/doc/

### For Application Users
- User manual: (to be created based on user needs)
- Training videos: (can be created post-deployment)

---

## 📈 Performance Optimization

### For Better Performance
1. Enable compression in IIS
2. Configure browser caching for static files
3. Optimize database queries (indexes)
4. Use connection pooling for MySQL
5. Consider Redis for caching (advanced)

### Monitoring
- Monitor IIS performance counters
- Track slow database queries
- Monitor disk space (logs can grow)
- Set up automated backups

---

## ✅ Deployment Success Criteria

Your deployment is successful when:

- ✅ Website accessible from browser
- ✅ Login page displays correctly
- ✅ Admin can login and access dashboard
- ✅ All menu items load properly
- ✅ Static files (CSS, JS, images) load
- ✅ Database operations work
- ✅ Work orders can be created
- ✅ Users can be added
- ✅ No errors in logs
- ✅ Accessible from other computers on network

---

## 🎉 Next Steps After Deployment

1. **Create initial data**:
   - Add operators (Jio, Airtel, etc.)
   - Add service types
   - Create supervisor categories
   - Add initial supervisors

2. **Configure system**:
   - Set up SIM operator pricing
   - Configure product categories
   - Add initial products
   - Set up pincodes

3. **Train users**:
   - Admin training
   - Supervisor training
   - Technician training
   - Retailer training

4. **Set up monitoring**:
   - Regular backup schedule
   - Log rotation
   - Performance monitoring
   - Uptime monitoring

---

## 📝 Version Information

- **Application**: Service Booking System
- **Django Version**: 5.2.4
- **Python Version**: 3.13
- **Database**: MySQL 8.0
- **Deployment Target**: Windows Server with IIS
- **Document Version**: 1.0
- **Last Updated**: November 2025

---

## 📄 License & Support

This is a proprietary application. All rights reserved.

For technical support or issues:
1. Check the deployment guides
2. Review log files
3. Contact system administrator
4. Contact development team

---

**Ready to deploy?** Start with `DEPLOYMENT_GUIDE_IIS.md` or `QUICK_DEPLOYMENT_CHECKLIST.md`
