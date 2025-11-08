from django.urls import path
from . import views
from . import views_sim_ec
from . import views_ec_recharge as views_ec
from . import views_handset

urlpatterns = [
    path('', views.login_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.admin_dashboard, name='dashboard'),

    path("stock-upload/", views.stock_upload_view, name="stock_upload"),
    path("stock-sales-list/", views.stock_sales_list, name="stock_sales_list"),

    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    # Operator management
    path("operators/", views.operator_list, name="operator_list"),
    path("operators/add/", views.operator_add, name="operator_add"),
    path("operators/<int:pk>/edit/", views.operator_edit, name="operator_edit"),

    # Stock movement and overview
    path("stocks/overview/", views.stock_overview, name="stock_overview"),
    path("stocks/transfer/supervisor/", views.transfer_stock_to_supervisor, name="transfer_stock_to_supervisor"),
    path("stocks/transfer/technician/", views.transfer_stock_to_technician, name="transfer_stock_to_technician"),
    path("stocks/detail/<str:role>/<int:product_id>/", views.stock_role_detail, name="stock_role_detail"),
    path("stocks/detail/supervisor/<int:product_id>/", views.stock_supervisor_detail, name="stock_supervisor_detail"),

    # Work web pages
    path("works/", views.work_list, name="work_list"),
    path("works/add/", views.work_add, name="work_add"),
    path("works/<int:pk>/edit/", views.work_edit, name="work_edit"),
    path("works/<int:pk>/close/", views.work_close, name="work_close"),
    path("works/<int:pk>/report/", views.work_report, name="work_report"),
    path("works/<int:pk>/cancel/", views.work_cancel, name="work_cancel"),

    # Work Assignment & OTP URLs
    path("works/<int:pk>/assign/", views.work_assign, name="work_assign"),
    path("works/<int:pk>/reassign/", views.work_reassign, name="work_reassign"),
    path("works/<int:pk>/send-otp/", views.work_send_otp, name="work_send_otp"),
    path("works/admin-otp-list/", views.admin_otp_list, name="admin_otp_list"),

    # Retailer Work URLs
    path("works/retailer/", views.retailer_work_list, name="retailer_work_list"),
    path("works/retailer/add/", views.retailer_work_add, name="retailer_work_add"),

    # Work dropdown masters
    path("works/master/<slug:slug>/", views.work_master_list, name="work_master_list"),
    path("works/master/<slug:slug>/add/", views.work_master_add, name="work_master_add"),
    path("works/master/<slug:slug>/<int:pk>/edit/", views.work_master_edit, name="work_master_edit"),
    path("works/master/<slug:slug>/<int:pk>/delete/", views.work_master_delete, name="work_master_delete"),

    # Service type CRUD
    path("service-types/", views.service_type_list, name="service_type_list"),
    path("service-types/add/", views.service_type_add, name="service_type_add"),
    path("service-types/<int:pk>/edit/", views.service_type_edit, name="service_type_edit"),
    path("service-types/<int:pk>/delete/", views.service_type_delete, name="service_type_delete"),

    # Work From CRUD
    path("work-from/", views.workfrom_list, name="workfrom_list"),
    path("work-from/add/", views.workfrom_add, name="workfrom_add"),
    path("work-from/<int:pk>/edit/", views.workfrom_edit, name="workfrom_edit"),
    path("work-from/<int:pk>/delete/", views.workfrom_delete, name="workfrom_delete"),

    # Purchase pages
    path("purchases/add/", views.purchase_add, name="purchase_add"),

    path("purchases/", views.purchase_list, name="purchase_list"),
    path("purchases/add/", views.purchase_add, name="purchase_add"),
    path("purchases/<int:pk>/", views.purchase_detail, name="purchase_detail"),
    path("purchases/<int:pk>/delete/", views.purchase_delete, name="purchase_delete"),    

    # Pincode Master pages
    path("pincodes/", views.pincode_list, name="pincode_list"),
    path("pincodes/add/", views.pincode_add, name="pincode_add"),
    path("pincodes/<int:pk>/edit/", views.pincode_edit, name="pincode_edit"),
    path("pincodes/<int:pk>/delete/", views.pincode_delete, name="pincode_delete"),
    
    # Pincode Assignment pages
    path("pincode-assignments/", views.pincode_assignment_list, name="pincode_assignment_list"),
    path("pincode-assignments/add/", views.pincode_assignment_add, name="pincode_assignment_add"),
    path("pincode-assignments/<int:pk>/delete/", views.pincode_assignment_delete, name="pincode_assignment_delete"),

    path('add-supervisor/', views.add_supervisor, name='add_supervisor'),
    path('add-fos/', views.add_fos, name='add_fos'),
    path('add-retailer/', views.add_retailer, name='add_retailer'),
    path('add-technician/', views.add_technician, name='add_technician'),

    # Collection Transfer URLs
    path('collection/transfer/', views.transfer_to_supervisor_view, name='transfer_collection'),
    path('collection/pending/', views.pending_transfers_view, name='pending_transfers'),
    path('collection/transfer/<int:pk>/<str:action>/', views.transfer_action_view, name='transfer_action'),
    path('collection/supervisor-transfer/', views.supervisor_transfer_to_admin, name='supervisor_transfer_admin'),
    path('collection/history/', views.transfer_history_view, name='transfer_history'),

    # Stock Take Back URLs
    path('stock/take-back/from-technician/', views.supervisor_take_back_from_technician, name='supervisor_take_back_from_technician'),
    path('stock/take-back/from-supervisor/', views.admin_take_back_from_supervisor, name='admin_take_back_from_supervisor'),

    # Freelancer Payment URLs
    path('payments/supervisor/mark-payment/', views.supervisor_mark_payment, name='supervisor_mark_payment'),
    path('payments/technician/pending/', views.technician_pending_payments, name='technician_pending_payments'),
    path('payments/technician/<int:pk>/<str:action>/', views.technician_payment_action, name='technician_payment_action'),
    path('payments/history/', views.payment_history, name='payment_history'),
    path('payments/history/supervisor/', views.payment_history, name='supervisor_payment_history'),

    # User Management URLs
    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),

    # SIM Stock Management URLs
    path('sim/operator-pricing/', views_sim_ec.sim_operator_price_list, name='sim_operator_price_list'),
    path('sim/operator-pricing/add/', views_sim_ec.sim_operator_price_add, name='sim_operator_price_add'),
    path('sim/operator-pricing/<int:pk>/edit/', views_sim_ec.sim_operator_price_edit, name='sim_operator_price_edit'),

    path('sim/purchase/add/', views_sim_ec.sim_purchase_add, name='sim_purchase_add'),
    path('sim/purchase/', views_sim_ec.sim_purchase_list, name='sim_purchase_list'),
    path('sim/purchase/<int:pk>/', views_sim_ec.sim_purchase_detail, name='sim_purchase_detail'),

    path('sim/stock/', views_sim_ec.sim_stock_list, name='sim_stock_list'),

    path('sim/transfer/create/', views_sim_ec.sim_transfer_create, name='sim_transfer_create'),
    path('sim/transfer/pending/', views_sim_ec.sim_transfer_pending, name='sim_transfer_pending'),
    path('sim/transfer/<str:pk>/<str:action>/', views_sim_ec.sim_transfer_action, name='sim_transfer_action'),
    path('sim/transfer/history/', views_sim_ec.sim_transfer_history, name='sim_transfer_history'),

    path('sim/return/create/', views_sim_ec.sim_return_create, name='sim_return_create'),

    # SIM Collection URLs
    path('sim/collect/retailer/', views_sim_ec.sim_collect_from_retailer, name='sim_collect_from_retailer'),
    path('sim/collect/fos/', views_sim_ec.sim_collect_from_fos, name='sim_collect_from_fos'),
    path('sim/collect/supervisor/', views_sim_ec.sim_collect_from_supervisor, name='sim_collect_from_supervisor'),

    # EC Recharge System URLs
    path('ec/upload/', views_ec.ec_upload_all_in_one, name='ec_upload_select'),
    path('ec/sample/excel/', views_ec.ec_excel_sample_download, name='ec_excel_sample'),
    path('ec/api/get-fos/', views_ec.get_fos_by_supervisor_operator, name='ec_get_fos'),
    path('ec/api/get-supervisors/', views_ec.get_supervisors_by_operator, name='ec_get_supervisors'),
    path('ec/api/get-operators/', views_ec.get_operators_by_supervisor, name='ec_get_operators'),

    # EC Collection URLs
    path('ec/collect/retailer/', views_ec.ec_collect_from_retailer, name='ec_collect_from_retailer'),
    path('ec/collect/fos/', views_ec.ec_collect_from_fos, name='ec_collect_from_fos'),
    path('ec/collect/supervisor/', views_ec.ec_collect_from_supervisor, name='ec_collect_from_supervisor'),
    path('ec/pending/', views_ec.ec_pending_collections, name='ec_pending_collections'),

    # EC Reports
    path('ec/report/sales/', views_ec.ec_sales_report, name='ec_sales_report'),
    path('ec/report/collection/', views_ec.ec_collection_report, name='ec_collection_report'),
    path('ec/history/sales/', views_ec.ec_sales_history, name='ec_sales_history'),
    path('ec/history/collection/', views_ec.ec_collection_history, name='ec_collection_history'),

    # ==================== HANDSET MANAGEMENT URLs ====================
    # Handset Type Management
    path('handset/type/list/', views_handset.handset_type_list, name='handset_type_list'),
    path('handset/type/add/', views_handset.handset_type_add, name='handset_type_add'),
    path('handset/type/<int:pk>/edit/', views_handset.handset_type_edit, name='handset_type_edit'),

    # Handset Purchase
    path('handset/purchase/add/', views_handset.handset_purchase_add, name='handset_purchase_add'),
    path('handset/purchase/list/', views_handset.handset_purchase_list, name='handset_purchase_list'),
    path('handset/purchase/<int:pk>/detail/', views_handset.handset_purchase_detail, name='handset_purchase_detail'),

    # Handset Stock
    path('handset/stock/list/', views_handset.handset_stock_list, name='handset_stock_list'),

    # Handset Transfer
    path('handset/transfer/create/', views_handset.handset_transfer_create, name='handset_transfer_create'),
    path('handset/transfer/pending/', views_handset.handset_transfer_pending, name='handset_transfer_pending'),
    path('handset/transfer/<str:pk>/<str:action>/', views_handset.handset_transfer_action, name='handset_transfer_action'),
    path('handset/transfer/history/', views_handset.handset_transfer_history, name='handset_transfer_history'),

    # Handset Collection URLs
    path('handset/collect/retailer/', views_handset.handset_collect_from_retailer, name='handset_collect_from_retailer'),
    path('handset/collect/fos/', views_handset.handset_collect_from_fos, name='handset_collect_from_fos'),
    path('handset/collect/supervisor/', views_handset.handset_collect_from_supervisor, name='handset_collect_from_supervisor'),
]