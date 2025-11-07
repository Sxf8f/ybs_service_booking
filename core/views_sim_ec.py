"""
SIM and EC Stock Management Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone

from .models import (
    User, Operator, SimOperatorPrice, SimPurchase, SimStock, SimTransfer,
    RetailerSimWallet, FosSimWallet, SupervisorSimWallet, SimCollection
)
from decimal import Decimal
from .forms import (
    SimOperatorPriceForm, SimPurchaseForm, SimStockForm, SimTransferForm
)


# ==================== SIM OPERATOR PRICING ====================

@login_required
def sim_operator_price_list(request):
    """List all SIM operator prices (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    prices = SimOperatorPrice.objects.select_related('operator').all()
    return render(request, 'sim/operator_price_list.html', {'prices': prices})


@login_required
def sim_operator_price_add(request):
    """Add/Edit SIM operator price (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = SimOperatorPriceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'SIM operator price added successfully!')
            return redirect('sim_operator_price_list')
    else:
        form = SimOperatorPriceForm()

    return render(request, 'sim/operator_price_form.html', {'form': form, 'title': 'Add SIM Operator Price'})


@login_required
def sim_operator_price_edit(request, pk):
    """Edit SIM operator price (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    price = get_object_or_404(SimOperatorPrice, pk=pk)

    if request.method == 'POST':
        form = SimOperatorPriceForm(request.POST, instance=price)
        if form.is_valid():
            form.save()
            messages.success(request, 'SIM operator price updated successfully!')
            return redirect('sim_operator_price_list')
    else:
        form = SimOperatorPriceForm(instance=price)

    return render(request, 'sim/operator_price_form.html', {'form': form, 'title': 'Edit SIM Operator Price'})


# ==================== SIM PURCHASE ====================

@login_required
def sim_purchase_add(request):
    """Add SIM purchase and individual SIM cards (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = SimPurchaseForm(request.POST)
        serial_numbers_text = request.POST.get('serial_numbers', '')

        if form.is_valid() and serial_numbers_text:
            with transaction.atomic():
                # Create purchase record
                purchase = form.save(commit=False)
                purchase.created_by = request.user
                purchase.save()

                # Get operator pricing
                try:
                    operator_price = SimOperatorPrice.objects.get(operator=purchase.operator)
                except SimOperatorPrice.DoesNotExist:
                    messages.error(request, f'Please set pricing for {purchase.operator.name} first.')
                    purchase.delete()
                    return redirect('sim_operator_price_add')

                # Parse serial numbers
                serial_numbers = [sn.strip() for sn in serial_numbers_text.split('\n') if sn.strip()]

                # Validate quantity matches
                if len(serial_numbers) != purchase.total_quantity:
                    messages.error(request, f'Serial numbers count ({len(serial_numbers)}) does not match total quantity ({purchase.total_quantity}).')
                    purchase.delete()
                    return redirect('sim_purchase_add')

                # Check for duplicates
                existing_serials = SimStock.objects.filter(serial_number__in=serial_numbers).values_list('serial_number', flat=True)
                if existing_serials:
                    messages.error(request, f'Duplicate serial numbers found: {", ".join(existing_serials)}')
                    purchase.delete()
                    return redirect('sim_purchase_add')

                # Create SIM stock entries
                sim_stocks = []
                for serial_number in serial_numbers:
                    sim_stocks.append(SimStock(
                        serial_number=serial_number,
                        operator=purchase.operator,
                        purchase=purchase,
                        current_holder=request.user,  # Admin holds initially
                        purchase_price=operator_price.purchase_price,
                        selling_price=operator_price.selling_price,
                        status='available'
                    ))

                SimStock.objects.bulk_create(sim_stocks)
                messages.success(request, f'Purchase created successfully with {len(serial_numbers)} SIM cards!')
                return redirect('sim_purchase_list')
    else:
        form = SimPurchaseForm()

    return render(request, 'sim/purchase_add.html', {'form': form})


@login_required
def sim_purchase_list(request):
    """List all SIM purchases (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    purchases = SimPurchase.objects.select_related('operator', 'created_by').annotate(
        sim_count=Count('sim_cards')
    ).order_by('-created_at')

    return render(request, 'sim/purchase_list.html', {'purchases': purchases})


@login_required
def sim_purchase_detail(request, pk):
    """View SIM purchase detail with all SIM cards"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can access this page.')
        return redirect('dashboard')

    purchase = get_object_or_404(SimPurchase, pk=pk)
    sim_cards = purchase.sim_cards.select_related('current_holder').all()

    return render(request, 'sim/purchase_detail.html', {
        'purchase': purchase,
        'sim_cards': sim_cards
    })


# ==================== SIM STOCK LISTING ====================

@login_required
def sim_stock_list(request):
    """
    SIM stock list - accessible by Admin, Sales Supervisor, FOS, Retailer
    Shows user's own SIM stock with filters
    """
    user = request.user

    # Check access
    if user.role not in ['admin', 'supervisor', 'fos', 'retailer']:
        messages.error(request, 'You do not have access to SIM stock.')
        return redirect('dashboard')

    # Filter by current holder
    if user.role == 'admin':
        sims = SimStock.objects.select_related('operator', 'current_holder').all()
    else:
        sims = SimStock.objects.filter(current_holder=user).select_related('operator')

    # Apply filters
    operator_id = request.GET.get('operator')
    status = request.GET.get('status')
    search = request.GET.get('search')

    if operator_id:
        sims = sims.filter(operator_id=operator_id)
    if status:
        sims = sims.filter(status=status)
    if search:
        sims = sims.filter(
            Q(serial_number__icontains=search) |
            Q(sold_to_customer__icontains=search)
        )

    # Operator-wise summary
    operator_summary = sims.values('operator__name').annotate(
        total=Count('id'),
        available=Count('id', filter=Q(status='available')),
        sold=Count('id', filter=Q(status='sold'))
    )

    operators = Operator.objects.all()

    return render(request, 'sim/stock_list.html', {
        'sims': sims.order_by('-created_at'),
        'operators': operators,
        'operator_summary': operator_summary
    })


# ==================== SIM TRANSFER ====================

@login_required
@transaction.atomic
def sim_transfer_create(request):
    """Transfer SIM cards to next level"""
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
        messages.error(request, 'You do not have permission to transfer SIM cards.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = SimTransferForm(request.POST, from_user=user)
        if form.is_valid():
            serial_numbers_text = form.cleaned_data['serial_numbers']
            to_user = form.cleaned_data['to_user']
            remark = form.cleaned_data['remark']

            # Parse serial numbers
            serial_numbers = [sn.strip() for sn in serial_numbers_text.split('\n') if sn.strip()]

            # Get SIM stocks
            sims = SimStock.objects.filter(
                serial_number__in=serial_numbers,
                current_holder=user,
                status='available'
            )

            if sims.count() != len(serial_numbers):
                messages.error(request, 'Some serial numbers are invalid or not in your stock.')
                return redirect('sim_transfer_create')

            # Create transfer records with batch ID
            import uuid
            batch_id = str(uuid.uuid4())  # Unique batch identifier

            transfers = []
            for sim in sims:
                transfers.append(SimTransfer(
                    sim=sim,
                    from_user=user,
                    to_user=to_user,
                    transfer_type='transfer',
                    status='pending',
                    batch_id=batch_id,
                    remark=remark
                ))

            SimTransfer.objects.bulk_create(transfers)
            messages.success(request, f'{len(transfers)} SIM cards transferred to {to_user.name}. Pending acceptance.')
            return redirect('sim_transfer_history')
    else:
        form = SimTransferForm(from_user=user)

    return render(request, 'sim/transfer_create.html', {'form': form})


@login_required
def sim_transfer_pending(request):
    """View pending SIM transfers (receiver) - grouped by batch"""
    user = request.user
    from django.db.models import Count, Min, F

    # Get all pending transfers
    pending_transfers = SimTransfer.objects.filter(
        to_user=user,
        status='pending'
    ).select_related('sim', 'from_user', 'sim__operator')

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
                'operator': first_transfer.sim.operator,
                'count': batch_info['count'],
                'created_at': batch_info['first_created'],
                'remark': first_transfer.remark,
                'transfers': list(batch_transfers)  # All transfers in this batch
            })

    return render(request, 'sim/transfer_pending.html', {'batches': batches})


@login_required
@transaction.atomic
def sim_transfer_action(request, pk, action):
    """Accept or reject SIM transfer batch"""
    # pk here is batch_id (not a single transfer ID)
    batch_id = pk
    transfers = SimTransfer.objects.filter(
        batch_id=batch_id,
        to_user=request.user,
        status='pending'
    )

    if not transfers.exists():
        messages.error(request, 'No pending transfers found for this batch.')
        return redirect('sim_transfer_pending')

    count = transfers.count()

    if action == 'accept':
        # Accept all transfers in the batch
        success_count = 0
        for transfer in transfers:
            if transfer.accept():
                success_count += 1

        if success_count == count:
            messages.success(request, f'Successfully accepted {success_count} SIM cards!')
        else:
            messages.warning(request, f'Accepted {success_count} out of {count} SIM cards.')

    elif action == 'reject':
        # Reject all transfers in the batch
        success_count = 0
        for transfer in transfers:
            if transfer.reject():
                success_count += 1

        if success_count == count:
            messages.success(request, f'Successfully rejected {success_count} SIM cards.')
        else:
            messages.warning(request, f'Rejected {success_count} out of {count} SIM cards.')

    return redirect('sim_transfer_pending')


@login_required
def sim_transfer_history(request):
    """View SIM transfer history"""
    user = request.user

    if user.role == 'admin':
        transfers = SimTransfer.objects.select_related('sim', 'from_user', 'to_user').all()
    else:
        transfers = SimTransfer.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).select_related('sim', 'from_user', 'to_user')

    # Filters
    status = request.GET.get('status')
    if status:
        transfers = transfers.filter(status=status)

    return render(request, 'sim/transfer_history.html', {
        'transfers': transfers.order_by('-created_at')
    })


# ==================== SIM RETURN/TAKE BACK ====================

@login_required
@transaction.atomic
def sim_return_create(request):
    """Return SIM cards to previous level"""
    user = request.user

    if user.role not in ['supervisor', 'fos', 'retailer']:
        messages.error(request, 'Invalid action.')
        return redirect('dashboard')

    if request.method == 'POST':
        serial_numbers_text = request.POST.get('serial_numbers', '')
        remark = request.POST.get('remark', '')

        # Determine return target
        if user.role == 'retailer':
            # Return to FOS
            to_user = user.fos_links.first()
        elif user.role == 'fos':
            # Return to supervisor
            to_user = user.supervisor
        elif user.role == 'supervisor':
            # Return to admin
            to_user = User.objects.filter(role='admin').first()
        else:
            messages.error(request, 'Cannot determine return target.')
            return redirect('sim_stock_list')

        if not to_user:
            messages.error(request, 'Return target not found.')
            return redirect('sim_stock_list')

        # Parse serial numbers
        serial_numbers = [sn.strip() for sn in serial_numbers_text.split('\n') if sn.strip()]

        # Get SIM stocks
        sims = SimStock.objects.filter(
            serial_number__in=serial_numbers,
            current_holder=user,
            status='available'
        )

        if sims.count() != len(serial_numbers):
            messages.error(request, 'Some serial numbers are invalid or not in your stock.')
            return redirect('sim_return_create')

        # Create return transfers
        transfers = []
        for sim in sims:
            transfers.append(SimTransfer(
                sim=sim,
                from_user=user,
                to_user=to_user,
                transfer_type='return',
                status='pending',
                remark=remark
            ))

        SimTransfer.objects.bulk_create(transfers)
        messages.success(request, f'{len(transfers)} SIM cards returned to {to_user.name}. Pending acceptance.')
        return redirect('sim_transfer_history')

    return render(request, 'sim/return_create.html', {})


# ==================== EC STOCK MANAGEMENT ====================

@login_required
def ec_stock_overview(request):
    """EC stock overview"""
    user = request.user

    if user.role == 'admin':
        ec_stocks = EcStock.objects.select_related('user').all()
    elif user.role == 'supervisor':
        # Show own and subordinates
        subordinate_ids = list(User.objects.filter(supervisor=user).values_list('id', flat=True))
        subordinate_ids.append(user.id)
        ec_stocks = EcStock.objects.filter(user_id__in=subordinate_ids).select_related('user')
    elif user.role in ['fos', 'retailer']:
        ec_stocks = EcStock.objects.filter(user=user)
    else:
        messages.error(request, 'You do not have access to EC stock.')
        return redirect('dashboard')

    return render(request, 'ec/stock_overview.html', {'ec_stocks': ec_stocks})


@login_required
@transaction.atomic
def ec_transfer_create(request):
    """Transfer EC stock to next level"""
    user = request.user

    # Check access
    if user.role == 'admin':
        allowed = True
    elif user.role == 'supervisor':
        allowed = user.supervisor_category and user.supervisor_category.name in ['Sales', 'Both']
    elif user.role == 'fos':
        allowed = True
    else:
        allowed = False

    if not allowed:
        messages.error(request, 'You do not have permission to transfer EC stock.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = EcTransferForm(request.POST, from_user=user)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            to_user = form.cleaned_data['to_user']
            remark = form.cleaned_data['remark']

            # Check sender has enough EC stock
            try:
                from_stock = EcStock.objects.get(user=user)
                if from_stock.quantity < quantity:
                    messages.error(request, f'Insufficient EC stock. Available: {from_stock.quantity}')
                    return redirect('ec_transfer_create')
            except EcStock.DoesNotExist:
                messages.error(request, 'You do not have any EC stock.')
                return redirect('ec_transfer_create')

            # Create transfer
            transfer = EcTransfer.objects.create(
                from_user=user,
                to_user=to_user,
                quantity=quantity,
                transfer_type='transfer',
                status='pending',
                remark=remark
            )

            messages.success(request, f'{quantity} EC units transferred to {to_user.name}. Pending acceptance.')
            return redirect('ec_transfer_history')
    else:
        form = EcTransferForm(from_user=user)

    # Get current EC stock
    try:
        current_stock = EcStock.objects.get(user=user).quantity
    except EcStock.DoesNotExist:
        current_stock = 0

    return render(request, 'ec/transfer_create.html', {
        'form': form,
        'current_stock': current_stock
    })


@login_required
def ec_transfer_pending(request):
    """View pending EC transfers"""
    user = request.user
    pending_transfers = EcTransfer.objects.filter(
        to_user=user,
        status='pending'
    ).select_related('from_user').order_by('-created_at')

    return render(request, 'ec/transfer_pending.html', {'transfers': pending_transfers})


@login_required
@transaction.atomic
def ec_transfer_action(request, pk, action):
    """Accept or reject EC transfer"""
    transfer = get_object_or_404(EcTransfer, pk=pk, to_user=request.user)

    try:
        if action == 'accept':
            if transfer.accept():
                messages.success(request, f'{transfer.quantity} EC units accepted successfully!')
            else:
                messages.error(request, 'Transfer could not be accepted.')
        elif action == 'reject':
            if transfer.reject():
                messages.success(request, f'{transfer.quantity} EC units rejected.')
            else:
                messages.error(request, 'Transfer could not be rejected.')
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('ec_transfer_pending')


@login_required
def ec_transfer_history(request):
    """View EC transfer history"""
    user = request.user

    if user.role == 'admin':
        transfers = EcTransfer.objects.select_related('from_user', 'to_user').all()
    else:
        transfers = EcTransfer.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).select_related('from_user', 'to_user')

    # Filters
    status = request.GET.get('status')
    if status:
        transfers = transfers.filter(status=status)

    return render(request, 'ec/transfer_history.html', {
        'transfers': transfers.order_by('-created_at')
    })


@login_required
@transaction.atomic
def ec_return_create(request):
    """Return EC stock to previous level"""
    user = request.user

    if user.role not in ['supervisor', 'fos', 'retailer']:
        messages.error(request, 'Invalid action.')
        return redirect('dashboard')

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))
        remark = request.POST.get('remark', '')

        # Determine return target
        if user.role == 'retailer':
            to_user = user.fos_links.first()
        elif user.role == 'fos':
            to_user = user.supervisor
        elif user.role == 'supervisor':
            to_user = User.objects.filter(role='admin').first()
        else:
            messages.error(request, 'Cannot determine return target.')
            return redirect('ec_stock_overview')

        if not to_user:
            messages.error(request, 'Return target not found.')
            return redirect('ec_stock_overview')

        # Check user has enough stock
        try:
            user_stock = EcStock.objects.get(user=user)
            if user_stock.quantity < quantity:
                messages.error(request, f'Insufficient EC stock. Available: {user_stock.quantity}')
                return redirect('ec_return_create')
        except EcStock.DoesNotExist:
            messages.error(request, 'You do not have any EC stock.')
            return redirect('ec_return_create')

        # Create return transfer
        transfer = EcTransfer.objects.create(
            from_user=user,
            to_user=to_user,
            quantity=quantity,
            transfer_type='return',
            status='pending',
            remark=remark
        )

        messages.success(request, f'{quantity} EC units returned to {to_user.name}. Pending acceptance.')
        return redirect('ec_transfer_history')

    # Get current stock
    try:
        current_stock = EcStock.objects.get(user=user).quantity
    except EcStock.DoesNotExist:
        current_stock = 0

    return render(request, 'ec/return_create.html', {'current_stock': current_stock})


@login_required
def ec_add_stock(request):
    """Add EC stock to admin (Admin only - initial stock entry)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admin can add EC stock.')
        return redirect('dashboard')

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))

        if quantity > 0:
            ec_stock, created = EcStock.objects.get_or_create(
                user=request.user,
                defaults={'quantity': 0}
            )
            ec_stock.quantity += quantity
            ec_stock.save()

            messages.success(request, f'{quantity} EC units added to stock.')
            return redirect('ec_stock_overview')

    return render(request, 'ec/add_stock.html', {})


# ==================== SIM COLLECTION FLOW ====================

@login_required
def sim_collect_from_retailer(request):
    """FOS collects SIM payment from Retailer"""
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

            # Get retailer's SIM wallets for this FOS
            wallets = RetailerSimWallet.objects.filter(
                retailer=retailer_user,
                pending_amount__gt=0
            ).select_related('operator').order_by('operator__name')

            if not wallets.exists():
                messages.error(request, "No pending amount found for this retailer")
                return redirect('sim_collect_from_retailer')

            # Calculate total pending
            total_pending = sum(w.pending_amount for w in wallets)

            # Validate collection amount
            if collection_amount > total_pending:
                messages.error(request, f"Collection amount (₹{collection_amount}) cannot exceed total pending (₹{total_pending})")
                return redirect('sim_collect_from_retailer')

            if collection_amount <= 0:
                messages.error(request, "Collection amount must be greater than zero")
                return redirect('sim_collect_from_retailer')

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
                    SimCollection.objects.create(
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

                    # Update RetailerSimWallet (reduce retailer's debt)
                    wallet.pending_amount -= collection_from_wallet
                    wallet.save()

                    # Update FosSimWallet (increase FOS's pending amount to supervisor)
                    fos_wallet, created = FosSimWallet.objects.get_or_create(
                        fos=request.user,
                        operator=wallet.operator,
                        defaults={'pending_amount': 0, 'total_collected_from_retailers': 0, 'total_paid_to_supervisor': 0}
                    )
                    fos_wallet.pending_amount += collection_from_wallet
                    fos_wallet.total_collected_from_retailers += collection_from_wallet
                    fos_wallet.save()

                    remaining_collection -= collection_from_wallet

            messages.success(request, f"Successfully collected ₹{collection_amount} from {retailer_user.name}")
            return redirect('sim_collect_from_retailer')

        except User.DoesNotExist:
            messages.error(request, "Retailer not found")
            return redirect('sim_collect_from_retailer')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('sim_collect_from_retailer')

    # Get retailers under this FOS with their total pending
    from .models import RetailerFosMap
    retailer_ids = RetailerFosMap.objects.filter(fos=request.user).values_list('retailer_id', flat=True)

    # Get retailers with their total pending grouped by retailer
    from django.db.models import Prefetch
    retailers_with_pending = User.objects.filter(
        id__in=retailer_ids,
        retailer_sim_wallet__pending_amount__gt=0
    ).distinct().prefetch_related(
        Prefetch('retailer_sim_wallet',
                queryset=RetailerSimWallet.objects.filter(pending_amount__gt=0).select_related('operator'),
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
    return render(request, 'sim/collect_from_retailer.html', context)


@login_required
def sim_collect_from_fos(request):
    """Supervisor collects SIM payment from FOS"""
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

            # Get FOS's SIM wallets for this supervisor
            wallets = FosSimWallet.objects.filter(
                fos=fos_user,
                pending_amount__gt=0
            ).select_related('operator').order_by('operator__name')

            if not wallets.exists():
                messages.error(request, "No pending amount found for this FOS")
                return redirect('sim_collect_from_fos')

            # Calculate total pending
            total_pending = sum(w.pending_amount for w in wallets)

            # Validate collection amount
            if collection_amount > total_pending:
                messages.error(request, f"Collection amount (₹{collection_amount}) cannot exceed total pending (₹{total_pending})")
                return redirect('sim_collect_from_fos')

            if collection_amount <= 0:
                messages.error(request, "Collection amount must be greater than zero")
                return redirect('sim_collect_from_fos')

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
                    SimCollection.objects.create(
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

                    # Update FosSimWallet (reduce FOS's debt)
                    wallet.pending_amount -= collection_from_wallet
                    wallet.total_paid_to_supervisor += collection_from_wallet
                    wallet.save()

                    # Update SupervisorSimWallet (increase Supervisor's pending amount to admin)
                    sup_wallet, created = SupervisorSimWallet.objects.get_or_create(
                        supervisor=request.user,
                        operator=wallet.operator,
                        defaults={'pending_amount': 0, 'total_collected_from_fos': 0, 'total_paid_to_admin': 0}
                    )
                    sup_wallet.pending_amount += collection_from_wallet
                    sup_wallet.total_collected_from_fos += collection_from_wallet
                    sup_wallet.save()

                    remaining_collection -= collection_from_wallet

            messages.success(request, f"Successfully collected ₹{collection_amount} from {fos_user.name}")
            return redirect('sim_collect_from_fos')

        except User.DoesNotExist:
            messages.error(request, "FOS not found")
            return redirect('sim_collect_from_fos')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('sim_collect_from_fos')

    # Get FOS under this supervisor with their total pending
    fos_users = User.objects.filter(role='fos', supervisor=request.user)

    # Get FOS with their total pending grouped by FOS
    from django.db.models import Prefetch
    fos_with_pending = User.objects.filter(
        id__in=fos_users.values_list('id', flat=True),
        fos_sim_wallet__pending_amount__gt=0
    ).distinct().prefetch_related(
        Prefetch('fos_sim_wallet',
                queryset=FosSimWallet.objects.filter(pending_amount__gt=0).select_related('operator'),
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
    return render(request, 'sim/collect_from_fos.html', context)


@login_required
def sim_collect_from_supervisor(request):
    """Admin collects SIM payment from Supervisor"""
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

            # Get Supervisor's SIM wallets
            wallets = SupervisorSimWallet.objects.filter(
                supervisor=supervisor_user,
                pending_amount__gt=0
            ).select_related('operator').order_by('operator__name')

            if not wallets.exists():
                messages.error(request, "No pending amount found for this supervisor")
                return redirect('sim_collect_from_supervisor')

            # Calculate total pending
            total_pending = sum(w.pending_amount for w in wallets)

            # Validate collection amount
            if collection_amount > total_pending:
                messages.error(request, f"Collection amount (₹{collection_amount}) cannot exceed total pending (₹{total_pending})")
                return redirect('sim_collect_from_supervisor')

            if collection_amount <= 0:
                messages.error(request, "Collection amount must be greater than zero")
                return redirect('sim_collect_from_supervisor')

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
                    SimCollection.objects.create(
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

                    # Update SupervisorSimWallet (reduce supervisor's debt - fully settled)
                    wallet.pending_amount -= collection_from_wallet
                    wallet.total_paid_to_admin += collection_from_wallet
                    wallet.save()

                    remaining_collection -= collection_from_wallet

            messages.success(request, f"Successfully collected ₹{collection_amount} from {supervisor_user.name}")
            return redirect('sim_collect_from_supervisor')

        except User.DoesNotExist:
            messages.error(request, "Supervisor not found")
            return redirect('sim_collect_from_supervisor')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('sim_collect_from_supervisor')

    # Get supervisors with their total pending
    supervisors = User.objects.filter(
        role='supervisor',
        supervisor_category__name__in=['Sales', 'Both']
    )

    # Get supervisors with their total pending grouped by supervisor
    from django.db.models import Prefetch
    supervisors_with_pending = User.objects.filter(
        id__in=supervisors.values_list('id', flat=True),
        supervisor_sim_wallet__pending_amount__gt=0
    ).distinct().prefetch_related(
        Prefetch('supervisor_sim_wallet',
                queryset=SupervisorSimWallet.objects.filter(pending_amount__gt=0).select_related('operator'),
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
    return render(request, 'sim/collect_from_supervisor.html', context)
