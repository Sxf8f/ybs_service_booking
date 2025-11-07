from pyexpat.errors import messages
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .models import FosOperatorMap, Operator, Pincode, PincodeAssignment, RetailerFosMap, SupervisorCategory, User
from django.contrib import messages
import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import StockSale
from .forms import ProductForm, StockSaleForm, StockUploadForm, OperatorSelectionForm, PincodeForm, PincodeAssignmentForm, OperatorForm
from datetime import datetime
import io
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
User = get_user_model()
from pandas.api import types as pdtypes
from django import forms
from .models import Product, Operator, ProductStock, Purchase, PurchaseItem, ProductSerial, UserProductStock, CollectionTransfer, TechnicianPayment, WorkCategoryOption, WorkWarrantyOption, WorkJobTypeOption, WorkDthTypeOption, WorkFiberTypeOption, WorkFrIssueOption
from django.db import transaction
from django.db.models import Sum, ExpressionWrapper, F, FloatField, Q
from django.forms import modelform_factory
from .forms import StockTransferToSupervisorForm, StockTransferToTechnicianForm, WorkForm, WorkCloseForm
from .models import WorkStb, WorkReport, TypeOfService, WorkFromTheRole
from django.views.decorators.csrf import ensure_csrf_cookie
import requests
import random
from django.utils import timezone
from django.shortcuts import get_object_or_404



def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        try:
            # First, get the user by email
            user = User.objects.get(email=email)
            # Check if password is correct using Django's check_password
            if user.password == password:
                login(request, user)
                return redirect('dashboard')
            else:
                return render(request, "login.html", {"error": "Invalid credentials"})
        except User.DoesNotExist:
            return render(request, "login.html", {"error": "Invalid credentials"})
    return render(request, "login.html")


def logout_view(request):
    """Logout user and redirect to login page"""
    from django.contrib.auth import logout
    logout(request)
    return redirect('/login/')


@login_required
def stock_upload_view(request):
    sale_form = StockSaleForm()
    upload_form = StockUploadForm()
    operator_form = OperatorSelectionForm()

    if request.method == "POST":
        # Manual Multi-Entry
        if "multi_submit" in request.POST:
            operator_form = OperatorSelectionForm(request.POST)
            
            if operator_form.is_valid():
                selected_operator = operator_form.cleaned_data["operator"]
                
                # Get all the form data arrays
                order_ids = request.POST.getlist('order_id[]')
                order_dates = request.POST.getlist('order_date[]')
                partner_ids = request.POST.getlist('partner_id[]')
                partner_names = request.POST.getlist('partner_name[]')
                transfer_amounts = request.POST.getlist('transfer_amount[]')
                commissions = request.POST.getlist('commission[]')
                amounts_without_commission = request.POST.getlist('amount_without_commission[]')
                
                added, skipped = 0, 0
                
                for i in range(len(order_ids)):
                    order_id = order_ids[i].strip()
                    if not order_id:  # Skip empty rows
                        continue
                        
                    if StockSale.objects.filter(order_id=order_id).exists():
                        skipped += 1
                        continue
                    
                    try:
                        order_date = datetime.strptime(order_dates[i].strip(), "%Y-%m-%d").date()
                    except ValueError:
                        messages.error(request, f"Invalid date format for Order ID: {order_id}")
                        continue
                    
                    StockSale.objects.create(
                        operator=selected_operator.name,
                        order_id=order_id,
                        order_date=order_date,
                        partner_id=partner_ids[i] if partner_ids[i] else "",
                        partner_name=partner_names[i] if partner_names[i] else "",
                        transfer_amount=float(transfer_amounts[i]) if transfer_amounts[i] else 0.0,
                        commission=float(commissions[i]) if commissions[i] else 0.0,
                        amount_without_commission=float(amounts_without_commission[i]) if amounts_without_commission[i] else 0.0,
                        uploaded_by=request.user
                    )
                    added += 1
                
                if added > 0:
                    messages.success(request, f"{added} entries added, {skipped} skipped (duplicates).")
                else:
                    messages.warning(request, "No valid entries to add.")
                    
                return redirect("stock_upload")
            else:
                messages.error(request, "Please select an operator.")

        # Excel Upload
        elif "file_submit" in request.POST:
            operator_form = OperatorSelectionForm(request.POST)
            upload_form = StockUploadForm(request.POST, request.FILES)
            
            if operator_form.is_valid() and upload_form.is_valid():
                selected_operator = operator_form.cleaned_data["operator"]
                file = request.FILES["file"]
                try:
                    df = pd.read_excel(file)

                    required_cols = [
                        "Order ID", "Order Date", "Partner ID",
                        "Partner Name", "Transfer Amount", "Commission", "Amount Without Commission"
                    ]

                    # validate columns
                    if not all(col in df.columns for col in required_cols):
                        print(df.columns)
                        print('required', required_cols)
                        messages.error(request, "Invalid Excel format! Please use correct column names.")
                        return redirect("stock_upload")

                    added, skipped = 0, 0
                    for _, row in df.iterrows():
                        order_id = str(row["Order ID"]).strip()
                        if StockSale.objects.filter(order_id=order_id).exists():
                            skipped += 1
                            continue

                        order_date = datetime.strptime(str(row["Order Date"]).strip(), "%d.%m.%Y").date()

                        StockSale.objects.create(
                            operator=selected_operator.name,
                            order_id=order_id,
                            order_date=order_date,
                            partner_id=row["Partner ID"],
                            partner_name=row["Partner Name"],
                            transfer_amount=row["Transfer Amount"],
                            commission=row["Commission"],
                            amount_without_commission=row["Amount Without Commission"],
                            uploaded_by=request.user
                        )
                        added += 1

                    messages.success(request, f"{added} entries added, {skipped} skipped (duplicates).")
                    return redirect("stock_upload")

                except Exception as e:
                    messages.error(request, f"Error processing file: {str(e)}")
            else:
                messages.error(request, "Please select an operator and upload a valid file.")

    return render(request, "stock_upload.html", {
        "sale_form": sale_form,
        "upload_form": upload_form,
        "operator_form": operator_form,
    })




@login_required
def stock_sales_list(request):
    operator = request.GET.get("operator", "")
    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")
    user_id = request.GET.get("user", "")
    export = request.GET.get("export", "")

    sales = StockSale.objects.all().order_by("-order_date")

    # --- Filtering logic ---
    if operator:
        sales = sales.filter(operator__icontains=operator)

    if start_date and end_date:
        sales = sales.filter(order_date__range=[start_date, end_date])
    elif start_date:
        sales = sales.filter(order_date__gte=start_date)
    elif end_date:
        sales = sales.filter(order_date__lte=end_date)

    if user_id:
        sales = sales.filter(uploaded_by_id=user_id)

    # --- Export Excel ---
    if export == "xlsx":
        # use uploaded_by__name because your custom User model has `name`, not `username`
        qs_values = list(sales.values(
            "operator", "order_id", "order_date", "partner_id", "partner_name",
            "transfer_amount", "commission", "amount_without_commission",
            "uploaded_by__name", "uploaded_at"
        ))

        df = pd.DataFrame(qs_values)

        # rename columns for user-friendly headers
        df.rename(columns={
            "operator": "Operator",
            "order_id": "Order ID",
            "order_date": "Order Date",
            "partner_id": "Partner ID",
            "partner_name": "Partner Name",
            "transfer_amount": "Transfer Amount",
            "commission": "Commission",
            "amount_without_commission": "Amount Without Commission",
            "uploaded_by__name": "Uploaded By",
            "uploaded_at": "Uploaded At"
        }, inplace=True)

        # Ensure datetime columns are timezone-naive (Excel needs naive datetimes)
        for col in df.columns:
            try:
                if pdtypes.is_datetime64tz_dtype(df[col]):
                    # convert to UTC then drop tz
                    df[col] = df[col].dt.tz_convert("UTC").dt.tz_localize(None)
                elif pdtypes.is_datetime64_any_dtype(df[col]):
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                # ignore columns that fail conversion
                df[col] = df[col]

        # fallback: if any datetime still has tz info, convert to ISO strings
        if "Uploaded At" in df.columns:
            if pdtypes.is_datetime64tz_dtype(df["Uploaded At"]):
                df["Uploaded At"] = df["Uploaded At"].dt.tz_convert("UTC").dt.tz_localize(None)
            df["Uploaded At"] = pd.to_datetime(df["Uploaded At"], errors="coerce")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="StockSales")

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = 'attachment; filename="stock_sales_report.xlsx"'
        return response

    # --- Pagination ---
    paginator = Paginator(sales, 25)  # 25 per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    users = User.objects.all()

    return render(request, "stock_sales.html", {
        "page_obj": page_obj,
        "operator": operator,
        "start_date": start_date,
        "end_date": end_date,
        "user_id": user_id,
        "users": users,
    })








from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, Operator, ProductStock, Purchase, PurchaseItem, ProductSerial
from django.contrib.auth.decorators import login_required
from django.db import transaction

@login_required
def product_list(request):
    products = Product.objects.select_related("operator").all().order_by("operator__name","name")
    return render(request, "products/product_list.html", {"products": products})

@transaction.atomic
@login_required
def product_add(request):
    # Only admin can add products
    if request.user.role != 'admin':
        messages.error(request, "Permission denied. Only admins can add products.")
        return redirect("product_list")

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            ProductStock.objects.get_or_create(product=product, defaults={"qty": 0})
            # Assign 0 initial stock to admin for new product
            admin_user = User.objects.filter(role="admin").first() or User.objects.filter(is_admin=True).first()
            if admin_user:
                UserProductStock.objects.get_or_create(user=admin_user, product=product, defaults={"qty": 0})
            messages.success(request, "Product added.")
            return redirect("product_list")
    else:
        form = ProductForm()
    return render(request, "products/product_form.html", {"form": form, "title": "Add Product"})

@login_required
def product_edit(request, pk):
    # Only admin can edit products
    if request.user.role != 'admin':
        messages.error(request, "Permission denied. Only admins can edit products.")
        return redirect("product_list")

    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated.")
            return redirect("product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "products/product_form.html", {"form": form, "title": "Edit Product"})

@login_required
def product_delete(request, pk):
    # Only admin can delete products
    if request.user.role != 'admin':
        messages.error(request, "Permission denied. Only admins can delete products.")
        return redirect("product_list")

    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted.")
        return redirect("product_list")
    return render(request, "products/product_confirm_delete.html", {"product": product})

 
def _style_master_form(form):
    for field in form.fields.values():
        widget = field.widget
        existing = widget.attrs.get('class', '')
        widget.attrs['class'] = (existing + ' modern-input').strip()
        if field.label:
            widget.attrs.setdefault('placeholder', field.label)
        if isinstance(widget, forms.Textarea):
            widget.attrs.setdefault('rows', 3)


WORK_MASTER_CONFIG = {
    'category': {
        'title': 'Work Categories',
        'singular': 'Work Category',
        'model': WorkCategoryOption,
        'fields': ['code', 'name', 'description', 'ordering', 'is_active'],
        'code_help': 'Unique identifier used in works (e.g. dth, fiber).',
    },
    'warranty': {
        'title': 'Warranty Options',
        'singular': 'Warranty Option',
        'model': WorkWarrantyOption,
        'fields': ['code', 'name', 'description', 'ordering', 'is_active'],
        'code_help': 'Unique identifier (e.g. in, out).',
    },
    'job-type': {
        'title': 'Job Types',
        'singular': 'Job Type',
        'model': WorkJobTypeOption,
        'fields': ['code', 'name', 'description', 'ordering', 'is_active'],
        'code_help': 'Unique identifier (e.g. fr, retrieval).',
    },
    'dth-type': {
        'title': 'DTH Options',
        'singular': 'DTH Option',
        'model': WorkDthTypeOption,
        'fields': ['code', 'name', 'ordering', 'is_active'],
        'code_help': 'Unique identifier (e.g. fullset, box).',
    },
    'fiber-type': {
        'title': 'Fiber Options',
        'singular': 'Fiber Option',
        'model': WorkFiberTypeOption,
        'fields': ['code', 'name', 'ordering', 'is_active'],
        'code_help': 'Unique identifier (e.g. with_iptv).',
    },
    'fr-issue': {
        'title': 'FR Issues',
        'singular': 'FR Issue',
        'model': WorkFrIssueOption,
        'fields': ['code', 'name', 'ordering', 'is_active'],
        'code_help': 'Unique identifier (e.g. box, signal).',
    },
}


def _get_master_config(slug):
    config = WORK_MASTER_CONFIG.get(slug)
    if not config:
        raise Http404("Invalid work master")
    return config


@login_required
def work_master_list(request, slug):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    config = _get_master_config(slug)
    model = config['model']
    items = model.objects.all().order_by('ordering', 'name')

    return render(request, 'works/master_list.html', {
        'config': config,
        'items': items,
        'slug': slug,
    })


@login_required
def work_master_add(request, slug):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    config = _get_master_config(slug)
    model = config['model']
    form_class = modelform_factory(model, fields=config['fields'])

    if request.method == 'POST':
        form = form_class(request.POST)
        _style_master_form(form)
        if form.is_valid():
            form.save()
            messages.success(request, f"{config['singular']} added successfully.")
            return redirect('work_master_list', slug=slug)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = form_class()
        _style_master_form(form)
        if 'code' in form.fields and config.get('code_help'):
            form.fields['code'].help_text = config['code_help']

    return render(request, 'works/master_form.html', {
        'config': config,
        'form': form,
        'slug': slug,
        'title': f"Add {config['singular']}",
    })


@login_required
def work_master_edit(request, slug, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    config = _get_master_config(slug)
    model = config['model']
    instance = get_object_or_404(model, pk=pk)
    form_class = modelform_factory(model, fields=config['fields'])

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        _style_master_form(form)
        if form.is_valid():
            form.save()
            messages.success(request, f"{config['singular']} updated successfully.")
            return redirect('work_master_list', slug=slug)
        messages.error(request, 'Please correct the errors below.')
    else:
        form = form_class(instance=instance)
        _style_master_form(form)
        if 'code' in form.fields and config.get('code_help'):
            form.fields['code'].help_text = config['code_help']

    return render(request, 'works/master_form.html', {
        'config': config,
        'form': form,
        'slug': slug,
        'title': f"Edit {config['singular']}",
    })


@login_required
def work_master_delete(request, slug, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    config = _get_master_config(slug)
    model = config['model']
    instance = get_object_or_404(model, pk=pk)

    if request.method == 'POST':
        instance.delete()
        messages.success(request, f"{config['singular']} deleted successfully.")
        return redirect('work_master_list', slug=slug)

    return render(request, 'works/master_confirm_delete.html', {
        'config': config,
        'item': instance,
        'slug': slug,
    })


 
@login_required
def operator_list(request):
    if request.user.role != 'admin':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    operators = Operator.objects.all().order_by('name')
    return render(request, 'operators/operator_list.html', {
        'operators': operators
    })


@login_required
def operator_add(request):
    if request.user.role != 'admin':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = OperatorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Operator added successfully.')
            return redirect('operator_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = OperatorForm()

    return render(request, 'operators/operator_form.html', {
        'form': form,
        'title': 'Add Operator'
    })


@login_required
def operator_edit(request, pk):
    if request.user.role != 'admin':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    operator = get_object_or_404(Operator, pk=pk)

    if request.method == 'POST':
        form = OperatorForm(request.POST, instance=operator)
        if form.is_valid():
            form.save()
            messages.success(request, 'Operator updated successfully.')
            return redirect('operator_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = OperatorForm(instance=operator)

    return render(request, 'operators/operator_form.html', {
        'form': form,
        'title': 'Edit Operator',
        'operator_obj': operator
    })


from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_date
import json

@login_required
@transaction.atomic
def purchase_add(request):
    operators = Operator.objects.all()
    # products for initial page load (empty until operator selected)
    if request.method == "POST":
        # Expecting POST keys:
        # operator_id, bill_number, bill_date
        # product_id[], qty[], unit_price[]
        # For serialized items: serials_for_item_<index> as newline-separated or JSON list (we'll accept JSON in hidden input)
        operator_id = request.POST.get("operator_id")
        bill_number = request.POST.get("bill_number")
        bill_date = request.POST.get("bill_date")
        product_ids = request.POST.getlist("product_id[]")
        qtys = request.POST.getlist("qty[]")
        unit_prices = request.POST.getlist("unit_price[]")
        serials_json_list = request.POST.getlist("serials_json[]")  # each row can have a JSON list of serials or empty string

        if not operator_id or not bill_number or not bill_date or not product_ids:
            messages.error(request, "Please fill required fields.")
            return redirect("purchase_add")

        operator = Operator.objects.get(pk=operator_id)
        # unique bill enforcement can be done via model constraint too
        if Purchase.objects.filter(operator=operator, bill_number=bill_number).exists():
            messages.error(request, "Duplicate bill number for this operator.")
            return redirect("purchase_add")

        purchase = Purchase.objects.create(
            operator=operator,
            bill_number=bill_number,
            bill_date=parse_date(bill_date),
            created_by=request.user
        )

        total_lines = 0
        # credit stock to admin ownership
        admin_user = User.objects.filter(role="admin").first() or User.objects.filter(is_admin=True).first()
        for i, pid in enumerate(product_ids):
            if not pid:
                continue
            total_lines += 1
            product = Product.objects.get(pk=pid)
            qty = qtys[i] or "0"
            unit_price = unit_prices[i] or "0"
            qty_num = float(qty)
            unit_price_num = float(product.price)
            subtotal = qty_num * unit_price_num

            item = PurchaseItem.objects.create(
                purchase=purchase,
                product=product,
                qty=qty_num,
                unit_price=unit_price_num,
                subtotal=subtotal
            )
            # handle serials if product is serialized
            serials_json = serials_json_list[i] if i < len(serials_json_list) else ""
            if product.is_serialized:
                # expect JSON array string or newline separated
                serials = []
                try:
                    if serials_json:
                        serials = json.loads(serials_json)
                    else:
                        serials = []
                except Exception:
                    # fallback: treat as newline separated
                    serials = [s.strip() for s in serials_json.splitlines() if s.strip()]

                # validation: number of serials must equal qty (or at least not less)
                if len(serials) != int(qty_num):
                    # We allow or enforce? We'll enforce equal count
                    transaction.set_rollback(True)
                    messages.error(request, f"Serial count for product {product.name} does not match quantity.")
                    return redirect("purchase_add")

                # create ProductSerial rows and link them
                for s in serials:
                    if ProductSerial.objects.filter(serial=s).exists():
                        transaction.set_rollback(True)
                        messages.error(request, f"Serial {s} already exists in system.")
                        return redirect("purchase_add")
                    ps = ProductSerial.objects.create(product=product, serial=s, purchase_item=item)
            # update stock
            stock, created = ProductStock.objects.get_or_create(product=product)
            stock.qty = float(stock.qty) + qty_num
            stock.save()
            if admin_user:
                upstock, _ = UserProductStock.objects.get_or_create(user=admin_user, product=product)
                upstock.qty = float(upstock.qty) + qty_num
                upstock.save()

        messages.success(request, f"Purchase saved with {total_lines} lines.")
        return redirect("purchase_list")

    return render(request, "purchases/purchase_add.html", {"operators": operators})

@login_required
def transfer_stock_to_supervisor(request):
    if not getattr(request.user, "is_admin", False) and request.user.role != "admin":
        return redirect("dashboard")
    msg = None
    if request.method == 'POST':
        form = StockTransferToSupervisorForm(request.POST)
        if form.is_valid():
            supervisor = form.cleaned_data['supervisor']
            product = form.cleaned_data['product']
            qty = float(form.cleaned_data['qty'])
            admin_user = User.objects.filter(role='admin').first() or User.objects.filter(is_admin=True).first()
            try:
                with transaction.atomic():
                    apstock, _ = UserProductStock.objects.get_or_create(user=admin_user, product=product)
                    if float(apstock.qty) < qty:
                        raise ValueError(f"Not enough stock. Admin has {apstock.qty}, tried to transfer {qty}.")
                    spstock, _ = UserProductStock.objects.get_or_create(user=supervisor, product=product)
                    apstock.qty = float(apstock.qty) - qty
                    spstock.qty = float(spstock.qty) + qty
                    apstock.save()
                    spstock.save()
                    msg = f"Transferred {qty} {product.name} to {supervisor.name}."
                    messages.success(request, msg)
                    return redirect('stock_overview')
            except Exception as e:
                msg = str(e)
                messages.error(request, msg)
    else:
        form = StockTransferToSupervisorForm()
    return render(request, 'products/transfer_stock_supervisor.html', {'form': form, 'msg': msg})

@login_required
def transfer_stock_to_technician(request):
    if request.user.role != 'supervisor':
        return redirect('dashboard')
    techs = User.objects.filter(supervisor=request.user, role='technician')
    class DynamicStockTransferToTechnicianForm(StockTransferToTechnicianForm):
        technician = forms.ModelChoiceField(queryset=techs, required=True, label="Technician")
    msg = None
    if request.method == 'POST':
        form = DynamicStockTransferToTechnicianForm(request.POST)
        if form.is_valid():
            technician = form.cleaned_data['technician']
            product = form.cleaned_data['product']
            qty = float(form.cleaned_data['qty'])
            try:
                with transaction.atomic():
                    sup_stock, _ = UserProductStock.objects.get_or_create(user=request.user, product=product)
                    if float(sup_stock.qty) < qty:
                        raise ValueError(f"Not enough stock. Supervisor has {sup_stock.qty}, tried to transfer {qty}.")
                    tech_stock, _ = UserProductStock.objects.get_or_create(user=technician, product=product)
                    sup_stock.qty = float(sup_stock.qty) - qty
                    tech_stock.qty = float(tech_stock.qty) + qty
                    sup_stock.save()
                    tech_stock.save()
                    msg = f"Transferred {qty} {product.name} to {technician.name}."
                    messages.success(request, msg)
                    return redirect('stock_overview')
            except Exception as e:
                msg = str(e)
                messages.error(request, msg)
    else:
        form = DynamicStockTransferToTechnicianForm()
    return render(request, 'products/transfer_stock_technician.html', {'form': form, 'msg': msg})


# ============================================
# TAKE BACK STOCK VIEWS
# ============================================

@login_required
def supervisor_take_back_from_technician(request):
    """Supervisor takes back stock from technician"""
    if request.user.role != 'supervisor':
        messages.error(request, 'Only supervisors can take back stock from technicians.')
        return redirect('dashboard')

    # Get technicians under this supervisor
    technicians = User.objects.filter(supervisor=request.user, role='technician').order_by('name')

    if request.method == 'POST':
        technician_id = request.POST.get('technician')
        product_id = request.POST.get('product')
        qty = request.POST.get('qty')

        try:
            qty = float(qty)
            if qty <= 0:
                messages.error(request, 'Quantity must be greater than zero.')
                return redirect('supervisor_take_back_from_technician')

            technician = User.objects.get(pk=technician_id, supervisor=request.user, role='technician')
            product = Product.objects.get(pk=product_id)

            with transaction.atomic():
                # Get technician's stock
                tech_stock = UserProductStock.objects.filter(user=technician, product=product).first()

                if not tech_stock or float(tech_stock.qty) < qty:
                    available = float(tech_stock.qty) if tech_stock else 0
                    messages.error(request, f"Insufficient stock. {technician.name} has {available} {product.name}, tried to take back {qty}.")
                    return redirect('supervisor_take_back_from_technician')

                # Get supervisor's stock
                sup_stock, _ = UserProductStock.objects.get_or_create(user=request.user, product=product)

                # Transfer stock
                tech_stock.qty = float(tech_stock.qty) - qty
                sup_stock.qty = float(sup_stock.qty) + qty

                tech_stock.save()
                sup_stock.save()

                messages.success(request, f"Successfully took back {qty} {product.name} from {technician.name}.")
                return redirect('stock_overview')

        except User.DoesNotExist:
            messages.error(request, 'Technician not found.')
        except Product.DoesNotExist:
            messages.error(request, 'Product not found.')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    # For GET request - prepare data for template
    selected_tech_id = request.GET.get('technician')
    tech_stocks = []

    if selected_tech_id:
        tech_stocks = UserProductStock.objects.filter(
            user_id=selected_tech_id,
            qty__gt=0
        ).select_related('product', 'user').order_by('product__name')

    return render(request, 'products/supervisor_take_back.html', {
        'technicians': technicians,
        'tech_stocks': tech_stocks,
        'selected_tech_id': selected_tech_id
    })


@login_required
def admin_take_back_from_supervisor(request):
    """Admin takes back stock from supervisor"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admins can take back stock from supervisors.')
        return redirect('dashboard')

    # Get all supervisors
    supervisors = User.objects.filter(role='supervisor').order_by('name')

    if request.method == 'POST':
        supervisor_id = request.POST.get('supervisor')
        product_id = request.POST.get('product')
        qty = request.POST.get('qty')

        try:
            qty = float(qty)
            if qty <= 0:
                messages.error(request, 'Quantity must be greater than zero.')
                return redirect('admin_take_back_from_supervisor')

            supervisor = User.objects.get(pk=supervisor_id, role='supervisor')
            product = Product.objects.get(pk=product_id)

            with transaction.atomic():
                # Get supervisor's stock
                sup_stock = UserProductStock.objects.filter(user=supervisor, product=product).first()

                if not sup_stock or float(sup_stock.qty) < qty:
                    available = float(sup_stock.qty) if sup_stock else 0
                    messages.error(request, f"Insufficient stock. {supervisor.name} has {available} {product.name}, tried to take back {qty}.")
                    return redirect('admin_take_back_from_supervisor')

                # Get admin's stock
                admin_stock, _ = UserProductStock.objects.get_or_create(user=request.user, product=product)

                # Transfer stock
                sup_stock.qty = float(sup_stock.qty) - qty
                admin_stock.qty = float(admin_stock.qty) + qty

                sup_stock.save()
                admin_stock.save()

                messages.success(request, f"Successfully took back {qty} {product.name} from {supervisor.name}.")
                return redirect('stock_overview')

        except User.DoesNotExist:
            messages.error(request, 'Supervisor not found.')
        except Product.DoesNotExist:
            messages.error(request, 'Product not found.')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    # For GET request - prepare data for template
    selected_sup_id = request.GET.get('supervisor')
    sup_stocks = []

    if selected_sup_id:
        sup_stocks = UserProductStock.objects.filter(
            user_id=selected_sup_id,
            qty__gt=0
        ).select_related('product', 'user').order_by('product__name')

    return render(request, 'products/admin_take_back.html', {
        'supervisors': supervisors,
        'sup_stocks': sup_stocks,
        'selected_sup_id': selected_sup_id
    })


@login_required
def stock_overview(request):
    # Admin global view; supervisors see their area; technicians see own
    if request.user.role == 'admin' or getattr(request.user, 'is_admin', False):
        admin_user = request.user
        if request.user.role != 'admin':
            admin_user = User.objects.filter(role='admin').first() or request.user
        products = Product.objects.all().order_by('name')
        rows = []
        for p in products:
            admin_qty = UserProductStock.objects.filter(user=admin_user, product=p).aggregate(total=Sum('qty'))['total'] or 0
            sup_qty = UserProductStock.objects.filter(user__role='supervisor', product=p).aggregate(total=Sum('qty'))['total'] or 0
            tech_qty = UserProductStock.objects.filter(user__role='technician', product=p).aggregate(total=Sum('qty'))['total'] or 0
            rows.append({"product": p, "admin_qty": admin_qty, "sup_qty": sup_qty, "tech_qty": tech_qty})
        return render(request, 'products/stock_overview.html', {"rows": rows, "scope": "admin"})

    if request.user.role == 'supervisor':
        products = Product.objects.all().order_by('name')
        rows = []
        tech_ids = list(User.objects.filter(supervisor=request.user, role='technician').values_list('id', flat=True))
        for p in products:
            my_qty = UserProductStock.objects.filter(user=request.user, product=p).aggregate(total=Sum('qty'))['total'] or 0
            tech_qty = UserProductStock.objects.filter(user_id__in=tech_ids, product=p).aggregate(total=Sum('qty'))['total'] or 0
            rows.append({"product": p, "my_qty": my_qty, "tech_qty": tech_qty})
        return render(request, 'products/stock_overview.html', {"rows": rows, "scope": "supervisor"})

    # technician
    stocks = UserProductStock.objects.filter(user=request.user).select_related('product').order_by('product__name')
    return render(request, 'products/stock_overview.html', {"stocks": stocks, "scope": "technician"})

@login_required
def stock_role_detail(request, role, product_id):
    if request.user.role != 'admin' and not getattr(request.user, 'is_admin', False):
        return redirect('dashboard')
    product = get_object_or_404(Product, pk=product_id)
    users = User.objects.filter(role=role)
    items = []
    for u in users:
        qty = UserProductStock.objects.filter(user=u, product=product).aggregate(total=Sum('qty'))['total'] or 0
        if qty:
            items.append({"user": u, "qty": qty})
    return render(request, 'products/stock_user_detail.html', {"product": product, "items": items, "role": role})

@login_required
def stock_supervisor_detail(request, product_id):
    if request.user.role != 'supervisor':
        return redirect('dashboard')
    product = get_object_or_404(Product, pk=product_id)
    techs = User.objects.filter(supervisor=request.user, role='technician')
    items = []
    for t in techs:
        qty = UserProductStock.objects.filter(user=t, product=product).aggregate(total=Sum('qty'))['total'] or 0
        if qty:
            items.append({"user": t, "qty": qty})
    return render(request, 'products/stock_user_detail.html', {"product": product, "items": items, "role": 'technician'})





@login_required
def purchase_list(request):
    # Get filter parameters
    operator_id = request.GET.get("operator", "")
    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")
    bill_number = request.GET.get("bill_number", "")
    export = request.GET.get("export", "")
    
    # Base queryset with total amount calculation
    purchases = (
        Purchase.objects
        .select_related("operator", "created_by")
        .annotate(
            total_amount=Sum(
                ExpressionWrapper(F('items__qty') * F('items__unit_price'), output_field=FloatField())
            )
        )
        .order_by("-bill_date", "-id")
    )
    
    # Apply filters
    if operator_id:
        purchases = purchases.filter(operator_id=operator_id)
    
    if start_date and end_date:
        purchases = purchases.filter(bill_date__range=[start_date, end_date])
    elif start_date:
        purchases = purchases.filter(bill_date__gte=start_date)
    elif end_date:
        purchases = purchases.filter(bill_date__lte=end_date)
    
    if bill_number:
        purchases = purchases.filter(bill_number__icontains=bill_number)
    
    # Export Excel
    if export == "xlsx":
        qs_values = list(purchases.values(
            "operator__name", "bill_number", "bill_date", "total_amount",
            "created_by__name", "created_at"
        ))
        
        df = pd.DataFrame(qs_values)
        
        # Rename columns for user-friendly headers
        df.rename(columns={
            "operator__name": "Operator",
            "bill_number": "Bill Number", 
            "bill_date": "Bill Date",
            "total_amount": "Total Amount",
            "created_by__name": "Created By",
            "created_at": "Created At"
        }, inplace=True)
        
        # Handle datetime columns
        for col in df.columns:
            try:
                if pdtypes.is_datetime64tz_dtype(df[col]):
                    df[col] = df[col].dt.tz_convert("UTC").dt.tz_localize(None)
                elif pdtypes.is_datetime64_any_dtype(df[col]):
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                df[col] = df[col]
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="PurchaseReport")
        
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = 'attachment; filename="purchase_report.xlsx"'
        return response
    
    # Pagination
    paginator = Paginator(purchases, 25)  # 25 per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    # Get operators for filter dropdown
    operators = Operator.objects.all()
    
    return render(request, "purchases/purchase_list.html", {
        "page_obj": page_obj,
        "operators": operators,
        "operator_id": operator_id,
        "start_date": start_date,
        "end_date": end_date,
        "bill_number": bill_number,
    })

@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    items = purchase.items.select_related("product").all()
    return render(request, "purchases/purchase_detail.html", {"purchase": purchase, "items": items})

@login_required
def purchase_delete(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    purchase.delete()
    messages.success(request, "Purchase deleted successfully.")
    return redirect("purchase_list")








def add_supervisor(request):
    categories = SupervisorCategory.objects.all()

    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")
        email = request.POST.get("email")
        password = request.POST.get("password")
        category_id = request.POST.get("category")
        

        try:
         category = None
         if category_id:
            category = SupervisorCategory.objects.get(id=category_id)
            user = User.objects.create(
                name=name,
                phone=phone,
                email=email,
                password=password,
                role="supervisor",            
                supervisor_category=category,
            )
            messages.success(request, "Supervisor added successfully!")
            return redirect('add_supervisor')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, "add_supervisor.html", {"categories": categories})

def add_fos(request):
    supervisors = User.objects.filter(role="supervisor", supervisor_category__name__in=["Sales", "Both"])
    operators = Operator.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        password = request.POST.get('password')
        supervisor_id = request.POST.get('supervisor_id')
        selected_ops = request.POST.getlist('operators')

        supervisor = User.objects.get(id=supervisor_id)
        fos = User.objects.create(name=name, phone=phone, email=email, password=password, role='fos', supervisor=supervisor)

        # Link selected operators
        for op_id in selected_ops:
            FosOperatorMap.objects.create(fos=fos, operator_id=op_id)

        return redirect('dashboard')

    return render(request, 'add_fos.html', {'supervisors': supervisors, 'operators': operators})

def add_retailer(request):
    supervisors = User.objects.filter(role="supervisor", supervisor_category__name__in=["Sales", "Both"])

    fos_list = []
    fos_users = User.objects.filter(role='fos')

    # attach operators for display
    for fos in fos_users:
        fos.operators = [fom.operator for fom in FosOperatorMap.objects.filter(fos=fos)]
        fos_list.append(fos)

    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        password = request.POST.get('password')
        supervisor_id = request.POST.get('supervisor_id')
        fos_ids = request.POST.getlist('fos_ids')

        supervisor = User.objects.get(id=supervisor_id)
        retailer = User.objects.create(name=name, phone=phone, email=email, password=password, role='retailer', supervisor=supervisor)

        for fid in fos_ids:
            RetailerFosMap.objects.create(retailer=retailer, fos_id=fid)

        return redirect('dashboard')

    return render(request, 'add_retailer.html', {'supervisors': supervisors, 'fos_list': fos_list})

@login_required
def add_technician(request):
    supervisors = User.objects.filter(role="supervisor", supervisor_category__name__in=["Services", "Both"])

    # Check if logged-in user is a supervisor
    is_supervisor = request.user.is_authenticated and request.user.role == "supervisor"

    if request.method == "POST":
        name = request.POST.get("name")
        phone = request.POST.get("phone")
        email = request.POST.get("email")
        password = request.POST.get("password")
        technician_type = request.POST.get("technician_type")

        try:
            # If supervisor is logged in, use them as the supervisor
            if is_supervisor:
                supervisor = request.user
            else:
                # Admin selects supervisor from dropdown
                supervisor_id = request.POST.get("supervisor")
                if not supervisor_id:
                    messages.error(request, "Please select a supervisor.")
                    return redirect('add_technician')
            supervisor = User.objects.get(id=supervisor_id)

            tech = User.objects.create(
                name=name,
                phone=phone,
                email=email,
                password=password,
                role="technician",
                supervisor=supervisor,
                technician_type=technician_type
            )
            messages.success(request, "Technician added successfully!")
            return redirect('add_technician')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect('add_technician')

    return render(request, "add_technician.html", {
        "supervisors": supervisors,
        "is_supervisor": is_supervisor
    })






@login_required
def admin_dashboard(request):
    user = request.user
    from django.db.models import Count, Sum, Q
    from .models import WorkStb, SimStock, Product, ProductStock, EcSale, RetailerWallet, FosWallet, SupervisorWallet, FosOperatorMap, RetailerSimWallet, FosSimWallet, SupervisorSimWallet, RetailerHandsetWallet, FosHandsetWallet, SupervisorHandsetWallet, HandsetCollection, CollectionTransfer

    context = {"user": user}

    # Role-based dashboard data
    if user.role == 'admin':
        # Admin sees everything
        # Handset collection stats
        total_handset_collected = HandsetCollection.objects.aggregate(total=Sum('collection_amount'))['total'] or 0
        total_handset_pending = SupervisorHandsetWallet.objects.aggregate(total=Sum('pending_amount'))['total'] or 0

        context.update({
            'total_users': User.objects.count(),
            'total_supervisors': User.objects.filter(role='supervisor').count(),
            'total_fos': User.objects.filter(role='fos').count(),
            'total_retailers': User.objects.filter(role='retailer').count(),
            'total_technicians': User.objects.filter(role='technician').count(),

            'total_works': WorkStb.objects.count(),
            'pending_works': WorkStb.objects.filter(status='Pending').count(),
            'expired_works': WorkStb.objects.filter(status='Expired').count(),
            'closed_works': WorkStb.objects.filter(status='Closed').count(),

            'total_sim_stock': SimStock.objects.filter(status='available').count(),
            'total_sim_sold': SimStock.objects.filter(status='sold').count(),

            'total_ec_sales': EcSale.objects.count(),
            'total_ec_amount': EcSale.objects.aggregate(total=Sum('amount_without_commission'))['total'] or 0,
            'total_ec_pending': RetailerWallet.objects.aggregate(total=Sum('pending_amount'))['total'] or 0,

            'total_collection': User.objects.aggregate(total=Sum('collection_amount'))['total'] or 0,

            'handset_collected_total': total_handset_collected,
            'handset_pending_total': total_handset_pending,
        })

    elif user.role == 'supervisor':
        # Supervisor sees their team data
        context.update({
            'my_technicians': User.objects.filter(supervisor=user, role='technician').count(),
            'my_fos': User.objects.filter(supervisor=user, role='fos').count(),

            'my_works': WorkStb.objects.filter(supervisor=user).count(),
            'pending_works': WorkStb.objects.filter(supervisor=user, status='Pending').count(),
            'expired_works': WorkStb.objects.filter(supervisor=user, status='Expired').count(),
            'closed_works': WorkStb.objects.filter(supervisor=user, status='Closed').count(),

            'my_sim_stock': SimStock.objects.filter(current_holder=user, status='available').count(),
            'my_ec_sales': EcSale.objects.filter(supervisor=user).count(),
            'my_ec_amount': EcSale.objects.filter(supervisor=user).aggregate(total=Sum('amount_without_commission'))['total'] or 0,

            'my_collection': user.collection_amount,
            'pending_transfers': user.received_transfers.filter(status='pending').count() if hasattr(user, 'received_transfers') else 0,
        })

    elif user.role == 'fos':
        # FOS sees their retailers and stock
        from .models import RetailerFosMap
        context.update({
            'my_retailers': RetailerFosMap.objects.filter(fos=user).count(),

            'my_sim_stock': SimStock.objects.filter(current_holder=user, status='available').count(),
            'my_ec_sales': EcSale.objects.filter(fos=user).count(),
            'my_ec_amount': EcSale.objects.filter(fos=user).aggregate(total=Sum('amount_without_commission'))['total'] or 0,

            'pending_sim_transfers': user.sim_transfers_received.filter(status='pending').count() if hasattr(user, 'sim_transfers_received') else 0,
        })

    elif user.role == 'retailer':
        # Retailer sees their work and stock
        context.update({
            'my_works': WorkStb.objects.filter(created_by=user).count(),
            'pending_works': WorkStb.objects.filter(created_by=user, status='Pending').count(),
            'closed_works': WorkStb.objects.filter(created_by=user, status='Closed').count(),

            'my_sim_stock': SimStock.objects.filter(current_holder=user, status='available').count(),
            'my_ec_sales': EcSale.objects.filter(retailer=user).count(),
            'my_ec_pending': RetailerWallet.objects.filter(retailer=user).aggregate(total=Sum('pending_amount'))['total'] or 0,

            'my_collection': user.collection_amount,
        })

    elif user.role == 'technician':
        # Technician sees assigned works
        context.update({
            'assigned_works': WorkStb.objects.filter(assigned_technician=user).count(),
            'pending_works': WorkStb.objects.filter(assigned_technician=user, status='Pending').count(),
            'closed_works': WorkStb.objects.filter(assigned_technician=user, status='Closed').count(),

            'my_collection': user.collection_amount,
            'my_payment_wallet': user.payment_wallet if user.technician_type == 'freelance' else 0,
        })

    # Add wallet balances based on role and category
    wallets = []

    def add_wallet_entry(type_code, label, pending_value, description, color, collected_value=None):
        pending_value = pending_value or 0
        entry = {
            'type': type_code,
            'label': label,
            'pending': pending_value,
            'collected': collected_value if collected_value is not None else None,
            'description': description,
            'color': color,
            'amount': pending_value,
        }
        wallets.append(entry)

    if user.role == 'retailer':
        # Retailer: EC Wallet + SIM Wallet
        ec_data = RetailerWallet.objects.filter(retailer=user).aggregate(
            pending=Sum('pending_amount'),
            total=Sum('total_sales')
        )
        ec_pending = ec_data['pending'] or 0
        ec_total = ec_data['total'] or 0
        ec_collected = max(ec_total - ec_pending, 0)
        add_wallet_entry('ec', 'EC Wallet', ec_pending, 'EC debt to FOS', 'danger', ec_collected)

        sim_data = RetailerSimWallet.objects.filter(retailer=user).aggregate(
            pending=Sum('pending_amount'),
            total=Sum('total_amount')
        )
        sim_pending = sim_data['pending'] or 0
        sim_total = sim_data['total'] or 0
        sim_collected = max(sim_total - sim_pending, 0)
        add_wallet_entry('sim', 'SIM Wallet', sim_pending, 'SIM debt to FOS', 'warning', sim_collected)

        handset_data = RetailerHandsetWallet.objects.filter(retailer=user).aggregate(
            pending=Sum('pending_amount'),
            total=Sum('total_amount')
        )
        handset_pending = handset_data['pending'] or 0
        handset_total = handset_data['total'] or 0
        handset_collected = max(handset_total - handset_pending, 0)
        add_wallet_entry('handset', 'Handset Wallet', handset_pending, 'Handset debt to FOS', 'info', handset_collected)

        # Add FOS operator details (if needed)
        context['user_operators'] = None

    elif user.role == 'fos':
        # FOS: EC Wallet + SIM Wallet + Handset Wallet
        ec_data = FosWallet.objects.filter(fos=user).aggregate(
            pending=Sum('pending_amount'),
            collected=Sum('total_collected_from_retailers')
        )
        add_wallet_entry('ec', 'EC Wallet', ec_data['pending'] or 0, 'EC from retailers, pending to supervisor', 'danger', ec_data['collected'] or 0)

        sim_data = FosSimWallet.objects.filter(fos=user).aggregate(
            pending=Sum('pending_amount'),
            collected=Sum('total_collected_from_retailers')
        )
        add_wallet_entry('sim', 'SIM Wallet', sim_data['pending'] or 0, 'SIM from retailers, pending to supervisor', 'warning', sim_data['collected'] or 0)

        handset_data = FosHandsetWallet.objects.filter(fos=user).aggregate(
            pending=Sum('pending_amount'),
            collected=Sum('total_collected_from_retailers')
        )
        add_wallet_entry('handset', 'Handset Wallet', handset_data['pending'] or 0, 'Handset from retailers, pending to supervisor', 'info', handset_data['collected'] or 0)

        # Add FOS operator details
        fos_operators = FosOperatorMap.objects.filter(fos=user).select_related('operator')
        context['user_operators'] = ', '.join([fo.operator.name for fo in fos_operators]) if fos_operators else 'No operators'

    elif user.role == 'supervisor':
        # Supervisor: Depends on category
        if user.supervisor_category:
            category_name = user.supervisor_category.name
            context['user_category'] = category_name

            if category_name == 'Sales':
                # Sales Supervisor: EC Wallet + SIM Wallet + Handset Wallet
                ec_data = SupervisorWallet.objects.filter(supervisor=user).aggregate(
                    pending=Sum('pending_amount'),
                    collected=Sum('total_collected_from_fos')
                )
                add_wallet_entry('ec', 'EC Wallet', ec_data['pending'] or 0, 'EC from FOS, pending to company', 'danger', ec_data['collected'] or 0)

                sim_data = SupervisorSimWallet.objects.filter(supervisor=user).aggregate(
                    pending=Sum('pending_amount'),
                    collected=Sum('total_collected_from_fos')
                )
                add_wallet_entry('sim', 'SIM Wallet', sim_data['pending'] or 0, 'SIM from FOS, pending to company', 'warning', sim_data['collected'] or 0)

                handset_data = SupervisorHandsetWallet.objects.filter(supervisor=user).aggregate(
                    pending=Sum('pending_amount'),
                    collected=Sum('total_collected_from_fos')
                )
                add_wallet_entry('handset', 'Handset Wallet', handset_data['pending'] or 0, 'Handsets from FOS, pending to company', 'info', handset_data['collected'] or 0)

            elif category_name == 'Service':
                # Service Supervisor: Only Service Collection
                add_wallet_entry('service', 'Service Collection', user.collection_amount, 'Work amount collected', 'success')

            elif category_name == 'Both':
                # Both: EC + SIM + Service Collection
                ec_data = SupervisorWallet.objects.filter(supervisor=user).aggregate(
                    pending=Sum('pending_amount'),
                    collected=Sum('total_collected_from_fos')
                )
                add_wallet_entry('ec', 'EC Wallet', ec_data['pending'] or 0, 'EC from FOS, pending to company', 'danger', ec_data['collected'] or 0)

                sim_data = SupervisorSimWallet.objects.filter(supervisor=user).aggregate(
                    pending=Sum('pending_amount'),
                    collected=Sum('total_collected_from_fos')
                )
                add_wallet_entry('sim', 'SIM Wallet', sim_data['pending'] or 0, 'SIM from FOS, pending to company', 'warning', sim_data['collected'] or 0)

                add_wallet_entry('service', 'Service Collection', user.collection_amount, 'Work amount collected', 'success')

                handset_data = SupervisorHandsetWallet.objects.filter(supervisor=user).aggregate(
                    pending=Sum('pending_amount'),
                    collected=Sum('total_collected_from_fos')
                )
                add_wallet_entry('handset', 'Handset Wallet', handset_data['pending'] or 0, 'Handsets from FOS, pending to company', 'info', handset_data['collected'] or 0)

    elif user.role == 'admin':
        # Admin: Show all wallet types separately

        # Total EC Receivable from supervisors
        ec_aggregate = SupervisorWallet.objects.aggregate(
            pending=Sum('pending_amount'),
            collected=Sum('total_collected_from_fos')
        )
        add_wallet_entry('ec', 'EC Receivable', ec_aggregate['pending'] or 0, 'Total EC pending from supervisors', 'danger', ec_aggregate['collected'] or 0)

        sim_aggregate = SupervisorSimWallet.objects.aggregate(
            pending=Sum('pending_amount'),
            collected=Sum('total_collected_from_fos')
        )
        add_wallet_entry('sim', 'SIM Receivable', sim_aggregate['pending'] or 0, 'Total SIM pending from supervisors', 'warning', sim_aggregate['collected'] or 0)

        total_service_collection = User.objects.filter(
            role='supervisor',
            supervisor_category__name__in=['Service', 'Both']
        ).aggregate(total=Sum('collection_amount'))['total'] or 0
        service_collected = CollectionTransfer.objects.filter(status='Accepted', supervisor__role='admin').aggregate(total=Sum('amount'))['total'] or 0
        add_wallet_entry('service', 'Service Collection', total_service_collection, 'Total work collections from service supervisors', 'success', service_collected)

        add_wallet_entry('handset', 'Handset Receivable', total_handset_pending, 'Total handset pending from supervisors', 'info', total_handset_collected)

    context['wallets'] = wallets
    if context.get('total_collection') and total_handset_pending is not None:
        context['handset_pending_total'] = total_handset_pending
    if context.get('total_collection') and total_handset_collected is not None:
        context['handset_collected_total'] = total_handset_collected
    return render(request, "admin_dashboard.html", context)







# Pincode CRUD Views
@login_required
def pincode_list(request):
    pincodes = Pincode.objects.all().order_by('pincode')
    
    # Pagination
    paginator = Paginator(pincodes, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'pincodes/pincode_list.html', {
        'page_obj': page_obj
    })

@login_required
def pincode_add(request):
    if request.method == 'POST':
        form = PincodeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pincode added successfully!')
            return redirect('pincode_list')
    else:
        form = PincodeForm()
    
    return render(request, 'pincodes/pincode_form.html', {
        'form': form,
        'title': 'Add Pincode'
    })

@login_required
def pincode_edit(request, pk):
    pincode = get_object_or_404(Pincode, pk=pk)
    
    if request.method == 'POST':
        form = PincodeForm(request.POST, instance=pincode)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pincode updated successfully!')
            return redirect('pincode_list')
    else:
        form = PincodeForm(instance=pincode)
    
    return render(request, 'pincodes/pincode_form.html', {
        'form': form,
        'title': 'Edit Pincode',
        'pincode': pincode
    })

@login_required
def pincode_delete(request, pk):
    pincode = get_object_or_404(Pincode, pk=pk)
    
    if request.method == 'POST':
        pincode.delete()
        messages.success(request, 'Pincode deleted successfully!')
        return redirect('pincode_list')
    
    return render(request, 'pincodes/pincode_confirm_delete.html', {
        'pincode': pincode
    })





# Pincode Assignment Views
@login_required
def pincode_assignment_list(request):
    assignments = PincodeAssignment.objects.select_related('supervisor', 'pincode').all().order_by('supervisor__name', 'pincode__pincode')
    
    # Pagination
    paginator = Paginator(assignments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'pincodes/pincode_assignment_list.html', {
        'page_obj': page_obj
    })

@login_required
def pincode_assignment_add(request):
    if request.method == 'POST':
        form = PincodeAssignmentForm(request.POST)
        if form.is_valid():
            supervisor = form.cleaned_data['supervisor']
            pincodes = form.cleaned_data['pincodes']
            
            # Create assignments
            created_count = 0
            for pincode in pincodes:
                assignment, created = PincodeAssignment.objects.get_or_create(
                    supervisor=supervisor,
                    pincode=pincode,
                    defaults={'assigned_by': request.user}
                )
                if created:
                    created_count += 1
            
            if created_count > 0:
                messages.success(request, f'{created_count} pincode(s) assigned successfully!')
            else:
                messages.warning(request, 'No new assignments were made. All selected pincodes were already assigned.')
            
            return redirect('pincode_assignment_list')
    else:
        form = PincodeAssignmentForm()
    
    return render(request, 'pincodes/pincode_assignment_form.html', {
        'form': form,
        'title': 'Assign Pincodes to Supervisor'
    })

@login_required
def pincode_assignment_delete(request, pk):
    assignment = get_object_or_404(PincodeAssignment, pk=pk)
    
    if request.method == 'POST':
        supervisor_name = assignment.supervisor.name
        pincode_code = assignment.pincode.pincode
        assignment.delete()
        messages.success(request, f'Pincode {pincode_code} unassigned from {supervisor_name}!')
        return redirect('pincode_assignment_list')
    
    return render(request, 'pincodes/pincode_assignment_confirm_delete.html', {
        'assignment': assignment
    })






@login_required
def work_list(request):
    # Check and mark expired works
    check_expired_works()

    qs = WorkStb.objects.select_related('operator','supervisor','assigned_technician').order_by('-id')
    role = getattr(request.user, 'role', '')
    if role == 'supervisor':
        qs = qs.filter(supervisor=request.user)
    elif role == 'technician':
        qs = qs.filter(assigned_technician=request.user)
    return render(request, 'works/work_list.html', { 'works': qs })

@ensure_csrf_cookie
@login_required
def work_add(request):
    # Only admin and supervisor can add works
    if request.user.role not in ['admin', 'supervisor']:
        messages.error(request, 'Only admin and supervisor can add works.')
        return redirect('work_list')

    if request.method == 'POST':
        form = WorkForm(request.POST)
        if form.is_valid():
            work = form.save(commit=False)
            work.created_by = request.user
            work.save()
            messages.success(request, 'Work created successfully! You can now assign it to a technician.')
            return redirect('work_list')
    else:
        form = WorkForm()
    return render(request, 'works/work_form.html', { 'form': form, 'title': 'Add Work' })

@ensure_csrf_cookie
@login_required
def work_edit(request, pk):
    # Only admin can edit works
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can edit works.')
        return redirect('work_list')

    work = get_object_or_404(WorkStb, pk=pk)
    if work.status not in ['Pending', 'Expired']:
        messages.error(request, 'Closed/Cancelled work cannot be edited')
        return redirect('work_list')
    if request.method == 'POST':
        form = WorkForm(request.POST, instance=work)
        if form.is_valid():
            form.save()
            messages.success(request, 'Work updated')
            return redirect('work_list')
    else:
        form = WorkForm(instance=work)
    return render(request, 'works/work_form.html', { 'form': form, 'title': 'Edit Work' })

@login_required
@transaction.atomic
def work_close(request, pk):
    work = get_object_or_404(WorkStb, pk=pk)
    # only supervisor or admin can close (NOT technicians)
    user = request.user
    is_supervisor = user.role == 'supervisor'
    is_admin = user.role == 'admin'

    if not (is_supervisor or is_admin):
        messages.error(request, f'Only admin or supervisor can close works. Your role: {user.role}')
        return redirect('work_list')

    tech = work.assigned_technician
    if not tech:
        messages.error(request, 'Assign a technician before closing')
        return redirect('work_list')

    # stocks available for the technician
    tech_stocks = UserProductStock.objects.filter(user=tech, qty__gt=0).select_related('product').order_by('product__name')

    if request.method == 'POST':
        form = WorkCloseForm(request.POST)
        if form.is_valid():
            # ===== OTP VALIDATION =====
            entered_otp = request.POST.get('closing_otp', '').strip()

            # Admin can bypass OTP or use stored OTP
            if user.role != 'admin':
                # For non-admin users, OTP is mandatory
                if not entered_otp:
                    transaction.set_rollback(True)
                    messages.error(request, 'Please enter the OTP sent to customer.')
                    return redirect('work_close', pk=pk)

                if not work.closing_otp:
                    transaction.set_rollback(True)
                    messages.error(request, 'OTP not generated yet. Please click "Send OTP to Customer" first.')
                    return redirect('work_close', pk=pk)

                if entered_otp != work.closing_otp:
                    transaction.set_rollback(True)
                    messages.error(request, 'Invalid OTP. Please check and try again.')
                    return redirect('work_close', pk=pk)
            else:
                # Admin can close with or without OTP
                if entered_otp and work.closing_otp and entered_otp != work.closing_otp:
                    transaction.set_rollback(True)
                    messages.error(request, 'Invalid OTP. Please check and try again.')
                    return redirect('work_close', pk=pk)

            # Check if this is a repair work
            is_repair_work = work.type_of_service and work.type_of_service.name and 'repair' in work.type_of_service.name.lower()
            repair_type = request.POST.get('repair_type') if is_repair_work else None

            # Parse products used
            prod_ids = request.POST.getlist('used_product_id[]')
            qtys = request.POST.getlist('used_qty[]')
            used = []
            total_used = 0.0

            # Validate each line and collect serial numbers for serialized products
            for i, pid in enumerate(prod_ids):
                if not pid:
                    continue
                qty = float(qtys[i] or 0)
                if qty <= 0:
                    continue
                product = Product.objects.get(pk=pid)

                # Check if product is serialized
                serials_for_this_product = []
                if product.is_serialized:
                    # Get serial numbers for this product line
                    serial_inputs = request.POST.getlist(f'used_serials_{i}[]')
                    serials_for_this_product = [s.strip() for s in serial_inputs if s.strip()]

                    # Validate: Must have exactly qty number of serials
                    if len(serials_for_this_product) != int(qty):
                        transaction.set_rollback(True)
                        messages.error(request, f"Product '{product.name}' requires {int(qty)} serial number(s), but {len(serials_for_this_product)} provided.")
                        return redirect('work_close', pk=pk)

                    # Validate each serial exists and is available in tech's stock
                    for serial_num in serials_for_this_product:
                        serial_obj = ProductSerial.objects.filter(
                            serial=serial_num,
                            product=product,
                            status='Available',
                            assigned_to_user=tech
                        ).first()

                        if not serial_obj:
                            transaction.set_rollback(True)
                            messages.error(request, f"Serial '{serial_num}' for '{product.name}' not found in {tech.name}'s available stock.")
                            return redirect('work_close', pk=pk)

                # Ensure tech has stock
                upstock = UserProductStock.objects.filter(user=tech, product=product).first()
                available = float(upstock.qty if upstock else 0)
                if qty > available:
                    transaction.set_rollback(True)
                    messages.error(request, f"Insufficient stock for {product.name}. Available {available}, tried {qty}")
                    return redirect('work_close', pk=pk)

                # Unit price from product master
                unit = float(product.price)
                line_total = unit * qty
                total_used += line_total
                used.append({
                    'product_id': product.id,
                    'product': product.name,
                    'unit_price': unit,
                    'qty': qty,
                    'total': line_total,
                    'is_serialized': product.is_serialized,
                    'serials': serials_for_this_product
                })

            # Handle repair-specific: returned product from customer
            returned_product_id = request.POST.get('returned_product_id') if repair_type == 'Swapping' else None
            returned_serial = request.POST.get('returned_serial', '').strip() if repair_type == 'Swapping' else None
            returned_quantity = float(request.POST.get('returned_quantity') or 0) if repair_type == 'Swapping' else 0

            returned_product_obj = None
            if returned_product_id:
                returned_product_obj = Product.objects.get(pk=returned_product_id)

                # If returned product is serialized, validate serial
                if returned_product_obj.is_serialized and not returned_serial:
                    transaction.set_rollback(True)
                    messages.error(request, f"Returned product '{returned_product_obj.name}' requires a serial number.")
                    return redirect('work_close', pk=pk)

            # Deduct stock for used materials
            for u in used:
                upstock = UserProductStock.objects.get(user=tech, product_id=u['product_id'])
                upstock.qty = float(upstock.qty) - float(u['qty'])
                upstock.save()

                # Mark serials as Used
                if u['is_serialized']:
                    for serial_num in u['serials']:
                        serial_obj = ProductSerial.objects.get(serial=serial_num, product_id=u['product_id'])
                        serial_obj.status = 'Used'
                        serial_obj.used_in_work = work
                        serial_obj.save()

            # Add returned defective product to tech's stock
            if returned_product_obj:
                tech_stock, _ = UserProductStock.objects.get_or_create(
                    user=tech,
                    product=returned_product_obj
                )
                tech_stock.qty = float(tech_stock.qty) + returned_quantity
                tech_stock.save()

                # If serialized, create/update ProductSerial with Defective status
                if returned_product_obj.is_serialized and returned_serial:
                    defective_serial, created = ProductSerial.objects.get_or_create(
                        serial=returned_serial,
                        defaults={
                            'product': returned_product_obj,
                            'status': 'Defective',
                            'assigned_to_user': tech
                        }
                    )
                    if not created:
                        defective_serial.status = 'Defective'
                        defective_serial.assigned_to_user = tech
                        defective_serial.save()

            # Get collection amount and who collected
            collected_amount = float(form.cleaned_data.get('collected_amount') or 0.0)
            who_collected_id = request.POST.get('who_collected')

            # Determine who collected the money
            if who_collected_id:
                who_collected = User.objects.get(pk=who_collected_id)
            else:
                who_collected = tech

            # Handle freelancer payment
            freelancer_payment_amount = 0.0
            if tech.technician_type == 'freelance':
                freelancer_payment_amount = float(request.POST.get('freelancer_payment_amount') or 0.0)

            # Create/update report
            report, _ = WorkReport.objects.get_or_create(work=work)
            report.used_materials = used
            report.subtotal_amount = float(work.amount) + total_used
            report.collected_amount = collected_amount
            report.who_collected = who_collected
            report.cancellation_remark = form.cleaned_data.get('cancellation_remark')
            report.freelancer_payment_amount = freelancer_payment_amount

            # Save repair-specific fields
            report.repair_type = repair_type
            report.returned_product = returned_product_obj
            report.returned_serial = returned_serial
            report.returned_quantity = returned_quantity
            report.save()

            # Credit collection amount to the collector's wallet
            if collected_amount > 0 and who_collected:
                who_collected.collection_amount = float(who_collected.collection_amount) + collected_amount
                who_collected.save()

            # Add freelancer payment to technician's payment_wallet
            if freelancer_payment_amount > 0 and tech.technician_type == 'freelance':
                tech.payment_wallet = float(tech.payment_wallet) + freelancer_payment_amount
                tech.save()

            work.status = 'Closed'
            from django.utils import timezone
            work.work_closing_time = timezone.now()
            work.save()

            success_msg = f'Work closed successfully! ₹{collected_amount} credited to {who_collected.name}\'s wallet.'
            if freelancer_payment_amount > 0:
                success_msg += f' ₹{freelancer_payment_amount} added to freelancer {tech.name}\'s payment wallet.'

            messages.success(request, success_msg)
            return redirect('work_report', pk=work.pk)
    else:
        form = WorkCloseForm()

    # Determine if user is supervisor closing work
    user_is_supervisor = user.role == 'supervisor' or is_supervisor

    # Check if this is a repair work
    is_repair_work = work.type_of_service and work.type_of_service.name and 'repair' in work.type_of_service.name.lower()

    # Get all products for returned product selection
    all_products = Product.objects.all().order_by('name')

    return render(request, 'works/work_close.html', {
        'form': form,
        'work': work,
        'tech_stocks': tech_stocks,
        'user_is_supervisor': user_is_supervisor,
        'is_repair_work': is_repair_work,
        'all_products': all_products
    })

@login_required
def work_report(request, pk):
    work = get_object_or_404(WorkStb, pk=pk)
    report = getattr(work, 'report', None)
    return render(request, 'works/work_report.html', { 'work': work, 'report': report })




# CRUD for TypeOfService
@login_required
def service_type_list(request):
    items = TypeOfService.objects.all().order_by('name')
    return render(request, 'works/service_type_list.html', {'items': items})

@login_required
def service_type_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            TypeOfService.objects.get_or_create(name=name)
            messages.success(request, 'Saved')
            return redirect('service_type_list')
    return render(request, 'works/service_type_form.html', {'title': 'Add Service Type'})

@login_required
def service_type_edit(request, pk):
    item = get_object_or_404(TypeOfService, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            item.name = name
            item.save()
            messages.success(request, 'Updated')
            return redirect('service_type_list')
    return render(request, 'works/service_type_form.html', {'title': 'Edit Service Type', 'item': item})

@login_required
def service_type_delete(request, pk):
    item = get_object_or_404(TypeOfService, pk=pk)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Deleted')
        return redirect('service_type_list')
    return render(request, 'works/service_type_confirm_delete.html', {'item': item})











# CRUD for WorkFromTheRole
@login_required
def workfrom_list(request):
    items = WorkFromTheRole.objects.all().order_by('name')
    return render(request, 'works/workfrom_list.html', {'items': items})

@login_required
def workfrom_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            WorkFromTheRole.objects.get_or_create(name=name)
            messages.success(request, 'Saved')
            return redirect('workfrom_list')
    return render(request, 'works/workfrom_form.html', {'title': 'Add Work From'})

@login_required
def workfrom_edit(request, pk):
    item = get_object_or_404(WorkFromTheRole, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            item.name = name
            item.save()
            messages.success(request, 'Updated')
            return redirect('workfrom_list')
    return render(request, 'works/workfrom_form.html', {'title': 'Edit Work From', 'item': item})

@login_required
def workfrom_delete(request, pk):
    item = get_object_or_404(WorkFromTheRole, pk=pk)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Deleted')
        return redirect('workfrom_list')
    return render(request, 'works/workfrom_confirm_delete.html', {'item': item})


# ============================================
# COLLECTION TRANSFER VIEWS
# ============================================

@login_required
def transfer_to_supervisor_view(request):
    """Technician transfers money to their supervisor"""
    if request.user.role != 'technician':
        messages.error(request, 'Only technicians can transfer to supervisors.')
        return redirect('dashboard')

    if not request.user.supervisor:
        messages.error(request, 'You do not have a supervisor assigned.')
        return redirect('dashboard')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        remark = request.POST.get('remark', '')

        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than zero.')
                return redirect('transfer_collection')

            # Check if technician has sufficient balance
            if request.user.collection_amount < amount:
                messages.error(request, f'Insufficient balance. You have ₹{request.user.collection_amount}, but tried to transfer ₹{amount}.')
                return redirect('transfer_collection')

            # Create transfer request
            transfer = CollectionTransfer.objects.create(
                technician=request.user,
                supervisor=request.user.supervisor,
                amount=amount,
                remark=remark,
                status='Pending'
            )

            messages.success(request, f'Transfer request of ₹{amount} sent to {request.user.supervisor.name}. Waiting for approval.')
            return redirect('transfer_history')

        except ValueError:
            messages.error(request, 'Invalid amount entered.')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'collection/transfer_to_supervisor.html', {
        'current_balance': request.user.collection_amount,
        'supervisor': request.user.supervisor
    })


@login_required
def pending_transfers_view(request):
    """Supervisor/Admin views pending transfer requests"""
    if request.user.role not in ['supervisor', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Get transfers where current user is the receiver
    pending = CollectionTransfer.objects.filter(
        supervisor=request.user,
        status='Pending'
    ).select_related('technician').order_by('-created_at')

    # Also get recent accepted/rejected for history
    recent = CollectionTransfer.objects.filter(
        supervisor=request.user,
        status__in=['Accepted', 'Rejected']
    ).select_related('technician').order_by('-updated_at')[:10]

    return render(request, 'collection/pending_transfers.html', {
        'pending_transfers': pending,
        'recent_transfers': recent
    })


@login_required
@transaction.atomic
def transfer_action_view(request, pk, action):
    """Accept or reject a transfer request"""
    if request.user.role not in ['supervisor', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    transfer = get_object_or_404(CollectionTransfer, pk=pk)

    # Verify that the current user is the receiver
    if transfer.supervisor != request.user:
        messages.error(request, 'You are not authorized to act on this transfer.')
        return redirect('pending_transfers')

    if transfer.status != 'Pending':
        messages.warning(request, 'This transfer has already been processed.')
        return redirect('pending_transfers')

    try:
        if action == 'accept':
            transfer.accept()
            messages.success(request, f'Transfer of ₹{transfer.amount} from {transfer.technician.name} accepted. Amount credited to your wallet.')
        elif action == 'reject':
            transfer.reject()
            messages.info(request, f'Transfer of ₹{transfer.amount} from {transfer.technician.name} rejected.')
        else:
            messages.error(request, 'Invalid action.')

    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error processing transfer: {e}')

    return redirect('pending_transfers')


@login_required
def supervisor_transfer_to_admin(request):
    """Supervisor transfers money to admin"""
    if request.user.role != 'supervisor':
        messages.error(request, 'Only supervisors can transfer to admin.')
        return redirect('dashboard')

    # Get an admin user
    admin_user = User.objects.filter(role='admin').first() or User.objects.filter(is_admin=True).first()

    if not admin_user:
        messages.error(request, 'No admin user found in the system.')
        return redirect('dashboard')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        remark = request.POST.get('remark', '')

        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than zero.')
                return redirect('supervisor_transfer_admin')

            # Check if supervisor has sufficient balance
            if request.user.collection_amount < amount:
                messages.error(request, f'Insufficient balance. You have ₹{request.user.collection_amount}, but tried to transfer ₹{amount}.')
                return redirect('supervisor_transfer_admin')

            # Create transfer request (reusing CollectionTransfer model)
            transfer = CollectionTransfer.objects.create(
                technician=request.user,  # Sender (supervisor in this case)
                supervisor=admin_user,     # Receiver (admin)
                amount=amount,
                remark=remark,
                status='Pending'
            )

            messages.success(request, f'Transfer request of ₹{amount} sent to {admin_user.name}. Waiting for approval.')
            return redirect('transfer_history')

        except ValueError:
            messages.error(request, 'Invalid amount entered.')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'collection/supervisor_transfer_admin.html', {
        'current_balance': request.user.collection_amount,
        'admin_user': admin_user
    })


@login_required
def transfer_history_view(request):
    """View transfer history - both sent and received"""
    # Transfers sent by user
    sent = CollectionTransfer.objects.filter(
        technician=request.user
    ).select_related('supervisor').order_by('-created_at')

    # Transfers received by user
    received = CollectionTransfer.objects.filter(
        supervisor=request.user
    ).select_related('technician').order_by('-created_at')

    return render(request, 'collection/transfer_history.html', {
        'sent_transfers': sent,
        'received_transfers': received
    })


# ==================== WORK ASSIGNMENT & OTP VIEWS ====================

def send_whatsapp_message(mobile, message):
    """
    Send WhatsApp message via whatsbot.tech API.
    mobile should be without country code (we'll prepend '91')
    """
    api_token = "02d22c19-69a0-4082-a1fc-46b0e45f6340"
    full_mobile = f"91{mobile}"
    url = f"https://whatsbot.tech/api/send_sms"
    params = {
        "api_token": api_token,
        "mobile": full_mobile,
        "message": message,
    }

    try:
        print(f"\n{'='*60}")
        print(f"📱 SENDING WHATSAPP MESSAGE")
        print(f"{'='*60}")
        print(f"To: {full_mobile}")
        print(f"Message Preview: {message[:100]}...")
        print(f"API URL: {url}")
        print(f"{'='*60}\n")

        response = requests.get(url, params=params, timeout=10)

        print(f"\n{'='*60}")
        print(f"✅ WHATSAPP API RESPONSE")
        print(f"{'='*60}")
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        print(f"{'='*60}\n")

        return response.json()
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ WHATSAPP SENDING FAILED")
        print(f"{'='*60}")
        print(f"Error: {e}")
        print(f"{'='*60}\n")
        return None


@login_required
def work_assign(request, pk):
    """Assign work to a technician (initial assignment)"""
    work = get_object_or_404(WorkStb, pk=pk)
    user = request.user

    # Only allow admin or supervisor of this work to assign
    if user.role not in ['admin', 'supervisor']:
        messages.error(request, 'Only admin or supervisor can assign work.')
        return redirect('work_list')

    if user.role == 'supervisor' and work.supervisor != user:
        messages.error(request, 'You can only assign your own works.')
        return redirect('work_list')

    if work.status != 'Pending':
        messages.error(request, 'Only pending works can be assigned.')
        return redirect('work_list')

    # Get available technicians
    if user.role == 'admin':
        technicians = User.objects.filter(role='technician').order_by('name')
    else:  # supervisor
        technicians = User.objects.filter(role='technician', supervisor=user).order_by('name')

    if request.method == 'POST':
        technician_id = request.POST.get('technician_id')
        if not technician_id:
            messages.error(request, 'Please select a technician.')
            return redirect('work_assign', pk=pk)

        technician = get_object_or_404(User, pk=technician_id, role='technician')
        work.assigned_technician = technician
        work.save()

        # Send WhatsApp notification to technician
        if technician.phone or technician.whatsapp_no:
            mobile = technician.whatsapp_no or technician.phone
            msg = f"""
*New Work Assigned For You*

Customer: {work.customer_name}
Address: {work.address}
Pincode: {work.pincode}
Mobile: {work.mobile_no}
Alternate: {work.alternate_no or 'N/A'}

Operator: {work.operator.name if work.operator else ''}
Service: {work.type_of_service.name if work.type_of_service else ''}
Work From: {work.work_from.name if work.work_from else ''}
Amount: ₹{work.amount}
Status: {work.status}

Please attend to this work as soon as possible.
"""
            send_whatsapp_message(mobile, msg.strip())

        messages.success(request, f'Work assigned to {technician.name} successfully! WhatsApp notification sent.')
        return redirect('work_list')

    return render(request, 'works/work_assign.html', {
        'work': work,
        'technicians': technicians,
        'title': 'Assign Work'
    })


@login_required
def work_reassign(request, pk):
    """Reassign work to a different technician"""
    work = get_object_or_404(WorkStb, pk=pk)
    user = request.user

    # Only allow admin or supervisor of this work to reassign
    if user.role not in ['admin', 'supervisor']:
        messages.error(request, 'Only admin or supervisor can reassign work.')
        return redirect('work_list')

    if user.role == 'supervisor' and work.supervisor != user:
        messages.error(request, 'You can only reassign your own works.')
        return redirect('work_list')

    if work.status != 'Pending':
        messages.error(request, 'Only pending works can be reassigned.')
        return redirect('work_list')

    if not work.assigned_technician:
        messages.error(request, 'This work is not assigned yet. Use Assign instead.')
        return redirect('work_assign', pk=pk)

    # Get available technicians
    if user.role == 'admin':
        technicians = User.objects.filter(role='technician').order_by('name')
    else:  # supervisor
        technicians = User.objects.filter(role='technician', supervisor=user).order_by('name')

    if request.method == 'POST':
        technician_id = request.POST.get('technician_id')
        if not technician_id:
            messages.error(request, 'Please select a technician.')
            return redirect('work_reassign', pk=pk)

        old_technician = work.assigned_technician
        new_technician = get_object_or_404(User, pk=technician_id, role='technician')

        if old_technician.id == new_technician.id:
            messages.warning(request, 'Work is already assigned to this technician.')
            return redirect('work_list')

        work.assigned_technician = new_technician
        work.save()

        # Send WhatsApp notification to new technician
        if new_technician.phone or new_technician.whatsapp_no:
            mobile = new_technician.whatsapp_no or new_technician.phone
            msg = f"""
*Work Reassigned For You*

Customer: {work.customer_name}
Address: {work.address}
Pincode: {work.pincode}
Mobile: {work.mobile_no}
Alternate: {work.alternate_no or 'N/A'}

Operator: {work.operator.name if work.operator else ''}
Service: {work.type_of_service.name if work.type_of_service else ''}
Work From: {work.work_from.name if work.work_from else ''}
Amount: ₹{work.amount}
Status: {work.status}

Please attend to this work as soon as possible.
"""
            send_whatsapp_message(mobile, msg.strip())

        messages.success(request, f'Work reassigned from {old_technician.name} to {new_technician.name}! WhatsApp notification sent.')
        return redirect('work_list')

    return render(request, 'works/work_reassign.html', {
        'work': work,
        'technicians': technicians,
        'current_technician': work.assigned_technician,
        'title': 'Reassign Work'
    })


@login_required
def work_send_otp(request, pk):
    """Generate and send OTP to customer for work closing"""
    work = get_object_or_404(WorkStb, pk=pk)
    user = request.user

    # Only allow technician, supervisor or admin to send OTP
    is_tech = user.role == 'technician' and work.assigned_technician and work.assigned_technician.id == user.id
    is_supervisor = user.role == 'supervisor' and work.supervisor == user
    is_admin = user.role == 'admin'

    if not (is_tech or is_supervisor or is_admin):
        messages.error(request, 'You are not authorized to send OTP for this work.')
        return redirect('work_list')

    if work.status != 'Pending':
        messages.error(request, 'OTP can only be sent for pending works.')
        return redirect('work_list')

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    work.closing_otp = otp
    work.otp_sent_at = timezone.now()
    work.save()

    # Send OTP to customer via WhatsApp
    customer_mobile = work.wp_no or work.mobile_no
    if customer_mobile:
        msg = f"""
*Work Closing OTP*

Hello {work.customer_name},

Your OTP for closing work order is: *{otp}*

Operator: {work.operator.name if work.operator else ''}
Service: {work.type_of_service.name if work.type_of_service else ''}

Please share this OTP with the technician to complete the work.

Thank you!
"""
        send_whatsapp_message(customer_mobile, msg.strip())
        messages.success(request, f'OTP sent to customer {work.customer_name} at {customer_mobile}')
    else:
        messages.warning(request, f'OTP generated: {otp} (No WhatsApp number available to send)')

    return redirect('work_close', pk=pk)


@login_required
def admin_otp_list(request):
    """Admin view to see all works with OTPs"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can view OTP list.')
        return redirect('dashboard')

    # Get all pending works with OTP
    works_with_otp = WorkStb.objects.filter(
        status='Pending',
        closing_otp__isnull=False
    ).select_related('operator', 'supervisor', 'assigned_technician', 'type_of_service').order_by('-otp_sent_at')

    return render(request, 'works/admin_otp_list.html', {
        'works': works_with_otp,
        'title': 'OTP Listing '
    })


# ==================== FREELANCER PAYMENT VIEWS ====================

@login_required
def supervisor_mark_payment(request):
    """Supervisor marks payment as paid to freelance technicians"""
    if request.user.role != 'supervisor':
        messages.error(request, 'Only supervisors can mark payments.')
        return redirect('dashboard')

    # Get freelance technicians under this supervisor
    freelance_technicians = User.objects.filter(
        role='technician',
        technician_type='freelance',
        supervisor=request.user
    ).order_by('name')

    if request.method == 'POST':
        technician_id = request.POST.get('technician_id')
        amount = request.POST.get('amount')
        work_id = request.POST.get('work_id')
        remark = request.POST.get('remark', '')

        try:
            amount = float(amount)
            technician = User.objects.get(pk=technician_id, role='technician', technician_type='freelance')

            # Validate technician has sufficient pending amount
            if technician.payment_wallet < amount:
                messages.error(request, f'Insufficient pending payment. {technician.name} has ₹{technician.payment_wallet} pending.')
                return redirect('supervisor_mark_payment')

            # Create payment record
            payment = TechnicianPayment.objects.create(
                technician=technician,
                supervisor=request.user,
                work_id=work_id if work_id else None,
                amount=amount,
                status='Pending',
                remark=remark,
                marked_paid_at=timezone.now()
            )

            messages.success(request, f'Payment of ₹{amount} marked for {technician.name}. Waiting for technician acceptance.')
            return redirect('supervisor_payment_history')

        except ValueError:
            messages.error(request, 'Invalid amount entered.')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    # Get technicians with their pending amounts
    for tech in freelance_technicians:
        tech.pending_amount = tech.payment_wallet

    return render(request, 'payments/supervisor_mark_payment.html', {
        'technicians': freelance_technicians,
        'title': 'Mark Payment to Freelancer'
    })


@login_required
def technician_pending_payments(request):
    """Freelance technician views and accepts pending payments"""
    if request.user.role != 'technician' or request.user.technician_type != 'freelance':
        messages.error(request, 'Only freelance technicians can access this page.')
        return redirect('dashboard')

    # Get pending payments for this technician
    pending_payments = TechnicianPayment.objects.filter(
        technician=request.user,
        status='Pending'
    ).select_related('supervisor', 'work').order_by('-created_at')

    return render(request, 'payments/technician_pending_payments.html', {
        'payments': pending_payments,
        'current_balance': request.user.payment_wallet,
        'title': 'Pending Payments'
    })


@login_required
@transaction.atomic
def technician_payment_action(request, pk, action):
    """Technician accepts or rejects payment"""
    payment = get_object_or_404(TechnicianPayment, pk=pk, technician=request.user)

    if payment.status != 'Pending':
        messages.warning(request, 'This payment has already been processed.')
        return redirect('technician_pending_payments')

    if action == 'accept':
        try:
            payment.accept()
            messages.success(request, f'Payment of ₹{payment.amount} accepted! Amount deducted from your pending balance.')
        except ValueError as e:
            messages.error(request, str(e))
            transaction.set_rollback(True)
    elif action == 'reject':
        payment.reject()
        messages.info(request, f'Payment of ₹{payment.amount} rejected.')

    return redirect('technician_pending_payments')


@login_required
def payment_history(request):
    """View payment history with filters for all users"""
    user = request.user

    # Filter based on role
    if user.role == 'technician' and user.technician_type == 'freelance':
        # Technician sees payments they received
        payments = TechnicianPayment.objects.filter(
            technician=user
        ).select_related('supervisor', 'work').order_by('-created_at')
    elif user.role == 'supervisor':
        # Supervisor sees payments they sent
        payments = TechnicianPayment.objects.filter(
            supervisor=user
        ).select_related('technician', 'work').order_by('-created_at')
    elif user.role == 'admin':
        # Admin sees all payments
        payments = TechnicianPayment.objects.all().select_related(
            'technician', 'supervisor', 'work'
        ).order_by('-created_at')
    else:
        messages.error(request, 'You do not have access to payment history.')
        return redirect('dashboard')

    # Apply filters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if status_filter:
        payments = payments.filter(status=status_filter)

    if search_query:
        payments = payments.filter(
            Q(technician__name__icontains=search_query) |
            Q(supervisor__name__icontains=search_query) |
            Q(remark__icontains=search_query)
        )

    if date_from:
        from datetime import datetime
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        payments = payments.filter(created_at__gte=date_from_obj)

    if date_to:
        from datetime import datetime
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
        payments = payments.filter(created_at__lte=date_to_obj)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'payments/payment_history.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'title': 'Payment History'
    })


# ==================== USER MANAGEMENT VIEWS ====================

@login_required
def user_list(request):
    """Admin view for all users with filtering and search"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access user list.')
        return redirect('dashboard')

    # Order by role first, then by id - use select_related for supervisor_category and prefetch FOS operators, retailer FOS, and EC wallets
    users = User.objects.select_related('supervisor_category').prefetch_related(
        'fosoperatormap_set__operator',
        'retailer_fos_maps__fos',
        'retailer_wallet__operator'  # Prefetch EC recharge wallets for retailers
    ).all().order_by('role', '-id')

    # Apply filters
    role_filter = request.GET.get('role', '')
    tech_type_filter = request.GET.get('tech_type', '')
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    supervisor_category_filter = request.GET.get('supervisor_category', '')

    if role_filter:
        users = users.filter(role=role_filter)

    if tech_type_filter:
        users = users.filter(technician_type=tech_type_filter)

    if supervisor_category_filter:
        users = users.filter(supervisor_category__name=supervisor_category_filter)

    if search_query:
        users = users.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    # Pagination
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'users/user_list.html', {
        'page_obj': page_obj,
        'role_filter': role_filter,
        'tech_type_filter': tech_type_filter,
        'search_query': search_query,
        'status_filter': status_filter,
        'supervisor_category_filter': supervisor_category_filter,
        'title': 'User Management'
    })


@login_required
def user_edit(request, pk):
    """Admin can edit any user"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can edit users.')
        return redirect('dashboard')

    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        user.name = request.POST.get('name')
        user.email = request.POST.get('email')
        user.phone = request.POST.get('phone')
        user.alternate_no = request.POST.get('alternate_no', '')
        user.whatsapp_no = request.POST.get('whatsapp_no', '')
        user.address = request.POST.get('address', '')
        user.pincode = request.POST.get('pincode', '')
        user.remark = request.POST.get('remark', '')
        user.is_active = request.POST.get('is_active') == 'on'

        # Update password only if provided
        new_password = request.POST.get('password', '')
        if new_password:
            user.password = new_password

        user.save()

        # Update FOS operators if user is FOS
        if user.role == 'fos':
            from .models import FosOperatorMap
            selected_operators = request.POST.getlist('operators')

            # Clear existing operator mappings
            FosOperatorMap.objects.filter(fos=user).delete()

            # Create new operator mappings
            for operator_id in selected_operators:
                FosOperatorMap.objects.create(
                    fos=user,
                    operator_id=operator_id
                )

        messages.success(request, f'User {user.name} updated successfully!')
        return redirect('user_list')

    from .models import Operator
    supervisors = User.objects.filter(role='supervisor')
    categories = SupervisorCategory.objects.all()
    operators = Operator.objects.all()

    # Get current operators for this FOS
    current_operators = []
    if user.role == 'fos':
        from .models import FosOperatorMap
        current_operators = FosOperatorMap.objects.filter(fos=user).values_list('operator_id', flat=True)

    return render(request, 'users/user_edit.html', {
        'user_obj': user,
        'supervisors': supervisors,
        'categories': categories,
        'operators': operators,
        'current_operators': list(current_operators),
        'title': f'Edit User: {user.name}'
    })


# ==================== RETAILER WORK MANAGEMENT ====================

@login_required
def retailer_work_add(request):
    """Retailer adds work with auto 24-hour deadline"""
    if request.user.role != 'retailer':
        messages.error(request, 'Only retailers can access this page.')
        return redirect('dashboard')

    if request.method == 'POST':
        from .forms import RetailerWorkForm
        form = RetailerWorkForm(request.POST)
        if form.is_valid():
            work = form.save(commit=False)
            work.created_by = request.user

            # Auto-set deadline to 24 hours from now
            from datetime import timedelta
            work.work_deadline_time = timezone.now() + timedelta(hours=24)

            work.save()
            messages.success(request, f'Work created successfully! Deadline: 24 hours. Assigned to supervisor: {work.supervisor.name if work.supervisor else "N/A"}')
            return redirect('retailer_work_list')
    else:
        from .forms import RetailerWorkForm
        form = RetailerWorkForm()

    return render(request, 'works/retailer_work_add.html', {
        'form': form,
        'title': 'Add Work (Retailer)'
    })


@login_required
def retailer_work_list(request):
    """Retailer views only their created works (status only)"""
    if request.user.role != 'retailer':
        messages.error(request, 'Only retailers can access this page.')
        return redirect('dashboard')

    # Show only works created by this retailer
    works = WorkStb.objects.filter(created_by=request.user).select_related(
        'operator', 'supervisor', 'assigned_technician', 'type_of_service'
    ).order_by('-created_at')

    return render(request, 'works/retailer_work_list.html', {
        'works': works,
        'title': 'My Works (Retailer)'
    })


# ==================== WORK CANCELLATION ====================

@login_required
@transaction.atomic
def work_cancel(request, pk):
    """Admin or supervisor can cancel a work"""
    if request.user.role not in ['admin', 'supervisor']:
        messages.error(request, 'Only admin or supervisor can cancel works.')
        return redirect('work_list')

    work = get_object_or_404(WorkStb, pk=pk)

    # Supervisor can only cancel their own works
    if request.user.role == 'supervisor' and work.supervisor != request.user:
        messages.error(request, 'You can only cancel works assigned to you.')
        return redirect('work_list')

    if work.status in ['Closed', 'Cancelled']:
        messages.warning(request, f'Work is already {work.status}.')
        return redirect('work_list')

    if request.method == 'POST':
        cancellation_reason = request.POST.get('cancellation_reason', '').strip()

        if not cancellation_reason:
            messages.error(request, 'Please provide a cancellation reason.')
            return redirect('work_cancel', pk=pk)

        # Update work status
        work.status = 'Cancelled'
        work.save()

        # Create work report with cancellation reason
        report, _ = WorkReport.objects.get_or_create(work=work)
        report.cancellation_remark = cancellation_reason
        report.save()

        messages.success(request, f'Work #{work.id} cancelled successfully.')
        return redirect('work_list')

    return render(request, 'works/work_cancel.html', {
        'work': work,
        'title': 'Cancel Work'
    })


# ==================== AUTO-EXPIRE WORKS ====================
def check_expired_works():
    """Check and mark works as expired if deadline passed"""
    from django.utils import timezone
    expired_works = WorkStb.objects.filter(
        status='Pending',
        work_deadline_time__lt=timezone.now()
    )

    count = expired_works.update(status='Expired')
    return count






