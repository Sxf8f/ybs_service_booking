"""
Forms for EC Recharge System
"""
from django import forms
from .models import User, Operator, EcSale, EcCollection, Retailer
from django.core.exceptions import ValidationError


class EcUploadSelectForm(forms.Form):
    """Step 1: Select Operator, Supervisor, FOS"""
    operator = forms.ModelChoiceField(
        queryset=Operator.objects.all(),
        label="Select Operator",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    supervisor = forms.ModelChoiceField(
        queryset=User.objects.none(),  # Will be populated dynamically
        label="Select Supervisor (Sales/Both)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    fos = forms.ModelChoiceField(
        queryset=User.objects.none(),  # Will be populated dynamically
        label="Select FOS",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show only Sales and Both supervisors
        self.fields['supervisor'].queryset = User.objects.filter(
            role='supervisor',
            supervisor_category__name__in=['Sales', 'Both']
        )

        # Show all FOS initially (will be filtered by JavaScript based on supervisor and operator)
        self.fields['fos'].queryset = User.objects.filter(role='fos')


class EcManualEntryForm(forms.ModelForm):
    """Manual EC Entry Form"""
    retailer_search = forms.CharField(
        max_length=255,
        required=False,
        label="Search Retailer by Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type retailer name...',
            'autocomplete': 'off'
        })
    )

    class Meta:
        model = EcSale
        fields = [
            'order_id', 'order_date', 'partner_id', 'partner_name',
            'transfer_amount', 'commission', 'amount_without_commission', 'retailer'
        ]
        widgets = {
            'order_id': forms.TextInput(attrs={'class': 'form-control'}),
            'order_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'partner_id': forms.TextInput(attrs={'class': 'form-control'}),
            'partner_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'transfer_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'commission': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'amount_without_commission': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'retailer': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        fos_id = kwargs.pop('fos_id', None)
        super().__init__(*args, **kwargs)

        if fos_id:
            # Show only retailers under this FOS using RetailerFosMap
            from .models import RetailerFosMap
            retailer_ids = RetailerFosMap.objects.filter(
                fos_id=fos_id
            ).values_list('retailer_id', flat=True)

            self.fields['retailer'].queryset = User.objects.filter(
                id__in=retailer_ids,
                role='retailer'
            )
        else:
            self.fields['retailer'].queryset = User.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        retailer = cleaned_data.get('retailer')
        partner_name = cleaned_data.get('partner_name')

        if retailer:
            # Auto-fill partner_name with retailer's name
            if hasattr(retailer, 'user'):
                cleaned_data['partner_name'] = retailer.user.name

        return cleaned_data


class EcExcelUploadForm(forms.Form):
    """Excel Upload Form"""
    excel_file = forms.FileField(
        label="Upload Excel File",
        help_text="Upload Excel file with columns: Order ID, Order Date, Partner ID, Partner Name, Transfer Amount, Commission, Amount Without Commission",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'})
    )

    def clean_excel_file(self):
        file = self.cleaned_data['excel_file']

        # Validate file extension
        if not file.name.endswith(('.xlsx', '.xls')):
            raise ValidationError("Only Excel files (.xlsx, .xls) are allowed")

        # Validate file size (max 5MB)
        if file.size > 5 * 1024 * 1024:
            raise ValidationError("File size must be less than 5MB")

        return file


class EcCollectionForm(forms.ModelForm):
    """EC Collection Form"""
    class Meta:
        model = EcCollection
        fields = ['operator', 'from_user', 'collection_amount', 'collection_date', 'remarks']
        widgets = {
            'operator': forms.Select(attrs={'class': 'form-select'}),
            'from_user': forms.Select(attrs={'class': 'form-select'}),
            'collection_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'collection_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        collector_user = kwargs.pop('collector_user', None)
        super().__init__(*args, **kwargs)

        if collector_user:
            # Set queryset based on collector's role
            if collector_user.role == 'fos':
                # FOS collects from retailers under them - use RetailerFosMap
                from .models import RetailerFosMap
                retailer_ids = RetailerFosMap.objects.filter(fos=collector_user).values_list('retailer_id', flat=True)
                self.fields['from_user'].queryset = Retailer.objects.filter(
                    user_id__in=retailer_ids
                ).select_related('user')
                self.fields['from_user'].label = "Collect from Retailer"

            elif collector_user.role == 'supervisor':
                # Supervisor collects from FOS under them
                self.fields['from_user'].queryset = User.objects.filter(
                    role='fos',
                    supervisor=collector_user
                )
                self.fields['from_user'].label = "Collect from FOS"

            elif collector_user.role == 'admin':
                # Admin collects from supervisors
                self.fields['from_user'].queryset = User.objects.filter(
                    role='supervisor',
                    supervisor_category__name__in=['Sales', 'Both']
                )
                self.fields['from_user'].label = "Collect from Supervisor"


class EcSalesReportFilterForm(forms.Form):
    """Filter form for EC Sales Report"""
    operator = forms.ModelChoiceField(
        queryset=Operator.objects.all(),
        required=False,
        label="Operator",
        widget=forms.Select(attrs={'class': 'modern-input'}),
        empty_label="All Operators"
    )

    date_from = forms.DateField(
        required=False,
        label="From Date",
        widget=forms.DateInput(attrs={'class': 'modern-input', 'type': 'date'})
    )

    date_to = forms.DateField(
        required=False,
        label="To Date",
        widget=forms.DateInput(attrs={'class': 'modern-input', 'type': 'date'})
    )

    user_role = forms.ChoiceField(
        required=False,
        label="User Role",
        choices=[('', 'All Roles')] + [
            ('supervisor', 'Supervisor'),
            ('fos', 'FOS'),
            ('retailer', 'Retailer'),
        ],
        widget=forms.Select(attrs={'class': 'modern-input'})
    )

    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['supervisor', 'fos', 'retailer']),
        required=False,
        label="Specific User",
        widget=forms.Select(attrs={'class': 'modern-input'}),
        empty_label="All Users"
    )


class EcCollectionReportFilterForm(forms.Form):
    """Filter form for EC Collection Report"""
    operator = forms.ModelChoiceField(
        queryset=Operator.objects.all(),
        required=False,
        label="Operator",
        widget=forms.Select(attrs={'class': 'modern-input'}),
        empty_label="All Operators"
    )

    date_from = forms.DateField(
        required=False,
        label="From Date",
        widget=forms.DateInput(attrs={'class': 'modern-input', 'type': 'date'})
    )

    date_to = forms.DateField(
        required=False,
        label="To Date",
        widget=forms.DateInput(attrs={'class': 'modern-input', 'type': 'date'})
    )

    collection_level = forms.ChoiceField(
        required=False,
        label="Collection Level",
        choices=[('', 'All Levels')] + EcCollection.COLLECTION_LEVEL_CHOICES,
        widget=forms.Select(attrs={'class': 'modern-input'})
    )

    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['fos', 'supervisor', 'admin']),
        required=False,
        label="Collector",
        widget=forms.Select(attrs={'class': 'modern-input'}),
        empty_label="All Collectors"
    )
