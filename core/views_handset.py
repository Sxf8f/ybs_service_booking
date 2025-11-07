"""
Handset Stock Management Views (mirrors SIM flows)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Sum, Min, Prefetch
from django.utils import timezone
from django.http import HttpResponse
import csv
from decimal import Decimal

from .models import (
    User, Operator,
    HandsetType, HandsetPurchase, HandsetStock, HandsetTransfer,
    RetailerHandsetWallet, FosHandsetWallet, SupervisorHandsetWallet,
    HandsetCollection
)
from .forms import HandsetTransferForm


# ==================== HANDSET TYPE (per operator) ====================

@login_required
def handset_type_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access handset types.')
        return redirect('dashboard')
    types_ = HandsetType.objects.select_related('operator').order_by('operator__name','name')
    return render(request, 'handset/type_list.html', {'types': types_})


@login_required
def handset_type_add(request):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can add handset types.')
        return redirect('dashboard')
    if request.method == 'POST':
        operator_id = request.POST.get('operator_id')
        name = request.POST.get('name')
        model_number = request.POST.get('model_number')
        purchase_price = request.POST.get('purchase_price')
        selling_price = request.POST.get('selling_price')
        if operator_id and name and purchase_price and selling_price:
            op = get_object_or_404(Operator, pk=operator_id)
            HandsetType.objects.create(
                operator=op,
                name=name,
                model_number=model_number or '',
                purchase_price=purchase_price,
                selling_price=selling_price
            )
            messages.success(request, 'Handset type added')
            return redirect('handset_type_list')
    operators = Operator.objects.all()
    return render(request, 'handset/type_form.html', {'operators': operators, 'title': 'Add Handset Type'})


@login_required
def handset_type_edit(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can edit handset types.')
        return redirect('dashboard')
    t = get_object_or_404(HandsetType, pk=pk)
    if request.method == 'POST':
        t.name = request.POST.get('name') or t.name
        t.model_number = request.POST.get('model_number') or ''
        t.purchase_price = request.POST.get('purchase_price') or t.purchase_price
        t.selling_price = request.POST.get('selling_price') or t.selling_price
        t.save()
        messages.success(request, 'Handset type updated')
        return redirect('handset_type_list')
    operators = Operator.objects.all()
    return render(request, 'handset/type_form.html', {'operators': operators, 'title': 'Edit Handset Type', 'item': t})


# ==================== HANDSET PURCHASE ====================

@login_required
def handset_purchase_add(request):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can add handset purchases.')
        return redirect('dashboard')
    if request.method == 'POST':
        handset_type_id = request.POST.get('handset_type_id')
        total_quantity = int(request.POST.get('total_quantity') or 0)
        purchase_date = request.POST.get('purchase_date')
        serial_numbers_text = request.POST.get('serial_numbers','')
        if handset_type_id and total_quantity > 0 and purchase_date and serial_numbers_text:
            htype = get_object_or_404(HandsetType, pk=handset_type_id)
            serial_numbers = [sn.strip() for sn in serial_numbers_text.split('\n') if sn.strip()]
            if len(serial_numbers) != total_quantity:
                messages.error(request, 'Serial numbers count must match total quantity.')
                return redirect('handset_purchase_add')
            existing = HandsetStock.objects.filter(serial_number__in=serial_numbers).values_list('serial_number', flat=True)
            if existing:
                messages.error(request, f'Duplicate serials: {", ".join(existing)}')
                return redirect('handset_purchase_add')
            with transaction.atomic():
                purchase = HandsetPurchase.objects.create(
                    handset_type=htype,
                    total_quantity=total_quantity,
                    purchase_date=purchase_date,
                    created_by=request.user,
                )
                stocks = []
                for sn in serial_numbers:
                    stocks.append(HandsetStock(
                        serial_number=sn,
                        imei_number='',
                        handset_type=htype,
                        purchase=purchase,
                        current_holder=request.user,
                        purchase_price=htype.purchase_price,
                        selling_price=htype.selling_price,
                        status='available'
                    ))
                HandsetStock.objects.bulk_create(stocks)
                messages.success(request, f'Purchase created with {len(stocks)} handsets.')
                return redirect('handset_purchase_list')
    types_ = HandsetType.objects.select_related('operator').all()
    return render(request, 'handset/purchase_add.html', {'types': types_})


@login_required
def handset_purchase_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access handset purchases.')
        return redirect('dashboard')
    purchases = HandsetPurchase.objects.select_related('handset_type','created_by').annotate(
        count=Count('handsets')
    ).order_by('-created_at')
    return render(request, 'handset/purchase_list.html', {'purchases': purchases})


@login_required
def handset_purchase_detail(request, pk):
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access handset purchases.')
        return redirect('dashboard')
    purchase = get_object_or_404(HandsetPurchase, pk=pk)
    items = purchase.handsets.select_related('current_holder').all()
    return render(request, 'handset/purchase_detail.html', {'purchase': purchase, 'items': items})


# ==================== HANDSET STOCK LIST ====================

@login_required
def handset_stock_list(request):
    user = request.user
    if user.role == 'admin':
        qs = HandsetStock.objects.select_related('handset_type','current_holder','handset_type__operator').all()
    else:
        qs = HandsetStock.objects.filter(current_holder=user).select_related('handset_type','handset_type__operator')
    operator_id = request.GET.get('operator')
    status = request.GET.get('status')
    search = request.GET.get('search')
    if operator_id:
        qs = qs.filter(handset_type__operator_id=operator_id)
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(serial_number__icontains=search) | Q(imei_number__icontains=search))
    operators = Operator.objects.all()
    summary = qs.values('handset_type__operator__name').annotate(
        total=Count('id'),
        available=Count('id', filter=Q(status='available')),
        sold=Count('id', filter=Q(status='sold')),
    )
    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="handset_stock.csv"'
        writer = csv.writer(response)
        writer.writerow(['Operator','Type','Serial','Status','Holder'])
        for s in qs.order_by('handset_type__operator__name','handset_type__name','serial_number'):
            holder = getattr(s.current_holder, 'name', '') if s.current_holder_id else ''
            writer.writerow([s.handset_type.operator.name, s.handset_type.name, s.serial_number, s.status, holder])
        return response
    return render(request, 'handset/stock_list.html', {
        'items': qs.order_by('-created_at'),
        'operators': operators,
        'summary': summary,
    })


# ==================== HANDSET TRANSFER ====================


# ==================== HANDSET TYPE MANAGEMENT ====================

@login_required
def handset_type_list(request):
    """List all handset types (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    types = HandsetType.objects.select_related('operator').all()
    return render(request, 'handset/type_list.html', {'types': types})


@login_required
def handset_type_add(request):
    """Add handset type (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Convert operator_id from template to operator for form
        post_data = request.POST.copy()
        if 'operator_id' in post_data:
            post_data['operator'] = post_data['operator_id']
        form = HandsetTypeForm(post_data)
        if form.is_valid():
            form.save()
            messages.success(request, 'Handset type added successfully!')
            return redirect('handset_type_list')
    else:
        form = HandsetTypeForm()

    operators = Operator.objects.all()
    return render(request, 'handset/type_form.html', {'form': form, 'title': 'Add Handset Type', 'operators': operators})


@login_required
def handset_type_edit(request, pk):
    """Edit handset type (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    handset_type = get_object_or_404(HandsetType, pk=pk)

    if request.method == 'POST':
        # Convert operator_id from template to operator for form
        post_data = request.POST.copy()
        if 'operator_id' in post_data:
            post_data['operator'] = post_data['operator_id']
        form = HandsetTypeForm(post_data, instance=handset_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Handset type updated successfully!')
            return redirect('handset_type_list')
    else:
        form = HandsetTypeForm(instance=handset_type)

    operators = Operator.objects.all()
    return render(request, 'handset/type_form.html', {'form': form, 'title': 'Edit Handset Type', 'operators': operators, 'item': handset_type})


# ==================== HANDSET PURCHASE ====================

@login_required
def handset_purchase_add(request):
    """Add handset purchase and individual handsets (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = HandsetPurchaseForm(request.POST)
        serial_numbers_text = request.POST.get('serial_numbers', '')
        imei_numbers_text = request.POST.get('imei_numbers', '')

        if form.is_valid() and serial_numbers_text:
            with transaction.atomic():
                # Create purchase record
                purchase = form.save(commit=False)
                purchase.created_by = request.user
                purchase.save()

                handset_type = purchase.handset_type

                # Parse serial numbers and IMEI numbers
                serial_numbers = [sn.strip() for sn in serial_numbers_text.split('\n') if sn.strip()]
                imei_numbers = [imei.strip() for imei in imei_numbers_text.split('\n') if imei.strip()]

                # Validate quantity matches
                if len(serial_numbers) != purchase.total_quantity:
                    messages.error(request, f'Serial numbers count ({len(serial_numbers)}) does not match total quantity ({purchase.total_quantity}).')
                    purchase.delete()
                    return redirect('handset_purchase_add')

                # Check for duplicates
                existing_serials = HandsetStock.objects.filter(serial_number__in=serial_numbers).values_list('serial_number', flat=True)
                if existing_serials:
                    messages.error(request, f'Duplicate serial numbers found: {", ".join(existing_serials)}')
                    purchase.delete()
                    return redirect('handset_purchase_add')

                # Create handset stock entries
                handset_stocks = []
                for i, serial_number in enumerate(serial_numbers):
                    imei = imei_numbers[i] if i < len(imei_numbers) else None
                    handset_stocks.append(HandsetStock(
                        serial_number=serial_number,
                        imei_number=imei,
                        handset_type=handset_type,
                        purchase=purchase,
                        current_holder=request.user,  # Admin holds initially
                        purchase_price=handset_type.purchase_price,
                        selling_price=handset_type.selling_price,
                        status='available'
                    ))

                HandsetStock.objects.bulk_create(handset_stocks)
                messages.success(request, f'Purchase created successfully with {len(serial_numbers)} handsets!')
                return redirect('handset_purchase_list')
    else:
        form = HandsetPurchaseForm()

    return render(request, 'handset/purchase_add.html', {'form': form})


@login_required
def handset_purchase_list(request):
    """List all handset purchases (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    purchases = HandsetPurchase.objects.select_related('handset_type__operator', 'created_by').annotate(
        handset_count=Count('handsets')
    ).order_by('-created_at')

    return render(request, 'handset/purchase_list.html', {'purchases': purchases})


@login_required
def handset_purchase_detail(request, pk):
    """View handset purchase detail with all handsets"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    purchase = get_object_or_404(HandsetPurchase, pk=pk)
    handsets = purchase.handsets.select_related('current_holder').all()

    return render(request, 'handset/purchase_detail.html', {
        'purchase': purchase,
        'handsets': handsets
    })


# ==================== HANDSET STOCK LISTING ====================

@login_required
def handset_stock_list(request):
    """
    Handset stock list - accessible by Admin, Sales Supervisor, FOS, Retailer
    Shows user's own handset stock with filters
    """
    user = request.user

    # Check access
    if user.role not in ['admin', 'supervisor', 'fos', 'retailer']:
        messages.error(request, 'You do not have access to handset stock.')
        return redirect('dashboard')

    # Filter by current holder
    if user.role == 'admin':
        handsets = HandsetStock.objects.select_related('handset_type__operator', 'current_holder').all()
    else:
        handsets = HandsetStock.objects.filter(current_holder=user).select_related('handset_type__operator')

    # Apply filters
    operator_id = request.GET.get('operator')
    handset_type_id = request.GET.get('handset_type')
    status = request.GET.get('status')
    search = request.GET.get('search')

    if operator_id:
        handsets = handsets.filter(handset_type__operator_id=operator_id)
    if handset_type_id:
        handsets = handsets.filter(handset_type_id=handset_type_id)
    if status:
        handsets = handsets.filter(status=status)
    if search:
        handsets = handsets.filter(
            Q(serial_number__icontains=search) |
            Q(imei_number__icontains=search) |
            Q(sold_to_customer__icontains=search)
        )

    # Operator-wise summary
    operator_summary = handsets.values('handset_type__operator__name').annotate(
        total=Count('id'),
        available=Count('id', filter=Q(status='available')),
        sold=Count('id', filter=Q(status='sold'))
    )

    operators = Operator.objects.all()
    handset_types = HandsetType.objects.filter(is_active=True).select_related('operator')

    return render(request, 'handset/stock_list.html', {
        'handsets': handsets.order_by('-created_at'),
        'operators': operators,
        'handset_types': handset_types,
        'operator_summary': operator_summary
    })


# ==================== HANDSET TRANSFER ====================

@login_required
@transaction.atomic
def handset_transfer_create(request):
    """Transfer handsets to next level"""
    user = request.user

    # Check access based on role
    if user.role == 'admin':
        allowed = True
    elif user.role == 'supervisor':
        # Only sales supervisors
        allowed = user.supervisor_category and user.supervisor_category.name in ['Sales', 'Both']
    elif user.role == 'fos':
        allowed = True
    else:
        allowed = False

    if not allowed:
        messages.error(request, 'You do not have permission to transfer handsets.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = HandsetTransferForm(request.POST, from_user=user)
        if form.is_valid():
            serial_numbers_text = form.cleaned_data['serial_numbers']
            to_user = form.cleaned_data['to_user']
            remark = form.cleaned_data['remark']

            # Parse serial numbers
            serial_numbers = [sn.strip() for sn in serial_numbers_text.split('\n') if sn.strip()]

            # Get handset stocks
            handsets = HandsetStock.objects.filter(
                serial_number__in=serial_numbers,
                current_holder=user,
                status='available'
            )

            if handsets.count() != len(serial_numbers):
                messages.error(request, 'Some serial numbers are invalid or not in your stock.')
                return redirect('handset_transfer_create')

            # Create transfer records with batch ID
            import uuid
            batch_id = str(uuid.uuid4())  # Unique batch identifier

            transfers = []
            for handset in handsets:
                transfers.append(HandsetTransfer(
                    handset=handset,
                    from_user=user,
                    to_user=to_user,
                    transfer_type='transfer',
                    status='pending',
                    batch_id=batch_id,
                    remark=remark
                ))

            HandsetTransfer.objects.bulk_create(transfers)
            messages.success(request, f'{len(transfers)} handsets transferred to {to_user.name}. Pending acceptance.')
            return redirect('handset_transfer_history')
    else:
        form = HandsetTransferForm(from_user=user)

    return render(request, 'handset/transfer_create.html', {'form': form})


@login_required
def handset_transfer_pending(request):
    """View pending handset transfers (receiver) - grouped by batch"""
    user = request.user
    from django.db.models import Count, Min

    # Get all pending transfers
    pending_transfers = HandsetTransfer.objects.filter(
        to_user=user,
        status='pending'
    ).select_related('handset', 'from_user', 'handset__handset_type__operator')

    # Group by batch_id
    batches = []
    batch_groups = pending_transfers.values('batch_id').annotate(
        count=Count('id'),
        first_created=Min('created_at')
    ).order_by('-first_created')

    for batch_info in batch_groups:
        batch_id = batch_info['batch_id']
        batch_transfers = pending_transfers.filter(batch_id=batch_id)

        if batch_transfers.exists():
            first_transfer = batch_transfers.first()
            batches.append({
                'batch_id': batch_id,
                'from_user': first_transfer.from_user,
                'handset_type': first_transfer.handset.handset_type,
                'count': batch_info['count'],
                'created_at': batch_info['first_created'],
                'remark': first_transfer.remark,
                'transfers': list(batch_transfers)  # All transfers in this batch
            })

    return render(request, 'handset/transfer_pending.html', {'batches': batches})


@login_required
@transaction.atomic
def handset_transfer_action(request, pk, action):
    """Accept or reject handset transfer batch"""
    # pk here is batch_id (not a single transfer ID)
    batch_id = pk
    transfers = HandsetTransfer.objects.filter(
        batch_id=batch_id,
        to_user=request.user,
        status='pending'
    )

    if not transfers.exists():
        messages.error(request, 'No pending transfers found for this batch.')
        return redirect('handset_transfer_pending')

    count = transfers.count()

    if action == 'accept':
        # Accept all transfers in the batch
        success_count = 0
        for transfer in transfers:
            if transfer.accept():
                success_count += 1

        if success_count == count:
            messages.success(request, f'Successfully accepted {success_count} handsets!')
        else:
            messages.warning(request, f'Accepted {success_count} out of {count} handsets.')

    elif action == 'reject':
        # Reject all transfers in the batch
        success_count = 0
        for transfer in transfers:
            if transfer.reject():
                success_count += 1

        if success_count == count:
            messages.success(request, f'Successfully rejected {success_count} handsets.')
        else:
            messages.warning(request, f'Rejected {success_count} out of {count} handsets.')

    return redirect('handset_transfer_pending')


@login_required
def handset_transfer_history(request):
    """View handset transfer history"""
    user = request.user

    if user.role == 'admin':
        transfers = HandsetTransfer.objects.select_related('handset', 'from_user', 'to_user').all()
    else:
        transfers = HandsetTransfer.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).select_related('handset', 'from_user', 'to_user')

    # Filters
    status = request.GET.get('status')
    if status:
        transfers = transfers.filter(status=status)

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="handset_transfer_history.csv"'
        writer = csv.writer(response)
        writer.writerow(['Serial', 'Handset Type', 'Operator', 'From', 'To', 'Type', 'Status', 'Created'])
        for t in transfers.order_by('-created_at'):
            writer.writerow([
                t.handset.serial_number,
                t.handset.handset_type.name,
                t.handset.handset_type.operator.name,
                t.from_user.name,
                t.to_user.name,
                t.transfer_type,
                t.status,
                timezone.localtime(t.created_at).strftime('%Y-%m-%d %H:%M') if t.created_at else ''
            ])
        return response

    return render(request, 'handset/transfer_history.html', {
        'transfers': transfers.order_by('-created_at')
    })

@login_required
def handset_collect_from_retailer(request):
    """FOS collects handset payment from Retailer"""
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

            # Get retailer's handset wallets for this FOS
            wallets = RetailerHandsetWallet.objects.filter(
                retailer=retailer_user,
                pending_amount__gt=0
            ).select_related('operator').order_by('operator__name')

            if not wallets.exists():
                messages.error(request, "No pending amount found for this retailer")
                return redirect('handset_collect_from_retailer')

            # Calculate total pending
            total_pending = sum(w.pending_amount for w in wallets)

            # Validate collection amount
            if collection_amount > total_pending:
                messages.error(request, f"Collection amount (₹{collection_amount}) cannot exceed total pending (₹{total_pending})")
                return redirect('handset_collect_from_retailer')

            if collection_amount <= 0:
                messages.error(request, "Collection amount must be greater than zero")
                return redirect('handset_collect_from_retailer')

            # Process collection with transaction safety
            with transaction.atomic():
                remaining_collection = collection_amount

                # Distribute collection across operators (first-come-first-served)
                for wallet in wallets:
                    if remaining_collection <= 0:
                        break

                    # Calculate amount to deduct from this wallet
                    collection_from_wallet = min(remaining_collection, wallet.pending_amount)

                    # Create collection record for this operator
                    HandsetCollection.objects.create(
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

                    # Update RetailerHandsetWallet (reduce retailer's debt)
                    wallet.pending_amount -= collection_from_wallet
                    wallet.save()

                    # Update FosHandsetWallet (increase FOS's pending amount to supervisor)
                    fos_wallet, created = FosHandsetWallet.objects.get_or_create(
                        fos=request.user,
                        operator=wallet.operator,
                        defaults={'pending_amount': 0, 'total_collected_from_retailers': 0, 'total_paid_to_supervisor': 0}
                    )
                    fos_wallet.pending_amount += collection_from_wallet
                    fos_wallet.total_collected_from_retailers += collection_from_wallet
                    fos_wallet.save()

                    remaining_collection -= collection_from_wallet

            messages.success(request, f"Successfully collected ₹{collection_amount} from {retailer_user.name}")
            return redirect('handset_collect_from_retailer')

        except User.DoesNotExist:
            messages.error(request, "Retailer not found")
            return redirect('handset_collect_from_retailer')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('handset_collect_from_retailer')

    # Get retailers under this FOS with their total pending
    from .models import RetailerFosMap
    retailer_ids = RetailerFosMap.objects.filter(fos=request.user).values_list('retailer_id', flat=True)

    # Get retailers with their total pending grouped by retailer
    retailers_with_pending = User.objects.filter(
        id__in=retailer_ids,
        retailer_handset_wallet__pending_amount__gt=0
    ).distinct().prefetch_related(
        Prefetch('retailer_handset_wallet',
                queryset=RetailerHandsetWallet.objects.filter(pending_amount__gt=0).select_related('operator'),
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
        'retailers_data': retailers_data,
    }
    return render(request, 'handset/collect_from_retailer.html', context)


@login_required
def handset_collect_from_fos(request):
    """Supervisor collects handset payment from FOS"""
    if request.user.role != 'supervisor':
        messages.error(request, "Only Supervisors can collect from FOS")
        return redirect('dashboard')

    if request.method == 'POST':
        fos_id = request.POST.get('fos_id')
        collection_amount = Decimal(request.POST.get('collection_amount', 0))
        collection_date = request.POST.get('collection_date')
        remarks = request.POST.get('remarks', '')

        try:
            fos_user = User.objects.get(id=fos_id, role='fos')

            # Get FOS's handset wallets for this supervisor
            wallets = FosHandsetWallet.objects.filter(
                fos=fos_user,
                pending_amount__gt=0
            ).select_related('operator').order_by('operator__name')

            if not wallets.exists():
                messages.error(request, "No pending amount found for this FOS")
                return redirect('handset_collect_from_fos')

            # Calculate total pending
            total_pending = sum(w.pending_amount for w in wallets)

            # Validate collection amount
            if collection_amount > total_pending:
                messages.error(request, f"Collection amount (₹{collection_amount}) cannot exceed total pending (₹{total_pending})")
                return redirect('handset_collect_from_fos')

            if collection_amount <= 0:
                messages.error(request, "Collection amount must be greater than zero")
                return redirect('handset_collect_from_fos')

            # Process collection with transaction safety
            with transaction.atomic():
                remaining_collection = collection_amount

                # Distribute collection across operators (first-come-first-served)
                for wallet in wallets:
                    if remaining_collection <= 0:
                        break

                    # Calculate amount to deduct from this wallet
                    collection_from_wallet = min(remaining_collection, wallet.pending_amount)

                    # Create collection record for this operator
                    HandsetCollection.objects.create(
                        collection_level='fos_to_supervisor',
                        operator=wallet.operator,
                        from_user=fos_user,
                        to_user=request.user,
                        collected_by=request.user,
                        collection_amount=collection_from_wallet,
                        pending_before=wallet.pending_amount,
                        pending_after=wallet.pending_amount - collection_from_wallet,
                        collection_date=collection_date,
                        remarks=f"{remarks} (₹{collection_from_wallet} of ₹{collection_amount})" if remarks else f"₹{collection_from_wallet} of ₹{collection_amount} total"
                    )

                    # Update FosHandsetWallet (reduce FOS's debt)
                    wallet.pending_amount -= collection_from_wallet
                    wallet.total_paid_to_supervisor += collection_from_wallet
                    wallet.save()

                    # Update SupervisorHandsetWallet (increase Supervisor's pending amount to admin)
                    sup_wallet, created = SupervisorHandsetWallet.objects.get_or_create(
                        supervisor=request.user,
                        operator=wallet.operator,
                        defaults={'pending_amount': 0, 'total_collected_from_fos': 0, 'total_paid_to_admin': 0}
                    )
                    sup_wallet.pending_amount += collection_from_wallet
                    sup_wallet.total_collected_from_fos += collection_from_wallet
                    sup_wallet.save()

                    remaining_collection -= collection_from_wallet

            messages.success(request, f"Successfully collected ₹{collection_amount} from {fos_user.name}")
            return redirect('handset_collect_from_fos')

        except User.DoesNotExist:
            messages.error(request, "FOS not found")
            return redirect('handset_collect_from_fos')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('handset_collect_from_fos')

    # Get FOS under this supervisor with their total pending
    fos_users = User.objects.filter(role='fos', supervisor=request.user)

    # Get FOS with their total pending grouped by FOS
    fos_with_pending = User.objects.filter(
        id__in=fos_users.values_list('id', flat=True),
        fos_handset_wallet__pending_amount__gt=0
    ).distinct().prefetch_related(
        Prefetch('fos_handset_wallet',
                queryset=FosHandsetWallet.objects.filter(pending_amount__gt=0).select_related('operator'),
                to_attr='pending_wallets')
    ).order_by('name')

    # Calculate total for each FOS
    fos_pending = []
    for fos in fos_with_pending:
        total = sum(w.pending_amount for w in fos.pending_wallets)
        fos_pending.append({
            'fos': fos,
            'wallets': fos.pending_wallets,
            'total': total
        })

    context = {
        'fos_pending': fos_pending,
    }
    return render(request, 'handset/collect_from_fos.html', context)


@login_required
def handset_collect_from_supervisor(request):
    """Admin collects handset payment from Supervisor"""
    if request.user.role != 'admin':
        messages.error(request, "Only Admin can collect from Supervisors")
        return redirect('dashboard')

    if request.method == 'POST':
        supervisor_id = request.POST.get('supervisor_id')
        collection_amount = Decimal(request.POST.get('collection_amount', 0))
        collection_date = request.POST.get('collection_date')
        remarks = request.POST.get('remarks', '')

        try:
            supervisor_user = User.objects.get(id=supervisor_id, role='supervisor')

            # Get Supervisor's handset wallets
            wallets = SupervisorHandsetWallet.objects.filter(
                supervisor=supervisor_user,
                pending_amount__gt=0
            ).select_related('operator').order_by('operator__name')

            if not wallets.exists():
                messages.error(request, "No pending amount found for this supervisor")
                return redirect('handset_collect_from_supervisor')

            # Calculate total pending
            total_pending = sum(w.pending_amount for w in wallets)

            # Validate collection amount
            if collection_amount > total_pending:
                messages.error(request, f"Collection amount (₹{collection_amount}) cannot exceed total pending (₹{total_pending})")
                return redirect('handset_collect_from_supervisor')

            if collection_amount <= 0:
                messages.error(request, "Collection amount must be greater than zero")
                return redirect('handset_collect_from_supervisor')

            # Process collection with transaction safety
            with transaction.atomic():
                remaining_collection = collection_amount

                # Distribute collection across operators (first-come-first-served)
                for wallet in wallets:
                    if remaining_collection <= 0:
                        break

                    # Calculate amount to deduct from this wallet
                    collection_from_wallet = min(remaining_collection, wallet.pending_amount)

                    # Create collection record for this operator
                    HandsetCollection.objects.create(
                        collection_level='supervisor_to_admin',
                        operator=wallet.operator,
                        from_user=supervisor_user,
                        to_user=request.user,
                        collected_by=request.user,
                        collection_amount=collection_from_wallet,
                        pending_before=wallet.pending_amount,
                        pending_after=wallet.pending_amount - collection_from_wallet,
                        collection_date=collection_date,
                        remarks=f"{remarks} (₹{collection_from_wallet} of ₹{collection_amount})" if remarks else f"₹{collection_from_wallet} of ₹{collection_amount} total"
                    )

                    # Update SupervisorHandsetWallet (reduce supervisor's debt - fully settled)
                    wallet.pending_amount -= collection_from_wallet
                    wallet.total_paid_to_admin += collection_from_wallet
                    wallet.save()

                    remaining_collection -= collection_from_wallet

            messages.success(request, f"Successfully collected ₹{collection_amount} from {supervisor_user.name}")
            return redirect('handset_collect_from_supervisor')

        except User.DoesNotExist:
            messages.error(request, "Supervisor not found")
            return redirect('handset_collect_from_supervisor')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('handset_collect_from_supervisor')

    # Get supervisors with their total pending
    supervisors = User.objects.filter(
        role='supervisor',
        supervisor_category__name__in=['Sales', 'Both']
    )

    # Get supervisors with their total pending grouped by supervisor
    supervisors_with_pending = User.objects.filter(
        id__in=supervisors.values_list('id', flat=True),
        supervisor_handset_wallet__pending_amount__gt=0
    ).distinct().prefetch_related(
        Prefetch('supervisor_handset_wallet',
                queryset=SupervisorHandsetWallet.objects.filter(pending_amount__gt=0).select_related('operator'),
                to_attr='pending_wallets')
    ).order_by('name')

    # Calculate total for each supervisor
    supervisor_pending = []
    for supervisor in supervisors_with_pending:
        total = sum(w.pending_amount for w in supervisor.pending_wallets)
        supervisor_pending.append({
            'supervisor': supervisor,
            'wallets': supervisor.pending_wallets,
            'total': total
        })

    context = {
        'supervisor_pending': supervisor_pending,
    }
    return render(request, 'handset/collect_from_supervisor.html', context)
