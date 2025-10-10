from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager




class UserManager(BaseUserManager):
    def create_user(self, name, phone, email, password=None, role="technician"):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(name=name, phone=phone, email=email, role=role)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, name, phone, email, password):
        user = self.create_user(name=name, phone=phone, email=email, password=password, role="admin")
        user.is_admin = True
        user.save(using=self._db)
        return user

class User(AbstractBaseUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("supervisor", "Supervisor"),
        ("technician", "Technician"),
    ]

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    alternate_no = models.CharField(max_length=15, blank=True, null=True)
    whatsapp_no = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(unique=True)
    address = models.TextField(blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="technician")

    undersupervisor = models.ForeignKey(
        'self', on_delete=models.SET_NULL, blank=True, null=True, related_name='technicians_under'
    )

    collection_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    paid_to_company = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    pending_work = models.IntegerField(default=0)
    assigned_work = models.IntegerField(default=0)
    completed_work = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "phone"]

    objects = UserManager()

    def __str__(self):
        return self.name

    @property
    def is_staff(self):
        return self.is_admin

class CollectionTransfer(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Rejected", "Rejected"),
    ]

    technician = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="sent_transfers"
    )
    supervisor = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="received_transfers"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.technician.name} → {self.supervisor.name} ({self.amount})"

    def accept(self):
        """When supervisor accepts, move amount from technician to supervisor."""
        if self.status == "Pending":
            tech = self.technician
            sup = self.supervisor
            if tech.collection_amount >= self.amount:
                tech.collection_amount -= self.amount
                sup.collection_amount += self.amount
                tech.save()
                sup.save()
                self.status = "Accepted"
                self.save()

    def reject(self):
        if self.status == "Pending":
            self.status = "Rejected"
            self.save()




class Operator(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class TypeOfService(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class WorkFromTheRole(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Material(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    in_meter = models.BooleanField(default=False)

    def __str__(self):
        return self.name







class Technician(models.Model):
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    alternate_mobile = models.CharField(max_length=15, blank=True, null=True)
    whatsapp_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class WorkStb(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Closed", "Closed"),
        ("Cancelled", "Cancelled"),
    ]

    customer_name = models.CharField(max_length=100)
    address = models.TextField()
    pincode = models.CharField(max_length=10)
    mobile_no = models.CharField(max_length=15)
    alternate_no = models.CharField(max_length=15, blank=True, null=True)
    wp_no = models.CharField(max_length=15, blank=True, null=True)
    operator = models.ForeignKey("Operator", on_delete=models.CASCADE)
    type_of_service = models.ForeignKey("TypeOfService", on_delete=models.CASCADE)
    work_from = models.ForeignKey("WorkFromTheRole", on_delete=models.CASCADE)
    work_got_time = models.DateTimeField()
    work_closing_time = models.DateTimeField(blank=True, null=True)
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="supervisor_work")
    assigned_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="technician_work")
    remark = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")   
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.customer_name} - {self.operator}"


class WorkReport(models.Model):
    work = models.OneToOneField("WorkStb", on_delete=models.CASCADE, related_name="report")
    cancellation_remark = models.TextField(blank=True, null=True)
    used_materials = models.JSONField(default=list, blank=True)  # list of dicts
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    collected_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report for {self.work.customer_name}"

    def calculate_subtotal(self):
        """Calculate subtotal: work.amount + sum(used materials total)"""
        total_materials = 0.0
        for item in self.used_materials:
            try:
                total_materials += float(item.get("total", 0))
            except:
                pass
        return float(self.work.amount) + total_materials

