"""
Views for EC Recharge System
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, Count
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from datetime import date, timedelta
import pandas as pd
from decimal import Decimal
from io import BytesIO

from .models import (
    User, Operator, EcSale, RetailerWallet, EcCollection,
    Retailer, FosOperatorMap, RetailerFosMap, FosWallet, SupervisorWallet
)
from .forms_ec import (
    EcUploadSelectForm, EcManualEntryForm, EcExcelUploadForm,
    EcCollectionForm, EcSalesReportFilterForm, EcCollectionReportFilterForm
)


# ==================== EC UPLOAD VIEWS ====================

@login_required
def ec_upload_select(request):
    """Step 1: Select Operator, Supervisor, FOS"""
    if request.method == 'POST':
        form = EcUploadSelectForm(request.POST)
        if form.is_valid():
            # Store selections in session
            request.session['ec_operator_id'] = form.cleaned_data['operator'].id
            request.session['ec_supervisor_id'] = form.cleaned_data['supervisor'].id
            request.session['ec_fos_id'] = form.cleaned_data['fos'].id

            # Redirect to upload choice
            return redirect('ec_upload_choice')
    else:
        form = EcUploadSelectForm()

    return render(request, 'ec_recharge/select_hierarchy.html', {'form': form})


@login_required
def get_fos_by_supervisor_operator(request):
    """API endpoint to get FOS filtered by supervisor and operator"""
    supervisor_id = request.GET.get('supervisor_id')
    operator_id = request.GET.get('operator_id')

    if not supervisor_id or not operator_id:
        return JsonResponse({'fos_list': []})

    # Get FOS that have this operator assigned and are under this supervisor
    fos_with_operator = FosOperatorMap.objects.filter(
        operator_id=operator_id
    ).values_list('fos_id', flat=True)

    fos_users = User.objects.filter(
        role='fos',
        supervisor_id=supervisor_id,
        id__in=fos_with_operator
    ).values('id', 'name')

    return JsonResponse({'fos_list': list(fos_users)})


@login_required
def get_supervisors_by_operator(request):
    """API endpoint to get supervisors (Sales/Both category only)"""
    operator_id = request.GET.get('operator_id')

    if not operator_id:
        return JsonResponse({'supervisors': []})

    # Get supervisors with Sales or Both category
    supervisors = User.objects.filter(
        role='supervisor',
        supervisor_category__name__in=['Sales', 'Both']
    ).values('id', 'name')

    return JsonResponse({'supervisors': list(supervisors)})


@login_required
def get_operators_by_supervisor(request):
    """API endpoint to get operators assigned to FOS under a supervisor"""
    supervisor_id = request.GET.get('supervisor_id')

    if not supervisor_id:
        return JsonResponse({'operators': []})

    fos_ids = User.objects.filter(
        role='fos',
        supervisor_id=supervisor_id
    ).values_list('id', flat=True)

    operator_ids = FosOperatorMap.objects.filter(
        fos_id__in=fos_ids
    ).values_list('operator_id', flat=True).distinct()

    operators = Operator.objects.filter(
        id__in=operator_ids
    ).order_by('name').values('id', 'name')

    return JsonResponse({'operators': list(operators)})


@login_required
def download_ec_sample_excel(request):
    """Provide a sample Excel template for EC uploads"""
    columns = [
        'Order ID',
        'Order Date',
        'Partner ID',
        'Partner Name',
        'Transfer Amount',
        'Commission',
        'Amount Without Commission'
    ]

    sample_data = [{
        'Order ID': 'EC123456',
        'Order Date': date.today().strftime('%Y-%m-%d'),
        'Partner ID': 'P001',
        'Partner Name': 'Sample Retailer',
        'Transfer Amount': 5000,
        'Commission': 150,
        'Amount Without Commission': 4850,
    }]

    df = pd.DataFrame(sample_data, columns=columns)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='EC Upload Sample')
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=ec_upload_sample.xlsx'
    return response


@login_required
def ec_upload_choice(request):
    """Choose between Manual Entry or Excel Upload"""
    # Check if selections exist in session
    if not all(k in request.session for k in ['ec_operator_id', 'ec_supervisor_id', 'ec_fos_id']):
        messages.error(request, "Please select Operator, Supervisor, and FOS first.")
        return redirect('ec_upload_select')

    operator = Operator.objects.get(id=request.session['ec_operator_id'])
    supervisor = User.objects.get(id=request.session['ec_supervisor_id'])
    fos = User.objects.get(id=request.session['ec_fos_id'])

    context = {
        'operator': operator,
        'supervisor': supervisor,
        'fos': fos,
    }
    return render(request, 'ec_recharge/upload_choice.html', context)


@login_required
@transaction.atomic
def ec_manual_entry(request):
    """Manual EC Entry"""
    # Check session
    if not all(k in request.session for k in ['ec_operator_id', 'ec_supervisor_id', 'ec_fos_id']):
        messages.error(request, "Please select Operator, Supervisor, and FOS first.")
        return redirect('ec_upload_select')

    operator_id = request.session['ec_operator_id']
    supervisor_id = request.session['ec_supervisor_id']
    fos_id = request.session['ec_fos_id']

    if request.method == 'POST':
        form = EcManualEntryForm(request.POST, fos_id=fos_id)
        if form.is_valid():
            ec_sale = form.save(commit=False)
            ec_sale.operator_id = operator_id
            ec_sale.supervisor_id = supervisor_id
            ec_sale.fos_id = fos_id
            ec_sale.uploaded_by = request.user
            ec_sale.upload_type = 'manual'

            # Get retailer user
            retailer_obj = form.cleaned_data['retailer']
            ec_sale.retailer = retailer_obj.user

            ec_sale.save()

            # Update RetailerWallet (retailer debt to FOS)
            # NOTE: FosWallet is NOT updated here - it's updated when FOS actually collects
            wallet, created = RetailerWallet.objects.get_or_create(
                retailer=ec_sale.retailer,
                operator_id=operator_id,
                defaults={'pending_amount': 0, 'total_sales': 0}
            )
            wallet.pending_amount += ec_sale.amount_without_commission
            wallet.total_sales += ec_sale.amount_without_commission
            wallet.save()

            messages.success(request, f"EC Sale recorded successfully! Order ID: {ec_sale.order_id}")
            return redirect('ec_manual_entry')
    else:
        form = EcManualEntryForm(fos_id=fos_id)

    # Get context data
    operator = Operator.objects.get(id=operator_id)
    supervisor = User.objects.get(id=supervisor_id)
    fos = User.objects.get(id=fos_id)

    # Get retailers under this FOS using RetailerFosMap
    retailer_ids = RetailerFosMap.objects.filter(fos_id=fos_id).values_list('retailer_id', flat=True)
    retailers = User.objects.filter(id__in=retailer_ids, role='retailer')

    context = {
        'form': form,
        'operator': operator,
        'supervisor': supervisor,
        'fos': fos,
        'retailers': retailers,
    }
    return render(request, 'ec_recharge/manual_entry.html', context)


@login_required
@transaction.atomic
def ec_excel_upload(request):
    """Excel Upload for EC"""
    # Check session
    if not all(k in request.session for k in ['ec_operator_id', 'ec_supervisor_id', 'ec_fos_id']):
        messages.error(request, "Please select Operator, Supervisor, and FOS first.")
        return redirect('ec_upload_select')

    operator_id = request.session['ec_operator_id']
    supervisor_id = request.session['ec_supervisor_id']
    fos_id = request.session['ec_fos_id']

    if request.method == 'POST':
        form = EcExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']

            try:
                # Read Excel file
                df = pd.read_excel(excel_file)

                # Validate columns
                required_columns = [
                    'Order ID', 'Order Date', 'Partner ID', 'Partner Name',
                    'Transfer Amount', 'Commission', 'Amount Without Commission'
                ]
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    messages.error(request, f"Missing columns: {', '.join(missing_columns)}")
                    return redirect('ec_excel_upload')

                # Get retailers under this FOS
                retailers_map = {}
                retailers = Retailer.objects.filter(fos_id=fos_id).select_related('user')
                for ret in retailers:
                    retailers_map[ret.user.name.lower().strip()] = ret.user

                # Process rows
                success_count = 0
                error_count = 0
                errors = []

                for index, row in df.iterrows():
                    try:
                        order_id = str(row['Order ID']).strip()
                        partner_name = str(row['Partner Name']).strip()

                        # Check if retailer exists under this FOS
                        retailer_key = partner_name.lower().strip()
                        if retailer_key not in retailers_map:
                            error_count += 1
                            errors.append(f"Row {index + 2}: Retailer '{partner_name}' not found under this FOS")
                            continue

                        retailer_user = retailers_map[retailer_key]

                        # Check if order_id already exists
                        if EcSale.objects.filter(order_id=order_id).exists():
                            error_count += 1
                            errors.append(f"Row {index + 2}: Order ID '{order_id}' already exists")
                            continue

                        # Parse order date
                        order_date = pd.to_datetime(row['Order Date']).date()

                        # Create EC Sale
                        ec_sale = EcSale.objects.create(
                            order_id=order_id,
                            order_date=order_date,
                            operator_id=operator_id,
                            supervisor_id=supervisor_id,
                            fos_id=fos_id,
                            retailer=retailer_user,
                            partner_id=str(row['Partner ID']).strip(),
                            partner_name=partner_name,
                            transfer_amount=Decimal(str(row['Transfer Amount'])),
                            commission=Decimal(str(row['Commission'])),
                            amount_without_commission=Decimal(str(row['Amount Without Commission'])),
                            uploaded_by=request.user,
                            upload_type='excel'
                        )

                        # Update RetailerWallet (retailer debt to FOS)
                        wallet, created = RetailerWallet.objects.get_or_create(
                            retailer=retailer_user,
                            operator_id=operator_id,
                            defaults={'pending_amount': 0, 'total_sales': 0}
                        )
                        wallet.pending_amount += ec_sale.amount_without_commission
                        wallet.total_sales += ec_sale.amount_without_commission
                        wallet.save()

                        # NOTE: FosWallet is NOT updated here - only when FOS collects
                        success_count += 1

                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {index + 2}: {str(e)}")

                # Show results
                if success_count > 0:
                    messages.success(request, f"Successfully uploaded {success_count} EC sales records")
                if error_count > 0:
                    error_msg = f"{error_count} errors occurred:\n" + "\n".join(errors[:10])
                    if len(errors) > 10:
                        error_msg += f"\n... and {len(errors) - 10} more errors"
                    messages.warning(request, error_msg)

                return redirect('ec_sales_report')

            except Exception as e:
                messages.error(request, f"Error processing Excel file: {str(e)}")
                return redirect('ec_excel_upload')
    else:
        form = EcExcelUploadForm()

    # Get context data
    operator = Operator.objects.get(id=operator_id)
    supervisor = User.objects.get(id=supervisor_id)
    fos = User.objects.get(id=fos_id)

    context = {
        'form': form,
        'operator': operator,
        'supervisor': supervisor,
        'fos': fos,
    }
    return render(request, 'ec_recharge/excel_upload.html', context)


# ==================== EC COLLECTION VIEWS ====================

@login_required
@transaction.atomic
def ec_collect_from_retailer(request):
    """FOS collects from Retailer - Simplified: collect total from retailer"""
    if request.user.role != 'fos':
        messages.error(request, "Only FOS can collect from retailers")
        return redirect('dashboard')

    if request.method == 'POST':
        retailer_id = request.POST.get('retailer_id')
        collection_amount = Decimal(request.POST.get('collection_amount', 0))
        collection_date = request.POST.get('collection_date')
        remarks = request.POST.get('remarks', '')

        try:
            retailer_user = User.objects.get(id=retailer_id, role='retailer')

            # Get all wallets for this retailer
            wallets = RetailerWallet.objects.filter(
                retailer=retailer_user,
                pending_amount__gt=0
            ).select_related('operator').order_by('operator__name')

            if not wallets.exists():
                messages.error(request, "No pending amount found for this retailer")
                return redirect('ec_collect_from_retailer')

            # Calculate total pending
            total_pending = sum(w.pending_amount for w in wallets)

            # Validate collection amount
            if collection_amount > total_pending:
                messages.error(request, f"Collection amount (₹{collection_amount}) cannot exceed total pending (₹{total_pending})")
                return redirect('ec_collect_from_retailer')

            if collection_amount <= 0:
                messages.error(request, "Collection amount must be greater than zero")
                return redirect('ec_collect_from_retailer')

            # Process collection with transaction safety
            with transaction.atomic():
                remaining_collection = collection_amount

                # Distribute collection across operators (first-come-first-served)
                for wallet in wallets:
                    if remaining_collection <= 0:
                        break

                    # Calculate amount to deduct from this wallet
                    if remaining_collection >= wallet.pending_amount:
                        # Collect full amount from this wallet
                        collection_from_wallet = wallet.pending_amount
                    else:
                        # Collect partial amount
                        collection_from_wallet = remaining_collection

                    # Create collection record for this operator
                    EcCollection.objects.create(
                        collection_level='retailer_to_fos',
                        operator=wallet.operator,
                        from_user=retailer_user,
                        to_user=request.user,
                        collected_by=request.user,
                        collection_amount=collection_from_wallet,
                        pending_before=wallet.pending_amount,
                        pending_after=wallet.pending_amount - collection_from_wallet,
                        collection_date=collection_date,
                        remarks=f"{remarks} (₹{collection_from_wallet} of ₹{collection_amount})" if remarks else f"₹{collection_from_wallet} of ₹{collection_amount} total"
                    )

                    # Update RetailerWallet (reduce retailer's debt)
                    wallet.pending_amount -= collection_from_wallet
                    wallet.save()

                    # Update FosWallet (increase FOS's pending amount to supervisor)
                    fos_wallet, created = FosWallet.objects.get_or_create(
                        fos=request.user,
                        operator=wallet.operator,
                        defaults={'pending_amount': 0, 'total_collected_from_retailers': 0, 'total_paid_to_supervisor': 0}
                    )
                    fos_wallet.pending_amount += collection_from_wallet
                    fos_wallet.total_collected_from_retailers += collection_from_wallet
                    fos_wallet.save()

                    remaining_collection -= collection_from_wallet

            messages.success(request, f"Successfully collected ₹{collection_amount} from {retailer_user.name}")
            return redirect('ec_collect_from_retailer')

        except User.DoesNotExist:
            messages.error(request, "Retailer not found")
            return redirect('ec_collect_from_retailer')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('ec_collect_from_retailer')

    # Get retailers under this FOS with their total pending
    retailer_ids = RetailerFosMap.objects.filter(fos=request.user).values_list('retailer_id', flat=True)

    # Get pending summary by operator
    pending_summary = RetailerWallet.objects.filter(
        retailer_id__in=retailer_ids,
        pending_amount__gt=0
    ).values('operator__name').annotate(
        total_pending=Sum('pending_amount')
    )

    # Get retailers with their total pending grouped by retailer
    from django.db.models import Prefetch
    retailers_with_pending = User.objects.filter(
        id__in=retailer_ids,
        retailer_wallet__pending_amount__gt=0
    ).distinct().prefetch_related(
        Prefetch('retailer_wallet',
                queryset=RetailerWallet.objects.filter(pending_amount__gt=0).select_related('operator'),
                to_attr='pending_wallets')
    ).order_by('name')

    # Calculate total for each retailer
    retailers_data = []
    for retailer in retailers_with_pending:
        total = sum(w.pending_amount for w in retailer.pending_wallets)
        retailers_data.append({
            'retailer': retailer,
            'wallets': retailer.pending_wallets,
            'total_pending': total
        })

    context = {
        'pending_summary': pending_summary,
        'retailers_data': retailers_data,
    }
    return render(request, 'ec_recharge/collect_from_retailer.html', context)


@login_required
def ec_pending_collections(request):
    """View pending collections at all levels"""
    user = request.user

    context = {
        'user': user,
    }

    if user.role == 'fos':
        # Show retailers pending to pay FOS - get retailers from RetailerFosMap
        retailer_ids = RetailerFosMap.objects.filter(fos=user).values_list('retailer_id', flat=True)
        retailer_wallets = RetailerWallet.objects.filter(
            retailer_id__in=retailer_ids,
            pending_amount__gt=0
        ).select_related('retailer', 'operator').order_by('-pending_amount')

        total = retailer_wallets.aggregate(total=Sum('pending_amount'))['total'] or 0

        context['retailer_wallets'] = retailer_wallets
        context['total_pending'] = total

    elif user.role == 'supervisor':
        # Show FOS pending amounts from FosWallet
        fos_users = User.objects.filter(role='fos', supervisor=user)
        fos_pending = []

        for fos in fos_users:
            # Get pending from FosWallet
            fos_total = FosWallet.objects.filter(
                fos=fos,
                pending_amount__gt=0
            ).aggregate(total=Sum('pending_amount'))['total'] or 0

            if fos_total > 0:
                # Get operator breakdown
                operators = FosWallet.objects.filter(
                    fos=fos,
                    pending_amount__gt=0
                ).values('operator__name').annotate(pending=Sum('pending_amount'))

                fos_pending.append({
                    'fos_name': fos.name,
                    'operator_name': ', '.join([op['operator__name'] for op in operators]),
                    'pending': fos_total
                })

        context['fos_pending'] = fos_pending
        context['total_pending'] = sum(item['pending'] for item in fos_pending)

    elif user.role == 'admin':
        # Show supervisors pending amounts from SupervisorWallet
        supervisors = User.objects.filter(
            role='supervisor',
            supervisor_category__name__in=['Sales', 'Both']
        )
        supervisor_pending = []

        for sup in supervisors:
            # Get pending from SupervisorWallet
            sup_total = SupervisorWallet.objects.filter(
                supervisor=sup,
                pending_amount__gt=0
            ).aggregate(total=Sum('pending_amount'))['total'] or 0

            if sup_total > 0:
                # Get operator breakdown
                operators = SupervisorWallet.objects.filter(
                    supervisor=sup,
                    pending_amount__gt=0
                ).values('operator__name').annotate(pending=Sum('pending_amount'))

                supervisor_pending.append({
                    'supervisor_name': sup.name,
                    'operator_name': ', '.join([op['operator__name'] for op in operators]),
                    'pending': sup_total
                })

        context['supervisor_pending'] = supervisor_pending
        context['total_pending'] = sum(item['pending'] for item in supervisor_pending)

    return render(request, 'ec_recharge/pending_collections.html', context)


# ==================== EC REPORTS ====================

@login_required
def ec_sales_report(request):
    """EC Sales Report with Role-based Filters"""
    user = request.user

    # Base queryset filtered by role
    sales = EcSale.objects.select_related('operator', 'supervisor', 'fos', 'retailer')

    # Role-based base filtering
    if user.role == 'supervisor':
        sales = sales.filter(supervisor=user)
    elif user.role == 'fos':
        sales = sales.filter(fos=user)
    elif user.role == 'retailer':
        sales = sales.filter(retailer=user)
    # Admin sees all

    # Get filter parameters
    operator_id = request.GET.get('operator')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    user_filter = request.GET.get('user')

    # Apply filters
    if operator_id:
        sales = sales.filter(operator_id=operator_id)

    if date_from:
        sales = sales.filter(order_date__gte=date_from)

    if date_to:
        sales = sales.filter(order_date__lte=date_to)

    # User filter (role-specific)
    if user_filter:
        if user.role == 'admin':
            # Admin can filter by any user
            sales = sales.filter(Q(supervisor_id=user_filter) | Q(fos_id=user_filter) | Q(retailer_id=user_filter))
        elif user.role == 'supervisor':
            # Supervisor can filter by FOS or retailers under them
            sales = sales.filter(Q(fos_id=user_filter) | Q(retailer_id=user_filter))
        elif user.role == 'fos':
            # FOS can filter by retailers under them
            sales = sales.filter(retailer_id=user_filter)

    # Calculate totals
    totals_by_operator = sales.values('operator__name').annotate(
        total=Sum('amount_without_commission'),
        count=Count('id')
    ).order_by('operator__name')

    overall_total = sales.aggregate(
        total=Sum('amount_without_commission'),
        count=Count('id')
    )

    # Order by date descending
    sales = sales.order_by('-order_date', '-uploaded_at')

    # Get user list based on role
    user_choices = []
    if user.role == 'admin':
        # Admin can filter by supervisors, FOS, or retailers
        user_choices = User.objects.filter(
            role__in=['supervisor', 'fos', 'retailer']
        ).order_by('role', 'name')
    elif user.role == 'supervisor':
        # Supervisor can filter by their FOS and retailers under those FOS
        fos_users = User.objects.filter(role='fos', supervisor=user)
        retailer_ids = RetailerFosMap.objects.filter(fos__in=fos_users).values_list('retailer_id', flat=True)
        retailers = User.objects.filter(id__in=retailer_ids)
        from itertools import chain
        user_choices = list(chain(fos_users, retailers))
    elif user.role == 'fos':
        # FOS can filter by retailers under them
        retailer_ids = RetailerFosMap.objects.filter(fos=user).values_list('retailer_id', flat=True)
        user_choices = User.objects.filter(id__in=retailer_ids).order_by('name')

    context = {
        'sales': sales[:200],
        'totals_by_operator': totals_by_operator,
        'overall_total': overall_total,
        'operators': Operator.objects.all().order_by('name'),
        'user_choices': user_choices,
        'selected_operator': operator_id,
        'selected_user': user_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'ec_recharge/sales_report.html', context)


@login_required
def ec_collection_report(request):
    """EC Collection Report with Role-based Filters"""
    user = request.user

    # Base queryset filtered by role
    collections = EcCollection.objects.select_related('operator', 'from_user', 'to_user', 'collected_by')

    # Role-based base filtering
    if user.role == 'supervisor':
        # Supervisor sees collections they made or received
        collections = collections.filter(Q(collected_by=user) | Q(to_user=user) | Q(from_user=user))
    elif user.role == 'fos':
        # FOS sees collections they made or received
        collections = collections.filter(Q(collected_by=user) | Q(to_user=user) | Q(from_user=user))
    elif user.role == 'retailer':
        # Retailer sees collections where they paid
        collections = collections.filter(from_user=user)
    # Admin sees all

    # Get filter parameters
    operator_id = request.GET.get('operator')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    collection_level = request.GET.get('collection_level')
    user_filter = request.GET.get('user')

    # Apply filters
    if operator_id:
        collections = collections.filter(operator_id=operator_id)

    if date_from:
        collections = collections.filter(collection_date__gte=date_from)

    if date_to:
        collections = collections.filter(collection_date__lte=date_to)

    if collection_level:
        collections = collections.filter(collection_level=collection_level)

    # User filter (role-specific)
    if user_filter:
        if user.role == 'admin':
            # Admin can filter by any user
            collections = collections.filter(
                Q(collected_by_id=user_filter) | Q(from_user_id=user_filter) | Q(to_user_id=user_filter)
            )
        elif user.role == 'supervisor':
            # Supervisor can filter by FOS or retailers under them
            collections = collections.filter(
                Q(from_user_id=user_filter) | Q(to_user_id=user_filter)
            )
        elif user.role == 'fos':
            # FOS can filter by retailers under them
            collections = collections.filter(from_user_id=user_filter)

    # Calculate totals
    totals_by_level = collections.values('collection_level').annotate(
        total=Sum('collection_amount'),
        count=Count('id')
    ).order_by('collection_level')

    overall_total = collections.aggregate(
        total=Sum('collection_amount'),
        count=Count('id')
    )

    # Order by date descending
    collections = collections.order_by('-collection_date', '-created_at')

    # Get user list based on role
    user_choices = []
    if user.role == 'admin':
        # Admin can filter by supervisors, FOS, or retailers
        user_choices = User.objects.filter(
            role__in=['supervisor', 'fos', 'retailer']
        ).order_by('role', 'name')
    elif user.role == 'supervisor':
        # Supervisor can filter by their FOS and retailers
        fos_users = User.objects.filter(role='fos', supervisor=user)
        retailer_ids = RetailerFosMap.objects.filter(fos__in=fos_users).values_list('retailer_id', flat=True)
        retailers = User.objects.filter(id__in=retailer_ids)
        from itertools import chain
        user_choices = list(chain(fos_users, retailers))
    elif user.role == 'fos':
        # FOS can filter by retailers under them
        retailer_ids = RetailerFosMap.objects.filter(fos=user).values_list('retailer_id', flat=True)
        user_choices = User.objects.filter(id__in=retailer_ids).order_by('name')

    # Collection level choices
    level_choices = [
        ('retailer_to_fos', 'Retailer → FOS'),
        ('fos_to_supervisor', 'FOS → Supervisor'),
        ('supervisor_to_admin', 'Supervisor → Admin'),
    ]

    context = {
        'collections': collections[:200],
        'totals_by_level': totals_by_level,
        'overall_total': overall_total,
        'operators': Operator.objects.all().order_by('name'),
        'user_choices': user_choices,
        'level_choices': level_choices,
        'selected_operator': operator_id,
        'selected_user': user_filter,
        'selected_level': collection_level,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'ec_recharge/collection_report.html', context)


@login_required
def ec_sales_history(request):
    """Sales History - My Uploads"""
    user = request.user

    sales = EcSale.objects.filter(uploaded_by=user).select_related(
        'operator', 'supervisor', 'fos', 'retailer'
    ).order_by('-uploaded_at')[:50]

    total = sales.aggregate(total=Sum('amount_without_commission'))['total'] or 0

    context = {
        'sales': sales,
        'total': total,
    }
    return render(request, 'ec_recharge/sales_history.html', context)


@login_required
def ec_collection_history(request):
    """Collection History - My Collections"""
    user = request.user

    collections = EcCollection.objects.filter(
        Q(collected_by=user) | Q(from_user=user) | Q(to_user=user)
    ).select_related('operator', 'from_user', 'to_user').order_by('-collection_date')[:50]

    total_collected = EcCollection.objects.filter(collected_by=user).aggregate(
        total=Sum('collection_amount')
    )['total'] or 0

    total_given = EcCollection.objects.filter(from_user=user).aggregate(
        total=Sum('collection_amount')
    )['total'] or 0

    context = {
        'collections': collections,
        'total_collected': total_collected,
        'total_given': total_given,
    }
    return render(request, 'ec_recharge/collection_history.html', context)


# ==================== EC UPLOAD (ALL-IN-ONE) ====================

@login_required
@transaction.atomic
def ec_upload_all_in_one(request):
    """All-in-one page: Select hierarchy + choose entry method + multi-row or Excel upload"""
    # Restrict access: Only admin, Sales supervisors, and FOS can upload EC
    user = request.user

    if user.role == 'supervisor':
        # Only supervisors with Sales or Both category can access
        if not user.supervisor_category or user.supervisor_category.name not in ['Sales', 'Both']:
            messages.error(request, 'Only Sales supervisors can upload EC sales.')
            return redirect('dashboard')
    elif user.role not in ['admin', 'fos']:
        messages.error(request, 'You do not have permission to upload EC sales.')
        return redirect('dashboard')

    if request.method == 'POST':
        operator_id = request.POST.get('operator')
        entry_type = request.POST.get('entry_type', 'manual')

        # Auto-fill hierarchy based on user role
        if user.role == 'fos':
            # FOS uploads: auto-fill supervisor and fos
            supervisor_id = user.supervisor.id if user.supervisor else None
            fos_id = user.id
            if not supervisor_id:
                messages.error(request, 'Your account is not assigned to a supervisor. Contact admin.')
                return redirect('ec_upload_select')
        elif user.role == 'supervisor':
            # Supervisor uploads: auto-fill supervisor, select FOS
            supervisor_id = user.id
            fos_id = request.POST.get('fos')
            if not fos_id:
                messages.error(request, 'Please select FOS.')
                return redirect('ec_upload_select')
        else:  # admin
            # Admin uploads: select both supervisor and FOS
            supervisor_id = request.POST.get('supervisor')
            fos_id = request.POST.get('fos')
            if not supervisor_id or not fos_id:
                messages.error(request, 'Please select Supervisor and FOS.')
                return redirect('ec_upload_select')

        # Validate operator
        if not operator_id:
            messages.error(request, 'Please select Operator.')
            return redirect('ec_upload_select')

        operator = get_object_or_404(Operator, id=operator_id)
        supervisor = get_object_or_404(User, id=supervisor_id, role='supervisor')
        fos = get_object_or_404(User, id=fos_id, role='fos')

        # Get retailers under this FOS
        retailer_ids = RetailerFosMap.objects.filter(fos_id=fos_id).values_list('retailer_id', flat=True)
        retailers = User.objects.filter(id__in=retailer_ids, role='retailer')

        success_count = 0
        error_messages = []

        # Handle Excel upload
        if entry_type == 'excel':
            if 'excel_file' not in request.FILES or not request.FILES['excel_file']:
                messages.error(request, 'Please choose an Excel file before uploading.')
                return redirect('ec_upload_select')

            excel_file = request.FILES['excel_file']

            try:
                df = pd.read_excel(excel_file)
            except ModuleNotFoundError:
                messages.error(
                    request,
                    "Excel support requires the 'openpyxl' package. Please install it and try again."
                )
                return redirect('ec_upload_select')
            except Exception as e:
                messages.error(request, f'Unable to read the Excel file: {e}')
                return redirect('ec_upload_select')

            # Expected columns
            required_cols = ['Order ID', 'Order Date', 'Partner ID', 'Partner Name',
                            'Transfer Amount', 'Commission', 'Amount Without Commission']

            # Check if all required columns exist
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                messages.error(request, f"Missing columns in Excel: {', '.join(missing_cols)}")
                return redirect('ec_upload_select')

            # Process each row from Excel
            for index, row in df.iterrows():
                try:
                    order_id = str(row['Order ID']).strip()
                    order_date_raw = row['Order Date']
                    partner_id = str(row['Partner ID']).strip() if pd.notna(row['Partner ID']) else ''
                    partner_name = str(row['Partner Name']).strip() if pd.notna(row['Partner Name']) else ''
                    transfer_amount = Decimal(str(row['Transfer Amount'])) if pd.notna(row['Transfer Amount']) else 0
                    commission = Decimal(str(row['Commission'])) if pd.notna(row['Commission']) else 0
                    amount_without_commission = Decimal(str(row['Amount Without Commission'])) if pd.notna(row['Amount Without Commission']) else 0

                    # Parse date
                    if isinstance(order_date_raw, str):
                        # Try DD.MM.YYYY format
                        if '.' in order_date_raw:
                            parts = order_date_raw.split('.')
                            order_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
                        else:
                            order_date = pd.to_datetime(order_date_raw).date()
                    else:
                        order_date = pd.to_datetime(order_date_raw).date()

                    # Check duplicate
                    if EcSale.objects.filter(order_id=order_id).exists():
                        error_messages.append(f"Row {index+2}: Order ID {order_id} already exists.")
                        continue

                    # Match retailer
                    retailer = retailers.filter(name__iexact=partner_name).first()
                    if not retailer:
                        error_messages.append(f"Row {index+2}: Retailer '{partner_name}' not found under this FOS.")
                        continue

                    # Create EC Sale
                    EcSale.objects.create(
                        order_id=order_id,
                        order_date=order_date,
                        partner_id=partner_id,
                        partner_name=partner_name,
                        transfer_amount=transfer_amount,
                        commission=commission,
                        amount_without_commission=amount_without_commission,
                        operator=operator,
                        supervisor=supervisor,
                        fos=fos,
                        retailer=retailer,
                        uploaded_by=request.user
                    )

                    # Update RetailerWallet (retailer debt to FOS)
                    # NOTE: FosWallet is NOT updated here - it's updated when FOS actually collects
                    wallet, created = RetailerWallet.objects.get_or_create(
                        retailer=retailer,
                        operator=operator,
                        defaults={'pending_amount': 0, 'total_sales': 0}
                    )
                    wallet.pending_amount += amount_without_commission
                    wallet.total_sales += amount_without_commission
                    wallet.save()

                    success_count += 1

                except Exception as e:
                    error_messages.append(f"Row {index+2}: {str(e)}")

            if success_count == 0 and not error_messages:
                messages.warning(request, 'No rows were processed from the Excel file.')
                return redirect('ec_upload_select')

        # Handle manual entry
        else:
            # Get multi-row data
            order_ids = request.POST.getlist('order_id[]')
            order_dates = request.POST.getlist('order_date[]')
            partner_ids = request.POST.getlist('partner_id[]')
            partner_names = request.POST.getlist('partner_name[]')
            transfer_amounts = request.POST.getlist('transfer_amount[]')
            commissions = request.POST.getlist('commission[]')
            amounts_without_commission = request.POST.getlist('amount_without_commission[]')

            # Validate we have data
            if not order_ids:
                messages.error(request, 'Please add at least one entry.')
                return redirect('ec_upload_select')

            # Process each row
            for i in range(len(order_ids)):
                try:
                    order_id = order_ids[i].strip()
                    order_date = order_dates[i]
                    partner_id = partner_ids[i].strip() if i < len(partner_ids) else ''
                    partner_name = partner_names[i].strip() if i < len(partner_names) else ''
                    transfer_amount = Decimal(transfer_amounts[i]) if i < len(transfer_amounts) and transfer_amounts[i] else 0
                    commission = Decimal(commissions[i]) if i < len(commissions) and commissions[i] else 0
                    amount_without_commission = Decimal(amounts_without_commission[i]) if i < len(amounts_without_commission) and amounts_without_commission[i] else 0

                    # Skip empty rows
                    if not order_id or not order_date:
                        continue

                    # Check if order_id already exists
                    if EcSale.objects.filter(order_id=order_id).exists():
                        error_messages.append(f"Row {i+1}: Order ID {order_id} already exists.")
                        continue

                    # Try to match retailer by name
                    retailer = None
                    if partner_name:
                        retailer = retailers.filter(name__iexact=partner_name).first()

                    if not retailer:
                        error_messages.append(f"Row {i+1}: Retailer '{partner_name}' not found under this FOS.")
                        continue

                    # Create EC Sale
                    ec_sale = EcSale.objects.create(
                        order_id=order_id,
                        order_date=order_date,
                        partner_id=partner_id,
                        partner_name=partner_name,
                        transfer_amount=transfer_amount,
                        commission=commission,
                        amount_without_commission=amount_without_commission,
                        operator=operator,
                        supervisor=supervisor,
                        fos=fos,
                        retailer=retailer,
                        uploaded_by=request.user
                    )

                    # Update RetailerWallet (retailer debt to FOS)
                    # NOTE: FosWallet is NOT updated here - it's updated when FOS actually collects
                    wallet, created = RetailerWallet.objects.get_or_create(
                        retailer=retailer,
                        operator=operator,
                        defaults={'pending_amount': 0, 'total_sales': 0}
                    )
                    wallet.pending_amount += amount_without_commission
                    wallet.total_sales += amount_without_commission
                    wallet.save()

                    success_count += 1

                except Exception as e:
                    error_messages.append(f"Row {i+1}: {str(e)}")

            if success_count == 0 and not error_messages:
                messages.warning(request, 'Entries were submitted but nothing was saved. Please review the data and try again.')
                return redirect('ec_upload_select')

        # Show results
        if success_count > 0:
            messages.success(request, f'Successfully saved {success_count} EC recharge entries.')

        if error_messages:
            for err in error_messages[:10]:  # Show first 10 errors
                messages.error(request, err)
            if len(error_messages) > 10:
                messages.error(request, f"... and {len(error_messages) - 10} more errors.")

        if success_count > 0:
            return redirect('dashboard')
        else:
            return redirect('ec_upload_select')

    # GET request - show form
    operators = Operator.objects.none()

    # Filter operators and FOS based on role
    if user.role == 'fos':
        # FOS: show only operators they have assigned via FosOperatorMap
        fos_operator_ids = FosOperatorMap.objects.filter(
            fos=user
        ).values_list('operator_id', flat=True)
        operators = Operator.objects.filter(
            id__in=fos_operator_ids
        ).order_by('name')
        supervisors = None  # FOS doesn't select supervisor
        fos_users = None  # FOS doesn't select FOS (it's themselves)
    elif user.role == 'supervisor':
        # Supervisor: show operators linked to their FOS and list those FOS
        supervisor_fos_ids = User.objects.filter(
            role='fos',
            supervisor=user
        ).values_list('id', flat=True)
        operator_ids = FosOperatorMap.objects.filter(
            fos_id__in=supervisor_fos_ids
        ).values_list('operator_id', flat=True).distinct()
        operators = Operator.objects.filter(
            id__in=operator_ids
        ).order_by('name')
        if not operators.exists():
            operators = Operator.objects.all().order_by('name')
        supervisors = None  # Supervisor is implicit
        fos_users = User.objects.filter(role='fos', supervisor=user).order_by('name')
    else:  # admin
        # Admin: supervisors first; operators loaded dynamically
        supervisors = User.objects.filter(
            role='supervisor',
            supervisor_category__name__in=['Sales', 'Both']
        ).order_by('name')
        fos_users = None  # Will be loaded via AJAX based on supervisor selection

    context = {
        'operators': operators,
        'supervisors': supervisors,
        'fos_users': fos_users,
        'user_role': user.role,
    }
    return render(request, 'ec_recharge/upload_all_in_one.html', context)


@login_required
def ec_collect_from_fos(request):
    """Supervisor collects from FOS"""
    if request.user.role != 'supervisor':
        messages.error(request, "Only Supervisors can collect from FOS")
        return redirect('dashboard')

    if request.method == 'POST':
        operator_id = request.POST.get('operator')
        fos_id = request.POST.get('fos')
        collection_amount = Decimal(request.POST.get('collection_amount', 0))
        collection_date = request.POST.get('collection_date')
        remarks = request.POST.get('remarks', '')

        try:
            operator = Operator.objects.get(id=operator_id)
            fos = User.objects.get(id=fos_id, role='fos')

            # Get FOS wallet
            fos_wallet = FosWallet.objects.get(fos=fos, operator=operator)

            # Validate collection amount
            if collection_amount > fos_wallet.pending_amount:
                messages.error(request, f"Collection amount cannot exceed pending amount: ₹{fos_wallet.pending_amount}")
                return redirect('ec_collect_from_fos')

            # Create collection record
            with transaction.atomic():
                collection = EcCollection.objects.create(
                    collection_level='fos_to_supervisor',
                    operator=operator,
                    from_user=fos,
                    to_user=request.user,
                    collected_by=request.user,
                    collection_amount=collection_amount,
                    pending_before=fos_wallet.pending_amount,
                    pending_after=fos_wallet.pending_amount - collection_amount,
                    collection_date=collection_date,
                    remarks=remarks
                )

                # Update FOS wallet - reduce pending
                fos_wallet.pending_amount -= collection_amount
                fos_wallet.total_paid_to_supervisor += collection_amount
                fos_wallet.save()

                # Update Supervisor wallet - increase pending
                sup_wallet, created = SupervisorWallet.objects.get_or_create(
                    supervisor=request.user,
                    operator=operator,
                    defaults={'pending_amount': 0, 'total_collected_from_fos': 0}
                )
                sup_wallet.pending_amount += collection_amount
                sup_wallet.total_collected_from_fos += collection_amount
                sup_wallet.save()

            messages.success(request, f"Successfully collected ₹{collection_amount} from {fos.name}")
            return redirect('ec_collect_from_fos')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('ec_collect_from_fos')

    # Get FOS under this supervisor with pending amounts
    fos_users = User.objects.filter(role='fos', supervisor=request.user)
    fos_pending = []

    for fos in fos_users:
        wallets = FosWallet.objects.filter(fos=fos, pending_amount__gt=0).select_related('operator')
        if wallets.exists():
            fos_pending.append({
                'fos': fos,
                'wallets': wallets,
                'total': wallets.aggregate(total=Sum('pending_amount'))['total']
            })

    context = {
        'fos_pending': fos_pending,
    }
    return render(request, 'ec_recharge/collect_from_fos.html', context)


@login_required
def ec_collect_from_supervisor(request):
    """Admin collects from Supervisor"""
    if request.user.role != 'admin':
        messages.error(request, "Only Admin can collect from Supervisors")
        return redirect('dashboard')

    if request.method == 'POST':
        operator_id = request.POST.get('operator')
        supervisor_id = request.POST.get('supervisor')
        collection_amount = Decimal(request.POST.get('collection_amount', 0))
        collection_date = request.POST.get('collection_date')
        remarks = request.POST.get('remarks', '')

        try:
            operator = Operator.objects.get(id=operator_id)
            supervisor = User.objects.get(id=supervisor_id, role='supervisor')

            # Get Supervisor wallet
            sup_wallet = SupervisorWallet.objects.get(supervisor=supervisor, operator=operator)

            # Validate collection amount
            if collection_amount > sup_wallet.pending_amount:
                messages.error(request, f"Collection amount cannot exceed pending amount: ₹{sup_wallet.pending_amount}")
                return redirect('ec_collect_from_supervisor')

            # Create collection record
            with transaction.atomic():
                collection = EcCollection.objects.create(
                    collection_level='supervisor_to_admin',
                    operator=operator,
                    from_user=supervisor,
                    to_user=request.user,
                    collected_by=request.user,
                    collection_amount=collection_amount,
                    pending_before=sup_wallet.pending_amount,
                    pending_after=sup_wallet.pending_amount - collection_amount,
                    collection_date=collection_date,
                    remarks=remarks
                )

                # Update Supervisor wallet - reduce pending (fully settled)
                sup_wallet.pending_amount -= collection_amount
                sup_wallet.total_paid_to_admin += collection_amount
                sup_wallet.save()

            messages.success(request, f"Successfully collected ₹{collection_amount} from {supervisor.name}")
            return redirect('ec_collect_from_supervisor')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('ec_collect_from_supervisor')

    # Get supervisors with pending amounts
    supervisors = User.objects.filter(
        role='supervisor',
        supervisor_category__name__in=['Sales', 'Both']
    )
    supervisor_pending = []

    for supervisor in supervisors:
        wallets = SupervisorWallet.objects.filter(supervisor=supervisor, pending_amount__gt=0).select_related('operator')
        if wallets.exists():
            supervisor_pending.append({
                'supervisor': supervisor,
                'wallets': wallets,
                'total': wallets.aggregate(total=Sum('pending_amount'))['total']
            })

    context = {
        'supervisor_pending': supervisor_pending,
    }
    return render(request, 'ec_recharge/collect_from_supervisor.html', context)
