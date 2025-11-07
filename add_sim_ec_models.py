"""Script to add SIM and EC models to core/models.py"""

sim_ec_models = '''

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

    remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.from_user.name} → {self.to_user.name} - {self.sim.serial_number} [{self.status}]"

    def accept(self):
        """Accept transfer and update SIM holder"""
        if self.status == "pending":
            self.status = "accepted"
            self.accepted_at = timezone.now()
            self.sim.current_holder = self.to_user
            self.sim.save()
            self.save()
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

class EcStock(models.Model):
    """EC Stock tracking per user"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ec_stocks")
    quantity = models.IntegerField(default=0, help_text="Number of EC units")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user']

    def __str__(self):
        return f"{self.user.name} - EC: {self.quantity}"


class EcTransfer(models.Model):
    """Track EC stock transfers between users"""
    TRANSFER_TYPE_CHOICES = [
        ("transfer", "Transfer"),
        ("return", "Return"),
    ]

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ec_transfers_sent")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ec_transfers_received")
    quantity = models.IntegerField(help_text="Number of EC units")
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES, default="transfer")

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.from_user.name} → {self.to_user.name} - EC: {self.quantity} [{self.status}]"

    def accept(self):
        """Accept transfer and update EC stock"""
        if self.status == "pending":
            from django.db import transaction

            with transaction.atomic():
                # Get or create EC stock records
                from_stock, _ = EcStock.objects.get_or_create(user=self.from_user, defaults={'quantity': 0})
                to_stock, _ = EcStock.objects.get_or_create(user=self.to_user, defaults={'quantity': 0})

                # Validate sender has enough stock
                if from_stock.quantity < self.quantity:
                    raise ValueError(f"Insufficient EC stock. Available: {from_stock.quantity}, Required: {self.quantity}")

                # Update stocks
                from_stock.quantity -= self.quantity
                to_stock.quantity += self.quantity
                from_stock.save()
                to_stock.save()

                # Update transfer status
                self.status = "accepted"
                self.accepted_at = timezone.now()
                self.save()

            return True
        return False

    def reject(self):
        if self.status == "pending":
            self.status = "rejected"
            self.rejected_at = timezone.now()
            self.save()
            return True
        return False
'''

# Read current models.py
with open('core/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Append new models
with open('core/models.py', 'a', encoding='utf-8') as f:
    f.write(sim_ec_models)

print("SIM and EC models added successfully!")
