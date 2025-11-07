from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.conf import settings
from django.utils import timezone


class SupervisorCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g., Sales, Services, Both

    def __str__(self):
        return self.name



class UserManager(BaseUserManager):
    def create_user(self, name, phone, email, password=None, role="technician"):
        if not email:
           raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(name=name, phone=phone, email=email, role=role)
        user.password = password  # plain
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
        ("fos", "FOS"),
        ("retailer", "Retailer"),
        ("technician", "Technician"),
    ]

    TECHNICIAN_TYPE_CHOICES = [
        ("own", "Own Technician"),
        ("freelance", "Freelance Technician"),
    ]

    supervisor_category = models.ForeignKey(
        "SupervisorCategory", on_delete=models.SET_NULL, null=True, blank=True, 
        related_name="supervisors"
    )

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    alternate_no = models.CharField(max_length=15, blank=True, null=True)
    whatsapp_no = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(unique=True)
    address = models.TextField(blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="technician")
    technician_type = models.CharField(max_length=20, choices=TECHNICIAN_TYPE_CHOICES, null=True, blank=True)

    # Relationship fields
    supervisor = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='users_under'
    )

    fos_links = models.ManyToManyField(
        'self', blank=True, related_name='retailers_under', symmetrical=False
    )

    # money tracking
    collection_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Amount collected from customers")
    paid_to_company = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    pending_work = models.IntegerField(default=0)
    assigned_work = models.IntegerField(default=0)
    completed_work = models.IntegerField(default=0)

    # Freelancer payment tracking (only for freelance technicians)
    payment_wallet = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Pending payment amount for freelancer work")

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "phone"]

    objects = UserManager()

    def __str__(self):
        return f"{self.name} ({self.role})"

    @property
    def is_staff(self):
        return self.is_admin







class StockSale(models.Model):
    operator = models.CharField(max_length=100)
    order_id = models.CharField(max_length=50, unique=True)
    order_date = models.DateField()
    partner_id = models.CharField(max_length=50)
    partner_name = models.CharField(max_length=200)
    transfer_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission = models.DecimalField(max_digits=12, decimal_places=2)
    amount_without_commission = models.DecimalField(max_digits=12, decimal_places=2)
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.operator} - {self.order_id}"















class FOS(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, limit_choices_to={'role': 'fos'}, related_name='fos_profile'
    )
    supervisor = models.ForeignKey(
        User, on_delete=models.CASCADE, limit_choices_to={'role': 'supervisor'}, related_name='fos_supervisors'
    )
    operators = models.ManyToManyField("Operator")  # Multiple operators

    def __str__(self):
        return self.user.name

class Retailer(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, limit_choices_to={'role': 'retailer'}, related_name='retailer_profile'
    )
    supervisor = models.ForeignKey(
        User, on_delete=models.CASCADE, limit_choices_to={'role': 'supervisor'}, related_name='retailer_supervisors'
    )
    fos = models.ManyToManyField(FOS)  # Multiple FOS

    def __str__(self):
        return self.user.name

class Technician(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, limit_choices_to={'role': 'technician'}, related_name='technician_profile'
    )
    supervisor = models.ForeignKey(
        User, on_delete=models.CASCADE, limit_choices_to={'role': 'supervisor'}, related_name='technician_supervisors',
        null=True, blank=True  # <-- add this
    )

    def __str__(self):
        return self.user.name

# ...existing code...



class CollectionTransfer(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Rejected", "Rejected"),
    ]

    # Renamed fields to be generic (sender/receiver instead of technician/supervisor)
    # to support supervisor → admin transfers too
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
        """When receiver accepts, move amount from sender to receiver."""
        if self.status == "Pending":
            sender = self.technician  # Can be technician or supervisor
            receiver = self.supervisor  # Can be supervisor or admin

            # Validate sender has sufficient balance
            if sender.collection_amount < self.amount:
                raise ValueError(f"{sender.name} has insufficient balance. Available: ₹{sender.collection_amount}, Required: ₹{self.amount}")

            # Perform transfer
            sender.collection_amount = float(sender.collection_amount) - float(self.amount)
            receiver.collection_amount = float(receiver.collection_amount) + float(self.amount)

            # For receivers (supervisor/admin), also track paid_to_company
            if receiver.role in ['supervisor', 'admin']:
                receiver.paid_to_company = float(receiver.paid_to_company) + float(self.amount)

            sender.save()
            receiver.save()
            self.status = "Accepted"
            self.save()

            return True
        return False

    def reject(self):
        if self.status == "Pending":
            self.status = "Rejected"
            self.save()
            return True
        return False





class Operator(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name




class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, blank=True, null=True)   # optional SKU/code
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="products")
    is_meter = models.BooleanField(default=False)      # product sold in meters (float qtys)
    is_serialized = models.BooleanField(default=False) # product needs serial numbers
    # if product itself has serial number (per unit) -> ProductSerial rows capture serials

    PRODUCT_CATEGORY_CHOICES = [
        ("dth", "DTH"),
        ("fiber", "Fiber"),
    ]
    product_category = models.CharField(max_length=10, choices=PRODUCT_CATEGORY_CHOICES, default="dth")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("operator", "name")  # optional: avoid duplicates per operator

    def __str__(self):
        return f"{self.name} ({self.operator.name})"




class ProductStock(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="stock")
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)  # supports meters
    # For serialized items, qty should match number of serials available
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} — {self.qty}"

class ProductSerial(models.Model):
    STATUS_CHOICES = [
        ("Available", "Available"),
        ("Used", "Used"),
        ("Defective", "Defective"),
        ("Returned", "Returned"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="serials")
    serial = models.CharField(max_length=255, unique=True)  # unique serial across products
    purchase_item = models.ForeignKey("PurchaseItem", on_delete=models.SET_NULL, null=True, blank=True, related_name="serials")
    created_at = models.DateTimeField(auto_now_add=True)
    is_sold = models.BooleanField(default=False)  # optionally mark sold when allocated to sale

    # New fields for tracking usage and status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Available",
        help_text="Current status of this serial number"
    )
    used_in_work = models.ForeignKey(
        "WorkStb",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="used_serials",
        help_text="Work order where this serial was used"
    )
    assigned_to_user = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_serials",
        help_text="User who currently has this serial in stock"
    )

    def __str__(self):
        return f"{self.serial} ({self.product.name}) - {self.status}"

class Purchase(models.Model):
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="purchases")
    bill_number = models.CharField(max_length=100)
    bill_date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("operator", "bill_number")  # avoid duplicate bills for same operator

    def __str__(self):
        return f"Purchase {self.bill_number} / {self.operator.name} - {self.bill_date}"

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    # For serialized items, serials are stored in ProductSerial.purchase_item -> backref

    def save(self, *args, **kwargs):
        # compute subtotal if not provided
        self.subtotal = float(self.qty) * float(self.unit_price)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.qty} @ {self.unit_price}"




class Pincode(models.Model):
    pincode = models.CharField(max_length=10, unique=True)
    area_name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['pincode']

    def __str__(self):
        return f"{self.pincode} - {self.area_name}, {self.city}"

class PincodeAssignment(models.Model):
    supervisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assigned_pincodes", limit_choices_to={'role': 'supervisor'})
    pincode = models.ForeignKey(Pincode, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="pincode_assignments_made")

    class Meta:
        unique_together = ('supervisor', 'pincode')  # Prevent duplicate assignments
        ordering = ['supervisor__name', 'pincode__pincode']

    def __str__(self):
        return f"{self.supervisor.name} - {self.pincode.pincode}"







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







class WorkCategoryOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "name"]

    def __str__(self):
        return self.name


class WorkWarrantyOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "name"]

    def __str__(self):
        return self.name


class WorkJobTypeOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "name"]

    def __str__(self):
        return self.name


class WorkDthTypeOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "name"]

    def __str__(self):
        return self.name


class WorkFiberTypeOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "name"]

    def __str__(self):
        return self.name


class WorkFrIssueOption(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "name"]

    def __str__(self):
        return self.name


class WorkStb(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Expired", "Expired"),
        ("Closed", "Closed"),
        ("Cancelled", "Cancelled"),
    ]

    KIND_CHOICES = [
        ("service", "Service"),
        ("installation", "Installation"),
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
    work_deadline_time = models.DateTimeField(help_text="Deadline to complete the work", null=True, blank=True)
    work_closing_time = models.DateTimeField(blank=True, null=True)

    # Track who added the work
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="works_created", help_text="User who created this work")

    # New fields for web flows
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="service")
    warranty = models.CharField(max_length=50, default="out")
    category = models.CharField(max_length=50, default="dth")
    dth_type = models.CharField(max_length=50, blank=True, null=True)
    fiber_type = models.CharField(max_length=50, blank=True, null=True)
    job_type = models.CharField(max_length=50, default="fr")
    fr_issue = models.CharField(max_length=50, blank=True, null=True)

    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="supervisor_work")
    assigned_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="technician_work")
    remark = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    # OTP fields for work closing
    closing_otp = models.CharField(max_length=6, blank=True, null=True, help_text="OTP sent to customer for work closing")
    otp_sent_at = models.DateTimeField(blank=True, null=True, help_text="When OTP was sent")


    def __str__(self):
        return f"{self.customer_name} - {self.operator}"

    def is_expired(self):
        """Check if work deadline has passed"""
        if self.status in ['Closed', 'Cancelled']:
            return False
        return timezone.now() > self.work_deadline_time

    def time_remaining(self):
        """Return time remaining or time overdue as timedelta"""
        return self.work_deadline_time - timezone.now()

    def get_category_display(self):
        option = WorkCategoryOption.objects.filter(code=self.category).first()
        return option.name if option else (self.category or "-")

    def get_warranty_display(self):
        option = WorkWarrantyOption.objects.filter(code=self.warranty).first()
        return option.name if option else (self.warranty or "-")

    def get_job_type_display(self):
        option = WorkJobTypeOption.objects.filter(code=self.job_type).first()
        return option.name if option else (self.job_type or "-")

    def get_dth_type_display(self):
        option = WorkDthTypeOption.objects.filter(code=self.dth_type).first()
        return option.name if option else (self.dth_type or "-")

    def get_fiber_type_display(self):
        option = WorkFiberTypeOption.objects.filter(code=self.fiber_type).first()
        return option.name if option else (self.fiber_type or "-")

    def get_fr_issue_display(self):
        option = WorkFrIssueOption.objects.filter(code=self.fr_issue).first()
        return option.name if option else (self.fr_issue or "-")



class WorkReport(models.Model):
    REPAIR_TYPE_CHOICES = [
        ("Swapping", "Swapping"),
        ("Field Repair", "Field Repair"),
        ("Retrieval", "Retrieval"),
    ]

    work = models.OneToOneField("WorkStb", on_delete=models.CASCADE, related_name="report")
    cancellation_remark = models.TextField(blank=True, null=True)
    used_materials = models.JSONField(default=list, blank=True)  # list of dicts with serials
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    collected_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    who_collected = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="collections_made",
        help_text="Who collected the money from customer"
    )

    # Repair-specific fields
    repair_type = models.CharField(
        max_length=20,
        choices=REPAIR_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="Type of repair work (only for repair service)"
    )
    returned_product = models.ForeignKey(
        "Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="returned_in_works",
        help_text="Defective product returned by customer"
    )
    returned_serial = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Serial number of returned defective product"
    )
    returned_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Quantity of returned product (for non-serialized)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Freelancer payment
    freelancer_payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        help_text="Amount to be paid to freelancer technician for this work"
    )

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

    def materials_total(self):
        total = 0.0
        for item in self.used_materials:
            try:
                total += float(item.get("total", 0))
            except Exception:
                continue
        return total


# Link FOS ↔ Operators
class FosOperatorMap(models.Model):
    fos = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'fos'})
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('fos', 'operator')

    def __str__(self):
        return f"{self.fos.name} → {self.operator.name}"


# Link Retailer ↔ FOS
class RetailerFosMap(models.Model):
    retailer = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'retailer'},related_name="retailer_fos_maps")
    fos = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'fos'},related_name="fos_retailer_maps")

    def __str__(self):
        return f"{self.retailer.name} ↔ {self.fos.name}"



class UserProductStock(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="product_stocks")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="user_stocks")
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)  # support for meters
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["user__name", "product__name"]

    def __str__(self):
        return f"{self.user.name} — {self.product.name}: {self.qty}"


class TechnicianPayment(models.Model):
    """
    Track payment requests from supervisor to freelance technicians.
    Flow: Supervisor marks payment → Technician accepts → Amount deducted from payment_wallet
    """
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Rejected", "Rejected"),
    ]

    technician = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_payments",
        limit_choices_to={'role': 'technician', 'technician_type': 'freelance'}
    )
    supervisor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_payments",
        limit_choices_to={'role': 'supervisor'}
    )
    work = models.ForeignKey(
        "WorkStb",
        on_delete=models.CASCADE,
        related_name="technician_payments",
        null=True,
        blank=True,
        help_text="Work order for which payment is being made"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    marked_paid_at = models.DateTimeField(null=True, blank=True, help_text="When supervisor marked as paid")
    accepted_at = models.DateTimeField(null=True, blank=True, help_text="When technician accepted payment")

    def __str__(self):
        return f"{self.supervisor.name} → {self.technician.name} (₹{self.amount}) [{self.status}]"

    def accept(self):
        """When technician accepts, deduct amount from their payment_wallet"""
        if self.status == "Pending":
            # Validate technician has sufficient balance
            if self.technician.payment_wallet < self.amount:
                raise ValueError(f"Insufficient balance. Available: ₹{self.technician.payment_wallet}, Required: ₹{self.amount}")

            # Deduct from payment wallet
            self.technician.payment_wallet = float(self.technician.payment_wallet) - float(self.amount)
            self.technician.save()

            self.status = "Accepted"
            self.accepted_at = timezone.now()
            self.save()
            return True
        return False

    def reject(self):
        if self.status == "Pending":
            self.status = "Rejected"
            self.save()
            return True
        return False
















# ==================== SIM STOCK MANAGEMENT ====================

class SimOperatorPrice(models.Model):
    """Purchase and selling price for SIM cards by operator"""
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="sim_prices")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at which SIM is purchased")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at which SIM is sold")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["operator"]

    def __str__(self):
        return f"{self.operator.name} - Purchase: ?{self.purchase_price}, Selling: ?{self.selling_price}"


class SimPurchase(models.Model):
    """SIM purchase record (similar to Product Purchase)"""
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="sim_purchases")
    purchase_date = models.DateField()
    supplier_name = models.CharField(max_length=200, blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    total_quantity = models.IntegerField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    remark = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sim_purchases_created")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SIM Purchase - {self.operator.name} - {self.total_quantity} cards - {self.purchase_date}"


class SimStock(models.Model):
    """Individual SIM card with unique serial number"""
    serial_number = models.CharField(max_length=100, unique=True, help_text="Unique serial number for SIM card")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="sim_stocks")
    purchase = models.ForeignKey(SimPurchase, on_delete=models.CASCADE, related_name="sim_cards", null=True, blank=True)

    # Current holder
    current_holder = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sim_stocks")

    # Status tracking
    STATUS_CHOICES = [
        ("available", "Available"),
        ("sold", "Sold"),
        ("returned", "Returned"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")

    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)

    sold_date = models.DateTimeField(null=True, blank=True)
    sold_to_customer = models.CharField(max_length=200, blank=True, null=True, help_text="End customer name")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.operator.name} - {self.serial_number} - {self.status}"


class SimTransfer(models.Model):
    """Track SIM stock transfers between users"""
    TRANSFER_TYPE_CHOICES = [
        ("transfer", "Transfer"),
        ("return", "Return"),
    ]

    sim = models.ForeignKey(SimStock, on_delete=models.CASCADE, related_name="transfers")
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sim_transfers_sent")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sim_transfers_received")
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES, default="transfer")
    quantity = models.IntegerField(default=1, help_text="Always 1 for SIM (individual tracking)")

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    batch_id = models.CharField(max_length=100, null=True, blank=True, help_text="Group transfers made together")
    remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.from_user.name} → {self.to_user.name} - {self.sim.serial_number} [{self.status}]"

    def accept(self):
        """Accept transfer and update SIM holder"""
        from django.db import transaction

        if self.status == "pending":
            with transaction.atomic():
                self.status = "accepted"
                self.accepted_at = timezone.now()
                self.sim.current_holder = self.to_user
                self.sim.save()
                self.save()

                # If recipient is a retailer, add SIM value to their wallet (debt to FOS)
                if self.to_user.role == 'retailer':
                    wallet, created = RetailerSimWallet.objects.get_or_create(
                        retailer=self.to_user,
                        operator=self.sim.operator,
                        defaults={'pending_amount': 0, 'total_sims_received': 0, 'total_amount': 0}
                    )
                    wallet.pending_amount += self.sim.selling_price
                    wallet.total_sims_received += 1
                    wallet.total_amount += self.sim.selling_price
                    wallet.save()

            return True
        return False

    def reject(self):
        if self.status == "pending":
            self.status = "rejected"
            self.rejected_at = timezone.now()
            self.save()
            return True
        return False


# ==================== EC STOCK MANAGEMENT ====================

# ==================== EC RECHARGE SYSTEM ====================

class EcSale(models.Model):
    """EC (Electronic Recharge) Sales Record"""
    order_id = models.CharField(max_length=50, unique=True, help_text="Order ID from recharge system")
    order_date = models.DateField(help_text="Date of recharge order")

    # Hierarchy
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="ec_sales")
    supervisor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ec_sales_supervisor",
        limit_choices_to={'role': 'supervisor'}
    )
    fos = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ec_sales_fos",
        limit_choices_to={'role': 'fos'}
    )
    retailer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ec_sales_retailer",
        limit_choices_to={'role': 'retailer'}
    )

    # Recharge Details
    partner_id = models.CharField(max_length=50, help_text="Partner ID from system")
    partner_name = models.CharField(max_length=255, help_text="Partner Name (Retailer name)")
    transfer_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total transfer amount")
    commission = models.DecimalField(max_digits=10, decimal_places=2, help_text="Commission earned")
    amount_without_commission = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount retailer owes to FOS")

    # Tracking
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="ec_uploads")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    upload_type = models.CharField(max_length=20, choices=[('manual', 'Manual'), ('excel', 'Excel')], default='manual')

    class Meta:
        ordering = ['-order_date', '-uploaded_at']
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['operator', 'order_date']),
            models.Index(fields=['retailer']),
        ]

    def __str__(self):
        return f"EC-{self.order_id} | {self.retailer.name} | ₹{self.amount_without_commission}"


class RetailerWallet(models.Model):
    """Retailer's pending wallet - amount they owe to FOS"""
    retailer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="retailer_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount pending to pay FOS")
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total EC sales")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['retailer', 'operator']

    def __str__(self):
        return f"{self.retailer.name} | {self.operator.name} | Pending: ₹{self.pending_amount}"


class FosWallet(models.Model):
    """FOS's EC wallet - amount collected from retailers, pending to supervisor"""
    fos = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fos_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount collected from retailers, pending to supervisor")
    total_collected_from_retailers = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total EC collected from retailers")
    total_paid_to_supervisor = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total EC paid to supervisor")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['fos', 'operator']

    def __str__(self):
        return f"{self.fos.name} (FOS) | {self.operator.name} | Pending: ₹{self.pending_amount}"


class SupervisorWallet(models.Model):
    """Supervisor's EC wallet - amount collected from FOS, pending to admin"""
    supervisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="supervisor_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount collected from FOS, pending to admin")
    total_collected_from_fos = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total EC collected from FOS")
    total_paid_to_admin = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total EC paid to admin")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['supervisor', 'operator']

    def __str__(self):
        return f"{self.supervisor.name} (Supervisor) | {self.operator.name} | Pending: ₹{self.pending_amount}"


class EcCollection(models.Model):
    """EC Collection tracking - money flow from retailer to admin"""
    COLLECTION_LEVEL_CHOICES = [
        ('retailer_to_fos', 'Retailer → FOS'),
        ('fos_to_supervisor', 'FOS → Supervisor'),
        ('supervisor_to_admin', 'Supervisor → Admin'),
    ]

    collection_level = models.CharField(max_length=30, choices=COLLECTION_LEVEL_CHOICES)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)

    # From-To Users
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ec_collections_given")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ec_collections_received")

    # Amount Details
    collection_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount collected")
    pending_before = models.DecimalField(max_digits=12, decimal_places=2, help_text="Pending amount before collection")
    pending_after = models.DecimalField(max_digits=12, decimal_places=2, help_text="Pending amount after collection")

    # Tracking
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="ec_collections_done")
    collection_date = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-collection_date', '-created_at']

    def __str__(self):
        return f"{self.from_user.name} → {self.to_user.name} | ₹{self.collection_amount} | {self.collection_date}"


# ==================== SIM WALLET MANAGEMENT ====================

class RetailerSimWallet(models.Model):
    """Retailer's SIM wallet - debt owed to FOS for SIM purchases"""
    retailer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="retailer_sim_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount owed to FOS for SIMs received")
    total_sims_received = models.IntegerField(default=0, help_text="Total SIMs received from FOS")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total value of SIMs received")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['retailer', 'operator']

    def __str__(self):
        return f"{self.retailer.name} (Retailer) | {self.operator.name} | Pending: ₹{self.pending_amount}"


class FosSimWallet(models.Model):
    """FOS's SIM wallet - amount collected from retailers, pending to supervisor"""
    fos = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fos_sim_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount collected from retailers, pending to supervisor")
    total_collected_from_retailers = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total amount collected from retailers")
    total_paid_to_supervisor = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total amount paid to supervisor")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['fos', 'operator']

    def __str__(self):
        return f"{self.fos.name} (FOS) | {self.operator.name} | Pending: ₹{self.pending_amount}"


class SupervisorSimWallet(models.Model):
    """Supervisor's SIM wallet - amount collected from FOS, pending to admin"""
    supervisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="supervisor_sim_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount collected from FOS, pending to admin")
    total_collected_from_fos = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total amount collected from FOS")
    total_paid_to_admin = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total amount paid to admin")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['supervisor', 'operator']

    def __str__(self):
        return f"{self.supervisor.name} (Supervisor) | {self.operator.name} | Pending: ₹{self.pending_amount}"


class SimCollection(models.Model):
    """SIM Collection tracking - money flow from retailer to admin for SIM purchases"""
    COLLECTION_LEVEL_CHOICES = [
        ('retailer_to_fos', 'Retailer → FOS'),
        ('fos_to_supervisor', 'FOS → Supervisor'),
        ('supervisor_to_admin', 'Supervisor → Admin'),
    ]

    collection_level = models.CharField(max_length=30, choices=COLLECTION_LEVEL_CHOICES)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)

    # From-To Users
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sim_collections_given')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sim_collections_received')
    collected_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sim_collections_made')

    # Amount tracking
    collection_amount = models.DecimalField(max_digits=12, decimal_places=2)
    pending_before = models.DecimalField(max_digits=12, decimal_places=2)
    pending_after = models.DecimalField(max_digits=12, decimal_places=2)

    collection_date = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-collection_date', '-created_at']

    def __str__(self):
        return f"SIM: {self.from_user.name} → {self.to_user.name} | ₹{self.collection_amount} | {self.collection_date}"


# ==================== HANDSET STOCK MANAGEMENT ====================

class HandsetType(models.Model):
    """Handset types for each operator (e.g., JioPhone, Airtel 4G Handset)"""
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="handset_types")
    name = models.CharField(max_length=200, help_text="Handset type name (e.g., JioPhone Next)")
    model_number = models.CharField(max_length=100, blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at which handset is purchased")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at which handset is sold")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['operator', 'name']
        ordering = ['operator', 'name']

    def __str__(self):
        return f"{self.operator.name} - {self.name} (₹{self.selling_price})"


class HandsetPurchase(models.Model):
    """Bulk handset purchase record"""
    handset_type = models.ForeignKey(HandsetType, on_delete=models.CASCADE, related_name="purchases")
    total_quantity = models.IntegerField()
    purchase_date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-purchase_date']

    def __str__(self):
        return f"{self.handset_type.name} - {self.total_quantity} units - {self.purchase_date}"


class HandsetStock(models.Model):
    """Individual handset tracking"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('damaged', 'Damaged'),
        ('returned', 'Returned'),
    ]

    serial_number = models.CharField(max_length=100, unique=True)
    imei_number = models.CharField(max_length=20, blank=True, null=True, help_text="IMEI number if applicable")
    handset_type = models.ForeignKey(HandsetType, on_delete=models.CASCADE, related_name="stock_items")
    purchase = models.ForeignKey(HandsetPurchase, on_delete=models.CASCADE, related_name="handsets")
    current_holder = models.ForeignKey(User, on_delete=models.CASCADE, related_name="handset_stock")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    sold_to_customer = models.CharField(max_length=200, blank=True, null=True)
    sold_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.handset_type.name} - {self.serial_number} ({self.status})"


class HandsetTransfer(models.Model):
    """Handset transfer tracking"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    TRANSFER_TYPE_CHOICES = [
        ('transfer', 'Transfer'),
        ('return', 'Return'),
    ]

    handset = models.ForeignKey(HandsetStock, on_delete=models.CASCADE, related_name="transfers")
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='handset_transfers_sent')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='handset_transfers_received')
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES, default='transfer')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    batch_id = models.CharField(max_length=100, null=True, blank=True, help_text="Group transfers made together")
    remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    rejected_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.handset.serial_number}: {self.from_user.name} → {self.to_user.name} ({self.status})"

    def accept(self):
        """Accept transfer and update handset holder"""
        from django.db import transaction

        if self.status == "pending":
            with transaction.atomic():
                self.status = "accepted"
                self.accepted_at = timezone.now()
                self.handset.current_holder = self.to_user
                self.handset.save()
                self.save()

                # If recipient is a retailer, add handset value to their wallet (debt to FOS)
                if self.to_user.role == 'retailer':
                    wallet, created = RetailerHandsetWallet.objects.get_or_create(
                        retailer=self.to_user,
                        operator=self.handset.handset_type.operator,
                        defaults={'pending_amount': 0, 'total_handsets_received': 0, 'total_amount': 0}
                    )
                    wallet.pending_amount += self.handset.selling_price
                    wallet.total_handsets_received += 1
                    wallet.total_amount += self.handset.selling_price
                    wallet.save()

            return True
        return False

    def reject(self):
        """Reject transfer"""
        if self.status == "pending":
            self.status = "rejected"
            self.rejected_at = timezone.now()
            self.save()
            return True
        return False


# ==================== HANDSET WALLET MODELS ====================

class RetailerHandsetWallet(models.Model):
    """Retailer's handset wallet - debt owed to FOS for handset purchases"""
    retailer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="retailer_handset_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount pending to be paid to FOS")
    total_handsets_received = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total value of all handsets received")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['retailer', 'operator']
        ordering = ['retailer', 'operator']

    def __str__(self):
        return f"{self.retailer.name} - {self.operator.name}: ₹{self.pending_amount} pending"


class FosHandsetWallet(models.Model):
    """FOS's handset wallet - amount collected from retailers, pending to supervisor"""
    fos = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fos_handset_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount pending to be paid to Supervisor")
    total_collected_from_retailers = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_to_supervisor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['fos', 'operator']
        ordering = ['fos', 'operator']

    def __str__(self):
        return f"{self.fos.name} - {self.operator.name}: ₹{self.pending_amount} pending"


class SupervisorHandsetWallet(models.Model):
    """Supervisor's handset wallet - amount collected from FOS, pending to admin"""
    supervisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="supervisor_handset_wallet")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount pending to be paid to Admin")
    total_collected_from_fos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_to_admin = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['supervisor', 'operator']
        ordering = ['supervisor', 'operator']

    def __str__(self):
        return f"{self.supervisor.name} - {self.operator.name}: ₹{self.pending_amount} pending"


class HandsetCollection(models.Model):
    """Handset collection tracking - money flow from retailer to admin"""
    COLLECTION_LEVEL_CHOICES = [
        ('retailer_to_fos', 'Retailer → FOS'),
        ('fos_to_supervisor', 'FOS → Supervisor'),
        ('supervisor_to_admin', 'Supervisor → Admin'),
    ]

    collection_level = models.CharField(max_length=30, choices=COLLECTION_LEVEL_CHOICES)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)

    # From-To Users
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='handset_collections_given')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='handset_collections_received')
    collected_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='handset_collections_made')

    # Amount tracking
    collection_amount = models.DecimalField(max_digits=12, decimal_places=2)
    pending_before = models.DecimalField(max_digits=12, decimal_places=2)
    pending_after = models.DecimalField(max_digits=12, decimal_places=2)

    collection_date = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-collection_date', '-created_at']

    def __str__(self):
        return f"Handset: {self.from_user.name} → {self.to_user.name} | ₹{self.collection_amount} | {self.collection_date}"
