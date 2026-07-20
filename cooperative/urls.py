from django.urls import path, include
from rest_framework.routers import DefaultRouter
from cooperative import views

router = DefaultRouter()
router.register('farmers', views.FarmerViewSet, basename='farmers')
router.register('porter',views.PorterViewSet,basename='porter')
router.register('milkcollection',views.MilkCollectionViewSet,basename='milkcollection')
router.register('notice',views.NoticeViewSet,basename='notice')



# ️ Fix: Remove the extra 's' from 'urls'
urlpatterns = [
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('farmers-balance/', views.FarmersWithBal, name='farmers-with-balance'),
    path('payfarmer/', views.Pay_farmer, name='farmers-payments'),
    path('callback', views.MpesaCallback, name='mpesa-callback'),
    path('', include(router.urls))
]