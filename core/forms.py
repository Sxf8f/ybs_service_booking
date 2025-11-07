from django import forms
from .models import (
    Product,
    StockSale,
    Operator,
    Pincode,
    PincodeAssignment,
    User,
    WorkStb,
    WorkReport,
    WorkCategoryOption,
    WorkWarrantyOption,
    WorkJobTypeOption,
    WorkDthTypeOption,
    WorkFiberTypeOption,
    WorkFrIssueOption,
)

class StockSaleForm(forms.ModelForm):
    class Meta:
        model = StockSale
        fields = [
            "order_id",
            "order_date",
            "partner_id",
            "partner_name",
            "transfer_amount",
            "commission",
            "amount_without_commission",
        ]
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"})
        }

class OperatorSelectionForm(forms.Form):
    operator = forms.ModelChoiceField(
        queryset=Operator.objects.all(),
        empty_label="Select Operator",
        widget=forms.Select(attrs={"class": "form-control", "required": True})
    )


class OperatorForm(forms.ModelForm):
    class Meta:
        model = Operator
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter operator name"
            })
        }


class StockUploadForm(forms.Form):
    file = forms.FileField(
        label="Upload Excel File (.xlsx)",
        widget=forms.FileInput(attrs={"accept": ".xlsx","accept":".xls"})
    )

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "operator", "is_meter", "is_serialized", "product_category", "price"]


class PincodeForm(forms.ModelForm):
    class Meta:
        model = Pincode
        fields = ["pincode", "area_name", "city", "state", "is_active"]
        widgets = {
            "pincode": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter pincode"}),
            "area_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter area name"}),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter city"}),
            "state": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter state"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"})
        }

    def clean_pincode(self):
        pincode = self.cleaned_data.get('pincode')
        if pincode:
            # Check if pincode already exists (excluding current instance for updates)
            existing = Pincode.objects.filter(pincode=pincode)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("This pincode already exists.")
        return pincode


class PincodeAssignmentForm(forms.Form):
    supervisor = forms.ModelChoiceField(
        queryset=User.objects.filter(role='supervisor'),
        empty_label="Select Supervisor",
        widget=forms.Select(attrs={"class": "form-control", "required": True})
    )
    pincodes = forms.ModelMultipleChoiceField(
        queryset=Pincode.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=True,
        help_text="Select multiple pincodes to assign to the supervisor"
    )

    def clean(self):
        cleaned_data = super().clean()
        supervisor = cleaned_data.get('supervisor')
        pincodes = cleaned_data.get('pincodes')

        if supervisor and pincodes:
            # Check for existing assignments
            existing_assignments = PincodeAssignment.objects.filter(
                pincode__in=pincodes
            ).exclude(supervisor=supervisor)
            
            if existing_assignments.exists():
                assigned_pincodes = [str(assignment.pincode.pincode) for assignment in existing_assignments]
                raise forms.ValidationError(
                    f"The following pincodes are already assigned to other supervisors: {', '.join(assigned_pincodes)}"
                )
        
        return cleaned_data


class StockTransferToSupervisorForm(forms.Form):
    supervisor = forms.ModelChoiceField(queryset=User.objects.filter(role='supervisor'), required=True)
    product = forms.ModelChoiceField(queryset=Product.objects.all(), required=True)
    qty = forms.DecimalField(min_value=0.001, decimal_places=3, max_digits=12)

class StockTransferToTechnicianForm(forms.Form):
    # technician queryset to be overridden in view according to supervisor
    technician = forms.ModelChoiceField(queryset=User.objects.filter(role='technician'), required=True)
    product = forms.ModelChoiceField(queryset=Product.objects.all(), required=True)
    qty = forms.DecimalField(min_value=0.001, decimal_places=3, max_digits=12)

def _style_form_fields(form):
    for name, field in form.fields.items():
        widget = field.widget
        existing = widget.attrs.get('class', '')
        widget.attrs['class'] = (existing + ' modern-input').strip()
        if isinstance(widget, forms.Textarea):
            widget.attrs.setdefault('rows', 3)
        if isinstance(widget, forms.NumberInput):
            widget.attrs.setdefault('step', '0.01')


def _setup_choice_field(field, queryset, *, allow_blank=False, blank_label='Select an option', initial=None):
    options = list(queryset)
    choices = [(opt.code, opt.name) for opt in options]
    if allow_blank:
        choices = [('', blank_label)] + choices
        required = False
    else:
        required = field.required
    if not choices:
        choices = [('', 'No options configured')]
        required = False
        disabled = True
    else:
        disabled = False
    
    # Create a new ChoiceField to replace the CharField
    new_field = forms.ChoiceField(
        choices=choices,
        required=required,
        widget=forms.Select(attrs={'class': 'modern-input', 'disabled': disabled} if disabled else {'class': 'modern-input'})
    )
    if initial and not allow_blank:
        new_field.initial = initial
    elif not allow_blank and options and not initial:
        new_field.initial = options[0].code
    
    # Copy over any other attributes
    new_field.label = field.label
    new_field.help_text = field.help_text
    new_field.error_messages = field.error_messages
    
    return new_field


def _configure_work_form(form, include_deadline=True):
    _style_form_fields(form)

    if include_deadline and 'work_deadline_time' in form.fields:
        form.fields['work_deadline_time'].widget.attrs.setdefault('placeholder', 'Select deadline')

    form.fields['amount'].widget.attrs.setdefault('step', '0.01')
    form.fields['amount'].widget.attrs.setdefault('min', '0')

    master_configs = [
        ('category', WorkCategoryOption, False, 'Select category'),
        ('warranty', WorkWarrantyOption, False, 'Select warranty'),
        ('job_type', WorkJobTypeOption, False, 'Select job type'),
        ('dth_type', WorkDthTypeOption, True, 'Select DTH type'),
        ('fiber_type', WorkFiberTypeOption, True, 'Select fiber type'),
        ('fr_issue', WorkFrIssueOption, True, 'Select FR issue'),
    ]

    instance = getattr(form, 'instance', None)
    for field_name, model, allow_blank, blank_label in master_configs:
        if field_name not in form.fields:
            continue
        queryset = model.objects.filter(is_active=True).order_by('ordering', 'name')
        initial = None
        if instance and getattr(instance, field_name, None):
            initial = getattr(instance, field_name)
        # Replace the field with a ChoiceField
        form.fields[field_name] = _setup_choice_field(
            form.fields[field_name], 
            queryset, 
            allow_blank=allow_blank, 
            blank_label=blank_label, 
            initial=initial
        )


class WorkForm(forms.ModelForm):
    class Meta:
        model = WorkStb
        fields = [
            'customer_name','address','pincode','mobile_no','alternate_no','wp_no',
            'operator','type_of_service','work_from','work_deadline_time','amount',
            'remark',
            'warranty','category','dth_type','fiber_type','job_type','fr_issue'
        ]
        widgets = {
            'work_deadline_time': forms.DateTimeInput(attrs={'type':'datetime-local'})
        }
        labels = {
            'work_deadline_time': 'Work Deadline (Closing Time)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_work_form(self, include_deadline=True)

    def clean_pincode(self):
        pincode = self.cleaned_data.get('pincode')
        if pincode:
            from .models import PincodeAssignment
            if not PincodeAssignment.objects.filter(pincode__pincode=pincode).exists():
                raise forms.ValidationError("Enter a pincode assigned to a supervisor.")
        return pincode

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Derive kind from type_of_service name
        tos = self.cleaned_data.get('type_of_service')
        if tos:
            name = (tos.name or '').lower()
            obj.kind = 'installation' if 'install' in name else 'service'
        # Auto-assign supervisor from pincode
        pincode = self.cleaned_data.get('pincode')
        if pincode:
            from .models import PincodeAssignment
            assignment = PincodeAssignment.objects.filter(pincode__pincode=pincode).first()
            if assignment:
                obj.supervisor = assignment.supervisor
        if commit:
            obj.save()
        return obj

class RetailerWorkForm(forms.ModelForm):
    """Form for retailers - excludes work_deadline_time (auto-set to 24 hours)"""
    class Meta:
        model = WorkStb
        fields = [
            'customer_name','address','pincode','mobile_no','alternate_no','wp_no',
            'operator','type_of_service','work_from','amount',
            'remark',
            'warranty','category','dth_type','fiber_type','job_type','fr_issue'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_work_form(self, include_deadline=False)

    def clean_pincode(self):
        pincode = self.cleaned_data.get('pincode')
        if pincode:
            from .models import PincodeAssignment
            if not PincodeAssignment.objects.filter(pincode__pincode=pincode).exists():
                raise forms.ValidationError("Enter a pincode assigned to a supervisor.")
        return pincode

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Derive kind from type_of_service name
        tos = self.cleaned_data.get('type_of_service')
        if tos:
            name = (tos.name or '').lower()
            obj.kind = 'installation' if 'install' in name else 'service'
        # Auto-assign supervisor from pincode
        pincode = self.cleaned_data.get('pincode')
        if pincode:
            from .models import PincodeAssignment
            assignment = PincodeAssignment.objects.filter(pincode__pincode=pincode).first()
            if assignment:
                obj.supervisor = assignment.supervisor
        if commit:
            obj.save()
        return obj


class WorkCloseForm(forms.Form):
    collected_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    cancellation_remark = forms.CharField(required=False, widget=forms.Textarea)
    # materials: will be sent as arrays product_id[] qty[] via template JS


# ==================== SIM STOCK FORMS ====================

class SimOperatorPriceForm(forms.ModelForm):
    class Meta:
        from .models import SimOperatorPrice
        model = SimOperatorPrice
        fields = ['operator', 'purchase_price', 'selling_price']
        widgets = {
            'purchase_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class SimPurchaseForm(forms.ModelForm):
    class Meta:
        from .models import SimPurchase
        model = SimPurchase
        fields = ['operator', 'purchase_date', 'supplier_name', 'invoice_number', 'total_quantity', 'total_amount', 'remark']
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'total_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'remark': forms.Textarea(attrs={'rows': 3}),
        }


class SimStockForm(forms.ModelForm):
    class Meta:
        from .models import SimStock
        model = SimStock
        fields = ['serial_number', 'operator', 'purchase_price', 'selling_price']
        widgets = {
            'purchase_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class SimTransferForm(forms.Form):
    serial_numbers = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Enter serial numbers, one per line'}),
        help_text='Enter one serial number per line'
    )
    to_user = forms.ModelChoiceField(queryset=None, label='Transfer To')
    remark = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        from_user = kwargs.pop('from_user', None)
        super().__init__(*args, **kwargs)
        if from_user:
            from .models import User
            # Admin can transfer to sales supervisors
            if from_user.role == 'admin':
                self.fields['to_user'].queryset = User.objects.filter(
                    role='supervisor',
                    supervisor_category__name__in=['Sales', 'Both']
                )
            # Sales supervisor can transfer to FOS
            elif from_user.role == 'supervisor':
                self.fields['to_user'].queryset = User.objects.filter(role='fos', supervisor=from_user)
            # FOS can transfer to retailers
            elif from_user.role == 'fos':
                from .models import RetailerFosMap
                retailer_ids = RetailerFosMap.objects.filter(fos=from_user).values_list('retailer_id', flat=True)
                self.fields['to_user'].queryset = User.objects.filter(id__in=retailer_ids, role='retailer')


# ==================== EC STOCK FORMS ====================

class EcTransferForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label='EC Quantity')
    to_user = forms.ModelChoiceField(queryset=None, label='Transfer To')
    remark = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        from_user = kwargs.pop('from_user', None)
        super().__init__(*args, **kwargs)
        if from_user:
            from .models import User
            # Admin can transfer to sales supervisors
            if from_user.role == 'admin':
                self.fields['to_user'].queryset = User.objects.filter(
                    role='supervisor',
                    supervisor_category__name__in=['Sales', 'Both']
                )
            # Sales supervisor can transfer to FOS
            elif from_user.role == 'supervisor':
                self.fields['to_user'].queryset = User.objects.filter(role='fos', supervisor=from_user)
            # FOS can transfer to retailers
            elif from_user.role == 'fos':
                from .models import RetailerFosMap
                retailer_ids = RetailerFosMap.objects.filter(fos=from_user).values_list('retailer_id', flat=True)
                self.fields['to_user'].queryset = User.objects.filter(id__in=retailer_ids, role='retailer')


# ==================== HANDSET FORMS ====================

class HandsetTypeForm(forms.ModelForm):
    class Meta:
        from .models import HandsetType
        model = HandsetType
        fields = ['operator', 'name', 'model_number', 'purchase_price', 'selling_price', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class HandsetPurchaseForm(forms.ModelForm):
    class Meta:
        from .models import HandsetPurchase
        model = HandsetPurchase
        fields = ['handset_type', 'total_quantity', 'purchase_date']
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'handset_type': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import HandsetType
        # Customize the handset_type queryset to show all types with operator info
        self.fields['handset_type'].queryset = HandsetType.objects.select_related('operator').all().order_by('operator__name', 'name')
        # Customize label_from_instance to show operator and name
        self.fields['handset_type'].label_from_instance = lambda obj: f"{obj.operator.name} - {obj.name}{' (' + obj.model_number + ')' if obj.model_number else ''}"


class HandsetTransferForm(forms.Form):
    to_user = forms.ModelChoiceField(queryset=None, label="Transfer To")
    serial_numbers = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'placeholder': 'Enter serial numbers (one per line)'}),
        label="Serial Numbers"
    )
    remark = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional remarks'}),
        required=False,
        label="Remarks"
    )

    def __init__(self, *args, from_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import User

        if from_user:
            # Admin can transfer to supervisors
            if from_user.role == 'admin':
                self.fields['to_user'].queryset = User.objects.filter(
                    role='supervisor',
                    supervisor_category__name__in=['Sales', 'Both']
                )
            # Supervisor can transfer to FOS
            elif from_user.role == 'supervisor':
                self.fields['to_user'].queryset = User.objects.filter(role='fos', supervisor=from_user)
            # FOS can transfer to retailers
            elif from_user.role == 'fos':
                from .models import RetailerFosMap
                retailer_ids = RetailerFosMap.objects.filter(fos=from_user).values_list('retailer_id', flat=True)
                self.fields['to_user'].queryset = User.objects.filter(id__in=retailer_ids, role='retailer')

